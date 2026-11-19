package com.ruoyi.base.agent.core;

/**
 * 线程安全的事件出口。框架适配层与工具层都通过它向 SSE 写事件，
 * 具体实现负责背压与 seq 递增。
 */
@FunctionalInterface
public interface AgentEventSink {

    void emit(AgentEvent event);

    default void delta(String text) {
        if (text != null && !text.isEmpty()) {
            emit(AgentEvent.delta(0, text));
        }
    }
}
