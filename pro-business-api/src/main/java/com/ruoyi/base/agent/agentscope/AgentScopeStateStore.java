package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import io.agentscope.core.state.AgentState;
import io.agentscope.core.state.AgentStateStore;
import io.agentscope.core.state.State;
import io.agentscope.core.util.JsonUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * AgentScope 会话状态存储（Redis 实现）。
 *
 * <p>为什么不直接用 {@code agentscope-extensions-redis} 的 {@code RedisAgentStateStore}：</p>
 * <blockquote>
 * 该扩展强制依赖 jedis 7.4.1 / redisson 4.2.0 / lettuce 6.4.2，而本工程根 pom 把 jedis
 * 锁定在 4.4.8（{@code JedisCluster}/{@code HostAndPort} 构造签名在 5.x 之后变化）。
 * 版本被 dependencyManagement 覆盖后，扩展里的 {@code UnifiedJedis} 调用会在运行期抛
 * {@code NoSuchMethodError}。因此这里只依赖 Spring Data Redis，自行实现 6 个方法的状态存储，
 * 与 {@code RedisAgentSessionStore} 共用同一套连接与 Key 风格。
 * </blockquote>
 *
 * <p>Key 结构（{@code prefix} 默认 {@code agent}）：</p>
 * <ul>
 *   <li>{@code agent:as:state:{user}:{sessionId}:{key}} — String，单个 State 的 JSON；</li>
 *   <li>{@code agent:as:list:{user}:{sessionId}:{key}} — List，元素为 State 的 JSON；</li>
 *   <li>{@code agent:as:keys:{user}:{sessionId}} — Set，登记该会话写过的 key，供 delete 清理；</li>
 *   <li>{@code agent:as:sessions:{user}} — Set，会话索引，供 {@code listSessionIds}。</li>
 * </ul>
 *
 * <p>一致性取舍：不实现 {@code supportsVersioning()}，采用 last-writer-wins。同一会话的并发调用已由
 * {@code ReActAgent} 按 {@code (userId, sessionId)} 串行化；跨实例并发同一会话属于异常用法，
 * 若后续确有需要，可在此加 Redis WATCH 实现 CAS。</p>
 *
 * <p>可用性取舍：Redis 异常时退化为进程内存储（单实例可用、多实例不一致），只打 WARN，
 * 不阻断对话——与 {@code RedisAgentSessionStore} 的策略一致。</p>
 */
@Slf4j
public class AgentScopeStateStore implements AgentStateStore {

    private static final String ANON = "__anon__";

    private final StringRedisTemplate redis;
    private final AgentProperties properties;

    /** Redis 故障期的本地兜底，key 为完整 Redis key。 */
    private final Map<String, String> localState = new ConcurrentHashMap<>();
    private final Map<String, List<String>> localList = new ConcurrentHashMap<>();
    private final Map<String, Set<String>> localSessions = new ConcurrentHashMap<>();
    private final Map<String, Set<String>> localKeys = new ConcurrentHashMap<>();

