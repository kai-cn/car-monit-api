package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 两级限流：用户 + 租户，按分钟固定窗口。
 *
 * <p>Redis INCR + EXPIRE 保证多实例一致；Redis 故障时退化为单机计数，
 * 并在 {@link #isDegraded()} 中暴露给健康检查。</p>
 */
@Slf4j
@Component
public class AgentRateLimiter {

    private final StringRedisTemplate redis;
    private final AgentProperties properties;
    private final Map<String, AtomicInteger> local = new ConcurrentHashMap<>();
    private volatile boolean degraded = false;

    public AgentRateLimiter(StringRedisTemplate redis, AgentProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    /**
     * @return null 表示放行；否则返回被限制的维度描述
     */
    public String tryAcquire(AgentPrincipal principal) {
        String userKey = properties.getKeyPrefix() + ":rl:u:" + principal.tenantId() + ":" + principal.userId();
        String tenantKey = properties.getKeyPrefix() + ":rl:t:" + principal.tenantId();
        if (overLimit(userKey, properties.getRateLimitPerUserPerMinute())) {
            return "user";
        }
        if (overLimit(tenantKey, properties.getRateLimitPerTenantPerMinute())) {
            return "tenant";
        }
        return null;
    }

    private boolean overLimit(String key, int limit) {
        if (limit <= 0) {
            return false;
        }
        long minute = System.currentTimeMillis() / 60_000L;
        String bucket = key + ":" + minute;
        try {
            Long count = redis.opsForValue().increment(bucket);
            if (count != null && count == 1L) {
                redis.expire(bucket, Duration.ofSeconds(90));
            }
            degraded = false;
            return count != null && count > limit;
        } catch (RuntimeException e) {
            degraded = true;
            log.warn("[Agent限流] Redis 不可用，使用单机计数: {}", e.getMessage());
            AtomicInteger counter = local.computeIfAbsent(bucket, k -> new AtomicInteger());
            // 简单清理，避免本地 Map 无限增长
            if (local.size() > 10_000) {
                local.clear();
            }
            return counter.incrementAndGet() > limit;
        }
    }

    public boolean isDegraded() {
        return degraded;
    }
}
