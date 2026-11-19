package com.ruoyi.base.agent.agentscope;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentEventSink;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.ToolContextKeys;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import com.ruoyi.base.agent.tools.AgentToolService;
import io.agentscope.core.agent.RuntimeContext;
import io.agentscope.core.message.ToolResultBlock;
import io.agentscope.core.tool.AgentTool;
import io.agentscope.core.tool.ToolCallParam;
import io.agentscope.core.tool.Toolkit;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 把框架无关的 {@link AgentToolCatalog} 装配成 AgentScope {@link Toolkit}。
 *
 * <p>设计要点：</p>
 * <ul>
 *   <li><b>Schema 单一事实源</b>：工具名、描述、JSON Schema 全部来自 {@link AgentToolCatalog}，
 *       与 Spec 文档、{@code GET /api/v1/agent/tools} 完全同源，杜绝“文档与实现漂移”；</li>
 *   <li><b>不用 {@code @Tool} 注解反射生成 schema</b>：参数名保持 snake_case，且不依赖
 *       {@code -parameters} 编译参数，GraalVM native-image 更友好；</li>
 *   <li><b>事件/审计/指标在适配层完成</b>：业务工具（{@link AgentToolService}）只管查数，
 *       不感知 SSE、不感知 AgentScope；</li>
 *   <li><b>上下文只从 RuntimeContext 取</b>：调用主体、确认令牌由服务端注入，模型无法伪造。</li>
 * </ul>
 */
@Slf4j
@Component
public class AgentScopeTools {

    private final AgentToolService toolService;
    private final AgentMetrics metrics;
    private final AgentAuditLogger auditLogger;
    private final AgentProperties properties;
    private final Toolkit toolkit;
    private final Set<String> registeredTools;

