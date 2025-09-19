package com.ruoyi.base.service.impl;


import com.alibaba.fastjson.JSON;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.*;
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


    public static final String BORDER_WEIGHING_CAPTURE = "BorderWeighingCapture";
    public static final String GANTRY_CAPTURE = "GantryCapture";
    public static final String PROV_CAPTURE = "ProvCapture";
    public static final String SERVICE_AREA_CAPTURE = "ServiceAreaCapture";
    public static final String STATION_CAPTURE = "StationCapture";
    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IZdataTrailTracksService zdataTrailTracksService;
    @Autowired
    private IOdsSzdnProvinceBorderVehicleWeightNewstructureService provinceBorderVehicleWeightNewstructureService;
    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowAddcodeService;
    @Autowired
    private IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService provcaptureAddcodeService;
    @Autowired
    private IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService stationcaptureAddcodeService;


    /**
     * 设置cache key
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String getCacheKey(String configKey) {
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

        String borderWeighingCaptureUUids = ""; // 省界称重
        String gantryCaptureUUids = ""; // 门架抓拍
        String provCaptureUUids = ""; // 省界抓拍
        String serviceAreaCaptureUUids = ""; // 服务区抓拍
        String stationCaptureUUids = ""; // 收费站抓拍

        Map<String, List<TrailBo>> mapCar = new HashMap<>();
        for (CarVO carVO : carlist) {
            String carNo = carVO.getCarNo();
            String keyValue = redisCache.getCacheObject(carNo);
            List<TrailBo> josnList = JSON.parseArray(keyValue, TrailBo.class);
            for (TrailBo trailBo : josnList) {
                String stateType = CommonUtil.isNull(trailBo.getStateType());
                switch (stateType) {
                    case BORDER_WEIGHING_CAPTURE:
                        borderWeighingCaptureUUids += trailBo.getPointUuid() +",";
                        break;
                    case GANTRY_CAPTURE:
                        gantryCaptureUUids += trailBo.getPointUuid() +",";
                        break;
                    case PROV_CAPTURE:
                        provCaptureUUids += trailBo.getPointUuid() +",";
                        break;
                    case SERVICE_AREA_CAPTURE:
                        serviceAreaCaptureUUids += trailBo.getPointUuid() +",";
                        break;
                    case STATION_CAPTURE:
                        stationCaptureUUids += trailBo.getPointUuid() +",";
                        break;
                }
            }
            mapCar.put(carNo, josnList);

        }
        Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> weightNewstructureMap = new HashMap<>();
        Map<String, OdsRtSzdnSnapshotFlowAddcode> snapshotFlowAddcodeMap = new HashMap<>();
        Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> provcaptureAddcodeMap = new HashMap<>();
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> stationcaptureAddcodeMap = new HashMap<>();

        borderWeighingCaptureUUids = CommonUtil.deleteEnd(borderWeighingCaptureUUids);
        if (!borderWeighingCaptureUUids.isEmpty()) {
            weightNewstructureMap = provinceBorderVehicleWeightNewstructureService.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(borderWeighingCaptureUUids);
        }
        gantryCaptureUUids = CommonUtil.deleteEnd(gantryCaptureUUids);
        if (!gantryCaptureUUids.isEmpty()) {
            snapshotFlowAddcodeMap = snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(gantryCaptureUUids);
        }
        provCaptureUUids = CommonUtil.deleteEnd(provCaptureUUids);
        if (!provCaptureUUids.isEmpty()) {
            provcaptureAddcodeMap = provcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(provCaptureUUids);
        }
        stationCaptureUUids = CommonUtil.deleteEnd(stationCaptureUUids);
        if (!stationCaptureUUids.isEmpty()) {
            stationcaptureAddcodeMap = stationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(stationCaptureUUids);
        }


        for (Map.Entry<String, List<TrailBo>> entry : mapCar.entrySet()) {
            List<TrailBo> trailBoList = entry.getValue();
            for (TrailBo trailBo : trailBoList) {
                String stateType = CommonUtil.isNull(trailBo.getStateType());
                String pointUuid = trailBo.getPointUuid();
                switch (stateType) {
                    case BORDER_WEIGHING_CAPTURE:
                        OdsSzdnProvinceBorderVehicleWeightNewstructure obj1 = weightNewstructureMap.get(pointUuid);
                        if (obj1 != null) {
                            trailBo.setPointJosn(JSON.toJSONString(obj1));
                        }
                        break;
                    case GANTRY_CAPTURE:
                        OdsRtSzdnSnapshotFlowAddcode obj2 = snapshotFlowAddcodeMap.get(pointUuid);
                        if (obj2 != null) {
                            trailBo.setPointJosn(JSON.toJSONString(obj2));
                        }
                        break;
                    case PROV_CAPTURE:
                        OdsRtSzdnSnapshotFlowProvcaptureAddcode obj3 = provcaptureAddcodeMap.get(pointUuid);
                        if (obj3 != null) {
                            trailBo.setPointJosn(JSON.toJSONString(obj3));
                        }
                        break;
                    case SERVICE_AREA_CAPTURE:
                        break;
                    case STATION_CAPTURE:
                        OdsRtSzdnSnapshotFlowStationcaptureAddcode obj5 = stationcaptureAddcodeMap.get(pointUuid);
                        if (obj5 != null) {
                            trailBo.setPointJosn(JSON.toJSONString(obj5));
                        }
                        break;
                }
            }

        }

        return AjaxResult.success(mapCar);
    }


}
