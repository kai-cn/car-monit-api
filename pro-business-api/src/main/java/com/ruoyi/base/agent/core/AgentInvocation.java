package com.ruoyi.base.agent.core;

import lombok.Builder;
import lombok.Getter;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 一次 Agent 调用的不可变入参。
 */
@Getter
@Builder
public class AgentInvocation {

    private final String requestId;
    private final AgentPrincipal principal;
    private final String sessionId;
    private final String message;
    /** 高风险操作的一次性确认令牌；由客户端在二次确认后回传，模型不可见。 */
    private final String confirmToken;
    private final String locale;
    private final long startedAt;

    @Builder.Default
    private final Map<String, Object> attributes = new LinkedHashMap<>();

    public String conversationKey() {
        return principal.tenantId() + ":" + principal.userId() + ":" + sessionId;
    }
}
