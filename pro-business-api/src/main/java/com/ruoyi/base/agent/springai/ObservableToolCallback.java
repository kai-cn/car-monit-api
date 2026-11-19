package com.ruoyi.base.agent.springai;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentEventSink;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.ToolContextKeys;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.definition.ToolDefinition;
import org.springframework.ai.tool.metadata.ToolMetadata;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 工具回调装饰器：在不侵入业务工具的前提下，把 tool_call/tool_result 事件推给 SSE，
 * 并记录耗时、审计与指标。
 *
 * <h2>设计模式：装饰器（Decorator）</h2>
 * <p>它实现和被测对象一样的 {@link ToolCallback}，内部持有 {@code delegate}，在调用前后插入
 * "发事件 / 记指标 / 扣预算 / 卡超时 / 写审计"。这样 {@link AgentToolService} 完全不知道
 * 自己被动观测了，将来要加"限流""缓存"也只改这一层。这比在每个工具方法里手写
 * {@code metrics.record(...)} 更不易漏。</p>
 *
 * <h2>一次工具调用发生了什么</h2>
 * <pre>
 * 模型输出 tool_call
 *   → 本类发 tool_call 事件（前端立刻显示"正在查询…"）
 *   → 校验预算（超了就返回 TOOL_ERROR 的 JSON，不执行）
 *   → 提交到虚拟线程执行（带超时）
 *   → 拿到结果：脱敏/截断已在业务层完成
 *   → 发 tool_result 事件（含 status/latencyMs）+ 写审计 + 打指标
 *   → 把 JSON 字符串交回框架，框架再喂给模型
 * </pre>
 */
public class ObservableToolCallback implements ToolCallback {

