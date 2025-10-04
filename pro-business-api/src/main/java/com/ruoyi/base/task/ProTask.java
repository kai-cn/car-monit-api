package com.ruoyi.base.task;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.domain.ZdataTrailTracks;
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
import java.util.List;
import java.util.Map;

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

    @Autowired
    private ISysUtilService sysUtilService;

    /**
     * 同步可疑车俩: 0 0/3 * * * ?
     */
    @Scheduled(cron = "0 0 1 * * ?")
    private void syncSuspiciousCar() {
        log.info("每一天凌晨1点执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        sysUtilService.syncSuspiciousCarQutaz(1, 10);

        log.info("每一天凌晨1点执行（同步可疑车俩），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

    /**
     * 同步轨迹
     */
    @Scheduled(cron = "0 0 2 * * ?")
    private void syncTrack() {
        log.info("每一天凌晨2点执行（同步轨迹），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));



        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        log.info("每一天凌晨2点执行（同步轨迹），间隔1天执行一次 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


