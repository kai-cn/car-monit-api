package com.ruoyi.base.agent.core;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Agent 调用主体。
 *
 * <p>由网关/backend 通过请求头注入，服务端只读。模型无法修改该对象，
 * 所有租户隔离、字段脱敏、工具授权都以它为准（而不是以模型输出为准）。</p>
 */
public record AgentPrincipal(
        String tenantId,
        String userId,
        Set<String> roles,
        boolean trusted
) {

    public AgentPrincipal {
        tenantId = normalize(tenantId, "default");
        userId = normalize(userId, "anonymous");
        roles = roles == null ? Collections.emptySet() : Collections.unmodifiableSet(new LinkedHashSet<>(roles));
    }

    private static String normalize(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        String v = value.trim();
        // 请求头进入 Redis key/日志前做字符白名单，避免 key 注入与日志伪造。
        return v.length() > 64 ? v.substring(0, 64) : v.replaceAll("[^A-Za-z0-9_.:@-]", "_");
    }

    public boolean hasRole(String role) {
        return roles.contains(role);
    }

    public boolean hasAnyRole(String... candidates) {
        for (String c : candidates) {
            if (roles.contains(c)) {
                return true;
            }
        }
        return false;
    }

    public boolean canSeeFullPlate() {
        return hasAnyRole("audit", "admin");
    }

    public boolean canExport() {
        return hasAnyRole("admin");
    }

    /** 日志/指标里的用户标识：不可逆短哈希，避免明文用户 ID 扩散。 */
    public String userHash() {
        return shortHash(tenantId + ":" + userId);
    }

    public String tenantHash() {
        return shortHash(tenantId);
    }

    public static String shortHash(String value) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(12);
            for (int i = 0; i < 6; i++) {
                sb.append(String.format("%02x", digest[i]));
            }
            return sb.toString();
        } catch (Exception e) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
