package com.ruoyi.base.controller;

import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.*;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.text.SimpleDateFormat;
import java.util.*;

@RestController
@RequestMapping("/base/sysutilTest")
@Slf4j
public class SysTestController extends BaseController {

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
     * 车俩实时轨迹同步
     */
    @GetMapping(value = "/syncCurrentTrack")
    public void syncCurrentTrack() {
        log.info("每5分钟（同步当前轨迹轨迹）开始 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncTrack(new CarParaVO());
        log.info("每5分钟（同步当前轨迹轨迹）结束 " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 车俩实时轨迹同步
     */
    @GetMapping(value = "/syncBaseInfo")
    public void syncBaseInfo() {
        log.info("每天凌晨0点执行（同步基础信息）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        odsSzdnGantryService.saveGantryRedis(); // 门架信息：用于门架转名称收费流水列表
        odsSzdnGantryIpService.updateRedis();  // 门架ip redis
        odsSzdnTollStationIpService.updateRedis(); // 站ip redis
        zdataLocationDictService.updateRedis(); // 位置点信息
        dwdLcztFwqjcxxService.updateRedis(); // 服务区
        log.info("每天凌晨0点执行（同步基础信息）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 车俩实时轨迹同步
     */
    @GetMapping(value = "/syncHistroyTrack")
    public void syncHistroyTrack() {
        log.info("每天凌晨4点执行（同步历史轨迹）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

            log.info("同步车辆数量 " +  carlist.size());
            for (CarVO carVO : carlist) {
                String carNo = CommonUtil.isNull(carVO.getCarNo());
                if (CommonUtil.isNotBlank(carNo)){

                    // 车辆的轨迹
                    String historyKey = Constants.car_history_trail + carNo;
                    List<TrailInfo> trailList = new ArrayList<>();
                    Map<String,String> uuidMap = new HashMap<>();

                    CarParaVO carParaVO = new CarParaVO();
                    carParaVO.setCarNo(carNo);

                    // --- 同步时间存入到缓存 没有就是默认
                    String timeKey = Constants.car_sync_time + carNo;
                    String carSynctime = CommonUtil.isNull(redisCache.getCacheObject(timeKey));
                    if (carSynctime.equals("")){
                        carParaVO.setFlag("bannian");  // 默认查询半年的数据
                    }else{
                        // 同步时间查询
                        carParaVO.setFlag("yiyue");  // 默认查询1月
                    }

                    List<TrailInfo> newList = sysUtilService.carTrackQuery(carParaVO);
                    if (null != newList && newList.size() > 0) {
                        for (TrailInfo trailInfoRtn : newList) {
                            ZdataTrailTracks tracks = trailInfoRtn.getTracks();
                            List<TrailBo> tempTrailList = trailInfoRtn.getTrailList();
                            if (null != tracks && null != tempTrailList && tempTrailList.size() > 0) {
                                String uuid = CommonUtil.isNull(tracks.getUuid());
                                trailList.add(trailInfoRtn);
                                uuidMap.put(uuid,uuid);
                            }
                        }
                    }

                    List<TrailInfo> oldList = redisCache.getCacheObject(historyKey);
                    if (null != oldList && oldList.size() > 0) {
                        for (TrailInfo trailInfoRtn : oldList) {
                            ZdataTrailTracks tracks = trailInfoRtn.getTracks();
                            List<TrailBo> tempTrailList = trailInfoRtn.getTrailList();
                            if (null != tracks && null != tempTrailList && tempTrailList.size() > 0) {
                                String uuid = CommonUtil.isNull(tracks.getUuid());
                                if (!uuidMap.containsKey(uuid)){
                                    trailList.add(trailInfoRtn);
                                }
                            }
                        }
                    }


                    redisCache.setCacheObject(historyKey, trailList);

                    // --------同步时间
                    Date now = new Date();
                    String formattedDate = sdf.format(now);
                    redisCache.setCacheObject(timeKey, formattedDate);


                }
            }
        }
        log.info("每天凌晨4点执行（同步历史轨迹）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }


    /**
     * 车俩实时轨迹同步
     */
    @GetMapping(value = "/syncSuspiciousCar1")
    public void syncSuspiciousCar1() {
        log.info("每天凌晨1点执行（同步可疑车俩）开始 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        sysUtilService.syncSuspiciousCarQutaz(1, 1);
        log.info("每天凌晨1点执行（同步可疑车俩）结束 " +new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
    }



}
