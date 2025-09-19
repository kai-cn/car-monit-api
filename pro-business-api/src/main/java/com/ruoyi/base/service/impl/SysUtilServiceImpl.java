package com.ruoyi.base.service.impl;


import com.alibaba.fastjson.JSON;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.base.service.IZdataTrailTracksService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 服务区基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class SysUtilServiceImpl implements ISysUtilService {


    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IZdataTrailTracksService zdataTrailTracksService;

    /**
     * 设置cache key
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String getCacheKey(String configKey)
    {
        return Constants.trail + configKey;
    }


    /**
     * 新增或者修改车辆信息
     *
     * @param sysUtil 基础类
     * @return 结果
     */
    public AjaxResult saveRedis(SysUtil sysUtil) {

       /* ZdataTrailTracks zdataTrailTracks = new ZdataTrailTracks();
        List<ZdataTrailTracks> trackList = zdataTrailTracksService.selectZdataTrailTracksList(zdataTrailTracks);
        for (ZdataTrailTracks trackBo : trackList) {
            redisCache.setCacheObject(getCacheKey(trackBo.getPlateKey()), trackBo.getTrailPoints());
        }*/

      /*  Collection<String> keys = redisCache.keys(Constants.trail + "*");
        Iterator<String> it = keys.iterator();
        while (it.hasNext()) {
            String key = it.next();
            String keyValue = redisCache.getCacheObject(key);
            List<TrailBo> josnList = JSON.parseArray(keyValue,TrailBo.class);
            System.out.println(key + "值---"+josnList);
        }*/
        return AjaxResult.success();
    }

    /**
     * 同步轨迹
     *
     * @param carParaVO carParaVO 车俩列表
     * @return 结果
     */
    public AjaxResult syncTrack(CarParaVO carParaVO) {
        List<CarVO> carlist = carParaVO.getCarlist();

        String BorderWeighingCaptureUUids = ""; // 省界称重
        String gantryCaptureUUids = ""; // 门架抓拍
        String provCaptureUUids = ""; // 省界抓拍
        String serviceAreaCaptureUUids = ""; // 服务区抓拍
        String stationCaptureUUids = ""; // 收费站抓拍

        Map<String, List<TrailBo>> mapCar = new HashMap<>();
        for (CarVO carVO : carlist) {
            String carNo = carVO.getCarNo();
            String keyValue = redisCache.getCacheObject(carNo);
            List<TrailBo> josnList = JSON.parseArray(keyValue, TrailBo.class);
            for (TrailBo trailBo :josnList){
                if (CommonUtil.isNull(trailBo.getStateType()).equals("BorderWeighingCapture")){
                    BorderWeighingCaptureUUids += trailBo.getPointUuid() +",";
                }
            }
            mapCar.put(carNo,josnList);

        }
        BorderWeighingCaptureUUids = CommonUtil.deleteEnd(BorderWeighingCaptureUUids);
        if (!BorderWeighingCaptureUUids.equals("")){

        }


        return AjaxResult.success(mapCar);
    }


}
