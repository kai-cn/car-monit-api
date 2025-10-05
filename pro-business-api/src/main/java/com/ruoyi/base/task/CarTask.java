package com.ruoyi.base.task;

import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnTollStationIpService;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.core.redis.RedisCache;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.text.SimpleDateFormat;
import java.util.Date;

@Component
@EnableScheduling
@Slf4j
public class CarTask {

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IOdsSzdnGantryIpService odsSzdnGantryIpService;

    @Autowired
    private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;

    @Autowired
    private ISysUtilService sysUtilService;




    /**
     * 每天凌晨1点
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 1 * * ?")
    private void syncSuspiciousCar() {
        log.info("每天凌晨1点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(1, 10);
        log.info("每天凌晨1点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }





}


