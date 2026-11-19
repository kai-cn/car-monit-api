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
 * Spring AI 2.x 实现：ChatClient + MessageChatMemoryAdvisor + ToolCallback。
 *
 * <h2>这个类在干什么（一次请求的完整旅程）</h2>
 * <ol>
 *   <li>先把 {@code meta} 事件推给前端（前端据此拿到 requestId / 模型名）；</li>
 *   <li>把用户这句问题写进 UI 历史（{@link AgentSessionStore}，只存文本）；</li>
 *   <li>组装 {@code toolContext}——注意这里是"旁路通道"，身份/确认令牌不进提示词；</li>
 *   <li>调 {@code ChatClient.stream()}：Spring AI 会自动把工具 schema 发给模型；</li>
 *   <li>模型每吐一段文本就转成 {@code delta} 事件；如果模型要求调工具，
 *       Spring AI 的 {@code ToolCallingAdvisor} 会自动执行工具、把结果回填、<b>再调一次模型</b>，
 *       这个循环对我们是透明的（所以本类里看不到 while 循环）；</li>
 *   <li>流结束：补 {@code usage} 与 {@code done}，把最终答案写进 UI 历史。</li>
 * </ol>
 *
 * <h2>AI 概念：ChatClient / Advisor / 工具上下文</h2>
 * <ul>
 *   <li><b>ChatClient</b>：Spring AI 的高层门面，类似 {@code RestTemplate} 之于 HTTP，
 *       把"拼消息、带历史、注册工具、发请求"都封装好了。</li>
 *   <li><b>Advisor</b>：请求/响应的拦截器链（很像 Servlet Filter）。{@code MessageChatMemoryAdvisor}
 *       负责在每次调用前把历史消息塞进上下文、调用后把本轮问答存回去——这就是"模型有记忆"的原理：
 *       模型本身无状态，所谓记忆只是每次都把历史重新发一遍。</li>
 *   <li><b>toolContext</b>：随工具回调传递的 {@code Map}，<b>不发给模型</b>。
 *       我们用它在"编排器 → 工具回调"之间传 principal 与确认令牌（详见 {@link ToolContextKeys}）。</li>
 * </ul>
 *
 * <p>关键设计：</p>
 * <ul>
 *   <li>每个请求独立 {@link ToolBudget}，防止工具循环；</li>
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
        // 【Reactor 说明】Flux.create 是"手动挡"：我们自己决定什么时候 next/complete。
        // 这里必须手动挡，因为工具回调发生在 Spring AI 内部线程，需要把它的输出"塞进"同一条流。
        // 参数 lambda 只有在有人订阅时才执行——这正是"冷流"的含义（不订阅就不调模型、不花钱）。
        return Flux.create(sink -> {
            long started = System.currentTimeMillis();
            // 终态只允许落一次：正常完成、异常、取消三条路径可能几乎同时发生。
            // compareAndSet 保证"先到先得"，避免 done 之后再补一个 error（前端会当成两次回答）。
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
            // 下面这一串就是"一次对话"的全部：
            //   system  → 系统提示词（角色、规则、口径），由 PromptLibrary 渲染租户/角色占位符
            //   user    → 用户这句话
            //   advisors→ 挂上 ChatMemory，框架自动读/写历史（conversationId 决定用哪份记忆）
            //   toolCallbacks → 可用工具；框架自动把 schema 发给模型并处理 tool_call 循环
            //   toolContext   → 旁路给工具回调的上下文（身份、令牌、预算），模型看不到
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
        // 【Java 10+ var】局部变量类型推断：编译器根据右侧表达式推出实际类型。
        // 这里真实类型是 ChatResponse（泛型嵌套很长），写 var 只为可读性；不是"动态类型"。
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

    /**
     * 把底层异常收敛成稳定错误码。
     *
     * <p>为什么不直接把异常消息抛给前端：上游可能是 OpenAI 的 401/429、也可能是网络超时，
     * 文案随供应商变化。前端只认 {@link AgentErrorCode} 这套稳定枚举，才能做"重试按钮是否可点"。</p>
     *
     * <p>【Java 16+ instanceof 模式匹配】{@code error instanceof AgentException ae} 一行完成
     * "判断类型 + 声明变量 + 强转"三步（旧写法要写两行），且变量作用域被限制在 if 为真的分支内。</p>
     */
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
