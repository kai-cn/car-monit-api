package com.ruoyi.base.agent.api;

import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentMessage;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentSessionStore;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 会话历史接口。只允许访问本人会话；管理员也不跨用户读取（审计场景走日志平台）。
 */
@RestController
@RequestMapping("/api/v1/agent/sessions")
public class AgentSessionController {

    private final AgentSessionStore sessionStore;
    private final AgentRequestContext requestContext;
    private final ObjectProvider<AgentOrchestrator> orchestratorProvider;

    public AgentSessionController(AgentSessionStore sessionStore,
                                  AgentRequestContext requestContext,
                                  ObjectProvider<AgentOrchestrator> orchestratorProvider) {
        this.sessionStore = sessionStore;
        this.requestContext = requestContext;
        this.orchestratorProvider = orchestratorProvider;
    }

    @GetMapping
    public Map<String, Object> list(@RequestParam(defaultValue = "20") int limit, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        List<String> sessions = sessionStore.listSessions(principal, limit);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("sessions", sessions);
        return ok(data);
    }

    @GetMapping("/{sessionId}")
    public Map<String, Object> messages(@PathVariable String sessionId,
                                        @RequestParam(defaultValue = "50") int limit,
                                        HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        if (!sessionStore.exists(principal, sessionId)) {
            throw new AgentException(AgentErrorCode.AGENT_SESSION_NOT_FOUND);
        }
        List<AgentMessage> messages = sessionStore.load(principal, sessionId, Math.min(limit, 200));
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("sessionId", sessionId);
        data.put("messages", messages);
        return ok(data);
    }

    @DeleteMapping("/{sessionId}")
    public Map<String, Object> clear(@PathVariable String sessionId, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        // 先清框架侧模型上下文（记忆/状态），再清 UI 历史；否则"清空后模型仍记得"。
        AgentOrchestrator orchestrator = orchestratorProvider.getIfAvailable();
        if (orchestrator != null) {
            orchestrator.clearSession(principal, sessionId);
        }
        sessionStore.clear(principal, sessionId);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("sessionId", sessionId);
        data.put("cleared", true);
        return ok(data);
    }

    private static Map<String, Object> ok(Object data) {
        Map<String, Object> wrapper = new LinkedHashMap<>();
        wrapper.put("code", 200);
        wrapper.put("message", "ok");
        wrapper.put("data", data);
        return wrapper;
    }
}
