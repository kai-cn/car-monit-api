package com.ruoyi.base.agent.agentscope;

import io.agentscope.core.message.AssistantMessage;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.MsgRole;
import io.agentscope.core.message.SystemMessage;
import io.agentscope.core.message.UserMessage;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 上下文窗口裁剪单测：保留 system、只留最近 N 轮、裁剪点对齐 user 边界。
 */
class HistoryWindowMiddlewareTest {

    @Test
    @DisplayName("历史超过窗口时只保留最近 N 轮，system 消息始终保留")
    void keepsSystemAndRecentTurns() {
        List<Msg> messages = new ArrayList<>();
        messages.add(new SystemMessage("系统提示词"));
        for (int i = 0; i < 5; i++) {
            messages.add(new UserMessage("问题" + i));
            messages.add(new AssistantMessage("回答" + i));
        }

        List<Msg> trimmed = new HistoryWindowMiddleware(2).trim(messages);

        assertEquals(1 + 4, trimmed.size());
        assertEquals(MsgRole.SYSTEM, trimmed.get(0).getRole());
        assertEquals("问题3", trimmed.get(1).getTextContent());
        assertEquals("回答4", trimmed.get(4).getTextContent());
    }

    @Test
    @DisplayName("裁剪点落在工具消息上时向前对齐到 user，避免拆散 tool_use/tool_result")
    void alignsToUserBoundary() {
        List<Msg> messages = new ArrayList<>();
        messages.add(new SystemMessage("系统提示词"));
        messages.add(new UserMessage("旧问题1"));
        messages.add(new AssistantMessage("旧回答1"));
        messages.add(new UserMessage("旧问题2"));
        messages.add(new AssistantMessage("调用工具"));
        messages.add(new AssistantMessage("工具结果"));
        messages.add(new UserMessage("新问题"));
        messages.add(new AssistantMessage("新回答"));

        // 窗口 2 轮 → 按条数会切到“调用工具”，对齐后应从“新问题”开始，
        // 否则回灌给模型的会是“工具结果 + 新问题 + 新回答”，tool_call_id 配对断裂会被模型端拒绝。
        List<Msg> trimmed = new HistoryWindowMiddleware(2).trim(messages);

        assertEquals(3, trimmed.size());
        assertEquals(MsgRole.SYSTEM, trimmed.get(0).getRole());
        assertEquals("新问题", trimmed.get(1).getTextContent());
        assertEquals("新回答", trimmed.get(2).getTextContent());
    }

    @Test
    @DisplayName("未超出窗口或窗口配置为 0 时原样返回（不复制、不改动）")
    void returnsSameInstanceWhenNoTrimNeeded() {
        List<Msg> messages = List.of(new SystemMessage("s"), new UserMessage("u"), new AssistantMessage("a"));
        assertSame(messages, new HistoryWindowMiddleware(5).trim(messages));
        assertSame(messages, new HistoryWindowMiddleware(0).trim(messages));
        assertTrue(new HistoryWindowMiddleware(0).trim(List.of()).isEmpty());
    }
}
