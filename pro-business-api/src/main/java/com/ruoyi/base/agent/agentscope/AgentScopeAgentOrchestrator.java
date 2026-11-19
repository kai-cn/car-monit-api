package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentEventSink;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMessage;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.ToolContextKeys;
import io.agentscope.core.ReActAgent;
import io.agentscope.core.agent.RuntimeContext;
import io.agentscope.core.event.AgentResultEvent;
import io.agentscope.core.event.ExceedMaxItersEvent;
import io.agentscope.core.event.ModelCallEndEvent;
import io.agentscope.core.event.TextBlockDeltaEvent;
import io.agentscope.core.event.ThinkingBlockDeltaEvent;
import io.agentscope.core.model.ChatUsage;
import io.agentscope.core.model.transport.HttpTransportException;
import lombok.extern.slf4j.Slf4j;
import reactor.core.Disposable;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * AgentScope Java 2.0.5 实现：{@link ReActAgent#streamEvents} → 统一 SSE 事件契约。
 *
 * <p>与 Spring AI 分支的关键差异：</p>
 * <ul>
 *   <li><b>编排由框架完成</b>：{@code ReActAgent} 内部跑完整的 ReAct 循环（推理 → 工具 → 再推理），
 *       不需要像 Spring AI 那样依赖 {@code ToolCallingAdvisor} 的隐式循环；</li>
 *   <li><b>事件源是 32 类细粒度事件</b>：这里只挑出 4 类做映射，工具事件由
 *       {@link AgentScopeTools} 在工具内部产出（两个分支的 {@code tool_call}/{@code tool_result}
 *       因此逐字段一致，前端不需要按框架分支）；</li>
 *   <li><b>会话状态由 {@code AgentStateStore} 承载</b>：模型上下文、工具上下文都在
 *       {@code (userId, sessionId)} 槽位里，天然支持多实例（Redis 实现见
 *       {@link AgentScopeStateStore}）。</li>
 * </ul>
 *
 * <p>事件映射表：</p>
 * <table border="1">
 *   <caption>AgentScope → SSE</caption>
 *   <tr><th>AgentScope 事件</th><th>SSE 事件</th><th>说明</th></tr>
 *   <tr><td>（订阅时）</td><td>meta</td><td>requestId/sessionId/framework/model/time</td></tr>
 *   <tr><td>TEXT_BLOCK_DELTA</td><td>delta</td><td>增量文本，前端直接拼接</td></tr>
 *   <tr><td>THINKING_BLOCK_DELTA</td><td>thinking</td><td>仅 {@code expose-thinking=true} 时下发</td></tr>
 *   <tr><td>MODEL_CALL_END</td><td>usage（聚合）</td><td>多轮 token 累加，结束时统一下发</td></tr>
 *   <tr><td>EXCEED_MAX_ITERS</td><td>done.finishReason=max_iters</td><td>框架已生成兜底总结，不当作错误</td></tr>
 *   <tr><td>（Flux onComplete）</td><td>done</td><td>finishReason/usage/elapsedMs</td></tr>
 *   <tr><td>（Flux onError）</td><td>error</td><td>错误码见 {@link AgentErrorCode}</td></tr>
 * </table>
 */
@Slf4j
public class AgentScopeAgentOrchestrator implements AgentOrchestrator {

    private final ReActAgent agent;
    private final AgentScopeTools tools;
    private final AgentSessionStore sessionStore;
    private final AgentProperties properties;

    public AgentScopeAgentOrchestrator(ReActAgent agent,
                                       AgentScopeTools tools,
                                       AgentSessionStore sessionStore,
                                       AgentProperties properties) {
        this.agent = agent;
        this.tools = tools;
        this.sessionStore = sessionStore;
        this.properties = properties;
    }

    @Override
    public String framework() {
        return "agentscope";
    }

    @Override
    public Set<String> registeredTools() {
        return tools.registeredTools();
    }

    @Override
    public Flux<AgentEvent> stream(AgentInvocation invocation) {
        return Flux.create(sink -> {
            long started = System.currentTimeMillis();
            AtomicBoolean terminal = new AtomicBoolean();
            StringBuilder streamed = new StringBuilder();
            AtomicReference<String> finalText = new AtomicReference<>();
            Map<String, Object> usage = new LinkedHashMap<>();
            AtomicBoolean exceeded = new AtomicBoolean();

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

            RuntimeContext context = buildContext(invocation, eventSink);
            // 先注册取消回调再订阅：客户端可能在订阅瞬间断开，晚注册会漏掉取消信号，
            // 导致上游模型流继续跑完（白烧 token）。
            reactor.core.Disposable.Swap swap = reactor.core.Disposables.swap();
            sink.onCancel(() -> {
                if (terminal.compareAndSet(false, true)) {
                    swap.dispose();
                }
            });

            Disposable disposable = agent.streamEvents(invocation.getMessage(), context)
                    .timeout(properties.getRequestTimeout())
                    .subscribe(
                            event -> consume(event, streamed, finalText, usage, exceeded, eventSink),
                            error -> fail(error, eventSink, sink, terminal),
                            () -> complete(invocation, streamed, finalText, usage, exceeded,
                                    started, eventSink, sink, terminal));
            swap.update(disposable);
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    /**
     * 每请求一个 RuntimeContext：
     * <ul>
     *   <li>{@code userId} 用 {@code tenant:user} 复合值——AgentScope 的会话槽位是
     *       {@code (userId, sessionId)}，只有复合才能隔离“不同租户用同一个 sessionId”；</li>
     *   <li>属性袋里放调用主体、工单信息、事件出口、工具预算与确认令牌，工具层只读；</li>
     *   <li>属性不持久化，随调用结束丢弃，不会把令牌写进 Redis。</li>
     * </ul>
     */
    private RuntimeContext buildContext(AgentInvocation invocation, AgentEventSink eventSink) {
        String scopeUser = invocation.getPrincipal().tenantId() + ":" + invocation.getPrincipal().userId();
        return RuntimeContext.builder()
                .userId(scopeUser)
                .sessionId(invocation.getSessionId())
                .put(ToolContextKeys.PRINCIPAL, invocation.getPrincipal())
                .put(ToolContextKeys.INVOCATION, invocation)
                .put(ToolContextKeys.SINK, eventSink)
                .put(ToolContextKeys.BUDGET, new AgentScopeToolBudget(toolBudget()))
                .put(ToolContextKeys.CONFIRM_TOKEN,
                        invocation.getConfirmToken() == null ? "" : invocation.getConfirmToken())
                .build();
    }

    /**
     * 单请求工具调用上限：与 Spring AI 分支的 {@code ToolBudget(maxIters)} 对齐，
     * 保证两个分支"最多几次工具调用"语义一致（轮数上限由 {@code ReActAgent.maxIters} 额外兜一层）。
     */
    private int toolBudget() {
        return Math.max(1, properties.getMaxIters());
    }

    private void consume(io.agentscope.core.event.AgentEvent event,
                         StringBuilder streamed,
                         AtomicReference<String> finalText,
                         Map<String, Object> usage,
                         AtomicBoolean exceeded,
                         AgentEventSink sink) {
        if (event == null || event.getType() == null) {
            return;
        }
        switch (event.getType()) {
            case TEXT_BLOCK_DELTA -> {
                TextBlockDeltaEvent delta = (TextBlockDeltaEvent) event;
                if (delta.getDelta() != null && !delta.getDelta().isEmpty()) {
                    streamed.append(delta.getDelta());
                    sink.emit(AgentEvent.delta(0, delta.getDelta()));
                }
            }
            case THINKING_BLOCK_DELTA -> {
                if (properties.isExposeThinking()) {
                    ThinkingBlockDeltaEvent thinking = (ThinkingBlockDeltaEvent) event;
                    if (thinking.getDelta() != null && !thinking.getDelta().isEmpty()) {
                        sink.emit(AgentEvent.thinking(0, thinking.getDelta()));
                    }
                }
            }
            case MODEL_CALL_END -> accumulate(((ModelCallEndEvent) event).getUsage(), usage);
            case AGENT_RESULT -> {
                // 兜底：某些路径（如 max_iters 后的总结）文本可能不走 TEXT_BLOCK_DELTA 下发，
                // 但最终消息里一定有完整答案，这里取一次作为权威结果。
                io.agentscope.core.message.Msg result = ((AgentResultEvent) event).getResult();
                if (result != null && result.getTextContent() != null && !result.getTextContent().isBlank()) {
                    finalText.set(result.getTextContent());
                }
            }
            case EXCEED_MAX_ITERS -> {
                exceeded.set(true);
                ExceedMaxItersEvent e = (ExceedMaxItersEvent) event;
                log.info("[AgentScope] 达到最大迭代轮数 max={} current={}", e.getMaxIters(), e.getCurrentIter());
            }
            default -> {
                // 其余事件（工具开始/结束、块开始/结束等）由工具适配层或最终 done 承载，避免重复下发。
            }
        }
    }

    private static void accumulate(ChatUsage usage, Map<String, Object> target) {
        if (usage == null) {
            return;
        }
        merge(target, "promptTokens", usage.getInputTokens());
        merge(target, "completionTokens", usage.getOutputTokens());
        merge(target, "totalTokens", usage.getTotalTokens());
    }

    private static void merge(Map<String, Object> target, String key, Number value) {
        if (value == null) {
            return;
        }
        Number current = (Number) target.get(key);
        long sum = (current == null ? 0L : current.longValue()) + value.longValue();
        target.put(key, sum);
    }

    private void complete(AgentInvocation invocation,
                          StringBuilder streamed,
                          AtomicReference<String> finalText,
                          Map<String, Object> usage,
                          AtomicBoolean exceeded,
                          long started,
                          AgentEventSink eventSink,
                          FluxSink<AgentEvent> sink,
                          AtomicBoolean terminal) {
        if (!terminal.compareAndSet(false, true)) {
            return;
        }
        String answer = finalText.get();
        if (answer == null || answer.isBlank()) {
            answer = streamed.toString();
        }
        if (!usage.isEmpty()) {
            eventSink.emit(AgentEvent.usage(0, usage));
        }
        if (answer != null && !answer.isBlank()) {
            sessionStore.append(invocation.getPrincipal(), invocation.getSessionId(),
                    List.of(AgentMessage.assistant(answer)));
        }
        Map<String, Object> done = new LinkedHashMap<>();
        done.put("finishReason", exceeded.get() ? "max_iters" : "stop");
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
        log.warn("[AgentScope] 执行失败 code={} : {}", code, error.getMessage());
        eventSink.emit(AgentEvent.error(0, code, code.defaultMessage()));
        sink.complete();
    }

    static AgentErrorCode classify(Throwable error) {
        if (error instanceof AgentException ae) {
            return ae.getCode();
        }
        if (error instanceof java.util.concurrent.TimeoutException) {
            return AgentErrorCode.AGENT_MODEL_TIMEOUT;
        }
        if (error instanceof HttpTransportException http) {
            Integer status = http.getStatusCode();
            if (status != null) {
                return switch (status) {
                    case 401, 403 -> AgentErrorCode.AGENT_MODEL_ERROR;
                    case 408, 504 -> AgentErrorCode.AGENT_MODEL_TIMEOUT;
                    case 429 -> AgentErrorCode.AGENT_RATE_LIMITED;
                    case 503 -> AgentErrorCode.AGENT_CIRCUIT_OPEN;
                    default -> AgentErrorCode.AGENT_MODEL_ERROR;
                };
            }
        }
        String message = error.getMessage() == null ? "" : error.getMessage().toLowerCase();
        if (message.contains("timeout") || message.contains("timed out")) {
            return AgentErrorCode.AGENT_MODEL_TIMEOUT;
        }
        if (message.contains("429") || message.contains("rate limit") || message.contains("too many")) {
            return AgentErrorCode.AGENT_RATE_LIMITED;
        }
        if (message.contains("401") || message.contains("unauthorized") || message.contains("invalid api key")) {
            return AgentErrorCode.AGENT_MODEL_ERROR;
        }
        return AgentErrorCode.AGENT_MODEL_ERROR;
    }
}
