package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.PromptLibrary;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import io.agentscope.core.ReActAgent;
import io.agentscope.core.model.ExecutionConfig;
import io.agentscope.core.model.GenerateOptions;
import io.agentscope.core.state.AgentStateStore;
import io.agentscope.extensions.model.openai.OpenAIChatModel;
import io.agentscope.extensions.redis.state.RedisAgentStateStore;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.data.redis.autoconfigure.DataRedisProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import redis.clients.jedis.DefaultJedisClientConfig;
import redis.clients.jedis.HostAndPort;
import redis.clients.jedis.JedisCluster;
import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.UnifiedJedis;

import java.time.Duration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

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

    /**
     * Jedis 客户端（AgentScope 状态的底层连接）。
     *
     * <p>为什么单独建一个 Jedis 而不是复用 Spring Data Redis 的 Lettuce：
     * {@link RedisAgentStateStore} 的 Jedis 适配器是<b>按 jedis 7.x 编译</b>的，
     * 用同一大版本能彻底避免二进制不兼容（{@code NoSuchMethodError}）；而 Spring Data Redis
     * 的 native client 属于连接工厂内部资源，交给第三方组件管理生命周期容易互相关闭。</p>
     *
     * <p>连接是<b>懒建立</b>的：{@code new JedisPooled} 不会在启动时握手，因此 Redis 短暂不可用
     * 不会阻断应用启动；真正失败会发生在第一次对话，并按 {@code error} 事件返回。</p>
     *
     * <p>集群：只认 Spring Boot 标准配置 {@code spring.data.redis.cluster.nodes}，
     * 不读业务侧的 {@code rediscluster.clusterNodes}（那是字典同步用的集群地址，
     * 默认值指向公网实例，会让所有环境都误走集群分支）。
     * 集群模式该构造器不支持密码；集群+密码请改用
     * {@code JedisCluster(HostAndPort, JedisClientConfig, int, GenericObjectPoolConfig)}。</p>
     */
    @Bean(destroyMethod = "close")
    public UnifiedJedis agentScopeJedis(DataRedisProperties redis) {
        Duration timeout = redis.getTimeout() == null ? Duration.ofSeconds(3) : redis.getTimeout();
        int timeoutMs = (int) Math.max(500, timeout.toMillis());
        DefaultJedisClientConfig config = DefaultJedisClientConfig.builder()
                .database(Math.max(0, redis.getDatabase()))
                .connectionTimeoutMillis(timeoutMs)
                .socketTimeoutMillis(timeoutMs)
                .user(redis.getUsername())
                .password(redis.getPassword())
                .clientName("agent-scope-state")
                .build();

        List<String> clusterNodes = redis.getCluster() == null ? List.of() : redis.getCluster().getNodes();
        if (clusterNodes != null && !clusterNodes.isEmpty()) {
            Set<HostAndPort> nodes = clusterNodes.stream()
                    .map(String::trim)
                    .filter(node -> node.contains(":"))
                    .map(node -> new HostAndPort(node.substring(0, node.lastIndexOf(':')),
                            Integer.parseInt(node.substring(node.lastIndexOf(':') + 1))))
                    .collect(Collectors.toCollection(LinkedHashSet::new));
            log.info("[AgentScope] 状态存储使用 Redis 集群 nodes={}", nodes);
            return new JedisCluster(nodes, timeoutMs);
        }
        String host = redis.getHost() == null || redis.getHost().isBlank() ? "127.0.0.1" : redis.getHost();
        int port = redis.getPort() <= 0 ? 6379 : redis.getPort();
        log.info("[AgentScope] 状态存储使用 Redis 单机 {}:{} db={}", host, port, config.getDatabase());
        return new JedisPooled(new HostAndPort(host, port), config);
    }

    /**
     * 官方 Redis 状态存储：{@code (userId, sessionId, key)} → Redis。
     *
     * <p>{@code keyPrefix} 与工程的 {@code agent.key-prefix} 对齐（默认 {@code agent:as}），
     * TTL 由 {@code RedisAgentStateStore} 内部按写入刷新；本 Bean 不负责过期策略。</p>
     *
     * <p>{@code destroyMethod = ""}：{@link RedisAgentStateStore#close()} 会关闭传入的 jedis，
     * 而该 jedis 是共享 Bean（由 {@link #agentScopeJedis} 管理）。让 Spring 各关各的，
     * 避免"状态存储关闭时把连接池也关了、其它组件再用就报 pool destroyed"。</p>
     */
    @Bean(destroyMethod = "")
    public AgentStateStore agentStateStore(UnifiedJedis agentScopeJedis, AgentProperties properties) {
        return RedisAgentStateStore.builder()
                .jedisClient(agentScopeJedis)
                .keyPrefix(properties.getKeyPrefix() + ":as")
                .build();
    }

    @Bean
    public ReActAgent agentScopeReActAgent(AgentScopeTools tools,
                                           AgentStateStore stateStore,
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
                                               AgentStateStore stateStore,
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
