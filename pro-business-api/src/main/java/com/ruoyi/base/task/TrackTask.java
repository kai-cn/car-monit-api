package com.ruoyi.base.task;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.domain.TrailInfo;
import com.ruoyi.base.domain.ZdataTrailTracks;
import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnTollStationIpService;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
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
        log.info("每三分钟（同步当前轨迹轨迹）开始 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        Map<ZdataTrailTracks, List<TrailBo>> rtnCar = sysUtilService.syncTrack(new CarParaVO());
        if (null != rtnCar) {
            for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : rtnCar.entrySet()) {
                ZdataTrailTracks tracksBo = entry.getKey();
                List<TrailBo> josnList = entry.getValue();

                String carNo = CommonUtil.isNull(tracksBo.getPlateKey());
                TrailInfo trailInfo = new TrailInfo();
                trailInfo.setTrailUuid(carNo);
                trailInfo.setTracks(tracksBo);
                trailInfo.setTrailList(josnList);

                String key = Constants.car_curent_trail + carNo;
                redisCache.setCacheObject(key, trailInfo);

            }

        }
        log.info("每三分钟（同步当前轨迹轨迹）结束 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
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


