package com.ruoyi.base.agent.config;

import com.ruoyi.base.agent.api.AgentSecurityInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.TaskExecutor;
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
        scheduler.setPoolSize(2);
        scheduler.setThreadNamePrefix("agent-heartbeat-");
        scheduler.setWaitForTasksToCompleteOnShutdown(false);
        scheduler.setRemoveOnCancelPolicy(true);
        scheduler.initialize();
        return scheduler;
    }

    @org.springframework.context.annotation.Bean("agentExecutor")
    public TaskExecutor agentExecutor() {
        org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor executor =
                new org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor();
        executor.setCorePoolSize(Math.max(4, properties.getMaxConcurrentRequests() / 4));
        executor.setMaxPoolSize(Math.max(8, properties.getMaxConcurrentRequests()));
        executor.setQueueCapacity(256);
        executor.setThreadNamePrefix("agent-exec-");
        executor.initialize();
        return executor;
    }
}
