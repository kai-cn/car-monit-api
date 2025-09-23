package com.ruoyi.base.service.impl;


import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.*;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

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


    @Autowired
    private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;


    @Autowired
    private IOdsSzdnGantryIpService odsSzdnGantryIpService;


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
    public Map<String, List<TrailBo>> syncTrack(CarParaVO carParaVO) {
        List<CarVO> carlist = carParaVO.getCarlist();
        Map<String, List<TrailBo>> mapCar = new HashMap<>();
        if (null != carlist && carlist.size() > 0) {
            for (CarVO carVO : carlist) {
                String carNo = carVO.getCarNo();
                String keyValue = redisCache.getCacheObject(getCacheKey(carNo));
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                }
                mapCar.put(carNo, josnList); // 车牌号
            }
            return this.changeData(mapCar);
        } else {
            return mapCar;
        }
    }


    /**
     * 数据转换
     *
     * @param mapCar
     * @return 结果
     */
    public Map<String, List<TrailBo>> changeData(Map<String, List<TrailBo>> mapCar) {

        if (null == mapCar) {
            Map<String, List<TrailBo>> rtnHashMap = new HashMap<>();
            return rtnHashMap;
        }

        String borderWeighingCaptureUUids = ""; // 省界称重
        String gantryCaptureUUids = ""; // 门架抓拍
        String provCaptureUUids = ""; // 省界抓拍
        String serviceAreaCaptureUUids = ""; // 服务区抓拍
        String stationCaptureUUids = ""; // 收费站抓拍


        int countNum = 0;

        for (Map.Entry<String, List<TrailBo>> entry : mapCar.entrySet()) {
            List<TrailBo> josnList = entry.getValue();
            for (TrailBo trailBo : josnList) {
                trailBo.setPointFlag("0"); // 无数据
                trailBo.setLocationFlag("0");
                String stateType = CommonUtil.isNull(trailBo.getStateType());
                String pointUuid = trailBo.getPointUuid();
                switch (stateType) {
                    case BORDER_WEIGHING_CAPTURE:
                        // 省界称重
                        borderWeighingCaptureUUids += pointUuid + ",";
                        break;
                    case GANTRY_CAPTURE:
                        // 门架抓拍
                        gantryCaptureUUids += pointUuid + ",";
                        break;
                    case PROV_CAPTURE:
                        // 省界抓拍
                        provCaptureUUids += pointUuid + ",";
                        break;
                    case SERVICE_AREA_CAPTURE:
                        // 服务区抓拍
                        serviceAreaCaptureUUids += pointUuid + ",";
                        break;
                    case STATION_CAPTURE:
                        // 收费站抓拍
                        stationCaptureUUids += pointUuid + ",";
                        break;
                }
            }
            countNum++;
        }

        // 没有数据
        if (countNum == 0) {
            return mapCar;
        }

        // 省界称重
        Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> weightNewstructureMap = new HashMap<>();
        borderWeighingCaptureUUids = CommonUtil.deleteEnd(borderWeighingCaptureUUids);
        if (CommonUtil.isNotBlank(borderWeighingCaptureUUids)) {
            weightNewstructureMap = provinceBorderVehicleWeightNewstructureService.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(borderWeighingCaptureUUids);
        }

        // 门架抓拍
        Map<String, OdsRtSzdnSnapshotFlowAddcode> snapshotFlowAddcodeMap = new HashMap<>();
        gantryCaptureUUids = CommonUtil.deleteEnd(gantryCaptureUUids);
        if (CommonUtil.isNotBlank(gantryCaptureUUids)) {
            snapshotFlowAddcodeMap = snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(gantryCaptureUUids);
        }

        // 省界抓拍
        Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> provcaptureAddcodeMap = new HashMap<>();
        provCaptureUUids = CommonUtil.deleteEnd(provCaptureUUids);
        if (CommonUtil.isNotBlank(provCaptureUUids)) {
            provcaptureAddcodeMap = provcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(provCaptureUUids);
        }

        // 收费站抓拍
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> stationcaptureAddcodeMap = new HashMap<>();
        stationCaptureUUids = CommonUtil.deleteEnd(stationCaptureUUids);
        if (CommonUtil.isNotBlank(stationCaptureUUids)) {
            stationcaptureAddcodeMap = stationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(stationCaptureUUids);
        }

        // 收费站ip
        Map<String, OdsSzdnTollStationIp> szdnTollMap = odsSzdnTollStationIpService.selectStationIpMap();

        // 门架IP
        Map<String, OdsSzdnGantryIp> szdnGantryMap = odsSzdnGantryIpService.selectOdsSzdnGantryIpMap();


        for (Map.Entry<String, List<TrailBo>> entry : mapCar.entrySet()) {
            List<TrailBo> josnList = entry.getValue();

            int stationCount = 0;

            for (TrailBo trailBo : josnList) {

                // --------------抓拍信息
                String pointUuid = trailBo.getPointUuid();
                String locationCode = CommonUtil.isNull(trailBo.getLocationCode()); // 设备IP地址
                String stateType = CommonUtil.isNull(trailBo.getStateType());  // 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表

                // ----------位置信息
                String[] locationCodeStr = locationCode.split(":");
                String ip ="";
                String ipType = "";
                if (locationCodeStr.length > 1){
                    ip = CommonUtil.isNull(locationCodeStr[1]);
                }


                switch (stateType) {
                    case BORDER_WEIGHING_CAPTURE:
                        // 省界称重
                        if (weightNewstructureMap.containsKey(pointUuid)){
                            OdsSzdnProvinceBorderVehicleWeightNewstructure  borderWeighingCaptureBO = weightNewstructureMap.get(pointUuid);
                            trailBo.setBorderWeighingCaptureBO(borderWeighingCaptureBO);
                            trailBo.setPointFlag("1"); // 有数据

                            // 抓拍照片
                            String imagesStr = CommonUtil.isNull(borderWeighingCaptureBO.getWeighingImagesArry());
                            if (CommonUtil.isNotBlank(imagesStr)){
                                String imagesSrc = "";
                                JSONArray imgesJsonArray = JSON.parseArray(imagesStr);
                                for (int zz = 0; zz < imgesJsonArray.size(); zz++) {
                                    JSONObject imageTempJosn = imgesJsonArray.getJSONObject(zz);
                                    if (null !=imageTempJosn){
                                        String tempImageSrc = CommonUtil.isNull(imageTempJosn.getString("snapPicturePath"));
                                        if (CommonUtil.isNotBlank(tempImageSrc)){
                                            imagesSrc += tempImageSrc +",";
                                        }
                                    }
                                }
                                trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc)); // 抓拍照片
                            }
                        }
                        ipType = "gantryip";
                        break;
                    case GANTRY_CAPTURE:
                        // 门架抓拍
                        if (snapshotFlowAddcodeMap.containsKey(pointUuid)){
                            OdsRtSzdnSnapshotFlowAddcode  gantryCaptureBO = snapshotFlowAddcodeMap.get(pointUuid);
                            trailBo.setGantryCaptureBO(gantryCaptureBO);
                            trailBo.setPointFlag("1"); // 有数据

                            trailBo.setDevCode(gantryCaptureBO.getGantrycode()); // 设备编号
                            trailBo.setDevName(gantryCaptureBO.getGantryname());  // 设备名称
                            trailBo.setImagesArry(gantryCaptureBO.getSnappicturepath()); // 抓拍照片
                            trailBo.setLon(gantryCaptureBO.getLon()); // 经度
                            trailBo.setLat(gantryCaptureBO.getLat()); // 维度

                        }
                        ipType = "gantryip";
                        break;
                    case PROV_CAPTURE:
                        // 省界抓拍
                        if (provcaptureAddcodeMap.containsKey(pointUuid)){
                            String imagesSrc = "";
                            OdsRtSzdnSnapshotFlowProvcaptureAddcode  provCaptureBO = provcaptureAddcodeMap.get(pointUuid);
                            trailBo.setProvCaptureBO(provCaptureBO);
                            trailBo.setPointFlag("1"); // 有数据

                            // 车牌图路径
                            if (CommonUtil.isNotBlank(provCaptureBO.getPlateimage())){
                                imagesSrc += provCaptureBO.getPlateimage() +",";
                            }

                            // 车身图路径
                            if (CommonUtil.isNotBlank(provCaptureBO.getSideimage())){
                                imagesSrc += provCaptureBO.getSideimage() +",";
                            }

                            // 车头图路径
                            if (CommonUtil.isNotBlank(provCaptureBO.getHeadimage())){
                                imagesSrc += provCaptureBO.getHeadimage() +",";
                            }
                            trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc)); // 抓拍照片
                        }
                        ipType = "gantryip";
                        break;
                    case SERVICE_AREA_CAPTURE:
                        // 服务区抓拍
                        break;
                    case STATION_CAPTURE:
                        // 收费站抓拍
                        if (stationcaptureAddcodeMap.containsKey(pointUuid)){
                            OdsRtSzdnSnapshotFlowStationcaptureAddcode  stationCapture = stationcaptureAddcodeMap.get(pointUuid);
                            trailBo.setStationCapture(stationCapture);
                            trailBo.setPointFlag("1"); // 有数据

                            trailBo.setDevCode(stationCapture.getTollcode()); // 设备编号
                            trailBo.setDevName(stationCapture.getTollname());  // 设备名称
                            trailBo.setImagesArry(stationCapture.getSnappicturepath()); // 抓拍照片

                            if (stationCount == 0){
                                trailBo.setFirtStationCode(stationCapture.getTollcode());
                                trailBo.setFirtStationName(stationCapture.getTollname());
                                trailBo.setFirtStationTime(trailBo.getCaptureTime());
                                stationCount ++;
                            }


                        }
                        ipType = "stationip";
                        break;
                }

                if (CommonUtil.isNotBlank(ip)){
                    trailBo.setIpType(ipType);
                    // 门架ip
                    if (ipType.equals("gantryip")){
                        if (szdnGantryMap.containsKey(ip)){
                            OdsSzdnGantryIp  gantryIpBO = szdnGantryMap.get(ip);
                            trailBo.setGantryIpBO(gantryIpBO);
                            trailBo.setLocationFlag("1"); // 有数据

                            trailBo.setDevCode(gantryIpBO.getGantryCode()); // 设备编号
                            trailBo.setDevName(gantryIpBO.getGantryName());  // 设备名称

                            OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                            if (null != odsSzdnGantry) {
                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())){
                                    trailBo.setLon(new BigDecimal(odsSzdnGantry.getLon())); // 经度
                                }

                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())){
                                    trailBo.setLat(new BigDecimal(odsSzdnGantry.getLat())); // 经度
                                }
                            }

                        }
                    }

                    // 收费站ip
                    if (ipType.equals("stationip")){
                        if (szdnTollMap.containsKey(ip)){

                            OdsSzdnTollStationIp  stationIpBO =  szdnTollMap.get(ip);
                            trailBo.setStationIpBO(stationIpBO);
                            trailBo.setLocationFlag("1"); // 有数据

                            trailBo.setDevCode(stationIpBO.getTollCode()); // 设备编号
                            trailBo.setDevName(stationIpBO.getTollName());  // 设备名称

                            OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                            if (null != odsSzdnToll){
                                if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())){
                                    trailBo.setLon(new BigDecimal(odsSzdnToll.getLongitude())); // 经度
                                }

                                if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())){
                                    trailBo.setLat(new BigDecimal(odsSzdnToll.getLatitude())); // 经度
                                }
                            }
                        }
                    }
                }
            }

        }
        return mapCar;
    }

    /**
     * 同步可疑车俩
     *
     * @param carParaVO
     * @return
     */
    @Override
    public Map<String, List<TrailBo>> syncSuspiciousCar(CarParaVO carParaVO) {
        List<ZdataTrailTracks> carlist = zdataTrailTracksService.getLatestTrail(carParaVO);
        Map<String, List<TrailBo>> mapCar = new HashMap<>();
        if (null != carlist && carlist.size() > 0) {
            Set<String> set = odsSzdnGantryIpService.selectIPSet();
            for (ZdataTrailTracks tracks : carlist) {
                String carNo = tracks.getPlateKey() + "@@" + tracks.getUuid(); // 车牌号 + 轨迹id
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                    // 筛选是吉安东的车----------
                    for (TrailBo item  : josnList){
                        // true=进入
                        if (null != item.getDirectionIn() && item.getDirectionIn()) {
                            String locationCode =  CommonUtil.isNull(item.getLocationCode());
                            // ----------位置信息
                            String[] locationCodeStr = locationCode.split(":");
                            String ip ="";
                            if (locationCodeStr.length > 1){
                                ip = CommonUtil.isNull(locationCodeStr[1]);
                                if (set.contains(ip)) {
                                    mapCar.put(carNo, josnList);
                                }
                            }
                        }
                    }
                }
            }
            return this.changeData(mapCar);
        } else {
            return mapCar;
        }
    }


    /**
     * 查询车俩历史记录
     * @param carParaVO
     * @return
     */
    @Override
    public Map<String, List<TrailBo>> carTrackQuery(CarParaVO carParaVO) {

        List<CarVO> carlistPara = carParaVO.getCarlist();
        if (null != carlistPara && carlistPara.size() > 0){
            List<String> carNoList = carlistPara.stream().map(CarVO::getCarNo).collect(Collectors.toList());
            carParaVO.setCarNoList(carNoList);
        }

        List<ZdataTrailTracks> carlist = zdataTrailTracksService.getHistoryTrail(carParaVO);

        Map<String, List<TrailBo>> mapCar = new HashMap<>();
        if (null != carlist && carlist.size() > 0) {
            for (ZdataTrailTracks tracks : carlist) {
                String carNo = tracks.getPlateKey() + "@@" + tracks.getUuid(); // 车牌号 + 轨迹id
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                    mapCar.put(carNo, josnList);
                }
            }
            return this.changeData(mapCar);
        } else {
            return mapCar;
        }

    }


}