    public AgentScopeStateStore(StringRedisTemplate redis, AgentProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    @Override
    public void save(String userId, String sessionId, String key, State value) {
        String redisKey = stateKey(userId, sessionId, key);
        String json = serialize(value);
        try {
            redis.opsForValue().set(redisKey, json, ttl());
            registerKey(userId, sessionId, "s:" + key);
            registerSession(userId, sessionId);
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 写入失败，退化为本地缓存: {}", e.getMessage());
            localState.put(redisKey, json);
        }
    }

    @Override
    public void save(String userId, String sessionId, String key, List<? extends State> values) {
        String redisKey = listKey(userId, sessionId, key);
        List<String> json = new ArrayList<>();
        if (values != null) {
            for (State value : values) {
                json.add(serialize(value));
            }
        }
        try {
            redis.delete(redisKey);
            if (!json.isEmpty()) {
                redis.opsForList().rightPushAll(redisKey, json);
                redis.expire(redisKey, ttl());
            }
            registerKey(userId, sessionId, "l:" + key);
            registerSession(userId, sessionId);
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 写入失败，退化为本地缓存: {}", e.getMessage());
            localList.put(redisKey, new ArrayList<>(json));
        }
    }

    @Override
    public <T extends State> Optional<T> get(String userId, String sessionId, String key, Class<T> type) {
        String redisKey = stateKey(userId, sessionId, key);
        String json;
        try {
            json = redis.opsForValue().get(redisKey);
            if (json == null) {
                json = localState.get(redisKey);
            }
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 读取失败，使用本地缓存: {}", e.getMessage());
            json = localState.get(redisKey);
        }
        if (json == null) {
            return Optional.empty();
        }
        try {
            return Optional.ofNullable(deserialize(json, type));
        } catch (RuntimeException e) {
            // 反序列化失败（版本升级/脏数据）时丢弃该会话状态，避免整轮对话不可用。
            log.warn("[AgentScope状态] 反序列化失败，忽略该状态 key={}: {}", redisKey, e.getMessage());
            return Optional.empty();
        }
    }

    @Override
    public <T extends State> List<T> getList(String userId, String sessionId, String key, Class<T> itemType) {
        String redisKey = listKey(userId, sessionId, key);
        List<String> raw;
        try {
            raw = redis.opsForList().range(redisKey, 0, -1);
            if (raw == null || raw.isEmpty()) {
                raw = localList.get(redisKey);
            }
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 读取失败，使用本地缓存: {}", e.getMessage());
            raw = localList.get(redisKey);
        }
        if (raw == null || raw.isEmpty()) {
            return List.of();
        }
        List<T> values = new ArrayList<>(raw.size());
        for (String json : raw) {
            try {
                T value = deserialize(json, itemType);
                if (value != null) {
                    values.add(value);
                }
            } catch (RuntimeException e) {
                log.warn("[AgentScope状态] 跳过无法反序列化的元素 key={}", redisKey);
            }
        }
        return values;
    }

    @Override
    public boolean exists(String userId, String sessionId) {
        String sessionsKey = sessionsKey(userId);
        try {
            Boolean member = redis.opsForSet().isMember(sessionsKey, safe(sessionId));
            if (Boolean.TRUE.equals(member)) {
                return true;
            }
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 探测失败，使用本地缓存: {}", e.getMessage());
        }
        Set<String> local = localSessions.get(sessionsKey);
        return local != null && local.contains(safe(sessionId));
    }

    @Override
    public void delete(String userId, String sessionId) {
        String keysKey = keysKey(userId, sessionId);
        try {
            Set<String> registered = redis.opsForSet().members(keysKey);
            if (registered != null) {
                for (String entry : registered) {
                    redis.delete(entry.startsWith("l:") ? listKey(userId, sessionId, entry.substring(2))
                            : stateKey(userId, sessionId, entry.substring(2)));
                }
            }
            redis.delete(keysKey);
            redis.opsForSet().remove(sessionsKey(userId), safe(sessionId));
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 删除失败: {}", e.getMessage());
        }
        // 本地兜底缓存必须一起清：get/getList 在 Redis 返回空时会回落到本地，
        // 不清就会"删完又冒出来"。
        String statePrefix = properties.getKeyPrefix() + ":as:state:" + user(userId) + ":" + safe(sessionId) + ":";
        String listPrefix = properties.getKeyPrefix() + ":as:list:" + user(userId) + ":" + safe(sessionId) + ":";
        localState.keySet().removeIf(k -> k.startsWith(statePrefix));
        localList.keySet().removeIf(k -> k.startsWith(listPrefix));
        localKeys.remove(keysKey);
        localSessions.getOrDefault(sessionsKey(userId), Collections.emptySet()).remove(safe(sessionId));
    }

    @Override
    public Set<String> listSessionIds(String userId) {
        try {
            Set<String> ids = redis.opsForSet().members(sessionsKey(userId));
            if (ids != null && !ids.isEmpty()) {
                return new LinkedHashSet<>(ids);
            }
        } catch (RuntimeException e) {
            log.warn("[AgentScope状态] Redis 会话列表读取失败: {}", e.getMessage());
        }
        Set<String> local = localSessions.get(sessionsKey(userId));
        return local == null ? Set.of() : new LinkedHashSet<>(local);
    }

    private void registerKey(String userId, String sessionId, String entry) {
        String keysKey = keysKey(userId, sessionId);
        redis.opsForSet().add(keysKey, entry);
        redis.expire(keysKey, ttl());
    }

    private void registerSession(String userId, String sessionId) {
        String sessionsKey = sessionsKey(userId);
        redis.opsForSet().add(sessionsKey, safe(sessionId));
        redis.expire(sessionsKey, ttl());
    }

    private Duration ttl() {
        Duration ttl = properties.getSessionTtl();
        return ttl == null || ttl.isNegative() || ttl.isZero() ? Duration.ofDays(7) : ttl;
    }

    /** AgentState 用框架自带的 JSON 编解码（字段语义由框架保证），其余 State 用全局 codec。 */
    private static String serialize(State value) {
        if (value instanceof AgentState state) {
            return state.toJson();
        }
        return JsonUtils.getJsonCodec().toJson(value);
    }

    private static <T extends State> T deserialize(String json, Class<T> type) {
        if (AgentState.class.equals(type)) {
            return type.cast(AgentState.fromJsonString(json));
        }
        return JsonUtils.getJsonCodec().fromJson(json, type);
    }

    private String stateKey(String userId, String sessionId, String key) {
        return properties.getKeyPrefix() + ":as:state:" + user(userId) + ":" + safe(sessionId) + ":" + safe(key);
    }

    private String listKey(String userId, String sessionId, String key) {
        return properties.getKeyPrefix() + ":as:list:" + user(userId) + ":" + safe(sessionId) + ":" + safe(key);
    }

    private String keysKey(String userId, String sessionId) {
        return properties.getKeyPrefix() + ":as:keys:" + user(userId) + ":" + safe(sessionId);
    }

    private String sessionsKey(String userId) {
        return properties.getKeyPrefix() + ":as:sessions:" + user(userId);
    }

    private static String user(String userId) {
        return userId == null || userId.isBlank() ? ANON : safe(userId);
    }

    private static String safe(String value) {
        if (value == null || value.isBlank()) {
            return "default";
        }
        String v = value.trim();
        String cleaned = v.replaceAll("[^A-Za-z0-9_.:@-]", "_");
        if (cleaned.length() <= 96) {
            return cleaned;
        }
        // 超长标识不能直接截断：截断会让不同租户/用户落到同一个 key（越权读取）。
        // 这里保留前 64 字符便于排查，再拼不可逆短哈希保证唯一。
        return cleaned.substring(0, 64) + "~" + com.ruoyi.base.agent.core.AgentPrincipal.shortHash(cleaned);
    }
}
