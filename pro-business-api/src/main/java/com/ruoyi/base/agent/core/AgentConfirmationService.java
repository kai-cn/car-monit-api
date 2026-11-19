package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.util.UUID;

/**
 * 高风险操作的一次性确认令牌。
 *
 * <p>流程：前端在用户点击“确认导出”后调用 {@code POST /api/v1/agent/confirm}，
 * 服务端签发绑定 tenant+user+session+action 的短 TTL 令牌；下一次聊天请求携带
 * {@code confirmToken}，工具层消费令牌后才执行导出。</p>
 *
 * <p>令牌只走 HTTP 请求上下文，<b>不作为工具参数暴露给模型</b>，模型无法自签自用。</p>
 */
@Slf4j
@Component
public class AgentConfirmationService {

    private final StringRedisTemplate redis;
    private final AgentProperties properties;

    public AgentConfirmationService(StringRedisTemplate redis, AgentProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    public String issue(AgentPrincipal principal, String sessionId, String action) {
        String token = UUID.randomUUID().toString().replace("-", "");
        String key = key(token);
        String value = principal.tenantId() + "|" + principal.userId() + "|" + sessionId + "|" + action;
        try {
            redis.opsForValue().set(key, value, properties.getConfirmTtl());
            return token;
        } catch (RuntimeException e) {
            // 确认令牌是安全控制，Redis 不可用时必须 fail-closed。
            log.error("[Agent确认] 令牌签发失败: {}", e.getMessage());
            throw new AgentException(AgentErrorCode.AGENT_INTERNAL, "确认服务暂不可用");
        }
    }

    /**
     * 消费令牌（一次性）。校验租户、用户、会话、动作四要素。
     */
    public boolean consume(AgentPrincipal principal, String sessionId, String action, String token) {
        if (token == null || token.isBlank()) {
            return false;
        }
        String expected = principal.tenantId() + "|" + principal.userId() + "|" + sessionId + "|" + action;
        try {
            String value = redis.opsForValue().getAndDelete(key(token));
            return expected.equals(value);
        } catch (RuntimeException e) {
            log.error("[Agent确认] 令牌校验失败: {}", e.getMessage());
            throw new AgentException(AgentErrorCode.AGENT_INTERNAL, "确认服务暂不可用");
        }
    }

    private String key(String token) {
        return properties.getKeyPrefix() + ":confirm:" + token;
    }
}
