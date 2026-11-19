package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import org.springframework.stereotype.Component;

import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 并发闸门：限制同时进行的 Agent 请求数，避免模型配额/线程池被瞬时打满。
 * 与限流互补：限流控制速率，闸门控制并发。
 */
@Component
public class AgentConcurrencyLimiter {

    private final Semaphore semaphore;
    private final int max;
    private final AtomicInteger active = new AtomicInteger();

    public AgentConcurrencyLimiter(AgentProperties properties) {
        this.max = Math.max(1, properties.getMaxConcurrentRequests());
        this.semaphore = new Semaphore(max, true);
    }

    public boolean tryAcquire() {
        boolean acquired = semaphore.tryAcquire();
        if (acquired) {
            active.incrementAndGet();
        }
        return acquired;
    }

    public void release() {
        active.decrementAndGet();
        semaphore.release();
    }

    public int active() {
        return active.get();
    }

    public int max() {
        return max;
    }
}
