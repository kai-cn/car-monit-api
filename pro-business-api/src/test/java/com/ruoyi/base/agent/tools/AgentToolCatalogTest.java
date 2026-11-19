package com.ruoyi.base.agent.tools;

import com.ruoyi.base.agent.core.AgentPrincipal;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 工具权限矩阵单测：{@code requiredRoles} 是授权的单一事实源，必须默认拒绝。
 */
class AgentToolCatalogTest {

    private static AgentPrincipal principal(String... roles) {
        return new AgentPrincipal("tenant-a", "u1", Set.of(roles), true);
    }

    @Test
    @DisplayName("只读工具对 ops 开放，轨迹回放只对 audit/admin 开放")
    void readToolsFollowRoleMatrix() {
        assertTrue(AgentToolCatalog.allows(principal("ops"), AgentToolCatalog.QUERY_TRAFFIC));
        assertTrue(AgentToolCatalog.allows(principal("ops"), AgentToolCatalog.SEARCH_KNOWLEDGE));
        assertTrue(AgentToolCatalog.allows(principal("ops"), AgentToolCatalog.DATA_QUALITY));
        assertFalse(AgentToolCatalog.allows(principal("ops"), AgentToolCatalog.VEHICLE_TRACK));
        assertTrue(AgentToolCatalog.allows(principal("audit"), AgentToolCatalog.VEHICLE_TRACK));
        assertTrue(AgentToolCatalog.allows(principal("admin"), AgentToolCatalog.VEHICLE_TRACK));
    }

    @Test
    @DisplayName("写工具只对 admin 开放")
    void writeToolRequiresAdmin() {
        assertFalse(AgentToolCatalog.allows(principal("ops"), AgentToolCatalog.SUBMIT_EXPORT));
        assertFalse(AgentToolCatalog.allows(principal("audit"), AgentToolCatalog.SUBMIT_EXPORT));
        assertTrue(AgentToolCatalog.allows(principal("admin"), AgentToolCatalog.SUBMIT_EXPORT));
    }

    @Test
    @DisplayName("无角色/未知工具/空主体一律拒绝（默认拒绝）")
    void defaultsToDeny() {
        assertFalse(AgentToolCatalog.allows(principal(), AgentToolCatalog.QUERY_TRAFFIC));
        assertFalse(AgentToolCatalog.allows(principal("ops"), "drop_table"));
        assertFalse(AgentToolCatalog.allows(null, AgentToolCatalog.QUERY_TRAFFIC));
    }
}
