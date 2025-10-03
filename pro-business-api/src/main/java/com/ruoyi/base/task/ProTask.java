package com.ruoyi.base.task;

import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnTollStationIpService;
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
public class ProTask {

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IOdsSzdnGantryIpService odsSzdnGantryIpService;

    @Autowired
    private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;

    /**
     * 同步可疑车俩:0/30000 * * * *
     */
    @Scheduled(cron = "0 0 0 * * ?")
    private void syncSuspiciousCar() {
        log.info("每一天凌晨执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));


        log.info("每一天凌晨执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 同步轨迹
     */
    @Scheduled(cron = "0 0 1 * * ?")
    private void syncTrack() {
        log.info("每一天凌晨执行（同步轨迹），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));



        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        log.info("每一天凌晨执行（同步轨迹），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


