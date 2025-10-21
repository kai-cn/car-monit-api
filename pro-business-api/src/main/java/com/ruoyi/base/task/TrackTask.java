package com.ruoyi.base.task;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.CarVO;
import com.ruoyi.base.domain.TrailInfo;
import com.ruoyi.base.service.*;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

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

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    @Autowired
    private IZdataLocationDictService zdataLocationDictService;

    @Autowired
    private IDwdLcztFwqjcxxService dwdLcztFwqjcxxService;


    /**
     * 每三分钟执行一次
     * 车俩实时轨迹同步
     */
    @Scheduled(cron = "0 0/5 * * * ?")
    private void syncCurrentTrack() {
        log.info("每5分钟（同步当前轨迹轨迹）开始 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncTrack(new CarParaVO());
        log.info("每5分钟（同步当前轨迹轨迹）结束 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨0点
     * 同步基础信息
     */
    @Scheduled(cron = "0 0 0 * * ?")
    private void syncBaseInfo() {
        log.info("每天凌晨0点执行（同步基础信息）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        odsSzdnGantryService.saveGantryRedis(); // 门架信息：用于门架转名称收费流水列表
        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        zdataLocationDictService.updateRedis(); // 位置点信息
        dwdLcztFwqjcxxService.updateRedis(); // 服务区
        log.info("每天凌晨0点执行（同步基础信息）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每天凌晨4点
     * 同步历史轨迹
     */
    @Scheduled(cron = "0 0 4 * * ?")
    private void syncHistroyTrack() {
        log.info("每天凌晨4点执行（同步历史轨迹）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            log.info("同步车辆数量 " +  carlist.size());
            for (CarVO carVO : carlist) {
                String carNo = CommonUtil.isNull(carVO.getCarNo());
                if (CommonUtil.isNotBlank(carNo)){
                    CarParaVO carParaVO = new CarParaVO();
                    carParaVO.setCarNo(carNo);
                    List<TrailInfo> trailList = sysUtilService.carTrackQuery(carParaVO);
                    // 车辆的轨迹
                    String key = Constants.car_history_trail + carNo;
                    redisCache.setCacheObject(key, trailList);
                }
            }
        }
        log.info("每天凌晨4点执行（同步历史轨迹）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每30分钟执行一次
     * 同步历史轨迹没有记录的车辆
     */
    @Scheduled(cron = "0 0/30 * * * ?")
    private void syncCurrentTrackNo() {
        log.info("每30执行（同步历史轨迹没有记录的车辆）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            List<CarVO> noCarlist = new ArrayList<>();
            for (CarVO carVO : carlist) {
                String curCarNo = CommonUtil.isNull(carVO.getCarNo());
                String curkey = Constants.car_history_trail + curCarNo;
                List<TrailInfo> trailInfoList = redisCache.getCacheObject(curkey);
                if (null == trailInfoList) {
                    noCarlist.add(carVO);
                }
            }

            if (noCarlist.size() > 0){
                log.info("同步车辆数量 " +  noCarlist.size());
                for (CarVO carVO : noCarlist) {
                    String carNo = CommonUtil.isNull(carVO.getCarNo());
                    if (CommonUtil.isNotBlank(carNo)){
                        CarParaVO carParaVO = new CarParaVO();
                        carParaVO.setCarNo(carNo);
                        List<TrailInfo> trailList = sysUtilService.carTrackQuery(carParaVO);
                        // 车辆的轨迹
                        String key = Constants.car_history_trail + carNo;
                        redisCache.setCacheObject(key, trailList);
                    }
                }
            }
        }
        log.info("每30执行（同步历史轨迹没有记录的车辆）结束 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


