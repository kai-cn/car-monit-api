package com.ruoyi.base.agent.springai;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentEventSink;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMessage;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.PromptLibrary;
import com.ruoyi.base.agent.core.ToolContextKeys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.ChatClientResponse;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.tool.ToolCallback;
import reactor.core.Disposable;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Spring AI 实现：ChatClient + MessageChatMemoryAdvisor + ToolCallback。
 *
 * <p>关键设计：</p>
 * <ul>
 *   <li>每个请求独立 ToolBudget，防止工具循环；</li>
 *   <li>ToolContext 携带 principal/confirmToken，工具层不信任模型参数；</li>
 *   <li>事件由工具回调与流式响应共同写入同一个 FluxSink，保证顺序与背压；</li>
 *   <li>会话双写：ChatMemory 供模型上下文，AgentSessionStore 供 UI 历史（只存文本）。</li>
 * </ul>
 */
@Slf4j
public class SpringAiAgentOrchestrator implements AgentOrchestrator {

    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    private final SpringAiToolCallbacks toolCallbacks;
    private final PromptLibrary promptLibrary;
    private final AgentSessionStore sessionStore;
    private final AgentProperties properties;

    public SpringAiAgentOrchestrator(ChatClient chatClient,
                                     ChatMemory chatMemory,
                                     SpringAiToolCallbacks toolCallbacks,
                                     PromptLibrary promptLibrary,
                                     AgentSessionStore sessionStore,
                                     AgentProperties properties) {
        this.chatClient = chatClient;
        this.chatMemory = chatMemory;
        this.toolCallbacks = toolCallbacks;
        this.promptLibrary = promptLibrary;
        this.sessionStore = sessionStore;
        this.properties = properties;
    }

    /**
     * 清空会话：ChatMemory 里的模型上下文与 UI 历史一起清，避免"历史清空了模型还记得"。
     */
    @Override
    public void clearSession(com.ruoyi.base.agent.core.AgentPrincipal principal, String sessionId) {
        if (principal == null || sessionId == null || sessionId.isBlank() || chatMemory == null) {
            return;
        }
        String conversationKey = principal.tenantId() + ":" + principal.userId() + ":" + sessionId;
        try {
            chatMemory.clear(conversationKey);
        } catch (RuntimeException e) {
            log.warn("[Agent][SpringAI] 清空会话记忆失败 session={}: {}", sessionId, e.getMessage());
        }
    }

    @Override
    public String framework() {
        return "spring-ai";
    }

    @Override
    public Set<String> registeredTools() {
        return toolCallbacks.registeredTools();
    }

