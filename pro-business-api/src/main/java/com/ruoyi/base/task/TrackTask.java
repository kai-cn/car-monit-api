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
public class TrackTask {

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IOdsSzdnGantryIpService odsSzdnGantryIpService;

    @Autowired
    private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;

    @Autowired
    private ISysUtilService sysUtilService;


    /**
     * 每三分钟执行一次
     * 车俩实时轨迹同步
     */
    @Scheduled(cron = "0 0/3 * * * ?")
    private void syncCurrentTrack() {
        log.info("每三分钟（同步当前轨迹轨迹）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        log.info("每三分钟（同步当前轨迹轨迹）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨3点
     * 同步历史轨迹
     */
    @Scheduled(cron = "0 0 4 * * ?")
    private void syncHistroyTrack() {
        log.info("每天凌晨4点执行（同步历史轨迹）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        log.info("每天凌晨4点执行（同步历史轨迹）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


