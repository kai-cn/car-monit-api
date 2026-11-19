package com.ruoyi.base.agent.core;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 会话中的一条消息。只持久化可展示的文本，不持久化工具原始报文，
 * 避免把大字段/敏感字段长期留在 Redis。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentMessage {

    public static final String ROLE_USER = "user";
    public static final String ROLE_ASSISTANT = "assistant";
    public static final String ROLE_SYSTEM = "system";

    private String role;
    private String content;
    private long createdAt;

    public static AgentMessage user(String content) {
        return new AgentMessage(ROLE_USER, content, System.currentTimeMillis());
    }

    public static AgentMessage assistant(String content) {
        return new AgentMessage(ROLE_ASSISTANT, content, System.currentTimeMillis());
    }
}
