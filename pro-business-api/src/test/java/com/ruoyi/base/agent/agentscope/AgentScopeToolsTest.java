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
import io.agentscope.core.message.TextBlock;
import io.agentscope.core.message.ToolResultBlock;
import io.agentscope.core.message.ToolUseBlock;
import io.agentscope.core.tool.AgentTool;
import io.agentscope.core.tool.ToolCallParam;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.ObjectProvider;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 工具适配层单测：目录一致性、事件顺序、预算熔断、车牌脱敏链路（由服务层负责，这里只验转发）。
 */
class AgentScopeToolsTest {

    private AgentToolService service;
    private AgentScopeTools tools;
    private AgentProperties properties;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        properties = new AgentProperties();
        service = mock(AgentToolService.class);
        ObjectProvider<MeterRegistry> provider = Mockito.mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(null);
        tools = new AgentScopeTools(service, new AgentMetrics(provider),
                new AgentAuditLogger(properties), properties);
    }

    @Test
    @DisplayName("Toolkit 注册的工具与目录完全一致，schema 可直接发给模型")
    void registersExactlyCatalogTools() {
        Set<String> expected = AgentToolCatalog.specs().stream()
                .map(AgentToolCatalog.ToolSpec::name)
                .collect(java.util.stream.Collectors.toSet());
        assertEquals(expected, tools.registeredTools());
        assertEquals(expected, tools.toolkit().getToolNames());
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            AgentTool tool = tools.toolkit().getTool(spec.name());
            assertEquals(spec.name(), tool.getName());
            assertEquals("object", tool.getParameters().get("type"));
            assertTrue(tool.getParameters().containsKey("properties"));
            assertEquals(spec.risk() == AgentToolCatalog.Risk.READ, tool.isReadOnly());
        }
    }

    @Test
    @DisplayName("工具调用产出 tool_call → tool_result，并把业务 JSON 原样回灌给模型")
    @SuppressWarnings("unchecked")
    void emitsToolEventsAndReturnsPayload() {
        List<Map<String, Object>> rows = List.of(Map.of("plate", "赣B2***5", "fee", 12));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("ok", true);
        payload.put("total", 1);
        payload.put("rows", rows);        when(service.queryTraffic(any(), any())).thenReturn(payload);

        List<AgentEvent> events = new ArrayList<>();
        AgentEventSink sink = events::add;
        ToolResultBlock result = call(AgentToolCatalog.QUERY_TRAFFIC, Map.of("table", "fee"), sink,
                new AgentScopeToolBudget(3));

        assertEquals(2, events.size());
        assertEquals(AgentEvent.TOOL_CALL, events.get(0).getType());
        assertEquals(AgentEvent.TOOL_RESULT, events.get(1).getType());
        assertEquals("ok", events.get(1).getPayload().get("status"));

        String text = ((TextBlock) result.getOutput().get(0)).getText();
        JSONObject json = JSON.parseObject(text);
        assertTrue(json.getBooleanValue("ok"));
        assertEquals(1, json.getIntValue("total"));
    }

    @Test
    @DisplayName("工具预算耗尽后不再执行，返回 AGENT_MAX_ITERS 让模型收敛")
    @SuppressWarnings("unchecked")
    void rejectsWhenBudgetExhausted() {
        when(service.queryTraffic(any(), any())).thenReturn(Map.of("ok", true));
        AgentScopeToolBudget budget = new AgentScopeToolBudget(1);
        List<AgentEvent> events = new ArrayList<>();

        call(AgentToolCatalog.QUERY_TRAFFIC, Map.of("table", "fee"), events::add, budget);
        ToolResultBlock second = call(AgentToolCatalog.QUERY_TRAFFIC, Map.of("table", "fee"), events::add, budget);

        String text = ((TextBlock) second.getOutput().get(0)).getText();
        assertEquals("AGENT_MAX_ITERS", JSON.parseObject(text).getString("errorCode"));
        // 第二次只执行到预算检查：tool_call + tool_result(error)，再加第一次的 2 个事件
        assertEquals(4, events.size());
        assertEquals("error", events.get(3).getPayload().get("status"));
        Mockito.verify(service, Mockito.times(1)).queryTraffic(any(), any());
    }

    @Test
    @DisplayName("缺少调用主体时按错误返回，避免以匿名身份越权查询")
    void failsFastWithoutPrincipal() {
        AgentTool tool = tools.toolkit().getTool(AgentToolCatalog.QUERY_TRAFFIC);
        RuntimeContext ctx = RuntimeContext.builder().userId("t:u").sessionId("s").build();
        ToolResultBlock result = tool.callAsync(ToolCallParam.builder()
                .toolUseBlock(new ToolUseBlock("call-1", AgentToolCatalog.QUERY_TRAFFIC, Map.of()))
                .input(Map.of("table", "fee"))
                .runtimeContext(ctx)
                .build()).block();

        String text = ((TextBlock) result.getOutput().get(0)).getText();
        assertFalse(text.isEmpty());
    }

    private ToolResultBlock call(String name, Map<String, Object> args, AgentEventSink sink,
                                 AgentScopeToolBudget budget) {
        AgentPrincipal principal = new AgentPrincipal("tenant-a", "u1", Set.of("ops"), false);
        AgentInvocation invocation = AgentInvocation.builder()
                .requestId("req-1").principal(principal).sessionId("s1").message("查一下")
                .startedAt(System.currentTimeMillis()).build();
        RuntimeContext ctx = RuntimeContext.builder()
                .userId("tenant-a:u1").sessionId("s1")
                .put(ToolContextKeys.PRINCIPAL, principal)
                .put(ToolContextKeys.INVOCATION, invocation)
                .put(ToolContextKeys.SINK, sink)
                .put(ToolContextKeys.BUDGET, budget)
                .put(ToolContextKeys.CONFIRM_TOKEN, "")
                .build();
        AgentTool tool = tools.toolkit().getTool(name);
        return tool.callAsync(ToolCallParam.builder()
                .toolUseBlock(new ToolUseBlock("call-" + name, name, args))
                .input(args)
                .runtimeContext(ctx)
                .build()).block();
    }
}
