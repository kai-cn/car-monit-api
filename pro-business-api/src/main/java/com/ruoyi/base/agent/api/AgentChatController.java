package com.ruoyi.base.agent.api;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentConcurrencyLimiter;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentEventSink;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentGuard;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentRateLimiter;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.api.dto.AgentChatRequest;
import com.ruoyi.base.agent.api.dto.AgentChatResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.MediaType;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.Disposable;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 对话入口：
 * <ul>
 *   <li>{@code POST /api/v1/agent/chat}：SSE 流式（前端默认）；</li>
 *   <li>{@code POST /api/v1/agent/chat/sync}：同步聚合（backend/BFF 调用）。</li>
 * </ul>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/agent")
public class AgentChatController {

    private final ObjectProvider<AgentOrchestrator> orchestratorProvider;
    private final AgentGuard guard;
    private final AgentRateLimiter rateLimiter;
    private final AgentConcurrencyLimiter concurrencyLimiter;
    private final AgentSessionStore sessionStore;
    private final AgentAuditLogger auditLogger;
    private final AgentMetrics metrics;
    private final AgentProperties properties;
    private final AgentRequestContext requestContext;
    private final TaskScheduler taskScheduler;

    public AgentChatController(ObjectProvider<AgentOrchestrator> orchestratorProvider,
                               AgentGuard guard,
                               AgentRateLimiter rateLimiter,
                               AgentConcurrencyLimiter concurrencyLimiter,
                               AgentSessionStore sessionStore,
                               AgentAuditLogger auditLogger,
                               AgentMetrics metrics,
                               AgentProperties properties,
                               AgentRequestContext requestContext,
                               @org.springframework.beans.factory.annotation.Qualifier("agentTaskScheduler")
                               TaskScheduler taskScheduler) {
        this.orchestratorProvider = orchestratorProvider;
        this.guard = guard;
        this.rateLimiter = rateLimiter;
        this.concurrencyLimiter = concurrencyLimiter;
        this.sessionStore = sessionStore;
        this.auditLogger = auditLogger;
        this.metrics = metrics;
        this.properties = properties;
        this.requestContext = requestContext;
        this.taskScheduler = taskScheduler;
    }

    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@Valid @RequestBody AgentChatRequest body, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        String requestId = requestContext.requestId(request);
        AgentOrchestrator orchestrator = requireOrchestrator();
        prepare(principal, body);

        String sessionId = resolveSessionId(principal, body.getSessionId());
        AgentInvocation invocation = AgentInvocation.builder()
                .requestId(requestId)
                .principal(principal)
                .sessionId(sessionId)
                .message(body.getMessage().trim())
                .confirmToken(body.getConfirmToken())
                .locale(body.getLocale() == null ? "zh-CN" : body.getLocale())
                .startedAt(System.currentTimeMillis())
                .build();

