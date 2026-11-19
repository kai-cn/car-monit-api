package com.ruoyi.base.agent.core;

import org.springframework.http.HttpStatus;

/**
 * Agent 错误码。错误码同时出现在 HTTP 状态、SSE error 事件和审计日志中，
 * 前端按 code 做稳定分支，不依赖 message 文案。
 */
public enum AgentErrorCode {

    AGENT_DISABLED(HttpStatus.SERVICE_UNAVAILABLE, false, "Agent 能力未开启"),
    AGENT_UNAUTHORIZED(HttpStatus.UNAUTHORIZED, false, "未授权访问"),
    AGENT_BAD_REQUEST(HttpStatus.BAD_REQUEST, false, "请求参数不合法"),
    AGENT_PROMPT_REJECTED(HttpStatus.BAD_REQUEST, false, "问题包含不被允许的指令"),
    AGENT_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, true, "请求过于频繁，请稍后再试"),
    AGENT_BUSY(HttpStatus.TOO_MANY_REQUESTS, true, "当前咨询人数较多，请稍后再试"),
    AGENT_SESSION_NOT_FOUND(HttpStatus.NOT_FOUND, false, "会话不存在或已过期"),
    AGENT_CONFIRM_REQUIRED(HttpStatus.CONFLICT, false, "该操作需要二次确认"),
    AGENT_CONFIRM_INVALID(HttpStatus.CONFLICT, false, "确认令牌无效或已过期"),
    AGENT_FORBIDDEN(HttpStatus.FORBIDDEN, false, "无权执行该操作"),
    AGENT_MODEL_TIMEOUT(HttpStatus.GATEWAY_TIMEOUT, true, "模型响应超时，请稍后重试"),
    AGENT_MODEL_ERROR(HttpStatus.BAD_GATEWAY, true, "模型服务暂不可用"),
    AGENT_MAX_ITERS(HttpStatus.OK, false, "工具调用轮数已达上限"),
    AGENT_TOOL_ERROR(HttpStatus.OK, false, "工具执行失败"),
    AGENT_CIRCUIT_OPEN(HttpStatus.SERVICE_UNAVAILABLE, true, "模型熔断中，请稍后重试"),
    AGENT_INTERNAL(HttpStatus.INTERNAL_SERVER_ERROR, false, "服务内部错误");

    private final HttpStatus httpStatus;
    private final boolean retryable;
    private final String defaultMessage;

    AgentErrorCode(HttpStatus httpStatus, boolean retryable, String defaultMessage) {
        this.httpStatus = httpStatus;
        this.retryable = retryable;
        this.defaultMessage = defaultMessage;
    }

    public HttpStatus httpStatus() {
        return httpStatus;
    }

    public boolean retryable() {
        return retryable;
    }

    public String defaultMessage() {
        return defaultMessage;
    }
}
