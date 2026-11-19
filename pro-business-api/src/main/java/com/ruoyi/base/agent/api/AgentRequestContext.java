package com.ruoyi.base.agent.api;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Component;

/**
 * 从请求属性中读取已认证主体与追踪号。
 */
@Component
public class AgentRequestContext {

    public static final String ATTR_PRINCIPAL = "traffic.agent.principal";
    public static final String ATTR_REQUEST_ID = "traffic.agent.requestId";

    private final AgentProperties properties;

    public AgentRequestContext(AgentProperties properties) {
        this.properties = properties;
    }

    public AgentPrincipal principal(HttpServletRequest request) {
        Object value = request.getAttribute(ATTR_PRINCIPAL);
        if (value instanceof AgentPrincipal p) {
            return p;
        }
        throw new AgentException(com.ruoyi.base.agent.core.AgentErrorCode.AGENT_UNAUTHORIZED, "缺少调用主体");
    }

    public String requestId(HttpServletRequest request) {
        Object value = request.getAttribute(ATTR_REQUEST_ID);
        if (value != null) {
            return String.valueOf(value);
        }
        String header = request.getHeader(properties.getRequestIdHeader());
        return header == null || header.isBlank() ? java.util.UUID.randomUUID().toString().replace("-", "") : header;
    }
}
