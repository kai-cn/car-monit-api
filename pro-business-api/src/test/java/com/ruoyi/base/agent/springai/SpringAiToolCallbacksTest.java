package com.ruoyi.base.agent.springai;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.ToolContextKeys;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import com.ruoyi.base.agent.tools.AgentToolService;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.beans.factory.ObjectProvider;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SpringAiToolCallbacksTest {

    @Test
    void exposesAllCatalogTools() {
        SpringAiToolCallbacks callbacks = newCallbacks(mock(AgentToolService.class));
        Set<String> names = callbacks.registeredTools();
        assertEquals(AgentToolCatalog.specs().size(), names.size());
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            assertTrue(names.contains(spec.name()), "missing tool " + spec.name());
        }
    }

    @Test
    void invokesToolAndEmitsEvents() {
        AgentToolService service = mock(AgentToolService.class);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("total", 3);
        result.put("rows", List.of());
        when(service.queryTraffic(any(), any())).thenReturn(result);

        SpringAiToolCallbacks callbacks = newCallbacks(service);
        ToolCallback callback = callbacks.callbacks().stream()
                .filter(c -> c.getToolDefinition().name().equals(AgentToolCatalog.QUERY_TRAFFIC))
                .findFirst().orElseThrow();

        List<AgentEvent> events = new ArrayList<>();
        AgentInvocation invocation = AgentInvocation.builder()
                .requestId("req-1")
                .principal(new AgentPrincipal("t1", "u1", Set.of("ops"), true))
                .sessionId("s1")
                .message("查一下")
                .startedAt(System.currentTimeMillis())
                .build();
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put(ToolContextKeys.PRINCIPAL, invocation.getPrincipal());
        ctx.put(ToolContextKeys.INVOCATION, invocation);
        ctx.put(ToolContextKeys.SINK, (com.ruoyi.base.agent.core.AgentEventSink) events::add);
        ctx.put(ToolContextKeys.BUDGET, new ToolBudget(3));
        ctx.put(ToolContextKeys.CONFIRM_TOKEN, "");

        String output = callback.call("{\"table\":\"snapshot\",\"page_size\":5}", new ToolContext(ctx));

        assertNotNull(output);
        assertTrue(output.contains("\"ok\":true"));
        verify(service).queryTraffic(eq(invocation.getPrincipal()), any());
        assertEquals(2, events.size());
        assertEquals(AgentEvent.TOOL_CALL, events.get(0).getType());
        assertEquals(AgentEvent.TOOL_RESULT, events.get(1).getType());
        assertEquals("query_traffic_records", events.get(0).getPayload().get("name"));
    }

    @Test
    void budgetBlocksExtraCalls() {
        AgentToolService service = mock(AgentToolService.class);
        when(service.searchKnowledge(any(), any())).thenReturn(Map.of("ok", true, "count", 1));
        SpringAiToolCallbacks callbacks = newCallbacks(service);
        ToolCallback callback = callbacks.callbacks().stream()
                .filter(c -> c.getToolDefinition().name().equals(AgentToolCatalog.SEARCH_KNOWLEDGE))
                .findFirst().orElseThrow();

        AgentInvocation invocation = AgentInvocation.builder()
                .requestId("req-2")
                .principal(new AgentPrincipal("t1", "u1", Set.of("ops"), true))
                .sessionId("s1")
                .message("知识")
                .startedAt(System.currentTimeMillis())
                .build();
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put(ToolContextKeys.PRINCIPAL, invocation.getPrincipal());
        ctx.put(ToolContextKeys.INVOCATION, invocation);
        ctx.put(ToolContextKeys.SINK, (com.ruoyi.base.agent.core.AgentEventSink) e -> { });
        ctx.put(ToolContextKeys.BUDGET, new ToolBudget(1));
        ctx.put(ToolContextKeys.CONFIRM_TOKEN, "");

        String first = callback.call("{\"query\":\"plate_norm\"}", new ToolContext(ctx));
        assertTrue(first.contains("\"ok\":true"));
        String blocked = callback.call("{\"query\":\"plate_norm\"}", new ToolContext(ctx));
        assertFalse(blocked.contains("\"ok\":true"));
        assertTrue(blocked.contains("AGENT_MAX_ITERS"));
    }

    private SpringAiToolCallbacks newCallbacks(AgentToolService service) {
        @SuppressWarnings("unchecked")
        ObjectProvider<MeterRegistry> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(null);
        AgentMetrics metrics = new AgentMetrics(provider);
        AgentAuditLogger audit = new AgentAuditLogger(new AgentProperties());
        return new SpringAiToolCallbacks(service, metrics, audit, new AgentProperties());
    }
}