    /**
     * 工具执行线程池：<b>每个任务一条虚拟线程</b>。
     *
     * <p>【Java 21 虚拟线程】虚拟线程是 JVM 调度的"轻量线程"：创建成本约几百字节（平台线程是 MB 级），
     * 阻塞时自动把底层载体线程让出去。因此"给每个工具调用开一条线程"不再奢侈，
     * 也避免了固定线程池被慢查询占满后其它工具饿死。</p>
     *
     * <p>写法拆解：{@code Thread.ofVirtual().name("agent-tool-", 0).factory()} 生成线程工厂
     * （名字带自增编号，便于 jstack/火焰图定位）；{@code Executors.newThreadPerTaskExecutor}
     * 把它包装成"一任务一线程"的执行器。</p>
     *
     * <p><b>注意</b>：虚拟线程适合"阻塞等待 I/O"，但<b>不能解决</b> CPU 密集或连接池上限问题，
     * 所以下面还有一个信号量。</p>
     */
    private static final ExecutorService TOOL_EXECUTOR =
            Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("agent-tool-", 0).factory());

    /**
     * 同时在跑的工具调用上限。虚拟线程本身不限制并发，不设闸的话"超时放弃等待"会让慢查询
     * 越积越多，最终打满 ES/GaussDB 连接池。这里按工具并发（而非请求并发）兜一层。
     */
    private static final Semaphore TOOL_PERMITS = new Semaphore(32, true);

    private final ToolCallback delegate;
    private final AgentMetrics metrics;
    private final AgentAuditLogger auditLogger;
    private final AgentProperties properties;

    public ObservableToolCallback(ToolCallback delegate, AgentMetrics metrics,
                                  AgentAuditLogger auditLogger, AgentProperties properties) {
        this.delegate = delegate;
        this.metrics = metrics;
        this.auditLogger = auditLogger;
        this.properties = properties;
    }

    @Override
    public ToolDefinition getToolDefinition() {
        return delegate.getToolDefinition();
    }

    @Override
    public ToolMetadata getToolMetadata() {
        return delegate.getToolMetadata();
    }

    @Override
    public String call(String toolInput) {
        // Spring AI 的 ToolCallingManager 始终调用双参版本；单参版本若被外部直接调用，
        // 会绕过预算/审计/超时。这里统一走同一条受控路径（无上下文 → 业务层会因缺少主体返回错误）。
        return call(toolInput, null);
    }

    @Override
    public String call(String toolInput, ToolContext toolContext) {
        String name = getToolDefinition().name();
        Map<String, Object> context = toolContext == null ? Map.of() : toolContext.getContext();
        AgentEventSink sink = context.get(ToolContextKeys.SINK) instanceof AgentEventSink s ? s : null;
        AgentInvocation invocation = context.get(ToolContextKeys.INVOCATION) instanceof AgentInvocation i ? i : null;
        ToolBudget budget = context.get(ToolContextKeys.BUDGET) instanceof ToolBudget b ? b : null;

        String callId = UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        Object arguments = parseArguments(toolInput);
        if (sink != null) {
            sink.emit(AgentEvent.toolCall(0, callId, name, arguments));
        }
        if (budget != null && !budget.tryUse()) {
            String msg = "{\"ok\":false,\"errorCode\":\"AGENT_MAX_ITERS\",\"message\":\"工具调用轮数已达上限，请直接根据已有结果回答\"}";
            if (sink != null) {
                sink.emit(AgentEvent.toolResult(0, callId, name, "error", "max iters", 0));
            }
            return msg;
        }

        long started = System.currentTimeMillis();
        try {
            String result = invokeWithTimeout(toolInput, toolContext);
            long elapsed = System.currentTimeMillis() - started;
            String status = isError(result) ? "error" : "ok";
            if (sink != null) {
                sink.emit(AgentEvent.toolResult(0, callId, name, status, summarize(result), elapsed));
            }
            metrics.toolCall(name, status, elapsed);
            if (invocation != null) {
                auditLogger.tool(invocation, name, status, elapsed, summarize(result));
            }
            return truncate(result);
        } catch (Exception e) {
            long elapsed = System.currentTimeMillis() - started;
            String message = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            if (sink != null) {
                sink.emit(AgentEvent.toolResult(0, callId, name, "error", message, elapsed));
            }
            metrics.toolCall(name, "error", elapsed);
            if (invocation != null) {
                auditLogger.tool(invocation, name, "error", elapsed, message);
            }
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("ok", false);
            error.put("errorCode", "TOOL_ERROR");
            error.put("message", message);
            return JSON.toJSONString(error);
        }
    }

    /**
     * 带超时的工具调用。
     *
     * <p>Spring AI 的 {@code ToolCallingManager} 不提供单工具超时，若不包一层，一个慢查询会一直
     * 占用并发许可直到 SSE 总超时（默认 120s），期间其它请求只能排队或直接 {@code AGENT_BUSY}。</p>
     *
     * <p><b>许可的所有权</b>：{@link #TOOL_PERMITS} 限制的是"真正在跑的查询数"，不是"在等结果的
     * 请求线程数"。因此 acquire 之后所有权就交给了任务本身，由任务在 {@code finally} 里 release。
     * 若在这里的 {@code finally} 释放（曾这么写），超时返回时底层 JDBC/HTTP 还在跑，
     * 许可却已经还回去了——超时越多、并发越高，恰恰与限流目的相反。</p>
     */
    private String invokeWithTimeout(String toolInput, ToolContext toolContext) throws Exception {
        long timeoutMs = properties.getToolTimeout() == null || properties.getToolTimeout().isNegative()
                ? 20_000L
                : Math.max(1, properties.getToolTimeout().toMillis());
        boolean acquired;
        try {
            acquired = TOOL_PERMITS.tryAcquire(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("工具执行被中断，请稍后重试");
        }
        if (!acquired) {
            throw new IllegalStateException("工具并发已满（>" + timeoutMs + "ms 未获得执行许可），请稍后重试");
        }

        CompletableFuture<String> future;
        try {
            future = CompletableFuture.supplyAsync(() -> delegate.call(toolInput, toolContext), TOOL_EXECUTOR);
        } catch (RuntimeException e) {
            // 提交失败（如线程池已关闭）说明任务不会执行，也不会有 future，许可必须在这里归还
            TOOL_PERMITS.release();
            throw e;
        }

        // 【唯一释放点】放在 whenComplete 而不是任务体里的 finally：
        // 若任务还在队列里排队就被取消，supplier 根本不会执行、finally 也不会跑，
        // 许可就永久泄漏了（32 个许可漏完，之后所有工具恒返回 AGENT_BUSY）。
        // future 一定会落到某个终态（正常完成 / 任务抛异常 / 被取消），
        // whenComplete 在三种情况下都会执行且只执行一次，因此这里释放既不漏也不重。
        future.whenComplete((ignored, error) -> TOOL_PERMITS.release());

        try {
            return future.get(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            // 【这里刻意不调用 future.cancel】它看起来更"干净"，但实测（JDK 25）：
            // 对**已在运行**的任务，cancel(false) 会立刻把 future 置为 CancellationException，
            // whenComplete 当场触发、许可立刻还回去，而底层 JDBC/HTTP 查询还在跑——
            // 于是"慢查询最该被限流"的场景恰恰限不住，与 TOOL_PERMITS 的设计目的相反。
            // cancel 也中断不了查询（真正的取消依赖 ES socket-timeout / GaussDB
            // statement_timeout），所以这里只放弃结果，许可等任务真正结束再归还。
            throw new IllegalStateException("工具执行超时（>" + timeoutMs + "ms），请缩小查询范围后重试");
        }
    }

    private static Object parseArguments(String toolInput) {
        try {
            JSONObject json = JSON.parseObject(toolInput);
            return json == null ? Map.of() : json;
        } catch (Exception e) {
            return toolInput;
        }
    }

    private static boolean isError(String result) {
        if (result == null) {
            return true;
        }
        try {
            JSONObject json = JSON.parseObject(result);
            return json != null && Boolean.FALSE.equals(json.get("ok"));
        } catch (Exception e) {
            return false;
        }
    }

    static String summarize(String result) {
        if (result == null) {
            return "";
        }
        try {
            JSONObject json = JSON.parseObject(result);
            if (json == null) {
                return result.substring(0, Math.min(result.length(), 160));
            }
            StringBuilder sb = new StringBuilder();
            append(sb, "ok", json.get("ok"));
            append(sb, "total", json.get("total"));
            append(sb, "count", json.get("count"));
            append(sb, "pointCount", json.get("pointCount"));
            append(sb, "status", json.get("status"));
            append(sb, "errorCode", json.get("errorCode"));
            if (sb.isEmpty()) {
                return result.substring(0, Math.min(result.length(), 160));
            }
            return sb.toString();
        } catch (Exception e) {
            return result.substring(0, Math.min(result.length(), 160));
        }
    }

    private static void append(StringBuilder sb, String key, Object value) {
        if (value == null) {
            return;
        }
        if (!sb.isEmpty()) {
            sb.append(',');
        }
        sb.append(key).append('=').append(value);
    }

    /**
     * 截断必须是合法 JSON：直接切字符串会让模型侧解析失败，因此包一层结构化标记，
     * 并把原始内容作为 {@code preview} 保留（便于模型判断"要不要缩小范围再查"）。
     */
    private String truncate(String result) {
        int max = properties.getMaxToolResultChars();
        max = Math.max(1000, max);
        if (result == null || result.length() <= max) {
            return result;
        }
        Map<String, Object> truncated = new LinkedHashMap<>();
        truncated.put("ok", true);
        truncated.put("truncated", true);
        truncated.put("message", "结果过大已截断，请缩小时间范围/增加筛选条件后重试");
        truncated.put("preview", result.substring(0, max));
        return JSON.toJSONString(truncated);
    }
}
