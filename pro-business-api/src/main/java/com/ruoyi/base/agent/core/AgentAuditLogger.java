package com.ruoyi.base.agent.core;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.agent.config.AgentProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 审计日志。独立 logger 名 {@code AGENT_AUDIT}，便于日志平台单独采集与保留：
 * 记录谁在什么时间、对哪个租户、调用了哪些工具、耗时与 token，不记录模型 Key。
 *
 * <p>默认不落原始问题（可能含车牌等个人信息），只记录长度与哈希；
 * 需要取证时通过 {@code traffic.agent.audit-log-question=true} 临时开启。</p>
 */
@Component
public class AgentAuditLogger {

    private static final Logger AUDIT = LoggerFactory.getLogger("AGENT_AUDIT");

    private final AgentProperties properties;

    public AgentAuditLogger(AgentProperties properties) {
        this.properties = properties;
    }

    public void chat(AgentInvocation inv, String result, long elapsedMs,
                     Map<String, Object> usage, String errorCode) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ts", System.currentTimeMillis());
        row.put("event", "chat");
        row.put("requestId", inv.getRequestId());
        row.put("tenant", inv.getPrincipal().tenantId());
        row.put("userHash", inv.getPrincipal().userHash());
        row.put("session", AgentPrincipal.shortHash(inv.conversationKey()));
        row.put("framework", properties.getFramework());
        row.put("result", result);
        row.put("elapsedMs", elapsedMs);
        row.put("usage", usage);
        row.put("errorCode", errorCode);
        row.put("questionLength", inv.getMessage() == null ? 0 : inv.getMessage().length());
        if (properties.isAuditLogQuestion()) {
            row.put("question", inv.getMessage());
        }
        AUDIT.info(JSON.toJSONString(row));
    }

    public void tool(AgentInvocation inv, String tool, String status, long elapsedMs, String summary) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ts", System.currentTimeMillis());
        row.put("event", "tool");
        row.put("requestId", inv.getRequestId());
        row.put("tenant", inv.getPrincipal().tenantId());
        row.put("userHash", inv.getPrincipal().userHash());
        row.put("tool", tool);
        row.put("status", status);
        row.put("elapsedMs", elapsedMs);
        row.put("summary", summary == null ? "" : summary.substring(0, Math.min(summary.length(), 200)));
        AUDIT.info(JSON.toJSONString(row));
    }

    public void rejected(String requestId, AgentPrincipal principal, String code, String detail) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ts", System.currentTimeMillis());
        row.put("event", "rejected");
        row.put("requestId", requestId);
        row.put("tenant", principal.tenantId());
        row.put("userHash", principal.userHash());
        row.put("code", code);
        row.put("detail", detail);
        AUDIT.warn(JSON.toJSONString(row));
    }
}
