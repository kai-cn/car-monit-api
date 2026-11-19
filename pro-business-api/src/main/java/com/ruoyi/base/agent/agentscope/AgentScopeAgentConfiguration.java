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
     * <p><b>连接是否懒建立</b>：{@code JedisPooled} 构造时不握手（Redis 短暂不可用不会阻断启动，
     * 失败发生在第一次对话）；{@code JedisCluster} 构造时就要拉取 slot 缓存，因此集群模式下
     * Redis 不可用会**启动失败**——这是刻意的：集群配置错误应当尽早暴露，而不是跑到线上才发现。</p>
     *
     * <p><b>只支持两种拓扑</b>：{@code host/port}（单机）与 {@code cluster.nodes}（集群）。
     * {@code spring.data.redis.url} / {@code sentinel} / {@code masterreplica} 一律 fail-fast：
     * Spring 自己的连接工厂认得这些写法，若这里静默忽略，会出现"订单走哨兵、Agent 状态走 127.0.0.1"
     * 的双地址分裂，排查成本极高。</p>
     *
     * <p>集群模式该构造器不支持密码；集群+密码请改用
     * {@code JedisCluster(HostAndPort, JedisClientConfig, int, GenericObjectPoolConfig)}，
     * 本方法会显式报错而不是带着空密码去连。</p>
     */
    @Bean(destroyMethod = "close")
    public UnifiedJedis agentScopeJedis(DataRedisProperties redis) {
        Duration timeout = redis.getTimeout() == null ? Duration.ofSeconds(3) : redis.getTimeout();
        int timeoutMs = (int) Math.max(500, timeout.toMillis());

        // ---- 拓扑兼容性检查：不支持就立刻失败，绝不"部分生效" ----
        if (redis.getUrl() != null && !redis.getUrl().isBlank()) {
            throw new IllegalStateException("traffic.agent 暂不支持 spring.data.redis.url（"
                    + maskUrl(redis.getUrl()) + "），请改用 spring.data.redis.host/port 或 cluster.nodes");
        }
        if (redis.getSentinel() != null && redis.getSentinel().getNodes() != null
                && !redis.getSentinel().getNodes().isEmpty()) {
            throw new IllegalStateException("traffic.agent 暂不支持 Redis Sentinel，请改用 cluster.nodes 或单机");
        }
        if (redis.getMasterreplica() != null && redis.getMasterreplica().getNodes() != null
                && !redis.getMasterreplica().getNodes().isEmpty()) {
            throw new IllegalStateException("traffic.agent 暂不支持 Redis 主从（masterreplica），请改用 cluster.nodes 或单机");
        }

        DefaultJedisClientConfig config = DefaultJedisClientConfig.builder()
                .database(Math.max(0, redis.getDatabase()))
                .connectionTimeoutMillis(timeoutMs)
                .socketTimeoutMillis(timeoutMs)
                .user(redis.getUsername())
                .password(redis.getPassword())
                .clientName("agent-scope-state")
                .build();

        List<String> clusterNodes = redis.getCluster() == null ? null : redis.getCluster().getNodes();
        if (clusterNodes != null && !clusterNodes.isEmpty()) {
            if (redis.getPassword() != null && !redis.getPassword().isBlank()) {
                throw new IllegalStateException("traffic.agent 的集群模式暂不支持密码认证；"
                        + "请使用单机 + 密码，或改造为 JedisCluster(HostAndPort, JedisClientConfig, ...)");
            }
            Set<HostAndPort> nodes = clusterNodes.stream()
                    .map(String::trim)
                    .filter(node -> !node.isEmpty())
                    .map(AgentScopeAgentConfiguration::parseNode)
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
     * 解析 {@code host:port}，兼容 IPv6 的 {@code [::1]:6379}。
     *
     * <p>用 {@code lastIndexOf(':')} 而不是 {@code split(":")}：IPv6 地址本身含冒号，
     * 直接 split 会把地址切碎。解析失败时抛出<b>带原始值</b>的异常，避免运维面对一个
     * 光秃秃的 {@code NumberFormatException}。</p>
     */
    private static HostAndPort parseNode(String node) {
        int sep = node.startsWith("[") ? node.lastIndexOf("]:") + 1 : node.lastIndexOf(':');
        if (sep <= 0 || sep == node.length() - 1) {
            throw new IllegalStateException("非法的 Redis 节点地址（应为 host:port）：" + node);
        }
        String host = node.substring(0, sep);
        if (host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
        }
        try {
            return new HostAndPort(host, Integer.parseInt(node.substring(sep + 1)));
        } catch (NumberFormatException e) {
            throw new IllegalStateException("非法的 Redis 节点端口：" + node, e);
        }
    }

    /** 打码 URL 中的密码，避免异常信息把凭据写进日志。 */
    private static String maskUrl(String url) {
        return url.replaceAll("://([^:@/]+):[^@/]+@", "://$1:***@");
    }

    /**
     * 官方 Redis 状态存储：{@code (userId, sessionId, key)} → Redis。
     *
     * <p><b>keyPrefix 必须以冒号结尾</b>：官方默认值是 {@code "agentscope:session:"}，
     * 布局是"前缀 + userId 直接拼接"，前缀里不带分隔符就会粘成一个词。
     * 这里传 {@code agent:as:}，最终 Key 形如
     * {@code agent:as:{tenant:user}/{sessionId}:{key}}（V0 布局，user 与 session 之间是 {@code /}），
     * 另有 {@code ...:{key}:list}（列表状态）与 {@code ...:_keys}（该会话写过的 key 索引）。
     * 少写这个冒号会得到 {@code agent:ast1:u1/...}——功能上能用，但按 {@code agent:as:*}
     * 做的运维清理与监控全部匹配不到（本项目真踩过）。</p>
     *
     * <p><b>注意：官方实现不设置 TTL</b>（反编译确认全程无 EXPIRE/PEXPIRE），
     * 状态会一直保留到被显式删除。生产必须配套清理策略：
     * 用户主动 {@code DELETE /sessions/{id}}、以及运维侧的
     * {@code scripts/agent/cleanup-agent-state.sh}（按 key 空闲时间清理）+
     * Redis {@code maxmemory-policy}。不要误以为 {@code traffic.agent.session-ttl}
     * 会作用到这里——它只约束 UI 历史与限流窗口。</p>
     *
     * <p>{@code destroyMethod = ""}：{@link RedisAgentStateStore#close()} 会关闭传入的 jedis，
     * 而该 jedis 是共享 Bean（由 {@link #agentScopeJedis} 管理）。让 Spring 各关各的，
     * 避免"状态存储关闭时把连接池也关了、其它组件再用就报 pool destroyed"。</p>
     */
    @Bean(destroyMethod = "")
    public AgentStateStore agentStateStore(UnifiedJedis agentScopeJedis, AgentProperties properties) {
        return RedisAgentStateStore.builder()
                .jedisClient(agentScopeJedis)
                // 结尾的 ':' 是布局的一部分（官方默认值 agentscope:session: 同理），不能省
                .keyPrefix(properties.getKeyPrefix() + ":as:")
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
