package com.ruoyi.base.agent.core;

import reactor.core.publisher.Flux;

/**
 * 框架无关的 Agent 执行接口。两个分支分别提供 Spring AI / AgentScope 实现，
 * 对外契约（事件、错误码、工具集）保持一致。
 */
public interface AgentOrchestrator {

    /** 实现标识：spring-ai / agentscope。 */
    String framework();

    /**
     * 返回冷流：订阅时才真正开始调用模型。
     * 事件顺序约定：META → (DELTA|THINKING|TOOL_CALL|TOOL_RESULT)* → USAGE → DONE/ERROR。
     */
    Flux<AgentEvent> stream(AgentInvocation invocation);

    /** 实际注册到框架的工具名，用于与目录做启动期一致性校验。 */
    default java.util.Set<String> registeredTools() {
        return java.util.Set.of();
    }

    /**
     * 清理某个会话在<b>框架侧</b>的模型上下文（记忆/状态）。
     *
     * <p>调用方是 {@code DELETE /api/v1/agent/sessions/{id}}：用户点"清空会话"时，
     * 只删 UI 历史而保留模型记忆会出现"历史清空了，再问一句模型还记得"的隐私问题，
     * 因此由适配层负责把框架内部状态一并清掉。</p>
     *
     * <p>默认空实现（便于新增框架时先跑通再补清理逻辑）；实现方必须做租户隔离。</p>
     */
    default void clearSession(AgentPrincipal principal, String sessionId) {
        // 默认无框架侧状态
    }
}
