package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentSessionStore;
import io.agentscope.core.ReActAgent;
import io.agentscope.core.state.AgentStateStore;
import io.agentscope.core.event.AgentResultEvent;
import io.agentscope.core.event.ExceedMaxItersEvent;
import io.agentscope.core.event.ModelCallEndEvent;
import io.agentscope.core.event.TextBlockDeltaEvent;
import io.agentscope.core.message.AssistantMessage;
import io.agentscope.core.model.ChatUsage;
import io.agentscope.core.model.transport.HttpTransportException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 编排器单测：验证 AgentScope 事件到统一 SSE 契约的映射，不依赖真实模型。
 */
class AgentScopeAgentOrchestratorTest {

    private ReActAgent agent;
    private AgentScopeAgentOrchestrator orchestrator;

    @BeforeEach
    void setUp() {
        agent = mock(ReActAgent.class);
        AgentScopeTools tools = mock(AgentScopeTools.class);
        when(tools.registeredTools()).thenReturn(Set.of("query_traffic_records"));
        AgentSessionStore sessionStore = mock(AgentSessionStore.class);
        AgentStateStore stateStore = mock(AgentStateStore.class);
        AgentProperties properties = new AgentProperties();
        properties.setModel("qwen-plus");
        orchestrator = new AgentScopeAgentOrchestrator(agent, tools, stateStore, sessionStore, properties);
    }

    @Test
    @DisplayName("正常流：meta → delta* → usage → done(stop)，且 usage 多轮累加")
    void mapsHappyPath() {
        when(agent.streamEvents(anyString(), any())).thenReturn(Flux.just(
                new TextBlockDeltaEvent("r1", "b1", "该车"),
                new TextBlockDeltaEvent("r1", "b1", "共 3 条流水"),
                new ModelCallEndEvent("r1", new ChatUsage(120, 30, 0.2)),
                new ModelCallEndEvent("r1", new ChatUsage(200, 40, 0.3)),
                new AgentResultEvent(new AssistantMessage("该车共 3 条流水"))
        ));

        List<AgentEvent> events = orchestrator.stream(invocation()).collectList().block();

        assertNotNull(events);
        assertEquals(AgentEvent.META, events.get(0).getType());
        assertEquals("agentscope", events.get(0).getPayload().get("framework"));
        assertEquals("qwen-plus", events.get(0).getPayload().get("model"));
        assertEquals(2, events.stream().filter(e -> AgentEvent.DELTA.equals(e.getType())).count());
        AgentEvent usage = events.stream().filter(e -> AgentEvent.USAGE.equals(e.getType())).findFirst().orElseThrow();
        assertEquals(320L, usage.getPayload().get("promptTokens"));
        assertEquals(70L, usage.getPayload().get("completionTokens"));
        AgentEvent done = events.get(events.size() - 1);
        assertEquals(AgentEvent.DONE, done.getType());
        assertEquals("stop", done.getPayload().get("finishReason"));
    }

    @Test
    @DisplayName("达到最大迭代轮数不算错误：done.finishReason=max_iters 且保留兜底总结")
    void marksMaxIters() {
        when(agent.streamEvents(anyString(), any())).thenReturn(Flux.just(
                new TextBlockDeltaEvent("r1", "b1", "已根据已有数据总结"),
                new ExceedMaxItersEvent("r1", 6, 6)
        ));

        List<AgentEvent> events = orchestrator.stream(invocation()).collectList().block();

        assertNotNull(events);
        AgentEvent done = events.get(events.size() - 1);
        assertEquals(AgentEvent.DONE, done.getType());
        assertEquals("max_iters", done.getPayload().get("finishReason"));
        assertTrue(events.stream().noneMatch(e -> AgentEvent.ERROR.equals(e.getType())));
    }

    @Test
    @DisplayName("模型 429 映射为 AGENT_RATE_LIMITED，且以 error 事件收尾")
    void mapsRateLimitError() {
        when(agent.streamEvents(anyString(), any()))
                .thenReturn(Flux.error(new HttpTransportException("too many requests", 429, "{}")));

        List<AgentEvent> events = orchestrator.stream(invocation()).collectList().block();

        assertNotNull(events);
        AgentEvent error = events.get(events.size() - 1);
        assertEquals(AgentEvent.ERROR, error.getType());
        assertEquals(AgentErrorCode.AGENT_RATE_LIMITED.name(), error.getPayload().get("code"));
        assertEquals(true, error.getPayload().get("retryable"));
    }

    @Test
    @DisplayName("模型 401 映射为 AGENT_MODEL_ERROR，熔断/超时各自有稳定错误码")
    void mapsAuthAndTimeout() {
        assertEquals(AgentErrorCode.AGENT_MODEL_ERROR,
                AgentScopeAgentOrchestrator.classify(new HttpTransportException("unauthorized", 401, "{}")));
        assertEquals(AgentErrorCode.AGENT_CIRCUIT_OPEN,
                AgentScopeAgentOrchestrator.classify(new HttpTransportException("unavailable", 503, "{}")));
        assertEquals(AgentErrorCode.AGENT_MODEL_TIMEOUT,
                AgentScopeAgentOrchestrator.classify(new java.util.concurrent.TimeoutException("timeout")));
    }

    private AgentInvocation invocation() {
        AgentPrincipal principal = new AgentPrincipal("tenant-a", "u1", Set.of("ops"), false);
        return AgentInvocation.builder()
                .requestId("req-1")
                .principal(principal)
                .sessionId("s1")
                .message("赣B21E85 今天走了哪些门架")
                .startedAt(System.currentTimeMillis())
                .attributes(Map.of())
                .build();
    }
}
