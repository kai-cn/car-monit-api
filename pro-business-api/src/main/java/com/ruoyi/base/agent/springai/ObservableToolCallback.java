package com.ruoyi.base.agent.springai;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
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

/**
 * 工具回调装饰器：在不侵入业务工具的前提下，把 tool_call/tool_result 事件推给 SSE，
 * 并记录耗时、审计与指标。
 */
public class ObservableToolCallback implements ToolCallback {

    private final ToolCallback delegate;
    private final AgentMetrics metrics;
    private final AgentAuditLogger auditLogger;

    public ObservableToolCallback(ToolCallback delegate, AgentMetrics metrics, AgentAuditLogger auditLogger) {
        this.delegate = delegate;
        this.metrics = metrics;
        this.auditLogger = auditLogger;
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
        return delegate.call(toolInput);
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
            String result = delegate.call(toolInput, toolContext);
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

    private static String truncate(String result) {
        int max = 8000;
        if (result == null || result.length() <= max) {
            return result;
        }
        return result.substring(0, max) + "...(truncated)";
    }
}
