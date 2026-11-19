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
}
