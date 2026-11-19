package com.ruoyi.common.core.redis;

import java.io.Serializable;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import redis.clients.jedis.HostAndPort;
import redis.clients.jedis.JedisCluster;

@Service
public class RedisSourceFactory implements Serializable {


    private static final long serialVersionUID = 1L;

    private static final Logger logger = LoggerFactory.getLogger(RedisSourceFactory.class);

    /**
     * 按节点串缓存 {@link JedisCluster}。
     *
     * <p><b>为什么必须缓存</b>：jedis 7 的 {@code JedisCluster} 自带连接池与后台线程，
     * 每次 {@code new} 都是"新建一整套资源"。调用方（如轨迹同步）是定时任务，
     * 每次执行都 new 一个且不关闭，等于每分钟泄漏一个连接池，几天后 Redis 侧连接数被打满。</p>
     *
     * <p>以 {@code cluster.nodes} 的原始字符串为 key：配置不变则复用同一实例；
     * 配置变更会得到新实例（旧实例由 {@link #destroy()} 在应用关闭时统一关闭）。</p>
     */
    private final Map<String, JedisCluster> clusterCache = new ConcurrentHashMap<>();

    public JedisCluster createSource(RedisConfig redisConfig) {
        if (redisConfig == null || redisConfig.getClusterNodes() == null || redisConfig.getClusterNodes().isEmpty()) {
            logger.error("Redis cluster node address 'cluster.nodes' is not configured.");
            throw new IllegalStateException("Redis cluster node address 'cluster.nodes' is not configured.");
        }

        Set<HostAndPort> jedisClusterNodes = new HashSet<HostAndPort>();
        String nodes = redisConfig.getClusterNodes();

        for (String node : nodes.split(",")) {
            String[] hp = node.trim().split(":");
            if (hp.length == 2) {
                try {
                    jedisClusterNodes.add(new HostAndPort(hp[0], Integer.parseInt(hp[1])));
                    logger.info("Added Redis node: " + node);
                } catch (NumberFormatException e) {
                    logger.warn("Invalid port number for Redis node: " + node + ". This node will be skipped.", e);
                }
            } else {
                logger.warn("Invalid node format (expected host:port): " + node + ". This node will be skipped.");
            }
        }

        return clusterCache.computeIfAbsent(nodes.trim(), key -> {
            try {
                JedisCluster jedisCluster = new JedisCluster(jedisClusterNodes);
                logger.info("JedisCluster created successfully with nodes: " + jedisClusterNodes);
                return jedisCluster;
            } catch (Exception e) {
                logger.error("Failed to create JedisCluster", e);
                throw e;
            }
        });
    }

    /** 应用关闭时释放所有缓存的集群连接池（jedis 7 每个实例都有独立线程与连接）。 */
    @PreDestroy
    public void destroy() {
        clusterCache.forEach((nodes, cluster) -> {
            try {
                cluster.close();
            } catch (Exception e) {
                logger.warn("关闭 JedisCluster 失败 nodes=" + nodes, e);
            }
        });
        clusterCache.clear();
    }
}
