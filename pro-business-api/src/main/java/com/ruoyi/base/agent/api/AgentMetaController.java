package com.ruoyi.base.agent.api;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.api.dto.AgentConfirmRequest;
import com.ruoyi.base.agent.api.dto.AgentFeedbackRequest;
import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentConfirmationService;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentGuard;
import com.ruoyi.base.agent.core.AgentMetrics;
import com.ruoyi.base.agent.core.AgentOrchestrator;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.AgentRateLimiter;
import com.ruoyi.base.agent.core.AgentSessionStore;
import com.ruoyi.base.agent.core.KnowledgeBase;
import com.ruoyi.base.agent.core.RedisAgentSessionStore;
import com.ruoyi.base.agent.tools.AgentToolCatalog;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Agent 元信息：工具清单、健康检查、二次确认令牌、用户反馈。
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/agent")
public class AgentMetaController {

    private static final Logger FEEDBACK = LoggerFactory.getLogger("AGENT_FEEDBACK");

    private final ObjectProvider<AgentOrchestrator> orchestratorProvider;
    private final AgentSessionStore sessionStore;
    private final AgentConfirmationService confirmationService;
    private final AgentGuard guard;
    private final AgentRateLimiter rateLimiter;
    private final AgentMetrics metrics;
    private final AgentProperties properties;
    private final AgentRequestContext requestContext;
    private final KnowledgeBase knowledgeBase;

    public AgentMetaController(ObjectProvider<AgentOrchestrator> orchestratorProvider,
                               AgentSessionStore sessionStore,
                               AgentConfirmationService confirmationService,
                               AgentGuard guard,
                               AgentRateLimiter rateLimiter,
                               AgentMetrics metrics,
                               AgentProperties properties,
                               AgentRequestContext requestContext,
                               KnowledgeBase knowledgeBase) {
        this.orchestratorProvider = orchestratorProvider;
        this.sessionStore = sessionStore;
        this.confirmationService = confirmationService;
        this.guard = guard;
        this.rateLimiter = rateLimiter;
        this.metrics = metrics;
        this.properties = properties;
        this.requestContext = requestContext;
        this.knowledgeBase = knowledgeBase;
    }

    @GetMapping("/tools")
    public Map<String, Object> tools() {
        AgentOrchestrator orchestrator = orchestratorProvider.getIfAvailable();
        // 目录（静态）与注册（运行期）是两件事：目录里有的工具不一定真的注册到了框架。
        // 这里严格按实际注册结果回填 registered，不做"取不到就都算注册"的兜底——
        // 那种兜底会让 /tools 在框架装配失败时依然显示"全部就绪"，把故障藏起来。
        Set<String> registered = orchestrator == null ? Set.of() : orchestrator.registeredTools();
        List<Map<String, Object>> specs = AgentToolCatalog.specs().stream().map(spec -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("name", spec.name());
            m.put("description", spec.description());
            m.put("risk", spec.risk().name());
            m.put("requiredRoles", spec.requiredRoles());
            m.put("registered", registered.contains(spec.name()));
            m.put("inputSchema", JSON.parseObject(spec.inputSchema()));
            return m;
        }).collect(Collectors.toList());
        Map<String, Object> data = new LinkedHashMap<>();
        // framework 必须取"实际装配的实现"，而不是配置项：配置写错时（例如分支切错、
        // 或两个分支镜像混用）只有真实值才能让前端与 E2E 发现不一致。
        data.put("framework", orchestrator == null ? null : orchestrator.framework());
        data.put("configuredFramework", properties.getFramework());
        data.put("enabled", orchestrator != null);
        data.put("tools", specs);
        return ok(data);
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        AgentOrchestrator orchestrator = orchestratorProvider.getIfAvailable();
        boolean redisUp = sessionStore instanceof RedisAgentSessionStore r && r.isAvailable();
        boolean degraded = !redisUp || rateLimiter.isDegraded();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("enabled", orchestrator != null);
        data.put("framework", orchestrator == null ? null : orchestrator.framework());
        data.put("configuredFramework", properties.getFramework());
        data.put("model", maskModel(properties.getModel()));
        data.put("tools", AgentToolCatalog.specs().size());
        data.put("knowledgeChunks", knowledgeBase.size());
        data.put("redis", redisUp ? "UP" : "DEGRADED");
        data.put("rateLimiter", rateLimiter.isDegraded() ? "DEGRADED" : "UP");
        data.put("exportEnabled", properties.isAllowExport());
        data.put("status", orchestrator == null ? "DISABLED" : (degraded ? "DEGRADED" : "UP"));
        return ok(data);
    }

    @PostMapping("/confirm")
    public Map<String, Object> confirm(@Valid @RequestBody AgentConfirmRequest body, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        String action = body.getAction().trim().toLowerCase();
        if (!"export".equals(action)) {
            throw new AgentException(AgentErrorCode.AGENT_BAD_REQUEST, "不支持的确认动作: " + body.getAction());
        }
        guard.requireExportEnabled();
        if (!principal.canExport()) {
            throw new AgentException(AgentErrorCode.AGENT_FORBIDDEN, "仅管理员可发起导出确认");
        }
        String token = confirmationService.issue(principal, body.getSessionId(), action);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("confirmToken", token);
        data.put("action", action);
        data.put("expiresInSeconds", properties.getConfirmTtl().toSeconds());
        return ok(data);
    }

    @PostMapping("/feedback")
    public Map<String, Object> feedback(@Valid @RequestBody AgentFeedbackRequest body, HttpServletRequest request) {
        AgentPrincipal principal = requestContext.principal(request);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ts", System.currentTimeMillis());
        row.put("requestId", body.getRequestId());
        row.put("sessionId", body.getSessionId());
        row.put("tenant", principal.tenantId());
        row.put("userHash", principal.userHash());
        row.put("rating", body.getRating());
        row.put("comment", body.getComment());
        FEEDBACK.info(JSON.toJSONString(row));
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("accepted", true);
        return ok(data);
    }

    private static String maskModel(String model) {
        if (model == null || model.length() <= 4) {
            return "****";
        }
        return model.substring(0, Math.min(6, model.length())) + "***";
    }

    private static Map<String, Object> ok(Object data) {
        Map<String, Object> wrapper = new LinkedHashMap<>();
        wrapper.put("code", 200);
        wrapper.put("message", "ok");
        wrapper.put("data", data);
        return wrapper;
    }
}
