package com.ruoyi.base.agent.core;

import java.util.List;

/**
 * 会话存取抽象。实现必须按 tenant + user 做隔离，sessionId 不能跨用户复用。
 */
public interface AgentSessionStore {

    List<AgentMessage> load(AgentPrincipal principal, String sessionId, int limit);

    void append(AgentPrincipal principal, String sessionId, List<AgentMessage> messages);

    void clear(AgentPrincipal principal, String sessionId);

    boolean exists(AgentPrincipal principal, String sessionId);

    List<String> listSessions(AgentPrincipal principal, int limit);
}
