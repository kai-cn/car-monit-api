package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.tools.ToolSupport;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ToolSupportTest {

    @Test
    void masksPlateKeepingPrefixAndSuffix() {
        assertEquals("赣B***85", ToolSupport.maskPlate("赣B21E85", false));
        assertEquals("赣B21E85", ToolSupport.maskPlate("赣B21E85", true));
        assertEquals("赣***", ToolSupport.maskPlate("赣B", false));
    }

    @Test
    void rejectsInvertedOrOversizedWindow() {
        long now = System.currentTimeMillis();
        assertThrows(AgentException.class,
                () -> ToolSupport.validateWindow(now, now - 1, Duration.ofDays(1), "查询"));
        assertThrows(AgentException.class,
                () -> ToolSupport.validateWindow(now - Duration.ofDays(40).toMillis(), now,
                        Duration.ofDays(31), "查询"));
    }

    @Test
    void truncatesLongText() {
        String s = "x".repeat(100);
        assertTrue(ToolSupport.truncate(s, 10).endsWith("...(truncated)"));
        assertEquals(10 + "...(truncated)".length(), ToolSupport.truncate(s, 10).length());
    }
}
