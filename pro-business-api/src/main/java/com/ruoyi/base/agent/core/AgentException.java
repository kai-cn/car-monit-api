package com.ruoyi.base.agent.core;

/**
 * Agent 业务异常：携带稳定错误码与可重试标记。
 */
public class AgentException extends RuntimeException {

    private final AgentErrorCode code;

    public AgentException(AgentErrorCode code) {
        super(code.defaultMessage());
        this.code = code;
    }

    public AgentException(AgentErrorCode code, String message) {
        super(message == null || message.isBlank() ? code.defaultMessage() : message);
        this.code = code;
    }

    public AgentException(AgentErrorCode code, String message, Throwable cause) {
        super(message == null || message.isBlank() ? code.defaultMessage() : message, cause);
        this.code = code;
    }

    public AgentErrorCode getCode() {
        return code;
    }

    public static AgentException badRequest(String message) {
        return new AgentException(AgentErrorCode.AGENT_BAD_REQUEST, message);
    }

    public static AgentException forbidden(String message) {
        return new AgentException(AgentErrorCode.AGENT_FORBIDDEN, message);
    }
}
