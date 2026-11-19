package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.PromptLibrary;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import io.agentscope.core.ReActAgent;
import io.agentscope.core.model.ExecutionConfig;
import io.agentscope.core.model.GenerateOptions;
import io.agentscope.extensions.model.openai.OpenAIChatModel;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * AgentScope 分支装配。
 *
 * <p>仅在 {@code traffic.agent.enabled=true} 时创建模型与 Agent；缺少 api-key/base-url 时
 * 启动即失败并给出明确提示（fail-fast），避免“看似开启、每次请求 500”。</p>
 *
 * <p>Bean 生命周期：{@link ReActAgent} 是<b>单例</b>，按 {@code (userId, sessionId)} 槽位隔离会话，
 * 不同会话可并行、同会话串行（框架内 {@code callSerializationKey} 保证），因此不需要
 * “每请求 new 一个 Agent”。</p>
 */
@Slf4j
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "traffic.agent", name = "enabled", havingValue = "true")
public class AgentScopeAgentConfiguration {

    @Bean
    public AgentScopeStateStore agentScopeStateStore(StringRedisTemplate redisTemplate,
                                                     AgentProperties properties) {
        return new AgentScopeStateStore(redisTemplate, properties);
    }

    @Bean
    public ReActAgent agentScopeReActAgent(AgentScopeTools tools,
                                           AgentScopeStateStore stateStore,
                                           PromptLibrary promptLibrary,
                                           AgentProperties properties) {
        if (properties.getApiKey() == null || properties.getApiKey().isBlank()) {
            throw new IllegalStateException(
                    "traffic.agent.enabled=true 但未配置 traffic.agent.api-key（请用环境变量注入，勿写入仓库）");
        }
        if (properties.getBaseUrl() == null || properties.getBaseUrl().isBlank()) {
            throw new IllegalStateException("traffic.agent.enabled=true 但未配置 traffic.agent.base-url");
        }

        GenerateOptions generateOptions = GenerateOptions.builder()
                .apiKey(properties.getApiKey())
                .baseUrl(properties.getBaseUrl())
                .modelName(properties.getModel())
                .stream(true)
                .temperature(properties.getTemperature())
                .maxCompletionTokens(properties.getMaxOutputTokens())
                .executionConfig(ExecutionConfig.builder()
                        .timeout(properties.getModelTimeout())
                        .maxAttempts(2)
                        .build())
                .build();

        OpenAIChatModel model = OpenAIChatModel.builder()
                .apiKey(properties.getApiKey())
                .baseUrl(properties.getBaseUrl())
                .modelName(properties.getModel())
                .stream(true)
                .generateOptions(generateOptions)
                .build();

        ReActAgent agent = ReActAgent.builder()
                .name("traffic-data-agent")
                .description("高速公路联网收费与监控数据问答助手：查流水、回放轨迹、看指标、查数据质量")
                .sysPrompt(promptLibrary.template())
                .model(model)
                .toolkit(tools.toolkit())
                .maxIters(properties.getMaxIters())
                .stateStore(stateStore)
                .defaultSessionId("default")
                // 逐请求渲染 {{tenantId}}/{{roles}} 等占位符；提示词模板仍只有一份
                .middleware(new PerRequestPromptMiddleware(promptLibrary))
                // 限制回灌给模型的会话历史，控制 token 成本并规避上下文超限
                .middleware(new HistoryWindowMiddleware(properties.getHistoryWindow()))
                .modelExecutionConfig(ExecutionConfig.builder()
                        .timeout(properties.getModelTimeout())
                        .maxAttempts(2)
                        .build())
                .toolExecutionConfig(ExecutionConfig.builder()
                        .timeout(properties.getToolTimeout())
                        .maxAttempts(1)
                        .build())
                .build();

        verifyToolContract(agent, tools);
        log.info("[AgentScope] ReActAgent 就绪 model={} maxIters={} tools={}",
                properties.getModel(), properties.getMaxIters(), agent.getToolkit().getToolNames());
        return agent;
    }

    @Bean
    public AgentOrchestrator agentOrchestrator(ReActAgent agentScopeReActAgent,
                                               AgentScopeTools tools,
                                               AgentScopeStateStore stateStore,
                                               AgentSessionStore sessionStore,
                                               AgentProperties properties) {
        return new AgentScopeAgentOrchestrator(agentScopeReActAgent, tools, stateStore,
                sessionStore, properties);
    }

    /**
     * 启动期契约校验：Agent 实际持有的工具集必须与目录完全一致。
     * 少了 → 模型看不见能力；多了 → 文档/权限矩阵漏登记。两种情况都必须在启动期暴露。
     */
    private static void verifyToolContract(ReActAgent agent, AgentScopeTools tools) {
        Set<String> expected = new LinkedHashSet<>();
        for (AgentToolCatalog.ToolSpec spec : AgentToolCatalog.specs()) {
            expected.add(spec.name());
        }
        Set<String> actual = agent.getToolkit().getToolNames();
        Set<String> missing = new LinkedHashSet<>(expected);
        missing.removeAll(actual);
        Set<String> unexpected = new LinkedHashSet<>(actual);
        unexpected.removeAll(expected);
        if (!missing.isEmpty() || !unexpected.isEmpty()) {
            throw new IllegalStateException("AgentScope 工具注册与目录不一致 missing=" + missing
                    + " unexpected=" + unexpected + "（tools.registered=" + tools.registeredTools() + "）");
        }
    }
}
