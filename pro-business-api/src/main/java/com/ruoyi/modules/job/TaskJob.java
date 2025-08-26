package com.ruoyi.modules.job;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.stereotype.Component;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/7/27 19:04
 * @Return
 */
@Slf4j
@Component
@EnableScheduling
public class TaskJob{

    // 每5分钟执行一次
    /*@Scheduled(cron = "0 0/5 * * * ?")
    public void syncTask(){
        IDhbApiService dhbApiService = SpringContextHolder.getBean(IDhbApiService.class);
        dhbApiService.syngOrderStatus();
    }*/
}
