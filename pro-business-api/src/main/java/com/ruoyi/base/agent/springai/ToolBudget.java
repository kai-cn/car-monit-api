package com.ruoyi.base.agent.springai;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 单次请求的工具调用预算。Spring AI 的默认 ToolCallingManager 会一直循环到模型不再调用工具，
 * 这里用回调侧的硬计数兜底，防止模型陷入工具循环消耗配额。
 */
public class ToolBudget {

    private final int max;
    private final AtomicInteger used = new AtomicInteger();

    public ToolBudget(int max) {
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
