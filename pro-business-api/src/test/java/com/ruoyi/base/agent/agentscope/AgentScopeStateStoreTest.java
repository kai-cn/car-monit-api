package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.config.AgentProperties;
import io.agentscope.core.state.AgentState;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 状态存储单测：Key 结构、AgentState 往返、Redis 故障降级、删除清理。
 */
class AgentScopeStateStoreTest {

    private StringRedisTemplate redis;
    private ValueOperations<String, String> valueOps;
    private SetOperations<String, String> setOps;
    private AgentScopeStateStore store;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        redis = mock(StringRedisTemplate.class);
        valueOps = mock(ValueOperations.class);
        setOps = mock(SetOperations.class);
        when(redis.opsForValue()).thenReturn(valueOps);
        when(redis.opsForSet()).thenReturn(setOps);
        store = new AgentScopeStateStore(redis, new AgentProperties());
    }

    @Test
    @DisplayName("Key 结构稳定：prefix:as:state:{user}:{session}:{key}，并带 TTL")
    void writesExpectedKeyWithTtl() {
        AgentState state = AgentState.builder().sessionId("s1").build();

        store.save("tenant-a:u1", "s1", "agent_state", state);

        ArgumentCaptor<String> key = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> json = ArgumentCaptor.forClass(String.class);
        verify(valueOps).set(key.capture(), json.capture(), any(Duration.class));
        assertEquals("agent:as:state:tenant-a:u1:s1:agent_state", key.getValue());
        assertTrue(json.getValue().contains("\"session_id\""));
        // 会话索引与 key 登记都要写，否则 listSessionIds / delete 会失效
        verify(setOps).add(eq("agent:as:keys:tenant-a:u1:s1"), eq("s:agent_state"));
        verify(setOps).add(eq("agent:as:sessions:tenant-a:u1"), eq("s1"));
    }

    @Test
    @DisplayName("AgentState 可 JSON 往返（多实例共享会话的前提）")
    void roundTripsAgentState() {
        AgentState state = AgentState.builder().sessionId("s1").userId("tenant-a:u1").build();
        when(valueOps.get("agent:as:state:tenant-a:u1:s1:agent_state")).thenReturn(state.toJson());

        Optional<AgentState> loaded = store.get("tenant-a:u1", "s1", "agent_state", AgentState.class);

        assertTrue(loaded.isPresent());
        assertEquals("s1", loaded.get().getSessionId());
        assertEquals("tenant-a:u1", loaded.get().getUserId());
    }

    @Test
    @DisplayName("Redis 故障时退化为进程内缓存，对话不中断")
    void degradesToLocalCacheWhenRedisFails() {
        when(redis.opsForValue()).thenThrow(new RuntimeException("redis down"));
        when(redis.opsForSet()).thenThrow(new RuntimeException("redis down"));

        AgentState state = AgentState.builder().sessionId("s2").build();
        store.save("tenant-a:u2", "s2", "agent_state", state);
        Optional<AgentState> loaded = store.get("tenant-a:u2", "s2", "agent_state", AgentState.class);

        assertTrue(loaded.isPresent());
        assertEquals("s2", loaded.get().getSessionId());
    }

    @Test
    @DisplayName("删除会话时按登记表清理标量与列表 key")
    void deletesAllRegisteredKeys() {
        when(setOps.members("agent:as:keys:tenant-a:u1:s1"))
                .thenReturn(java.util.Set.of("s:agent_state", "l:memory_messages"));

        store.delete("tenant-a:u1", "s1");

        verify(redis).delete("agent:as:state:tenant-a:u1:s1:agent_state");
        verify(redis).delete("agent:as:list:tenant-a:u1:s1:memory_messages");
        verify(redis).delete("agent:as:keys:tenant-a:u1:s1");
        verify(setOps).remove("agent:as:sessions:tenant-a:u1", "s1");
    }

    @Test
    @DisplayName("超长 userId 不截断拼接，避免不同租户落到同一 Key")
    void longUserIdsDoNotCollide() {
        String first = "tenant-" + "a".repeat(80);
        String second = "tenant-" + "a".repeat(79) + "b";
        when(valueOps.get(anyString())).thenReturn(null);

        store.get(first, "s1", "agent_state", AgentState.class);
        store.get(second, "s1", "agent_state", AgentState.class);

        ArgumentCaptor<String> keys = ArgumentCaptor.forClass(String.class);
        verify(valueOps, org.mockito.Mockito.times(2)).get(keys.capture());
        assertTrue(!keys.getAllValues().get(0).equals(keys.getAllValues().get(1)));
    }
}
