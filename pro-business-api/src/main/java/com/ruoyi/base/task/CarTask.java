package com.ruoyi.base.task;

import com.ruoyi.base.service.ISysUtilService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.text.SimpleDateFormat;
import java.util.Date;

@Component
@EnableScheduling
@Slf4j
public class CarTask {


    @Autowired
    private ISysUtilService sysUtilService;

    @Resource
    private ThreadPoolTaskExecutor threadTaskExecutor;



    /**
     * 每天凌晨1点
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 1 * * ?")
    private void syncSuspiciousCar1() {
        log.info("每天凌晨1点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 1; i < 11; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨1点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }



    /**
     * 每天凌晨1点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 1 * * ?")
    private void syncSuspiciousCar2() {
        log.info("每天凌晨1点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 11; i < 21; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨1点15点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨1点30
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 30 1 * * ?")
    private void syncSuspiciousCar3() {
        log.info("每天凌晨1点30执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 21; i < 31; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨1点30点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨1点45
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 45 1 * * ?")
    private void syncSuspiciousCar4() {
        log.info("每天凌晨1点45执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 31; i < 41; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨1点45点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨2
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 2 * * ?")
    private void syncSuspiciousCar5() {
        log.info("每天凌晨2点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 41; i < 51; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨2点点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 2 * * ?")
    private void syncSuspiciousCar6() {
        log.info("每天凌晨2点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 51; i < 61; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨2点15点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点30
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 30 2 * * ?")
    private void syncSuspiciousCar7() {
        log.info("每天凌晨2点30执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 61; i < 71; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨2点30点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨2点45
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 45 2 * * ?")
    private void syncSuspiciousCar8() {
        log.info("每天凌晨2点45执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 71; i < 81; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨2点45点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨3点
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 0 3 * * ?")
    private void syncSuspiciousCar9() {
        log.info("每天凌晨3点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 81; i < 91; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨3点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨3点15
     * 同步可疑车俩:
     */
    @Scheduled(cron = "0 15 3 * * ?")
    private void syncSuspiciousCar10() {
        log.info("每天凌晨3点15执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        for (int i = 91; i < 101; i++) {
            int finalI = i;
            threadTaskExecutor.execute(() -> {
                sysUtilService.syncSuspiciousCarQutaz(finalI, finalI);
            });
        }
        log.info("每天凌晨3点15执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 每天凌晨3点45
     * 同步可疑车俩: 门架抓拍流水 和 获取门架交易流水 对比
     */
    @Scheduled(cron = "0 45 3 * * ?")
    private void syncSuspiciousCar() {
        log.info("每天凌晨3点45执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.separateSnapshotFlowTimeList();
        log.info("每天凌晨3点45执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }



 /*   *//**
     * 每天凌晨4点30
     * 同步可疑车俩: 轨迹点和门架流水 找到可疑车辆 并放到redis中
     *//*
    @Scheduled(cron = "0 30 4 * * ?")
    private void syncSuspiciousCarRedis() {
        log.info("每天凌晨4点30执行（同步可疑车辆到redis）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.separateUnfiitingList();
        log.info("每天凌晨4点30执行（同步可疑车辆到redis）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    *//**
     * 每天凌晨6点30
     * 同步可疑车俩: 同步可疑车辆到数据库
     *//*
    @Scheduled(cron = "0 30 6 * * ?")
    private void syncSuspiciousCarDB() {
        log.info("每天凌晨6点30执行（同步可疑车辆到redis）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarDB();
        log.info("每天凌晨6点30执行（同步可疑车辆到redis）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }*/


}


