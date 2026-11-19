package com.ruoyi.base.agent.springai;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentAuditLogger;
import com.ruoyi.base.agent.core.AgentEvent;
import com.ruoyi.base.agent.core.AgentInvocation;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.PromptLibrary;
import com.ruoyi.base.agent.tools.AgentToolService;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.MessageType;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.ObjectProvider;
import reactor.core.publisher.Flux;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SpringAiAgentOrchestratorTest {

    @Test
    void streamsTextAndExecutesToolLoop() {
        AgentToolService toolService = mock(AgentToolService.class);
        when(toolService.searchKnowledge(any(), any())).thenReturn(Map.of("ok", true, "count", 1,
                "items", List.of(Map.of("title", "车牌", "content", "plate_norm 是归一化车牌"))));

        @SuppressWarnings("unchecked")
        ObjectProvider<MeterRegistry> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(null);
        AgentMetrics metrics = new AgentMetrics(provider);
        AgentAuditLogger audit = new AgentAuditLogger(new AgentProperties());
        AgentProperties props = new AgentProperties();
        SpringAiToolCallbacks callbacks = new SpringAiToolCallbacks(toolService, metrics, audit, props);

        AgentProperties properties = new AgentProperties();
        properties.setMaxIters(4);
        PromptLibrary prompts = new PromptLibrary(properties);
        prompts.load();

        AgentSessionStore sessionStore = mock(AgentSessionStore.class);
        ChatClient chatClient = ChatClient.builder(new FakeToolCallingModel()).build();
        SpringAiAgentOrchestrator orchestrator = new SpringAiAgentOrchestrator(
                chatClient, null, callbacks, prompts, sessionStore, properties);

        AgentInvocation invocation = AgentInvocation.builder()
                .requestId("req-test")
                .principal(new AgentPrincipal("t1", "u1", Set.of("ops"), true))
                .sessionId("s1")
                .message("plate_norm 是什么")
                .startedAt(System.currentTimeMillis())
                .build();

        List<AgentEvent> events = orchestrator.stream(invocation)
                .collectList()
                .block(Duration.ofSeconds(15));

        assertTrue(events != null && !events.isEmpty());
        assertTrue(events.stream().anyMatch(e -> e.getType().equals(AgentEvent.TOOL_CALL)));
        assertTrue(events.stream().anyMatch(e -> e.getType().equals(AgentEvent.TOOL_RESULT)));
        assertTrue(events.stream().anyMatch(e -> e.getType().equals(AgentEvent.DELTA)));
        assertTrue(events.stream().anyMatch(e -> e.getType().equals(AgentEvent.DONE)));
        String answer = events.stream().filter(e -> e.getType().equals(AgentEvent.DELTA))
                .map(e -> String.valueOf(e.getPayload().get("text")))
                .reduce("", String::concat);
        assertTrue(answer.contains("归一化车牌"), "answer=" + answer);
        org.mockito.Mockito.verify(sessionStore, org.mockito.Mockito.times(2))
                .append(any(), anyString(), any());
    }

    /**
     * 第一次返回 tool call，收到 ToolResponseMessage 后返回最终文本。
     */
    private static final class FakeToolCallingModel implements ChatModel {

        private final AtomicInteger calls = new AtomicInteger();

        @Override
        public ChatOptions getOptions() {
            return OpenAiChatOptions.builder().build();
        }

        @Override
        public ChatResponse call(Prompt prompt) {
            return next(prompt);
        }

        @Override
        public Flux<ChatResponse> stream(Prompt prompt) {
            return Flux.just(next(prompt));
        }

        private ChatResponse next(Prompt prompt) {
            boolean hasToolResponse = prompt.getInstructions().stream()
                    .anyMatch(m -> m.getMessageType() == MessageType.TOOL);
            if (!hasToolResponse && calls.getAndIncrement() == 0) {
                AssistantMessage message = AssistantMessage.builder()
                        .content("")
                        .toolCalls(List.of(new AssistantMessage.ToolCall(
                                "call-1", "function", "search_knowledge", "{\"query\":\"plate_norm\"}")))
                        .build();
                return new ChatResponse(List.of(new Generation(message)));
            }
            return new ChatResponse(List.of(new Generation(new AssistantMessage("plate_norm 是归一化车牌"))));
        }
    }
}
