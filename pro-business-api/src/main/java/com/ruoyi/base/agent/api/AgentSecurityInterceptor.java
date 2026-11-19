package com.ruoyi.base.agent.api;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Agent 端点入口防护：
 * <ol>
 *   <li>内部令牌校验（复用 {@code traffic.security.internal-token}，常量时间比较）；</li>
 *   <li>租户/用户/角色请求头解析，写入 request attribute；</li>
 *   <li>请求追踪号透传。</li>
 * </ol>
 *
 * <p>信任边界：Agent 服务部署在内网，由 backend/网关完成用户认证并注入请求头；
 * 内部令牌用于阻断绕过网关的直连。不要把这个端点直接暴露到公网。</p>
 */
@Component
public class AgentSecurityInterceptor implements HandlerInterceptor {

    public static final String TOKEN_HEADER = "X-Internal-Token";

    private final AgentProperties properties;
    private final String internalToken;

    public AgentSecurityInterceptor(AgentProperties properties,
                                    @org.springframework.beans.factory.annotation.Value("${traffic.security.internal-token:}")
                                    String internalToken) {
        this.properties = properties;
        this.internalToken = internalToken == null ? "" : internalToken.trim();
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        if (!tokenValid(request)) {
            return deny(response, AgentErrorCode.AGENT_UNAUTHORIZED, "内部端点需要有效的 " + TOKEN_HEADER);
        }
        String tenant = header(request, properties.getTenantHeader());
        String user = header(request, properties.getUserHeader());
        if (tenant == null || user == null) {
            // 身份缺失一律拒绝：绝不兜底成 default/anonymous——那会让所有缺头请求共用
            // 同一个会话槽位与限流桶（等于互相能读历史）。回环地址同样要求带身份，
            // 本地联调用 curl 显式加头即可。
            return deny(response, AgentErrorCode.AGENT_UNAUTHORIZED,
                    "缺少 " + properties.getTenantHeader() + " / " + properties.getUserHeader());
        }
        Set<String> roles = new LinkedHashSet<>();
        String rolesHeader = header(request, properties.getRolesHeader());
        if (rolesHeader != null) {
            Arrays.stream(rolesHeader.split(","))
                    .map(String::trim)
                    .filter(s -> !s.isEmpty())
                    // 归一化：大小写不敏感 + 去掉 Spring Security 风格前缀（ROLE_），
                    // 否则网关下发 "OPS"/"ROLE_OPS" 时会被判成无角色，全员 403。
                    .map(AgentSecurityInterceptor::normalizeRole)
                    .forEach(roles::add);
        }
        AgentPrincipal principal = new AgentPrincipal(tenant, user, roles, true);
        request.setAttribute(AgentRequestContext.ATTR_PRINCIPAL, principal);
        String requestId = header(request, properties.getRequestIdHeader());
        request.setAttribute(AgentRequestContext.ATTR_REQUEST_ID,
                requestId == null ? java.util.UUID.randomUUID().toString().replace("-", "") : requestId);
        return true;
    }

    private boolean tokenValid(HttpServletRequest request) {
        if (internalToken.isEmpty()) {
            return properties.isAllowLoopbackWithoutToken() && isLoopback(request);
        }
        String provided = request.getHeader(TOKEN_HEADER);
        return provided != null && constantTimeEquals(internalToken, provided.trim());
    }

    /** 角色归一化：小写 + 去 {@code ROLE_} 前缀，保证与 {@code AgentToolCatalog} 的写法可比。 */
    private static String normalizeRole(String raw) {
        String role = raw.toLowerCase(java.util.Locale.ROOT);
        return role.startsWith("role_") ? role.substring("role_".length()) : role;
    }

    private static boolean isLoopback(HttpServletRequest request) {
        String remote = request.getRemoteAddr();
        return "127.0.0.1".equals(remote) || "::1".equals(remote) || "0:0:0:0:0:0:0:1".equals(remote);
    }

    private static String header(HttpServletRequest request, String name) {
        String value = request.getHeader(name);
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private static boolean constantTimeEquals(String expected, String actual) {
        byte[] a = expected.getBytes(StandardCharsets.UTF_8);
        byte[] b = actual.getBytes(StandardCharsets.UTF_8);
        if (a.length != b.length) {
            return false;
        }
        int diff = 0;
        for (int i = 0; i < a.length; i++) {
            diff |= a[i] ^ b[i];
        }
        return diff == 0;
    }

    private static boolean deny(HttpServletResponse response, AgentErrorCode code, String message) throws Exception {
        response.setStatus(code.httpStatus().value());
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":\"" + code.name() + "\",\"message\":\"" + message + "\"}");
        return false;
    }
}