        SseEmitter emitter = new SseEmitter(properties.getRequestTimeout().toMillis());
        ChatStream stream = new ChatStream(emitter, orchestrator, invocation);
        emitter.onTimeout(stream::onTimeout);
        emitter.onError(stream::onError);
        emitter.onCompletion(stream::onCompletion);
        stream.start();
        return emitter;
    }

    @PostMapping(value = "/chat/sync", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> chatSync(@Valid @RequestBody AgentChatRequest body, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        String requestId = requestContext.requestId(request);
        AgentOrchestrator orchestrator = requireOrchestrator();
        prepare(principal, body);
        String sessionId = resolveSessionId(principal, body.getSessionId());

        AgentInvocation invocation = AgentInvocation.builder()
                .requestId(requestId)
                .principal(principal)
                .sessionId(sessionId)
                .message(body.getMessage().trim())
                .confirmToken(body.getConfirmToken())
                .locale(body.getLocale() == null ? "zh-CN" : body.getLocale())
                .startedAt(System.currentTimeMillis())
                .build();

        long started = System.currentTimeMillis();
        try {
            List<AgentEvent> events = orchestrator.stream(invocation)
                    .collectList()
                    .block(Duration.ofMillis(properties.getRequestTimeout().toMillis()));
            if (events == null) {
                throw new AgentException(AgentErrorCode.AGENT_MODEL_TIMEOUT);
            }
            AgentChatResponse response = aggregate(requestId, sessionId, events, started);
            auditLogger.chat(invocation, "ok", System.currentTimeMillis() - started,
                    response.getUsage(), null);
            metrics.requestFinished(orchestrator.framework(), "ok", System.currentTimeMillis() - started);
            Map<String, Object> wrapper = new LinkedHashMap<>();
            wrapper.put("code", 200);
            wrapper.put("message", "ok");
            wrapper.put("data", response);
            return wrapper;
        } catch (AgentException e) {
            auditLogger.chat(invocation, "error", System.currentTimeMillis() - started, null, e.getCode().name());
            metrics.error(orchestrator.framework(), e.getCode().name());
            throw e;
        } finally {
            concurrencyLimiter.release();
        }
    }

    private AgentChatResponse aggregate(String requestId, String sessionId, List<AgentEvent> events, long started) {
        StringBuilder answer = new StringBuilder();
        List<Map<String, Object>> tools = new ArrayList<>();
        Map<String, Object> usage = new LinkedHashMap<>();
        String finishReason = "stop";
        for (AgentEvent event : events) {
            switch (event.getType()) {
                case AgentEvent.DELTA -> answer.append(String.valueOf(event.getPayload().getOrDefault("text", "")));
                case AgentEvent.TOOL_CALL -> tools.add(new LinkedHashMap<>(event.getPayload()));
                case AgentEvent.TOOL_RESULT -> {
                    Object id = event.getPayload().get("id");
                    for (Map<String, Object> tool : tools) {
                        if (id != null && id.equals(tool.get("id"))) {
                            tool.put("result", event.getPayload());
                            break;
                        }
                    }
                }
                case AgentEvent.USAGE -> usage.putAll(event.getPayload());
                case AgentEvent.DONE -> {
                    Object fr = event.getPayload().get("finishReason");
                    if (fr != null) {
                        finishReason = String.valueOf(fr);
                    }
                    Object u = event.getPayload().get("usage");
                    if (u instanceof Map<?, ?> map) {
                        map.forEach((k, v) -> usage.put(String.valueOf(k), v));
                    }
                }
                case AgentEvent.ERROR -> {
                    Object code = event.getPayload().get("code");
                    throw new AgentException(AgentErrorCode.valueOf(String.valueOf(code)),
                            String.valueOf(event.getPayload().get("message")));
                }
                default -> {
                    // thinking/heartbeat 不进入同步响应
                }
            }
        }
        AgentChatResponse response = new AgentChatResponse();
        response.setRequestId(requestId);
        response.setSessionId(sessionId);
        response.setAnswer(answer.toString());
        response.setToolCalls(tools);
        response.setUsage(usage);
        response.setElapsedMs(System.currentTimeMillis() - started);
        response.setFinishReason(finishReason);
        return response;
    }

    private void prepare(AgentPrincipal principal, AgentChatRequest body) {
        guard.validateMessage(body.getMessage());
        String limited = rateLimiter.tryAcquire(principal);
        if (limited != null) {
            metrics.rateLimited(limited);
            throw new AgentException(AgentErrorCode.AGENT_RATE_LIMITED,
                    "租户" + ("tenant".equals(limited) ? "" : "用户") + "请求过于频繁，请稍后再试");
        }
        if (!concurrencyLimiter.tryAcquire()) {
            throw new AgentException(AgentErrorCode.AGENT_BUSY);
        }
    }

    private AgentOrchestrator requireOrchestrator() {
        AgentOrchestrator orchestrator = orchestratorProvider.getIfAvailable();
        if (orchestrator == null) {
            throw new AgentException(AgentErrorCode.AGENT_DISABLED);
        }
        return orchestrator;
    }

    private String resolveSessionId(AgentPrincipal principal, String requested) {
        if (requested != null && !requested.isBlank()) {
            return requested.trim();
        }
        return UUID.randomUUID().toString().replace("-", "");
    }

    /**
     * 单次 SSE 会话：负责序号、心跳、审计、并发释放与资源清理。
     */
    private final class ChatStream implements AgentEventSink {

        private final SseEmitter emitter;
        private final AgentOrchestrator orchestrator;
        private final AgentInvocation invocation;
        private final AtomicLong seq = new AtomicLong();
        private final AtomicBoolean finished = new AtomicBoolean();
        private final AtomicBoolean released = new AtomicBoolean();
        private final Map<String, Object> usage = new LinkedHashMap<>();
        private volatile Disposable disposable;
        private volatile ScheduledFuture<?> heartbeat;
        private volatile String errorCode;

        private ChatStream(SseEmitter emitter, AgentOrchestrator orchestrator, AgentInvocation invocation) {
            this.emitter = emitter;
            this.orchestrator = orchestrator;
            this.invocation = invocation;
        }

        void start() {
            metrics.requestStarted(orchestrator.framework());
            // meta 事件由编排器统一发出（携带 framework/model/time，属框架语义），
            // 这里不再重复下发，避免同一个 SSE 流出现两条 meta 事件。
            long interval = Math.max(1000, properties.getHeartbeatInterval().toMillis());
            heartbeat = taskScheduler.scheduleAtFixedRate(() -> {
                if (finished.get()) {
                    return;
                }
                try {
                    emitter.send(SseEmitter.event().comment("ping"));
                } catch (Exception ignored) {
                    // 客户端断开由 onCompletion/onError 统一清理
                }
            }, Instant.now().plusMillis(interval), Duration.ofMillis(interval));

            disposable = orchestrator.stream(invocation).subscribe(
                    this::emit,
                    err -> {
                        log.warn("[Agent] 流式执行失败 requestId={}: {}", invocation.getRequestId(), err.getMessage());
                        AgentErrorCode code = classify(err);
                        errorCode = code.name();
                        emit(AgentEvent.error(0, code, code.defaultMessage()));
                        finish("error");
                    },
                    () -> finish("ok"));
        }

        @Override
        public void emit(AgentEvent event) {
            if (finished.get()) {
                return;
            }
            long id = seq.incrementAndGet();
            if (AgentEvent.USAGE.equals(event.getType())) {
                usage.putAll(event.getPayload());
            }
            if (AgentEvent.ERROR.equals(event.getType())) {
                Object code = event.getPayload().get("code");
                errorCode = code == null ? AgentErrorCode.AGENT_INTERNAL.name() : String.valueOf(code);
            }
            try {
                emitter.send(SseEmitter.event()
                        .id(String.valueOf(id))
                        .name(event.getType())
                        .data(JSON.toJSONString(event.getPayload())));
            } catch (Exception e) {
                log.debug("[Agent] SSE 写入失败（客户端可能已断开）: {}", e.getMessage());
                finished.set(true);
                release();
                dispose();
                return;
            }
            if (AgentEvent.DONE.equals(event.getType()) || AgentEvent.ERROR.equals(event.getType())) {
                finish(AgentEvent.ERROR.equals(event.getType()) ? "error" : "ok");
            }
        }

        void onTimeout() {
            if (finished.compareAndSet(false, true)) {
                try {
                    emitter.send(SseEmitter.event().name(AgentEvent.ERROR)
                            .data(JSON.toJSONString(Map.of(
                                    "code", AgentErrorCode.AGENT_MODEL_TIMEOUT.name(),
                                    "message", "请求超时，请缩小查询范围后重试",
                                    "retryable", true))));
                } catch (Exception ignored) {
                    // ignore
                }
                errorCode = AgentErrorCode.AGENT_MODEL_TIMEOUT.name();
                release();
                dispose();
                emitter.complete();
                audit("timeout");
            }
        }

        void onError(Throwable throwable) {
            log.debug("[Agent] SSE 连接异常: {}", throwable.getMessage());
            if (finished.compareAndSet(false, true)) {
                release();
                dispose();
                audit("error");
            }
        }

        void onCompletion() {
            if (finished.compareAndSet(false, true)) {
                release();
                dispose();
                audit(errorCode == null ? "ok" : "error");
            }
        }

        private void finish(String result) {
            if (!finished.compareAndSet(false, true)) {
                return;
            }
            release();
            dispose();
            try {
                emitter.complete();
            } catch (Exception ignored) {
                // ignore
            }
            audit(result);
        }

        private void audit(String result) {
            long elapsed = System.currentTimeMillis() - invocation.getStartedAt();
            auditLogger.chat(invocation, result, elapsed, usage, errorCode);
            metrics.requestFinished(orchestrator.framework(), result, elapsed);
            Object prompt = usage.get("promptTokens");
            Object completion = usage.get("completionTokens");
            if (prompt instanceof Number n) {
                metrics.tokens(orchestrator.framework(), "prompt", n.longValue());
            }
            if (completion instanceof Number n) {
                metrics.tokens(orchestrator.framework(), "completion", n.longValue());
            }
        }

        private void release() {
            if (released.compareAndSet(false, true)) {
                concurrencyLimiter.release();
            }
        }

        private void dispose() {
            ScheduledFuture<?> hb = heartbeat;
            if (hb != null) {
                hb.cancel(false);
            }
            Disposable d = disposable;
            if (d != null && !d.isDisposed()) {
                d.dispose();
            }
        }

        private AgentErrorCode classify(Throwable err) {
            if (err instanceof AgentException ae) {
                return ae.getCode();
            }
            String name = err.getClass().getSimpleName().toLowerCase();
            String msg = err.getMessage() == null ? "" : err.getMessage().toLowerCase();
            if (name.contains("timeout") || msg.contains("timeout") || msg.contains("timed out")) {
                return AgentErrorCode.AGENT_MODEL_TIMEOUT;
            }
            return AgentErrorCode.AGENT_MODEL_ERROR;
        }
    }
}
