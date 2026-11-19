package com.ruoyi.base.agent.core;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 调用主体归一化单测：请求头是不可信输入，进 Redis key/日志前必须清洗且不可折叠。
 */
class AgentPrincipalTest {

    @Test
    @DisplayName("普通标识只做字符白名单替换")
    void sanitizesIllegalCharacters() {
        AgentPrincipal p = new AgentPrincipal("tenant a", "u1\n;DROP", Set.of("ops"), false);
        assertEquals("tenant_a", p.tenantId());
        assertEquals("u1__DROP", p.userId());
    }

    @Test
    @DisplayName("超长标识不截断折叠：前缀相同也必须产生不同身份")
    void longIdentifiersDoNotCollapse() {
        String prefix = "u".repeat(64);
        AgentPrincipal a = new AgentPrincipal("t", prefix + "A", Set.of("ops"), false);
        AgentPrincipal b = new AgentPrincipal("t", prefix + "B", Set.of("ops"), false);
        assertNotEquals(a.userId(), b.userId());
        assertTrue(a.userId().length() <= 64);
        // 会话/限流 key 里用的就是 userId，不折叠才不会互相读历史
        assertNotEquals(a.userHash(), b.userHash());
    }

    @Test
    @DisplayName("空值走兜底，非法值不抛异常")
    void fallsBackOnBlank() {
        AgentPrincipal p = new AgentPrincipal(null, "  ", null, false);
        assertEquals("default", p.tenantId());
        assertEquals("anonymous", p.userId());
        assertFalse(p.hasRole("admin"));
        assertTrue(p.roles().isEmpty());
    }
}
