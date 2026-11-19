package com.ruoyi.base.agent.core;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.config.AgentProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 基于 Redis List + ZSet 的会话存储。
 *
 * <p>Key 结构：</p>
 * <ul>
 *   <li>{@code agent:session:{tenant}:{user}:{sessionId}}：List，消息 JSON；</li>
 *   <li>{@code agent:sessions:{tenant}:{user}}：ZSet，score=最后活跃时间，用于会话列表；</li>
 * </ul>
 *
 * <p>Redis 不可用时退化为进程内 LRU（单实例可用、多实例不一致），
 * 只记录 WARN 并打点，不阻断对话——历史丢失比整站不可用更容易接受。</p>
 */
@Slf4j
@Component
public class RedisAgentSessionStore implements AgentSessionStore {

    private static final int MAX_MESSAGES_PER_SESSION = 200;
    private static final int FALLBACK_MAX_SESSIONS = 1000;

    private final StringRedisTemplate redis;
    private final AgentProperties properties;

    /** 仅 Redis 故障时使用的本地兜底，按访问顺序淘汰。 */
    private final Map<String, List<AgentMessage>> fallback = Collections.synchronizedMap(
            new LinkedHashMap<>(16, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, List<AgentMessage>> eldest) {
                    return size() > FALLBACK_MAX_SESSIONS;
                }
            });

    public RedisAgentSessionStore(StringRedisTemplate redis, AgentProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    @Override
    public List<AgentMessage> load(AgentPrincipal principal, String sessionId, int limit) {
        String key = sessionKey(principal, sessionId);
        int size = Math.max(1, Math.min(limit, MAX_MESSAGES_PER_SESSION));
        try {
            List<String> raw = redis.opsForList().range(key, -size, -1);
            if (raw == null || raw.isEmpty()) {
                return new ArrayList<>(fallback.getOrDefault(key, Collections.emptyList()));
            }
            List<AgentMessage> messages = new ArrayList<>(raw.size());
            for (String s : raw) {
                try {
                    messages.add(JSON.parseObject(s, AgentMessage.class));
                } catch (Exception e) {
                    log.warn("[Agent会话] 跳过损坏消息 key={}", key);
                }
            }
            return messages;
        } catch (RuntimeException e) {
            log.warn("[Agent会话] Redis 读取失败，使用本地兜底: {}", e.getMessage());
            return new ArrayList<>(fallback.getOrDefault(key, Collections.emptyList()));
        }
    }

    @Override
    public void append(AgentPrincipal principal, String sessionId, List<AgentMessage> messages) {
        if (messages == null || messages.isEmpty()) {
            return;
        }
        String key = sessionKey(principal, sessionId);
        List<String> raw = new ArrayList<>(messages.size());
        for (AgentMessage m : messages) {
            raw.add(JSON.toJSONString(m));
        }
        try {
            redis.opsForList().rightPushAll(key, raw);
            redis.opsForList().trim(key, -MAX_MESSAGES_PER_SESSION, -1);
            Duration ttl = properties.getSessionTtl();
            redis.expire(key, ttl);
            // ZSet 成员必须与 List key 用同一个清洗后的 id，否则索引里会留下
            // 一条指向不存在 List 的"幽灵会话"（历史列表点进去是空的）。
            redis.opsForZSet().add(indexKey(principal), safe(sessionId), System.currentTimeMillis());
            redis.expire(indexKey(principal), ttl);
        } catch (RuntimeException e) {
            log.warn("[Agent会话] Redis 写入失败，使用本地兜底: {}", e.getMessage());
            List<AgentMessage> local = fallback.computeIfAbsent(key, k -> new ArrayList<>());
            synchronized (local) {
                local.addAll(messages);
                if (local.size() > MAX_MESSAGES_PER_SESSION) {
                    local.subList(0, local.size() - MAX_MESSAGES_PER_SESSION).clear();
                }
            }
        }
    }

    @Override
    public void clear(AgentPrincipal principal, String sessionId) {
        String key = sessionKey(principal, sessionId);
        fallback.remove(key);
        try {
            redis.delete(key);
            redis.opsForZSet().remove(indexKey(principal), safe(sessionId));
        } catch (RuntimeException e) {
            log.warn("[Agent会话] Redis 删除失败: {}", e.getMessage());
        }
    }

    @Override
    public boolean exists(AgentPrincipal principal, String sessionId) {
        String key = sessionKey(principal, sessionId);
        try {
            Boolean exists = redis.hasKey(key);
            return Boolean.TRUE.equals(exists) || fallback.containsKey(key);
        } catch (RuntimeException e) {
            return fallback.containsKey(key);
        }
    }

    @Override
    public List<String> listSessions(AgentPrincipal principal, int limit) {
        int size = Math.max(1, Math.min(limit, 50));
        try {
            var ids = redis.opsForZSet().reverseRange(indexKey(principal), 0, size - 1);
            return ids == null ? Collections.emptyList() : new ArrayList<>(ids);
        } catch (RuntimeException e) {
            log.warn("[Agent会话] Redis 会话列表读取失败: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    /** 健康检查用：不抛异常。 */
    public boolean isAvailable() {
        try {
            redis.hasKey(properties.getKeyPrefix() + ":health");
            return true;
        } catch (RuntimeException e) {
            return false;
        }
    }

    private String sessionKey(AgentPrincipal p, String sessionId) {
        return properties.getKeyPrefix() + ":session:" + p.tenantId() + ":" + p.userId() + ":" + safe(sessionId);
    }

    private String indexKey(AgentPrincipal p) {
        return properties.getKeyPrefix() + ":sessions:" + p.tenantId() + ":" + p.userId();
    }

    private static String safe(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) {
            return "default";
        }
        String cleaned = sessionId.trim().replaceAll("[^A-Za-z0-9_.:-]", "_");
        if (cleaned.length() <= 64) {
            return cleaned;
        }
        // 超长 sessionId 不能直接截断：截断会让两个不同会话落到同一个 Redis List
        // （同用户下可读到另一个会话的历史）。保留前 48 字符 + 不可逆短哈希保证唯一。
        return cleaned.substring(0, 48) + "~" + AgentPrincipal.shortHash(cleaned);
    }
}
