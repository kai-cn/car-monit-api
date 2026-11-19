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
 * 把框架无关的工具目录装配成 Spring AI {@link ToolCallback} 列表。
 *
 * <h2>它解决的问题：框架适配</h2>
 * <p>业务逻辑（查什么、怎么查、怎么脱敏）写在 {@link AgentToolService}，与框架无关；
 * 但每个框架要求工具的"形状"不同：Spring AI 要 {@code ToolCallback}（能给出 ToolDefinition +
 * 接收 JSON 字符串），AgentScope 要 {@code AgentTool}（返回 {@code Mono<ToolResultBlock>}）。
 * 本类就是 Spring AI 侧的"插头转换器"：目录 → 回调列表，并在外面包一层
 * {@link ObservableToolCallback} 统一发事件、记审计、做预算与超时。</p>
 *
 * <p>为什么用循环而非 {@code @Tool} 注解：注解方式需要在编译期固定方法签名，每个工具一个方法；
 * 而我们的工具是"目录驱动"的（7 个工具、同一套 JSON 入参），用 {@link JsonToolCallback}
 * 手写 schema 可以做到"加一个工具只改目录"，两分支还能共用同一份目录。</p>
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

    /**
     * 按工具名分发到具体业务方法。
     *
     * <p>注意两点：</p>
     * <ol>
     *   <li><b>principal 来自 toolContext，不来自 args</b>——模型只能决定参数，不能决定身份；</li>
     *   <li>所有分支返回 {@code Map} 而非抛异常：工具失败要以"结构化结果"回到模型，
     *       让模型有机会换参数重试或向用户解释，而不是整条流挂掉。</li>
     * </ol>
     *
     * <p>【Java 14+ switch 表达式】{@code Map<String,Object> result = switch (name) { case X -> ... }}：
     * ① 是<b>表达式</b>，直接产出一个值，不必先声明变量再在每个分支赋值；
     * ② 用 {@code ->} 不会"贯穿"（不需要 break，漏写 break 的经典 bug 消失）；
     * ③ 编译器检查穷尽性（这里因有 default 而总是穷尽）。
     * 注意 {@code case AgentToolCatalog.QUERY_TRAFFIC} 用的是<b>常量</b>，所以能当 case 标签。</p>
     */
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

    /**
     * 从工具上下文取调用主体。
     *
     * <p>【Java 16+ instanceof 模式匹配】{@code x instanceof AgentPrincipal p} 在判断通过的同时
     * 把 {@code x} 绑定到新变量 {@code p}，省掉一次显式强转。取不到就抛异常——
     * 这属于"装配错误"，宁可 500 也不能拿匿名身份去查数据。</p>
     */
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
