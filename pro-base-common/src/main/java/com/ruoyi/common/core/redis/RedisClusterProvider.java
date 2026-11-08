package com.ruoyi.common.core.redis;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import redis.clients.jedis.JedisCluster;

import javax.annotation.PreDestroy;

/**
 * JedisCluster 单例提供者。
 *
 * <p>JedisCluster 内部持有每个节点的连接池，属于线程安全且应长期复用的重量级客户端。
 * 本类采用懒加载：首次使用时才创建，避免应用启动时因外部 Redis 集群不可达而启动失败；
 * 容器关闭时统一 close，避免每次调用新建实例造成连接/句柄泄漏。</p>
 */
@Slf4j
@Component
public class RedisClusterProvider {

    private final RedisSourceFactory redisSourceFactory;

    private final RedisConfig redisConfig;

    private volatile JedisCluster jedisCluster;

    public RedisClusterProvider(RedisSourceFactory redisSourceFactory, RedisConfig redisConfig) {
        this.redisSourceFactory = redisSourceFactory;
        this.redisConfig = redisConfig;
    }

    /**
     * 获取共享的 JedisCluster 实例（线程安全，双重检查懒加载）。
     */
    public JedisCluster getCluster() {
        JedisCluster local = jedisCluster;
        if (local == null) {
            synchronized (this) {
                local = jedisCluster;
                if (local == null) {
                    local = redisSourceFactory.createSource(redisConfig);
                    jedisCluster = local;
                }
            }
        }
        return local;
    }

    @PreDestroy
    public void close() {
        JedisCluster local = jedisCluster;
        if (local != null) {
            try {
                local.close();
                log.info("JedisCluster 已关闭");
            } catch (Exception e) {
                log.warn("关闭 JedisCluster 异常", e);
            }
            jedisCluster = null;
        }
    }
}
