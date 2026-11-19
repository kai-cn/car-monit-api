package com.ruoyi.base.agent.agentscope;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 单次请求的工具调用预算（AgentScope 版）。
 *
 * <p>AgentScope 的 {@code ReActAgent.maxIters} 限制的是“推理轮数”，一轮内模型可并行发起
 * 多个工具调用；本预算按“工具调用次数”硬计数，两者叠加可同时防住</p>
 * <ul>
 *   <li>轮数爆炸（每轮只调 1 个工具、无限循环）；</li>
 *   <li>单轮扇出爆炸（一次返回 N 个 tool_call）。</li>
 * </ul>
 *
 * <p>与 Spring AI 分支的 {@code ToolBudget} 语义保持一致，便于两分支行为对比。</p>
 */
public class AgentScopeToolBudget {

    private final int max;
    private final AtomicInteger used = new AtomicInteger();

    public AgentScopeToolBudget(int max) {
        this.max = Math.max(1, max);
    }

    public boolean tryUse() {
        return used.incrementAndGet() <= max;
    }

    public int used() {
        return used.get();
    }

    public int max() {
        return max;
    }
}
