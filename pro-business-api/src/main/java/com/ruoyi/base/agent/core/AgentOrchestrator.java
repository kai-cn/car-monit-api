package com.ruoyi.base.agent.core;

import reactor.core.publisher.Flux;

/**
 * 框架无关的 Agent 执行接口（<b>整个 Agent 链路的总纲，建议从这里开始读代码</b>）。
 *
 * <p>两个分支分别提供 Spring AI / AgentScope 实现，对外契约（事件、错误码、工具集）保持一致。</p>
 *
 * <h2>它在链路中的位置</h2>
 * <pre>
 * AgentChatController（HTTP/SSE 出口，管连接与心跳）
 *        ↓  调用
 * AgentOrchestrator（本接口：一次"对话请求"的生命周期）
 *        ↓  内部循环
 * 大模型 ⇄ 工具（AgentToolService，查库/查 ES/查知识库）
 * </pre>
 *
 * <h2>AI 概念：什么是 Orchestrator（编排器）</h2>
 * <p>大模型本身只会"生成文本"，不会查数据库。所谓 Agent（智能体），本质是让模型输出一个
 * <b>结构化的"我要调用 xx 工具、参数是 yy"</b>，由宿主程序真正去执行，再把结果塞回模型，
 * 模型据此决定"继续调工具"还是"给出最终回答"。这个"调模型 → 执行工具 → 再调模型"的循环
 * 叫 <b>ReAct（Reasoning + Acting）</b>。编排器就是跑这个循环的地方，并且负责：</p>
 * <ul>
 *   <li>把模型输出翻译成 SSE 事件（前端才能边生成边显示）；</li>
 *   <li>控制循环次数与工具调用预算（防止模型"无限查库"烧钱）；</li>
 *   <li>把异常统一收敛成 {@link AgentErrorCode}，前端只认一套错误码。</li>
 * </ul>
 *
 * <p>【Java 8+ 说明】返回值用 Reactor 的 {@link Flux}（响应式流）：它是"0..N 个事件的异步序列"，
 * 与 SSE 的"持续推送"天然对应。{@code Flux} 是<b>冷流</b>——不订阅就什么都不发生，
 * 订阅才开始调模型；这也让我们能把"取消"（用户关页面）表达成 {@code Disposable.dispose()}。
 * 若你没接触过 Reactor，可把它理解为"支持背压的 {@code Stream} + 异步回调"。</p>
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