    @Override
    public Flux<AgentEvent> stream(AgentInvocation invocation) {
        return Flux.create(sink -> {
            long started = System.currentTimeMillis();
            AtomicBoolean terminal = new AtomicBoolean();
            StringBuilder answer = new StringBuilder();
            Map<String, Object> usage = new LinkedHashMap<>();
            AgentEventSink eventSink = event -> {
                if (!sink.isCancelled()) {
                    sink.next(event);
                }
            };

            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("requestId", invocation.getRequestId());
            meta.put("sessionId", invocation.getSessionId());
            meta.put("framework", framework());
            meta.put("model", properties.getModel());
            meta.put("time", java.time.Instant.now().toString());
            eventSink.emit(AgentEvent.meta(0, meta));
            sessionStore.append(invocation.getPrincipal(), invocation.getSessionId(),
                    List.of(AgentMessage.user(invocation.getMessage())));

            Map<String, Object> toolContext = new LinkedHashMap<>();
            toolContext.put(ToolContextKeys.PRINCIPAL, invocation.getPrincipal());
            toolContext.put(ToolContextKeys.INVOCATION, invocation);
            toolContext.put(ToolContextKeys.SINK, eventSink);
            toolContext.put(ToolContextKeys.BUDGET, new ToolBudget(properties.getMaxIters()));
            toolContext.put(ToolContextKeys.CONFIRM_TOKEN,
                    invocation.getConfirmToken() == null ? "" : invocation.getConfirmToken());

            List<ToolCallback> callbacks = toolCallbacks.callbacks();
            Disposable disposable = chatClient.prompt()
                    .system(promptLibrary.render(invocation.getPrincipal()))
                    .user(invocation.getMessage())
                    .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, invocation.conversationKey()))
                    .toolCallbacks(callbacks)
                    .toolContext(toolContext)
                    .stream()
                    .chatClientResponse()
                    .doOnNext(response -> consume(response, answer, usage, eventSink, terminal))
                    .doOnError(error -> fail(error, eventSink, sink, terminal))
                    .doOnComplete(() -> complete(answer, usage, started, invocation, eventSink, sink, terminal))
                    .subscribe();

            sink.onCancel(() -> {
                if (terminal.compareAndSet(false, true)) {
                    disposable.dispose();
                }
            });
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    private void consume(ChatClientResponse response, StringBuilder answer, Map<String, Object> usage,
                         AgentEventSink eventSink, AtomicBoolean terminal) {
        if (terminal.get() || response == null || response.chatResponse() == null) {
            return;
        }
        var chatResponse = response.chatResponse();
        if (chatResponse.getResult() != null && chatResponse.getResult().getOutput() != null) {
            String text = chatResponse.getResult().getOutput().getText();
            if (text != null && !text.isEmpty()) {
                answer.append(text);
                eventSink.emit(AgentEvent.delta(0, text));
            }
        }
        Usage u = chatResponse.getMetadata() == null ? null : chatResponse.getMetadata().getUsage();
        if (u != null) {
            if (u.getPromptTokens() != null) {
                usage.put("promptTokens", u.getPromptTokens());
            }
            if (u.getCompletionTokens() != null) {
                usage.put("completionTokens", u.getCompletionTokens());
            }
            if (u.getTotalTokens() != null) {
                usage.put("totalTokens", u.getTotalTokens());
            }
        }
    }

    private void complete(StringBuilder answer, Map<String, Object> usage, long started,
                          AgentInvocation invocation, AgentEventSink eventSink,
                          FluxSink<AgentEvent> sink, AtomicBoolean terminal) {
        if (!terminal.compareAndSet(false, true)) {
            return;
        }
        if (!usage.isEmpty()) {
            eventSink.emit(AgentEvent.usage(0, usage));
        }
        if (!answer.isEmpty()) {
            sessionStore.append(invocation.getPrincipal(), invocation.getSessionId(),
                    List.of(AgentMessage.assistant(answer.toString())));
        }
        Map<String, Object> done = new LinkedHashMap<>();
        done.put("finishReason", "stop");
        done.put("usage", usage);
        done.put("elapsedMs", System.currentTimeMillis() - started);
        eventSink.emit(AgentEvent.done(0, done));
        sink.complete();
    }

    private void fail(Throwable error, AgentEventSink eventSink, FluxSink<AgentEvent> sink,
                      AtomicBoolean terminal) {
        if (!terminal.compareAndSet(false, true)) {
            return;
        }
        AgentErrorCode code = classify(error);
        log.warn("[Agent][SpringAI] 执行失败: {}", error.getMessage());
        eventSink.emit(AgentEvent.error(0, code, code.defaultMessage()));
        sink.complete();
    }

    private static AgentErrorCode classify(Throwable error) {
        if (error instanceof AgentException ae) {
            return ae.getCode();
        }
        String name = error.getClass().getSimpleName().toLowerCase();
        String message = error.getMessage() == null ? "" : error.getMessage().toLowerCase();
        if (name.contains("timeout") || message.contains("timeout") || message.contains("timed out")) {
            return AgentErrorCode.AGENT_MODEL_TIMEOUT;
        }
        if (message.contains("401") || message.contains("unauthorized") || message.contains("invalid api key")) {
            return AgentErrorCode.AGENT_MODEL_ERROR;
        }
        if (message.contains("429") || message.contains("rate limit")) {
            return AgentErrorCode.AGENT_RATE_LIMITED;
        }
        return AgentErrorCode.AGENT_MODEL_ERROR;
    }
}
