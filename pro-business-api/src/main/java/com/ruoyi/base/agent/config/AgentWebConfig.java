package com.ruoyi.base.agent.config;

import com.ruoyi.base.agent.api.AgentSecurityInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Agent 公共配置：安全拦截器 + 心跳调度器。
 * 仅当 {@code traffic.agent.enabled=true} 时装配（控制器保留，用于返回 AGENT_DISABLED）。
 */
@Configuration
public class AgentWebConfig implements WebMvcConfigurer {

    private final AgentSecurityInterceptor securityInterceptor;
    private final AgentProperties properties;

    public AgentWebConfig(AgentSecurityInterceptor securityInterceptor, AgentProperties properties) {
        this.securityInterceptor = securityInterceptor;
        this.properties = properties;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(securityInterceptor)
                .addPathPatterns("/api/v1/agent/**")
                .order(0);
    }

    @org.springframework.context.annotation.Bean("agentTaskScheduler")
    public TaskScheduler agentTaskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        // 每条活跃 SSE 流都会在这里挂一个"每 heartbeat-interval 发一帧注释"的周期任务。
        // 池子太小（原为 2）时，只要有一个客户端读得慢、让 emitter.send 阻塞住，
        // 其余会话的心跳就会被排队拖住，表现为"某些页面莫名断流"。
        // 因此按并发上限给到 4~16 个线程：心跳任务本身极轻，不需要等于并发上限。
        int poolSize = Math.max(4, Math.min(16, properties.getMaxConcurrentRequests()));
        scheduler.setPoolSize(poolSize);
        scheduler.setThreadNamePrefix("agent-heartbeat-");
        scheduler.setWaitForTasksToCompleteOnShutdown(false);
        scheduler.setRemoveOnCancelPolicy(true);
        scheduler.initialize();
        return scheduler;
    }
}
