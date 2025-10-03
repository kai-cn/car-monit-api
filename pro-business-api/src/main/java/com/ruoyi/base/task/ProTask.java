package com.ruoyi.base.task;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.text.SimpleDateFormat;
import java.util.Date;

@Component
@EnableScheduling
@Slf4j
public class ProTask {

    /**
     * 同步可疑车俩
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
        log.info("每一天凌晨执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));


        log.info("每一天凌晨执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


