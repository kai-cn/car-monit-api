package com.ruoyi.base.task;

import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnGantryService;
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
import java.util.*;

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
     * 每天凌晨4点
     * 同步历史轨迹
     */
    @Scheduled(cron = "0 0 4 * * ?")
    private void syncHistroyTrack() {
        log.info("每天凌晨4点执行（同步历史轨迹）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        CarParaVO carParaVO = new CarParaVO();
        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            carParaVO.setCarlist(carlist);
            List<TrailInfo>  trailList = sysUtilService.carTrackQuery(carParaVO);
            // 车辆的轨迹
            Map<String, List<TrailInfo>> carTrailInfoMap = new HashMap<>();
            for (TrailInfo trailInfo : trailList) {
                ZdataTrailTracks tracksBo = trailInfo.getTracks();
                // List<TrailBo> josnList = trailInfo.getTrailList();
                String carNo = CommonUtil.isNull(tracksBo.getPlateKey());
                if (carTrailInfoMap.containsKey(carNo)){
                    List<TrailInfo> oldList  = carTrailInfoMap.get(carNo);
                    oldList.add(trailInfo);
                    carTrailInfoMap.put(carNo,oldList);
                }else{
                    List<TrailInfo> newList = new ArrayList<>();
                    newList.add(trailInfo);
                    carTrailInfoMap.put(carNo,newList);
                }
            }

            for (CarVO carVO : carlist) {
                String carNo = CommonUtil.isNull(carVO.getCarNo());
                String key = Constants.car_history_trail + carNo;
                if (carTrailInfoMap.containsKey(carNo)){
                    redisCache.setCacheObject(key, carTrailInfoMap.get(carNo));
                }else{
                    redisCache.setCacheObject(key, new ArrayList<TrailInfo>());
                }
            }
        }




        odsSzdnGantryService.saveGantryRedis(); // 门架信息
        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        log.info("每天凌晨4点执行（同步历史轨迹）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 每30分钟执行一次
     * 车俩实时轨迹同步
     */
    @Scheduled(cron = "0 0/20 * * * ?")
    private void syncCurrentTrackNo() {
        log.info("每20执行（同步历史轨迹没有记录的车辆）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));

        CarParaVO carParaVO = new CarParaVO();
        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {

            List<CarVO> noCarlist = new ArrayList<>();
            for (CarVO carVO :noCarlist) {
                String curCarNo = CommonUtil.isNull(carVO.getCarNo());
                String curkey = Constants.car_history_trail + curCarNo;
                List<TrailInfo> trailInfoList = redisCache.getCacheObject(curkey);
                if (null == trailInfoList){
                    noCarlist.add(carVO);
                }

            }

            if (noCarlist.size() > 0){
                carParaVO.setCarlist(noCarlist);
                List<TrailInfo>  trailList = sysUtilService.carTrackQuery(carParaVO);
                // 车辆的轨迹
                Map<String, List<TrailInfo>> carTrailInfoMap = new HashMap<>();
                for (TrailInfo trailInfo : trailList) {
                    ZdataTrailTracks tracksBo = trailInfo.getTracks();
                    // List<TrailBo> josnList = trailInfo.getTrailList();
                    String carNo = CommonUtil.isNull(tracksBo.getPlateKey());
                    if (carTrailInfoMap.containsKey(carNo)){
                        List<TrailInfo> oldList  = carTrailInfoMap.get(carNo);
                        oldList.add(trailInfo);
                        carTrailInfoMap.put(carNo,oldList);
                    }else{
                        List<TrailInfo> newList = new ArrayList<>();
                        newList.add(trailInfo);
                        carTrailInfoMap.put(carNo,newList);
                    }
                }

                for (CarVO carVO : carlist) {
                    String carNo = CommonUtil.isNull(carVO.getCarNo());
                    String key = Constants.car_history_trail + carNo;
                    if (carTrailInfoMap.containsKey(carNo)){
                        redisCache.setCacheObject(key, carTrailInfoMap.get(carNo));
                    }else{
                        redisCache.setCacheObject(key, new ArrayList<TrailInfo>());
                    }
                }
            }



        }
        log.info("每20执行（同步历史轨迹没有记录的车辆）结束 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }

}


