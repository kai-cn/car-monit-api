package com.ruoyi.base.agent.core;

import lombok.Getter;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Agent 流式事件。SSE 的 {@code event} 名即 {@link #type}，{@code data} 为 {@link #payload} 的 JSON。
 */
@Getter
public class AgentEvent {

    public static final String META = "meta";
    public static final String DELTA = "delta";
    public static final String THINKING = "thinking";
    public static final String TOOL_CALL = "tool_call";
    public static final String TOOL_RESULT = "tool_result";
    public static final String USAGE = "usage";
    public static final String DONE = "done";
    public static final String ERROR = "error";
    public static final String HEARTBEAT = "heartbeat";

    private final String type;
    private final long seq;
    private final Map<String, Object> payload;

    private AgentEvent(String type, long seq, Map<String, Object> payload) {
        this.type = type;
        this.seq = seq;
        this.payload = payload == null ? new LinkedHashMap<>() : payload;
    }

    public static AgentEvent of(String type, long seq, Map<String, Object> payload) {
        return new AgentEvent(type, seq, payload);
    }

    public static AgentEvent meta(long seq, Map<String, Object> payload) {
        return new AgentEvent(META, seq, payload);
    }

    public static AgentEvent delta(long seq, String text) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("text", text);
        return new AgentEvent(DELTA, seq, p);
    }

    public static AgentEvent thinking(long seq, String text) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("text", text);
        return new AgentEvent(THINKING, seq, p);
    }

    public static AgentEvent toolCall(long seq, String id, String name, Object arguments) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("id", id);
        p.put("name", name);
        p.put("arguments", arguments);
        return new AgentEvent(TOOL_CALL, seq, p);
    }

    public static AgentEvent toolResult(long seq, String id, String name, String status,
                                        String summary, long latencyMs) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("id", id);
        p.put("name", name);
        p.put("status", status);
        p.put("summary", summary);
        p.put("latencyMs", latencyMs);
        return new AgentEvent(TOOL_RESULT, seq, p);
    }

    public static AgentEvent usage(long seq, Map<String, Object> usage) {
        return new AgentEvent(USAGE, seq, usage);
    }

    public static AgentEvent done(long seq, Map<String, Object> payload) {
        return new AgentEvent(DONE, seq, payload);
    }

    public static AgentEvent error(long seq, AgentErrorCode code, String message) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("code", code.name());
        p.put("message", message == null ? code.defaultMessage() : message);
        p.put("retryable", code.retryable());
        return new AgentEvent(ERROR, seq, p);
    }

    public static AgentEvent heartbeat(long seq) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("ts", System.currentTimeMillis());
        return new AgentEvent(HEARTBEAT, seq, p);
    }
}
