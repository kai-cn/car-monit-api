package com.ruoyi.base.task;

import com.ruoyi.base.service.ISysUtilService;
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
    private ISysUtilService sysUtilService;



    /**
     * 每天凌晨1点
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 1 * * ?")
    private void syncSuspiciousCar1() {
        log.info("每天凌晨1点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(1, 10);
        log.info("每天凌晨1点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }



    /**
     * 每天凌晨1点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 1 * * ?")
    private void syncSuspiciousCar2() {
        log.info("每天凌晨1点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(11, 20);
        log.info("每天凌晨1点15点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨1点30
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 30 1 * * ?")
    private void syncSuspiciousCar3() {
        log.info("每天凌晨1点30执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(21, 30);
        log.info("每天凌晨1点30点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨1点45
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 45 1 * * ?")
    private void syncSuspiciousCar4() {
        log.info("每天凌晨1点45执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(31, 40);
        log.info("每天凌晨1点45点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨2
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 2 * * ?")
    private void syncSuspiciousCar5() {
        log.info("每天凌晨2点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(41, 50);
        log.info("每天凌晨2点点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 2 * * ?")
    private void syncSuspiciousCar6() {
        log.info("每天凌晨2点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(51, 60);
        log.info("每天凌晨2点15点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点30
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 30 2 * * ?")
    private void syncSuspiciousCar7() {
        log.info("每天凌晨2点30执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(61, 70);
        log.info("每天凌晨2点30点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点45
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 45 2 * * ?")
    private void syncSuspiciousCar8() {
        log.info("每天凌晨2点45执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(71, 80);
        log.info("每天凌晨2点45点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨3点
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 3 * * ?")
    private void syncSuspiciousCar9() {
        log.info("每天凌晨3点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(81, 90);
        log.info("每天凌晨3点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨3点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 3 * * ?")
    private void syncSuspiciousCar10() {
        log.info("每天凌晨3点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(91, 100);
        log.info("每天凌晨3点15执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


}