    public AgentScopeTools(AgentToolService toolService,
                           AgentMetrics metrics,
                           AgentAuditLogger auditLogger,
                           AgentProperties properties) {
        this.toolService = toolService;
        this.metrics = metrics;
        this.auditLogger = auditLogger;
        this.properties = properties;
        validateCatalog();
        this.toolkit = new Toolkit();
        Set<String> names = new LinkedHashSet<>();
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            toolkit.registerAgentTool(new CatalogTool(spec));
            names.add(spec.name());
        }
        this.registeredTools = Set.copyOf(names);
        if (!registeredTools.equals(toolkit.getToolNames())) {
            throw new IllegalStateException("AgentScope Toolkit 注册的工具与目录不一致: "
                    + registeredTools + " vs " + toolkit.getToolNames());
        }
        log.info("[AgentScope] 已注册 {} 个工具: {}", registeredTools.size(), registeredTools);
    }

    /** 供 ReActAgent 共享的 Toolkit；工具本身无状态，可跨会话复用。 */
    public Toolkit toolkit() {
        return toolkit;
    }

    public Set<String> registeredTools() {
        return registeredTools;
    }

    /** 启动期校验：schema 必须是合法 JSON 对象，避免把坏 schema 发给模型。 */
    private static void validateCatalog() {
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            try {
                JSONObject json = JSON.parseObject(spec.inputSchema());
                if (json == null || !"object".equals(json.get("type"))) {
                    throw new IllegalStateException("工具 " + spec.name() + " 的 inputSchema 必须为 object");
                }
            } catch (IllegalStateException e) {
                throw e;
            } catch (Exception e) {
                throw new IllegalStateException("工具 " + spec.name() + " 的 inputSchema 不是合法 JSON", e);
            }
        }
    }

    /**
     * 单个工具的 AgentScope 适配器：把 {@link AgentToolService} 的返回值转成
     * {@link ToolResultBlock}，同时负责事件、预算、审计、指标与结果截断。
     */
    final class CatalogTool implements AgentTool {

        private final AgentToolCatalog.ToolSpec spec;
        private final Map<String, Object> parameters;

        CatalogTool(AgentToolCatalog.ToolSpec spec) {
            this.spec = spec;
            this.parameters = JSON.parseObject(spec.inputSchema(), Map.class);
        }

        @Override
        public String getName() {
            return spec.name();
        }

        @Override
        public String getDescription() {
            return spec.description();
        }

        @Override
        public Map<String, Object> getParameters() {
            return parameters;
        }

        @Override
        public boolean isReadOnly() {
            // 只读工具在受限执行模式下可自动放行；写工具（导出）永远需要用户二次确认。
            return spec.risk() == AgentToolCatalog.Risk.READ;
        }

        @Override
        public Mono<ToolResultBlock> callAsync(ToolCallParam param) {
            // 工具执行可能阻塞（ES/GaussDB 查询），必须切到弹性线程池，避免占用 Reactor 事件循环。
            return Mono.fromCallable(() -> invoke(param))
                    .subscribeOn(Schedulers.boundedElastic());
        }

        private ToolResultBlock invoke(ToolCallParam param) {
            RuntimeContext ctx = param.getRuntimeContext();
            String callId = param.getToolUseBlock() == null ? randomId() : param.getToolUseBlock().getId();
            Map<String, Object> args = param.getInput() == null ? Map.of() : new LinkedHashMap<>(param.getInput());
            AgentEventSink sink = attr(ctx, ToolContextKeys.SINK, AgentEventSink.class);
            AgentInvocation invocation = attr(ctx, ToolContextKeys.INVOCATION, AgentInvocation.class);
            AgentPrincipal principal = attr(ctx, ToolContextKeys.PRINCIPAL, AgentPrincipal.class);
            AgentScopeToolBudget budget = attr(ctx, ToolContextKeys.BUDGET, AgentScopeToolBudget.class);
            String confirmToken = attr(ctx, ToolContextKeys.CONFIRM_TOKEN, String.class);

            if (sink != null) {
                sink.emit(AgentEvent.toolCall(0, callId, spec.name(), args));
            }
            if (principal == null) {
                // 上下文缺失属于编程错误：显式失败，避免以“匿名主体”继续查询造成越权。
                String message = "工具上下文缺少调用主体";
                emitResult(sink, callId, "error", message, 0);
                return ToolResultBlock.error(message);
            }
            if (budget != null && !budget.tryUse()) {
                Map<String, Object> rejected = new LinkedHashMap<>();
                rejected.put("ok", false);
                rejected.put("errorCode", "AGENT_MAX_ITERS");
                rejected.put("message", "工具调用次数已达上限，请直接根据已有结果回答，或提示用户缩小范围");
                emitResult(sink, callId, "error", "max tool calls", 0);
                return ToolResultBlock.text(JSON.toJSONString(rejected));
            }

            long started = System.currentTimeMillis();
            try {
                Map<String, Object> result = dispatch(principal, invocation, confirmToken, args);
                long elapsed = System.currentTimeMillis() - started;
                String json = JSON.toJSONString(result);
                String status = Boolean.FALSE.equals(result.get("ok")) ? "error" : "ok";
                String summary = summarize(result);
                emitResult(sink, callId, status, summary, elapsed);
                metrics.toolCall(spec.name(), status, elapsed);
                if (invocation != null) {
                    auditLogger.tool(invocation, spec.name(), status, elapsed, summary);
                }
                return ToolResultBlock.text(truncate(json));
            } catch (Exception e) {
                long elapsed = System.currentTimeMillis() - started;
                String message = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                log.warn("[AgentScope] 工具 {} 执行失败: {}", spec.name(), message);
                emitResult(sink, callId, "error", message, elapsed);
                metrics.toolCall(spec.name(), "error", elapsed);
                if (invocation != null) {
                    auditLogger.tool(invocation, spec.name(), "error", elapsed, message);
                }
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("ok", false);
                error.put("errorCode", "AGENT_TOOL_ERROR");
                error.put("message", message);
                return ToolResultBlock.text(JSON.toJSONString(error));
            }
        }

        /** 工具名 → 业务实现。新增工具时这里与 {@link AgentToolCatalog} 必须同时改。 */
        private Map<String, Object> dispatch(AgentPrincipal principal, AgentInvocation invocation,
                                             String confirmToken, Map<String, Object> args) {
            return switch (spec.name()) {
                case AgentToolCatalog.QUERY_TRAFFIC -> toolService.queryTraffic(principal, args);
                case AgentToolCatalog.VEHICLE_TRACK -> toolService.vehicleTrack(principal, args);
                case AgentToolCatalog.BIGSCREEN_METRIC -> toolService.bigScreen(principal, args);
                case AgentToolCatalog.SEARCH_KNOWLEDGE -> toolService.searchKnowledge(args);
                case AgentToolCatalog.SUBMIT_EXPORT -> toolService.submitExport(
                        principal,
                        invocation == null ? "" : invocation.getSessionId(),
                        confirmToken == null ? "" : confirmToken,
                        args);
                case AgentToolCatalog.EXPORT_STATUS -> toolService.exportStatus(principal, args);
                case AgentToolCatalog.DATA_QUALITY -> toolService.dataQuality(principal, args);
                default -> Map.of("ok", false, "errorCode", "UNKNOWN_TOOL", "message", "未知工具: " + spec.name());
            };
        }

        private void emitResult(AgentEventSink sink, String callId, String status, String summary, long elapsed) {
            if (sink != null) {
                sink.emit(AgentEvent.toolResult(0, callId, spec.name(), status, summary, elapsed));
            }
        }

        private String truncate(String json) {
            int max = Math.max(1000, properties.getMaxToolResultChars());
            if (json == null || json.length() <= max) {
                return json;
            }
            // 截断必须仍是合法 JSON，否则模型侧解析会报错；这里包一层结构化的“已截断”标记。
            Map<String, Object> truncated = new LinkedHashMap<>();
            truncated.put("ok", true);
            truncated.put("truncated", true);
            truncated.put("message", "结果过大已截断，请缩小时间范围/增加筛选条件后重试");
            truncated.put("preview", json.substring(0, Math.min(max, json.length())));
            return JSON.toJSONString(truncated);
        }
    }

    private static <T> T attr(RuntimeContext ctx, String key, Class<T> type) {
        if (ctx == null) {
            return null;
        }
        Object value = ctx.get(key);
        return type.isInstance(value) ? type.cast(value) : null;
    }

    private static String randomId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }

    /** 从结果里抽取面向用户的短摘要，避免把整段 JSON 塞进 SSE。 */
    static String summarize(Map<String, Object> result) {
        if (result == null || result.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        for (String key : List.of("ok", "total", "count", "pointCount", "status", "errorCode")) {
            Object value = result.get(key);
            if (value == null) {
                continue;
            }
            if (!sb.isEmpty()) {
                sb.append(',');
            }
            sb.append(key).append('=').append(value);
        }
        if (sb.isEmpty()) {
            sb.append("keys=").append(result.keySet());
        }
        return sb.length() > 200 ? sb.substring(0, 200) : sb.toString();
    }
}
