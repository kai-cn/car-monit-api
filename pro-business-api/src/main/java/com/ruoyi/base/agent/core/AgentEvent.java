package com.ruoyi.base.agent.core;

import lombok.Getter;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Agent 流式事件——前后端之间唯一的"合同"。
 *
 * <p>SSE 的 {@code event} 名即 {@link #type}，{@code data} 为 {@link #payload} 的 JSON。</p>
 *
 * <h2>给只写过 CRUD 的 Java 开发者的 30 秒入门</h2>
 * <p>普通 HTTP 接口是"一问一答"：客户端等到服务端把整个结果算完才拿到响应。但大模型是
 * <b>一个 token 一个 token 往外吐字</b>的（token 可以粗略理解为"词片"，1 个汉字约 1~2 token），
 * 一次回答可能要 3~10 秒。如果等全部生成完再返回，用户会盯着空白屏。所以改用
 * <b>SSE（Server-Sent Events）</b>：一条 HTTP 长连接上，服务端可以持续往客户端推小段文本，
 * 浏览器用 {@code EventSource} 或 fetch 流式读取即可实现"打字机效果"。</p>
 *
 * <p>本类就是"一小段要推给前端的东西"。为什么不让框架直接推自己的事件？因为
 * <b>Spring AI 和 AgentScope 的事件模型完全不同</b>（前者是 ChatResponse 增量，后者是 31 种
 * {@code AgentEventType}）。把两者都翻译成本类的 9 个常量（8 类业务事件 + 心跳），
 * 前端就只写一套解析逻辑，将来换框架不用改页面——这就是"适配器模式"在 AI 场景的用处。</p>
 *
 * <h2>事件顺序（前端可以依赖的不变式）</h2>
 * <pre>
 * meta → (delta | thinking | tool_call | tool_result)* → usage → done | error
 * </pre>
 * <p>{@code seq} 是单条流的自增序号（从 1 开始），用于前端排序、去重和"断线后判断丢了哪一段"。
 * 并发下不要用时间戳排序：同一毫秒内可能到达多个事件。</p>
 *
 * <p>【Java 8+ 说明】本类刻意保持为普通 POJO + 静态工厂，而不是 {@code record}。
 * 理由不是"record 做不到"（record 同样可以带静态工厂和附加构造器，Jackson 也支持），
 * 而是：① 事件对象由框架侧高频创建、字段语义固定，用 record 的 {@code equals/hashCode}
 * 没有收益，反而在把它放进 {@code Set} 去重时容易误用；② Lombok 的 {@code @Getter}
 * 与既有序列化配置保持一致，避免在 9 个工厂方法之外再引入一套访问器风格。</p>
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
