package com.ruoyi.base.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.SchedulingConfigurer;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.scheduling.config.ScheduledTaskRegistrar;

/**
 * 定时任务配置类
 * 
 * 功能说明：
 * 1. 启用Spring定时任务功能
 * 2. 配置定时任务线程池，避免任务阻塞
 * 3. 设置合理的线程池大小和队列容量
 * 
 * 设计思路：
 * - 使用专用线程池执行定时任务，避免影响主线程
 * - 设置适当的线程数，根据任务类型调整
 * - 配置线程名称前缀，便于日志追踪
 */
@Slf4j
@Configuration
@EnableScheduling
public class SchedulingConfig implements SchedulingConfigurer {

    /**
     * 配置定时任务线程池
     * 
     * 思路：
     * 1. 创建ThreadPoolTaskScheduler作为定时任务执行器
     * 2. 设置线程池大小为10，可根据实际任务数量调整
     * 3. 设置线程名称前缀为"scheduler-"，便于日志追踪
     * 4. 配置等待任务完成后再关闭线程池
     * 
     * @param taskRegistrar 任务注册器
     */
    @Override
    public void configureTasks(ScheduledTaskRegistrar taskRegistrar) {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        
        // 设置线程池大小
        scheduler.setPoolSize(10);
        
        // 设置线程名称前缀
        scheduler.setThreadNamePrefix("scheduler-");
        
        // 设置等待所有任务完成后再关闭线程池
        scheduler.setWaitForTasksToCompleteOnShutdown(true);
        
        // 设置等待时间（秒）
        scheduler.setAwaitTerminationSeconds(60);
        
        // 初始化线程池
        scheduler.initialize();
        
        // 将线程池设置到任务注册器
        taskRegistrar.setTaskScheduler(scheduler);
        
        log.info("[定时任务配置] 线程池初始化完成，线程数: {}", scheduler.getPoolSize());
    }
}