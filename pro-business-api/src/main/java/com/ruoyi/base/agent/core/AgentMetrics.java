package com.ruoyi.base.agent.core;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agent 指标。项目未强依赖 actuator，MeterRegistry 可能不存在，
 * 此时所有方法退化为 no-op，不影响主流程。
 *
 * <p>指标命名遵循 Micrometer 约定，Prometheus 侧自动转下划线：
 * {@code agent_requests_total}、{@code agent_request_duration_seconds}、
 * {@code agent_tool_calls_total}、{@code agent_model_tokens_total}。</p>
 */
@Component
public class AgentMetrics {

    private final MeterRegistry registry;
    private final Map<String, Counter> counters = new ConcurrentHashMap<>();
    private final Map<String, Timer> timers = new ConcurrentHashMap<>();

    public AgentMetrics(ObjectProvider<MeterRegistry> registryProvider) {
        this.registry = registryProvider.getIfAvailable();
    }

    public void requestStarted(String framework) {
        if (registry == null) {
            return;
        }
        counter("agent.requests.started", "framework", framework).increment();
    }

    public void requestFinished(String framework, String result, long elapsedMs) {
        if (registry == null) {
            return;
        }
        counter("agent.requests.finished", "framework", framework, "result", result).increment();
        timer("agent.request.duration", "framework", framework, "result", result)
                .record(Duration.ofMillis(Math.max(0, elapsedMs)));
    }

    public void toolCall(String tool, String status, long elapsedMs) {
        if (registry == null) {
            return;
        }
        counter("agent.tool.calls", "tool", tool, "status", status).increment();
        timer("agent.tool.duration", "tool", tool).record(Duration.ofMillis(Math.max(0, elapsedMs)));
    }

    public void tokens(String framework, String type, long count) {
        if (registry == null || count <= 0) {
            return;
        }
        counter("agent.model.tokens", "framework", framework, "type", type).increment(count);
    }

    public void rateLimited(String dimension) {
        if (registry == null) {
            return;
        }
        counter("agent.rate.limited", "dimension", dimension).increment();
    }

    public void error(String framework, String code) {
        if (registry == null) {
            return;
        }
        counter("agent.errors", "framework", framework, "code", code).increment();
    }

    private Counter counter(String name, String... tags) {
        return counters.computeIfAbsent(key(name, tags),
                k -> Counter.builder(name).tags(tags).register(registry));
    }

    private Timer timer(String name, String... tags) {
        return timers.computeIfAbsent(key(name, tags),
                k -> Timer.builder(name).tags(tags)
                        .publishPercentiles(0.5, 0.95, 0.99).register(registry));
    }

    private static String key(String name, String... tags) {
        return name + "|" + String.join(",", tags);
    }
}
