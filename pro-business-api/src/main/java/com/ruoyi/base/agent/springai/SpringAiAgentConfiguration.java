package com.ruoyi.base.agent.springai;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.PromptLibrary;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;

/**
 * Spring AI 分支装配。
 *
 * <p>仅在 {@code traffic.agent.enabled=true} 时创建模型客户端；缺少 api-key/base-url 时
 * 启动失败并给出明确提示（fail-fast），避免“看似开启、实际每次请求 500”。</p>
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "traffic.agent", name = "enabled", havingValue = "true")
public class SpringAiAgentConfiguration {

    @Bean
    public ChatMemory agentChatMemory(StringRedisTemplate redisTemplate, AgentProperties properties) {
        return new RedisChatMemory(redisTemplate, properties);
    }

    @Bean
    public ChatModel agentChatModel(AgentProperties properties) {
        if (properties.getApiKey() == null || properties.getApiKey().isBlank()) {
            throw new IllegalStateException(
                    "traffic.agent.enabled=true 但未配置 traffic.agent.api-key（请用环境变量注入，勿写入仓库）");
        }
        if (properties.getBaseUrl() == null || properties.getBaseUrl().isBlank()) {
            throw new IllegalStateException("traffic.agent.enabled=true 但未配置 traffic.agent.base-url");
        }
        OpenAiChatOptions options = OpenAiChatOptions.builder()
                .baseUrl(properties.getBaseUrl())
                .apiKey(properties.getApiKey())
                .model(properties.getModel())
                .temperature(properties.getTemperature())
                .maxCompletionTokens(properties.getMaxOutputTokens())
                .timeout(properties.getModelTimeout())
                .maxRetries(2)
                .build();
        return OpenAiChatModel.builder().options(options).build();
    }

    @Bean
    public ChatClient agentChatClient(ChatModel agentChatModel, ChatMemory agentChatMemory) {
        return ChatClient.builder(agentChatModel)
                .defaultAdvisors(MessageChatMemoryAdvisor.builder(agentChatMemory).build())
                .build();
    }

    @Bean
    public AgentOrchestrator agentOrchestrator(ChatClient agentChatClient,
                                               ChatMemory agentChatMemory,
                                               SpringAiToolCallbacks toolCallbacks,
                                               PromptLibrary promptLibrary,
                                               AgentSessionStore sessionStore,
                                               AgentProperties properties) {
        return new SpringAiAgentOrchestrator(agentChatClient, agentChatMemory, toolCallbacks,
                promptLibrary, sessionStore, properties);
    }
}
