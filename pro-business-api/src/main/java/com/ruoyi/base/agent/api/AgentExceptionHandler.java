package com.ruoyi.base.agent.api;

import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Agent 端点异常映射：对外只暴露稳定错误码，不返回堆栈。
 */
@Slf4j
@RestControllerAdvice(basePackages = "com.ruoyi.base.agent.api")
public class AgentExceptionHandler {

    @ExceptionHandler(AgentException.class)
    public ResponseEntity<Map<String, Object>> handle(AgentException e) {
        return ResponseEntity.status(e.getCode().httpStatus()).body(body(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String msg = fieldError == null ? "请求参数不合法"
                : fieldError.getField() + " " + fieldError.getDefaultMessage();
        return ResponseEntity.badRequest().body(body(AgentErrorCode.AGENT_BAD_REQUEST, msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleOther(Exception e) {
        log.error("[Agent] 未预期异常", e);
        return ResponseEntity.status(AgentErrorCode.AGENT_INTERNAL.httpStatus())
                .body(body(AgentErrorCode.AGENT_INTERNAL, AgentErrorCode.AGENT_INTERNAL.defaultMessage()));
    }

    private static Map<String, Object> body(AgentErrorCode code, String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("code", code.name());
        m.put("message", message == null ? code.defaultMessage() : message);
        m.put("retryable", code.retryable());
        return m;
    }
}
