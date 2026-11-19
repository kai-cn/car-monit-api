package com.ruoyi.base.agent.springai;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.ToolContextKeys;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import com.ruoyi.base.agent.tools.AgentToolService;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 把框架无关的工具目录装配成 Spring AI ToolCallback 列表。
 * 每个回调都包一层 {@link ObservableToolCallback}，统一发事件/做审计。
 */
@Component
public class SpringAiToolCallbacks {

    private final AgentToolService toolService;
    private final AgentMetrics metrics;
    private final AgentAuditLogger auditLogger;
    private final AgentProperties properties;
    private final List<ToolCallback> callbacks;

    public SpringAiToolCallbacks(AgentToolService toolService, AgentMetrics metrics,
                                 AgentAuditLogger auditLogger, AgentProperties properties) {
        this.toolService = toolService;
        this.metrics = metrics;
        this.auditLogger = auditLogger;
        this.properties = properties;
        this.callbacks = build();
        validateCatalog();
    }

    public List<ToolCallback> callbacks() {
        return callbacks;
    }

    public Set<String> registeredTools() {
        Set<String> names = new LinkedHashSet<>();
        for (ToolCallback callback : callbacks) {
            names.add(callback.getToolDefinition().name());
        }
        return names;
    }

    private List<ToolCallback> build() {
        List<ToolCallback> list = new ArrayList<>();
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            JsonToolCallback callback = new JsonToolCallback(spec, (args, ctx) -> dispatch(spec.name(), args, ctx));
            list.add(new ObservableToolCallback(callback, metrics, auditLogger, properties));
        }
        return List.copyOf(list);
    }

    private String dispatch(String name, Map<String, Object> args, ToolContext context) {
        AgentPrincipal principal = principal(context);
        AgentInvocation invocation = invocation(context);
        String confirmToken = context == null ? null
                : String.valueOf(context.getContext().getOrDefault(ToolContextKeys.CONFIRM_TOKEN, ""));
        Map<String, Object> result = switch (name) {
            case AgentToolCatalog.QUERY_TRAFFIC -> toolService.queryTraffic(principal, args);
            case AgentToolCatalog.VEHICLE_TRACK -> toolService.vehicleTrack(principal, args);
            case AgentToolCatalog.BIGSCREEN_METRIC -> toolService.bigScreen(principal, args);
            case AgentToolCatalog.SEARCH_KNOWLEDGE -> toolService.searchKnowledge(principal, args);
            case AgentToolCatalog.SUBMIT_EXPORT -> toolService.submitExport(
                    principal, invocation.getSessionId(), confirmToken, args);
            case AgentToolCatalog.EXPORT_STATUS -> toolService.exportStatus(principal, args);
            case AgentToolCatalog.DATA_QUALITY -> toolService.dataQuality(principal, args);
            default -> Map.of("ok", false, "errorCode", "UNKNOWN_TOOL", "message", "未知工具: " + name);
        };
        return JSON.toJSONString(result);
    }

    private static AgentPrincipal principal(ToolContext context) {
        if (context != null && context.getContext().get(ToolContextKeys.PRINCIPAL) instanceof AgentPrincipal p) {
            return p;
        }
        throw new IllegalStateException("工具上下文缺少调用主体");
    }

    private static AgentInvocation invocation(ToolContext context) {
        if (context != null && context.getContext().get(ToolContextKeys.INVOCATION) instanceof AgentInvocation i) {
            return i;
        }
        throw new IllegalStateException("工具上下文缺少调用信息");
    }

    /** 启动期校验 schema 是合法 JSON，避免把坏 schema 发给模型。 */
    private void validateCatalog() {
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            try {
                JSON.parseObject(spec.inputSchema());
            } catch (Exception e) {
                throw new IllegalStateException("工具 " + spec.name() + " 的 inputSchema 不是合法 JSON", e);
            }
        }
    }
}
