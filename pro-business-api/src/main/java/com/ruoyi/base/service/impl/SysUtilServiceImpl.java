package com.ruoyi.base.service.impl;


import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.*;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.core.redis.RedisConfig;
import com.ruoyi.common.core.redis.RedisSourceFactory;
import com.ruoyi.common.utils.CommonUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import redis.clients.jedis.JedisCluster;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 服务区基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Slf4j
@Service
public class SysUtilServiceImpl implements ISysUtilService {


    public static final String BORDER_WEIGHING_CAPTURE = "BorderWeighingCapture";
    public static final String GANTRY_CAPTURE = "GantryCapture";
    public static final String PROV_CAPTURE = "ProvCapture";
    public static final String SERVICE_AREA_CAPTURE = "ServiceAreaCapture";
    public static final String STATION_CAPTURE = "StationCapture";

    public static final String FeeRecord = "FeeRecord";
    public static final String FeeStationEnter = "FeeStationEnter";
    public static final String FeeStationExit = "FeeStationExit";

    public static final String redisBiteKey = "sys_config:syncSuspiciousCar_bite"; // 比例默认为0.5
    public static final String redisTimeKey = "sys_config:syncSuspiciousCar_time"; // 默认7天
    public static final String supoer_mjnum = "sys_config:supoer_mjnum"; // 门架数量


    @Autowired
    private RedisCache redisCache;

    @Autowired
    private RedisSourceFactory redisSourceFactory;

    @Resource
    private RedisConfig redisConfig;

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

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service feeRecords01Service;
    @Autowired
    private IOdsLwzxsfsjFeeStationEnter01Service feeStationEnter01Service;
    @Autowired
    private IOdsLwzxsfsjFeeStationExit01Service feeStationExit01Service;

    @Autowired
    private IZdataLocationDictService zdataLocationDictService;
    @Autowired
    private IOdsCxztFwqcllsService fwqcllsService;
    @Autowired
    private IDwdLcztFwqjcxxService fwqjcxxService;
    @Autowired
    private IOdsSzdnSectionService sectionService;


    @Value("${isLocalhost}")
    private String isLocalhost;


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
     * 可疑车辆
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String getSuspiciousKey(String curData, String configKey) {
        return Constants.car_uspicious + curData + ":" + configKey;
    }



    /**
     * 新增或者修改车辆信息
     *
     * @param sysUtil 基础类
     * @return 结果
     */
    public AjaxResult saveRedis(SysUtil sysUtil) {

        log.info("获取的配置信息："+redisConfig.getClusterNodes()+"--本地配置："+isLocalhost);



        // ----------测试JedisCluster
       /* JedisCluster jedisCluster  = redisSourceFactory.createSource(redisConfig);
        List<String> carList = new ArrayList<String>();
        carList.add("苏CMA262");
        carList.add("苏F5HK60");
        carList.add("苏FD0A86");
        carList.add("苏MF3652");
        carList.add("赣A0253J");
        for (String carNo : carList) {
            String key = this.getCacheKey(carNo);
            String keyValue = jedisCluster.get(key);
            log.info("生产redis：" + key + "对应的轨迹点：" + keyValue);
            redisCache.setCacheObject(key, keyValue);
        }*/

        // ----------zdata_trail_tracks作废
       /* ZdataTrailTracks zdataTrailTracks = new ZdataTrailTracks();
        zdataTrailTracks.setPlateKey("赣CEA826");
        List<ZdataTrailTracks> trackList1 = zdataTrailTracksService.selectZdataTrailTracksList(zdataTrailTracks);
        for (ZdataTrailTracks trackBo : trackList1) {
            List<TrailBo> josnList = JSON.parseArray(trackBo.getTrailPoints(), TrailBo.class);
            // redisCache.setCacheObject(this.getCacheKey(trackBo.getPlateKey()), trackBo.getTrailPoints());
        }*/

/*
        CarParaVO carParaVO = new CarParaVO();
        carParaVO.setCarNo("赣FC0278");
        List<ZdataTrailTracks> trackList = zdataTrailTracksService.getHistoryTrail(carParaVO);
        for (ZdataTrailTracks trackBo : trackList) {
            try {
                List<TrailBo> trailBoList = this.getTrailBoList(trackBo.getTrailPoints());
                String test = "111";

                // redisCache.setCacheObject(this.getCacheKey(trackBo.getPlateKey()),JSON.toJSONString(trailBoList));
            } catch (Exception e) {
                e.printStackTrace();
                log.error("解析错误！");
            }
        }*/


       /* Collection<String> keys = redisCache.keys(residDist + "*");
        if (null != keys && keys.size() > 0){
            for (String key : keys) {
                String keyValue = redisCache.getCacheObject(key);
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                }
                log.info("本地redis：" + key + "对应的轨迹点：" + keyValue);
            }
        }*/
        return AjaxResult.success();
    }



    /**
     * 同步轨迹
     *
     * @param carParaVO carParaVO 车俩列表
     * @return 结果
     */
    public void syncTrack(CarParaVO carParaVO) {
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        Map<ZdataTrailTracks, List<TrailBo>> mapCar = new HashMap<>();
        if (null != carlist && carlist.size() > 0) {

            log.info("获取的配置信息："+redisConfig.getClusterNodes()+"--本地配置："+isLocalhost +"--同步车辆数量："+carlist.size());
            JedisCluster jedisCluster  = redisSourceFactory.createSource(redisConfig);

            for (CarVO carVO : carlist) {
                String carNo = CommonUtil.isNull(carVO.getCarNo());
                String keyValue = "";

                if (CommonUtil.isNull(isLocalhost).equals("local")){
                    // 本地
                    keyValue = redisCache.getCacheObject(this.getCacheKey(carNo));
                }else {
                    // 生产-------------
                    keyValue = jedisCluster.get(this.getCacheKey(carNo));
                }

                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {

                    // 先转josn数组 然后循环 一个一个手动赋值
                    JSONArray array = JSON.parseArray(keyValue);
                    for (Object o : array) {
                        JSONObject jsonObj = (JSONObject) o;
                        TrailBo trailBo = new TrailBo();
                        trailBo.setPointUuid(jsonObj.getString("pointUuid"));
                        trailBo.setStateType(jsonObj.getString("stateType"));
                        trailBo.setCaptureTime(jsonObj.getString("captureTime"));
                        trailBo.setLocationCode(jsonObj.getString("locationCode"));
                        trailBo.setLocationName(jsonObj.getString("locationName"));
                        trailBo.setStandardCode(jsonObj.getString("standardCode"));

                        String lon = jsonObj.getString("longitude");
                        String lat = jsonObj.getString("latitude");

                        if(CommonUtil.isNotBlank(lon)) {
                            trailBo.setLon(new BigDecimal(lon));
                        }
                        if(CommonUtil.isNotBlank(lat)) {
                            trailBo.setLat(new BigDecimal(lat));
                        }

                        trailBo.setDevCode(trailBo.getStandardCode());
                        trailBo.setDevName(trailBo.getLocationName());

                        josnList.add(trailBo);


                    }
                   //  josnList = JSON.parseArray(keyValue, TrailBo.class);


                    List<TrailBo> rtnList = this.mapTrailBoList(josnList);
                    // 最后一个轨迹点需要查询
                    if (null != rtnList && rtnList.size() > 0) {

                      /*  TrailBo trailBo = rtnList.get(rtnList.size() - 1); // 最后一条记录要查询
                        trailBo.setIsQuery("1");*/

                        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
                        String formattedDate = sdf.format(new Date());

                        ZdataTrailTracks tracks = new ZdataTrailTracks();
                        tracks.setPlateKey(carNo);
                        tracks.setUuid(carNo +"@@"+ formattedDate);
                        tracks.setFlag("currentTrack"); // 实时轨迹

                        TrailInfo trailInfo = this.changeData(tracks, rtnList); // 获取设备的经纬度

                        trailInfo.setTrailUuid(carNo);

                        String key = Constants.car_curent_trail + carNo;
                        redisCache.setCacheObject(key, trailInfo);
                    }


                }
            }
        }
    }


    /**
     * 数据转换
     *
     * @param josnList
     * @return 结果
     */
    public TrailInfo changeData(ZdataTrailTracks tracks, List<TrailBo> josnList) {

        TrailInfo trailInfo = new TrailInfo();


        if (null != josnList && josnList.size() >0) {
        }else{
            trailInfo.setTracks(tracks);
            List<TrailBo> tempList = new ArrayList<>();
            trailInfo.setTrailList(tempList);
            return trailInfo;
        }

        String serviceAreaCaptureUUids = ""; // 服务区抓拍

        for (TrailBo trailBo : josnList) {
            String pointUuid = trailBo.getPointUuid();
            String stateType = CommonUtil.isNull(trailBo.getStateType());
            if (stateType.equals(SERVICE_AREA_CAPTURE)){
                serviceAreaCaptureUUids += pointUuid + ",";
            }
        }

        // 服务区抓拍
        Map<String, OdsCxztFwqclls> fwqcllsMap = new HashMap<>();
        serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids);
        if (CommonUtil.isNotBlank(serviceAreaCaptureUUids)) {
            fwqcllsMap = fwqcllsService.selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids);
        }

        // 收费站ip
        Map<String, OdsSzdnTollStationIp> szdnTollMap = odsSzdnTollStationIpService.selectStationIpMap();

        // 门架IP
        Map<String, OdsSzdnGantryIp> szdnGantryMap = odsSzdnGantryIpService.selectOdsSzdnGantryIpMap();

        // 位置信息
        Map<String,ZdataLocationDict> locationMap = zdataLocationDictService.getRedisList();

        //服务区信息
        Map<String, DwdLcztFwqjcxx> serviceNameMap = fwqjcxxService.getServiceNameMap();

        // 根据路段查询路线map
        Map<String, OdsSzdnSection> sectionMap = sectionService.getSectionMap();


        String firtStationCode = "";
        // 入栈口名称
        String firtStationName = "";
        // 入栈口时间
        String firtStationTime= "";

        /** 车牌颜色（字典：1白色2黑色） */
        String plateColor = "";

        /** 车型 */
        String carType = "";

        /** 车种 */
        String carVehicle= "";

        /** 轴数 */
        Long carNum = null;

        // 1-OBU 2-CPC卡 3-纸券 9-无通行介质,4- M1卡
        String passType= "";

        /**
         * 查询类型
         */
        String indexType ="";

        for (TrailBo trailBo : josnList) {
            // --------------抓拍信息
            String pointUuid = trailBo.getPointUuid();
            String locationCode = CommonUtil.isNull(trailBo.getLocationCode()); // 设备IP地址
            String stateType = CommonUtil.isNull(trailBo.getStateType());  // 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表

            String sectionCode = CommonUtil.isNull(trailBo.getSectionCode());
            String pileno = CommonUtil.isNull(trailBo.getPileno());
            BigDecimal lon = trailBo.getLon();
            BigDecimal lat = trailBo.getLon();
            String roadCode = "";

            // 这个要查询数据库拿---
            if (CommonUtil.isNotBlank(sectionCode)) {
                if (sectionMap.containsKey(sectionCode)){
                    OdsSzdnSection section = sectionMap.get(sectionCode);
                    roadCode = CommonUtil.isNull(section.getRoadCode());
                    trailBo.setRoadCode(roadCode);
                }
            }

            switch (stateType) {
                case BORDER_WEIGHING_CAPTURE:
                    // 省界称重
                    indexType ="gantryType"; // 门架
                    break;
                case GANTRY_CAPTURE:
                    // 门架抓拍
                    indexType ="gantryType"; // 门架
                    break;
                case PROV_CAPTURE:
                    // 省界抓拍
                    indexType ="gantryType"; // 门架
                    break;
                case SERVICE_AREA_CAPTURE:
                    // 服务区抓拍
                    indexType ="service_area"; // 服务区
                    if(fwqcllsMap.containsKey(pointUuid)) {
                        OdsCxztFwqclls fwqclls = fwqcllsMap.get(pointUuid);

                        String imagesSrc = "";
                        // 抓拍照片url
                        if (CommonUtil.isNotBlank(fwqclls.getTargetpicurl())){
                            imagesSrc += fwqclls.getTargetpicurl() +",";
                        }

                        // 车牌照片
                        if (CommonUtil.isNotBlank(fwqclls.getPlatepicurl())){
                            imagesSrc += fwqclls.getPlatepicurl() +",";
                        }

                        // 抓拍照片
                        trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc)); // 抓拍照片
                        String servicename = CommonUtil.isNull(fwqclls.getServicename());

                        trailBo.setDevName(servicename);  // 设备名称
                        if(serviceNameMap.containsKey(servicename)){

                            DwdLcztFwqjcxx fwqjcxx = serviceNameMap.get(servicename);
                            trailBo.setDevCode(fwqjcxx.getFwqbm()); // 设备编号

                            if (CommonUtil.isNotBlank(fwqjcxx.getJd())) {
                                trailBo.setLon(new BigDecimal(fwqjcxx.getJd())); // 经度
                            }
                            if (CommonUtil.isNotBlank(fwqjcxx.getWd())) {
                                trailBo.setLat(new BigDecimal(fwqjcxx.getWd())); // 经度
                            }
                            // 路线编号
                            trailBo.setRoadCode(CommonUtil.isNull(fwqjcxx.getSslxbh()));
                            // 路段
                            trailBo.setSectionCode(CommonUtil.isNull(fwqjcxx.getSsldbh()));

                            // trailBo.setDirection(fwqjcxx.getFxmc()); // 方向
                            trailBo.setPileno(CommonUtil.isNull(fwqjcxx.getSczhkgs())); // 桩号

                        }
                    }
                    break;
                case STATION_CAPTURE:
                    // 收费站抓拍
                    indexType ="stationType"; // 收费站
                    break;
                case FeeRecord:
                    // 卡口流水
                    indexType = "gantryType"; // 门架
                    break;
                case FeeStationEnter:
                    // 收费站入口流水
                    indexType = "stationType"; // 收费站
                    break;
                case FeeStationExit:
                    // 收费站出口流水
                    indexType ="stationType"; // 收费站
                    break;
            }

            //---------------通过位置信息查询设备
            String devLocatCode = "";
            if (locationMap.containsKey(locationCode)){
                devLocatCode = CommonUtil.isNull(locationMap.get(locationCode).getStandardCode()); // 收费站/门架code
            }

            String devCodeId = CommonUtil.isNull(trailBo.getDevCode()); // 通过设备编码先查询

            if (indexType.equals("stationType")){
                // 收费站ip 或者CODE查询
                OdsSzdnTollStationIp stationIpBO = null;

                // 从位置信息
                if (CommonUtil.isNotBlank(devLocatCode)) {
                    stationIpBO = szdnTollMap.get(devLocatCode);
                }

                // 从设备id拿
                if (null == stationIpBO) {
                    // 从设备id拿
                    if (CommonUtil.isNotBlank(devCodeId)) {
                        stationIpBO = szdnTollMap.get(devCodeId);
                    }
                }

                // 从当前位置拿
                if (null == stationIpBO) {
                    if (CommonUtil.isNotBlank(locationCode)) {
                        stationIpBO = szdnTollMap.get(locationCode);
                    }

                }


                if (null != stationIpBO) {
                   /* trailBo.setStationIpBO(stationIpBO);
                    trailBo.setLocationFlag("1"); // 有数据*/

                    trailBo.setDevCode(stationIpBO.getTollCode()); // 设备编号
                    trailBo.setDevName(stationIpBO.getTollName());  // 设备名称

                    OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                    if (null != odsSzdnToll) {

                        if (null == lon) {
                            // 经度
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())) {
                                trailBo.setLon(new BigDecimal(odsSzdnToll.getLongitude()));
                            }
                        }

                        if (null == lat) {
                            // 经度
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())) {
                                trailBo.setLat(new BigDecimal(odsSzdnToll.getLatitude()));
                            }
                        }

                        if (CommonUtil.isBlank(roadCode)){
                            // 路线编号
                            trailBo.setRoadCode(CommonUtil.isNull(odsSzdnToll.getRoadCode()));
                        }

                        if (CommonUtil.isBlank(sectionCode)){
                            // 路段
                            trailBo.setSectionCode(CommonUtil.isNull(odsSzdnToll.getSectionCode()));
                        }

                        if (CommonUtil.isBlank(pileno)){
                            // 桩号
                            trailBo.setPileno(CommonUtil.isNull(odsSzdnToll.getPileNo()));
                        }

                        // trailBo.setDirection(odsSzdnToll.getDirection()); // 方向

                    }
                }

            }else  if (indexType.equals("gantryType")){
                // 门架ip
                OdsSzdnGantryIp  gantryIpBO = null;

                // 从位置信息
                if (CommonUtil.isNotBlank(devLocatCode)) {
                    gantryIpBO = szdnGantryMap.get(devLocatCode);
                }

                // 从设备id拿
                if (null == gantryIpBO) {
                    // 从设备id拿
                    if (CommonUtil.isNotBlank(devCodeId)) {
                        gantryIpBO = szdnGantryMap.get(devCodeId);
                    }
                }

                // 从当前位置拿
                if (null == gantryIpBO) {
                    if (CommonUtil.isNotBlank(locationCode)) {
                        gantryIpBO = szdnGantryMap.get(locationCode);
                    }

                }


                if (null != gantryIpBO) {
                      /*  trailBo.setGantryIpBO(gantryIpBO);
                        trailBo.setLocationFlag("1"); // 有数据*/

                    trailBo.setDevCode(gantryIpBO.getGantryCode()); // 设备编号
                    trailBo.setDevName(gantryIpBO.getGantryName());  // 设备名称

                    OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                    if (null != odsSzdnGantry) {

                        if (null == lon) {
                            // 经度
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                trailBo.setLon(new BigDecimal(odsSzdnGantry.getLon())); // 经度
                            }
                        }

                        if (null == lat) {
                            // 经度
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                trailBo.setLat(new BigDecimal(odsSzdnGantry.getLat())); // 经度
                            }
                        }

                        if (CommonUtil.isBlank(roadCode)){
                            // 路线编号
                            trailBo.setRoadCode(CommonUtil.isNull(odsSzdnGantry.getRoadCode()));
                        }

                        if (CommonUtil.isBlank(sectionCode)){
                            // 路段编号
                            trailBo.setSectionCode(CommonUtil.isNull(odsSzdnGantry.getSectionCode()));
                        }

                        if (CommonUtil.isBlank(pileno)){
                            // 桩号
                            trailBo.setPileno(CommonUtil.isNull(odsSzdnGantry.getPileNo())); // 桩号
                        }


                        trailBo.setDirection(odsSzdnGantry.getDirection()); // 方向

                    }
                }
            }else  if (indexType.equals("service_area")){
                // 服务区

            }

            // 设备名称没有默认位置信息--------------
            if (CommonUtil.isBlank(trailBo.getDevName())){
                trailBo.setDevName(CommonUtil.isNull(locationCode).replaceAll("devip:",""));
            }

        }


        tracks.setFirtStationCode(firtStationCode);
        tracks.setFirtStationName(firtStationName);
        tracks.setFirtStationTime(firtStationTime);
        tracks.setPlateColor(plateColor);
        tracks.setCarType(carType);
        tracks.setCarVehicle(carVehicle);
        tracks.setCarNum(carNum);
        tracks.setPassType(passType);


        //  -------------------------获取起点 终点 的经纬度
        List<TrailBo> jwdList = new ArrayList<TrailBo>();
        if (null != josnList && josnList.size() > 0) {
            for (TrailBo trailBo : josnList) {
                if (null != trailBo.getLon() && null != trailBo.getLat()) {
                    jwdList.add(trailBo);
                }
            }
        }


        if(CommonUtil.isNull(tracks.getFlag()).equals("currentTrack")){
            // 实时轨迹
            if (null != jwdList && jwdList.size() > 0) {
                TrailBo firstTrailBo = jwdList.get(0);

                tracks.setEntollstationid(CommonUtil.isNull(firstTrailBo.getDevCode()));
                tracks.setEntollstationname(CommonUtil.isNull(firstTrailBo.getDevName()));
                tracks.setStartLon(CommonUtil.isNull(firstTrailBo.getLon())); // 经度
                tracks.setStratLat(CommonUtil.isNull(firstTrailBo.getLat())); // 经度

                if (jwdList.size() > 1) {
                    TrailBo endTrailBo = jwdList.get(jwdList.size() - 1);
                    tracks.setExtollstationid(CommonUtil.isNull(endTrailBo.getDevCode()));
                    tracks.setExtollstationname(CommonUtil.isNull(endTrailBo.getDevName()));
                    tracks.setEndLon(CommonUtil.isNull(endTrailBo.getLon())); // 经度
                    tracks.setEndLat(CommonUtil.isNull(endTrailBo.getLat())); // 经度
                }
            }
        }else{
            // 历史轨迹：
            String firstCode = CommonUtil.isNull(tracks.getEntollstationid()); // 入口收费站编号
            String firstName = CommonUtil.repalaceSzdnTollName(tracks.getEntollstationname()); // 入口收费站名称
            String endCode = CommonUtil.isNull(tracks.getExtollstationid()); // 出口收费站编号
            String endName = CommonUtil.repalaceSzdnTollName(tracks.getExtollstationname()); // 出口收费站名称


            if (CommonUtil.isNotBlank(firstCode)){
                // 收费站ip
                if (szdnTollMap.containsKey(firstCode)){
                    OdsSzdnTollStationIp stationIpBO = szdnTollMap.get(firstCode);
                    OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                    if (null != odsSzdnToll) {
                        if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())) {
                            tracks.setStartLon(odsSzdnToll.getLongitude()); // 经度
                        }
                        if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())) {
                            tracks.setStratLat(odsSzdnToll.getLatitude()); // 经度
                        }
                    }
                }else {
                    // 门架
                    if (szdnGantryMap.containsKey(firstCode)){
                        OdsSzdnGantryIp  gantryIpBO = szdnGantryMap.get(firstCode);
                        OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                        if (null != odsSzdnGantry) {
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                tracks.setStartLon(odsSzdnGantry.getLon()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                tracks.setStratLat(odsSzdnGantry.getLat()); // 经度
                            }
                        }
                    }
                }
            }

            // --------- 如果拿不到就根据名称来拿
            if (CommonUtil.isBlank(tracks.getStartLon())){
                if (CommonUtil.isNotBlank(firstName)){
                    // 收费站ip
                    if (szdnTollMap.containsKey(firstName)){
                        OdsSzdnTollStationIp stationIpBO = szdnTollMap.get(firstName);
                        OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                        if (null != odsSzdnToll) {
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())) {
                                tracks.setStartLon(odsSzdnToll.getLongitude()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())) {
                                tracks.setStratLat(odsSzdnToll.getLatitude()); // 经度
                            }
                        }
                    }else {
                        // 门架
                        if (szdnGantryMap.containsKey(firstName)){
                            OdsSzdnGantryIp  gantryIpBO = szdnGantryMap.get(firstName);
                            OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                            if (null != odsSzdnGantry) {
                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                    tracks.setStartLon(odsSzdnGantry.getLon()); // 经度
                                }
                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                    tracks.setStratLat(odsSzdnGantry.getLat()); // 经度
                                }
                            }
                        }
                    }

                }
            }


            if (CommonUtil.isNotBlank(endCode)){
                // 收费站ip
                if (szdnTollMap.containsKey(endCode)){
                    OdsSzdnTollStationIp stationIpBO = szdnTollMap.get(endCode);
                    OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                    if (null != odsSzdnToll) {
                        if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())) {
                            tracks.setEndLon(odsSzdnToll.getLongitude()); // 经度
                        }
                        if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())) {
                            tracks.setEndLat(odsSzdnToll.getLatitude()); // 经度
                        }
                    }
                }else {
                    // 门架
                    if (szdnGantryMap.containsKey(endCode)){
                        OdsSzdnGantryIp  gantryIpBO = szdnGantryMap.get(endCode);
                        OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                        if (null != odsSzdnGantry) {
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                tracks.setEndLon(odsSzdnGantry.getLon()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                tracks.setEndLat(odsSzdnGantry.getLat()); // 经度
                            }
                        }
                    }
                }
            }

            // --------- 如果拿不到就根据名称来拿
            if (CommonUtil.isBlank(tracks.getEndLon())){
                if (CommonUtil.isNotBlank(endName)){
                    // 收费站ip
                    if (szdnTollMap.containsKey(endName)){
                        OdsSzdnTollStationIp stationIpBO = szdnTollMap.get(endName);
                        OdsSzdnToll odsSzdnToll = stationIpBO.getOdsSzdnToll();
                        if (null != odsSzdnToll) {
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLongitude())) {
                                tracks.setEndLon(odsSzdnToll.getLongitude()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnToll.getLatitude())) {
                                tracks.setEndLat(odsSzdnToll.getLatitude()); // 经度
                            }
                        }
                    }else {
                        // 门架
                        if (szdnGantryMap.containsKey(endName)){
                            OdsSzdnGantryIp  gantryIpBO = szdnGantryMap.get(endName);
                            OdsSzdnGantry odsSzdnGantry = gantryIpBO.getOdsSzdnGantry();
                            if (null != odsSzdnGantry) {
                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                    tracks.setEndLon(odsSzdnGantry.getLon()); // 经度
                                }
                                if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                    tracks.setEndLat(odsSzdnGantry.getLat()); // 经度
                                }
                            }
                        }
                    }
                }
            }

            // 如果获取的经纬度为空的话
           /* if (CommonUtil.isBlank(tracks.getStartLon())){
                if (null != jwdList && jwdList.size() > 0) {
                    TrailBo firstTrailBo = jwdList.get(0);
                    tracks.setStartLon(CommonUtil.isNull(firstTrailBo.getLon())); // 经度
                    tracks.setStratLat(CommonUtil.isNull(firstTrailBo.getLat())); // 经度
                }
            }

            if (CommonUtil.isBlank(tracks.getEndLon())){
                if (null != jwdList && jwdList.size() > 1) {
                    TrailBo endTrailBo = jwdList.get(jwdList.size() - 1);
                    tracks.setEndLon(CommonUtil.isNull(endTrailBo.getLon())); // 经度
                    tracks.setEndLat(CommonUtil.isNull(endTrailBo.getLat())); // 经度
                }
            }*/

        }


        if (CommonUtil.isNotBlank(tracks.getStartLon())){
            tracks.setStartLonDec(new BigDecimal(tracks.getStartLon()));
        }
        if (CommonUtil.isNotBlank(tracks.getStratLat())){
            tracks.setStratLatDec(new BigDecimal(tracks.getStratLat()));
        }
        if (CommonUtil.isNotBlank(tracks.getEndLon())){
            tracks.setEndLonDec(new BigDecimal(tracks.getEndLon()));
        }
        if (CommonUtil.isNotBlank(tracks.getEndLat())){
            tracks.setEndLatDec(new BigDecimal(tracks.getEndLat()));
        }

        trailInfo.setTracks(tracks);
        trailInfo.setTrailList(josnList);

        return trailInfo;
    }

    /**
     * 获取抓拍对象
     * @param trailBo
     * @return
     */
    public TrailBo getByTrailBo(TrailBo trailBo) {

        if (null == trailBo) {
            return new TrailBo();
        }

        String borderWeighingCaptureUUids = ""; // 省界称重
        String gantryCaptureUUids = ""; // 门架抓拍
        String provCaptureUUids = ""; // 省界抓拍
        String serviceAreaCaptureUUids = ""; // 服务区抓拍
        String stationCaptureUUids = ""; // 收费站抓拍
        String feeRecordUUids = ""; // 卡口流水
        String feeStationEnterUUids = ""; // 收费站入口流水
        String feeStationExitUUids = ""; // 收费站出口流水


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
            case FeeRecord:
                // 卡口流水
                // feeRecordUUids += pointUuid + ",";
                break;
            case FeeStationEnter:
                // 收费站入口流水
                // feeStationEnterUUids += pointUuid + ",";
                break;
            case FeeStationExit:
                // 收费站出口流水
                // feeStationExitUUids += pointUuid + ",";
                break;
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

        // 服务区抓拍
        Map<String, OdsCxztFwqclls> fwqcllsMap = new HashMap<>();
        serviceAreaCaptureUUids = CommonUtil.deleteEnd(serviceAreaCaptureUUids);
        if (CommonUtil.isNotBlank(serviceAreaCaptureUUids)) {
            fwqcllsMap = fwqcllsService.selectOdsCxztFwqcllsByQueryUuids(serviceAreaCaptureUUids);
        }

        // 收费站抓拍
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> stationcaptureAddcodeMap = new HashMap<>();
        stationCaptureUUids = CommonUtil.deleteEnd(stationCaptureUUids);
        if (CommonUtil.isNotBlank(stationCaptureUUids)) {
            stationcaptureAddcodeMap = stationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(stationCaptureUUids);
        }

        // 卡口流水
        Map<String, OdsLwzxsfsjFeeRecords01> feeRecordMap = new HashMap<>();
        feeRecordUUids = CommonUtil.deleteEnd(feeRecordUUids);
        if (CommonUtil.isNotBlank(feeRecordUUids)) {
            feeRecordMap = feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ByQueryUuids(feeRecordUUids);
        }


        // 收费站入口流水
        Map<String, OdsLwzxsfsjFeeStationEnter01> feeStationEnterMap = new HashMap<>();
        feeStationEnterUUids = CommonUtil.deleteEnd(feeStationEnterUUids);
        if (CommonUtil.isNotBlank(feeStationEnterUUids)) {
            feeStationEnterMap = feeStationEnter01Service.selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(feeStationEnterUUids);
        }

        // 收费站入口流水
        Map<String, OdsLwzxsfsjFeeStationExit01> feeStationExitMap = new HashMap<>();
        feeStationExitUUids = CommonUtil.deleteEnd(feeStationExitUUids);
        if (CommonUtil.isNotBlank(feeStationExitUUids)) {
            feeStationExitMap = feeStationExit01Service.selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(feeStationExitUUids);
        }

     /*   // 收费站ip
        Map<String, OdsSzdnTollStationIp> szdnTollMap = odsSzdnTollStationIpService.selectStationIpMap();

        // 门架IP
        Map<String, OdsSzdnGantryIp> szdnGantryMap = odsSzdnGantryIpService.selectOdsSzdnGantryIpMap();

        // 位置信息
        Map<String,ZdataLocationDict> locationMap = zdataLocationDictService.getRedisList();

        //服务区信息
        Map<String, DwdLcztFwqjcxx> serviceNameMap = fwqjcxxService.getServiceNameMap(); */


        switch (stateType) {
            case BORDER_WEIGHING_CAPTURE:
                // 省界称重
                if (weightNewstructureMap.containsKey(pointUuid)){
                    OdsSzdnProvinceBorderVehicleWeightNewstructure  borderWeighingCaptureBO = weightNewstructureMap.get(pointUuid);

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
                break;
            case GANTRY_CAPTURE:
                if (snapshotFlowAddcodeMap.containsKey(pointUuid)){
                    OdsRtSzdnSnapshotFlowAddcode  gantryCaptureBO = snapshotFlowAddcodeMap.get(pointUuid);
                    trailBo.setImagesArry(gantryCaptureBO.getSnappicturepath()); // 抓拍照片
                }
                break;
            case PROV_CAPTURE:
                // 省界抓拍
                if (provcaptureAddcodeMap.containsKey(pointUuid)){
                    String imagesSrc = "";
                    OdsRtSzdnSnapshotFlowProvcaptureAddcode  provCaptureBO = provcaptureAddcodeMap.get(pointUuid);
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
                break;
            case SERVICE_AREA_CAPTURE:
                // 服务区抓拍
                if(fwqcllsMap.containsKey(pointUuid)) {
                    OdsCxztFwqclls fwqclls = fwqcllsMap.get(pointUuid);
                    String imagesSrc = "";
                    // 抓拍照片url
                    if (CommonUtil.isNotBlank(fwqclls.getTargetpicurl())){
                        imagesSrc += fwqclls.getTargetpicurl() +",";
                    }

                    // 车牌照片
                    if (CommonUtil.isNotBlank(fwqclls.getPlatepicurl())){
                        imagesSrc += fwqclls.getPlatepicurl() +",";
                    }

                    // 抓拍照片
                    trailBo.setImagesArry(CommonUtil.deleteEnd(imagesSrc)); // 抓拍照片

                }
                break;
            case STATION_CAPTURE:
                // 收费站抓拍
                if (stationcaptureAddcodeMap.containsKey(pointUuid)){
                    OdsRtSzdnSnapshotFlowStationcaptureAddcode  stationCapture = stationcaptureAddcodeMap.get(pointUuid);
                    trailBo.setImagesArry(stationCapture.getSnappicturepath()); // 抓拍照片
                }
                break;
            case FeeRecord:
                // 卡口流水
                if (feeRecordMap.containsKey(pointUuid)) {
                    OdsLwzxsfsjFeeRecords01 feeRecords = feeRecordMap.get(pointUuid);
                    trailBo.setDevCode(feeRecords.getGantryid()); // 设备编号
                    trailBo.setImagesArry(""); // 抓拍照片
                }
                break;
            case FeeStationEnter:
                // 收费站入口流水
                if (feeStationEnterMap.containsKey(pointUuid)) {
                    OdsLwzxsfsjFeeStationEnter01 feeStationEnter = feeStationEnterMap.get(pointUuid);
                    trailBo.setImagesArry(""); // 抓拍照片
                }

                break;
            case FeeStationExit:
                // 收费站出口流水
                if (feeStationExitMap.containsKey(pointUuid)) {
                    OdsLwzxsfsjFeeStationExit01 feeStationExit = feeStationExitMap.get(pointUuid);
                    trailBo.setImagesArry(""); // 抓拍照片
                }
                break;
        }

        // 图片替换----
        String imagesArry = CommonUtil.deleteEnd(trailBo.getImagesArry());
        trailBo.setImagesArry(CommonUtil.repalacePicUrl(imagesArry));

        return  trailBo;
    }



    /**
     * 同步可疑车俩
     *
     * @param carParaVO
     * @return
     */
    @Override
    public Map<ZdataTrailTracks, List<TrailBo>> syncSuspiciousCar(CarParaVO carParaVO) {
        return  new HashMap<>();
    }


    /**
     * 同步可疑车俩：定时
     * startNum : 起始页面 1  最后页面 10
     *
     * @return
     */
    public void syncSuspiciousCarQutaz(int startNum, int endNum) {

        Integer pageSize = 10;
        Integer starTime = 3;
        Integer endTime = 14;
        BigDecimal bite = new BigDecimal("0.5");  // 门架抓拍和流水抓拍占比

        int supoerMjnum = 5; // 同步可疑车辆门架抓拍数量5个以上


        // -------------- 从缓存取得对应的配置
        String redisTimeValue = redisCache.getCacheObject(redisTimeKey); // 默认7天
        if (CommonUtil.isNotBlank(redisTimeValue)){
            starTime = Integer.parseInt(redisTimeValue);
            log.info("从缓存取得时间配置--------："+redisTimeValue);
        }

        String redisBiteValue = redisCache.getCacheObject(redisBiteKey); // 比例默认为0.5
        if (CommonUtil.isNotBlank(redisBiteValue)){
            bite = new BigDecimal(redisBiteValue);
            log.info("从缓存取得占比配置------："+bite);
        }

        String supoerMjnumValue = redisCache.getCacheObject(supoer_mjnum); // 比例默认为0.5
        if (CommonUtil.isNotBlank(supoerMjnumValue)){
            supoerMjnum = Integer.parseInt(supoerMjnumValue);
            log.info("从缓存取得门架抓拍数量------："+supoerMjnum);
        }


        if (CommonUtil.isNull(isLocalhost).equals("local")) {
            log.info("本地配置------："+CommonUtil.isNull(isLocalhost));
            // 本地  分页1000条 30 到 1 天
            pageSize = 2000;
            endTime = starTime * 2;
           /* starTime = 1;
            endTime = 30;*/
        } else {
            log.info("生产配置------："+CommonUtil.isNull(isLocalhost));
            // 生产------------- 分页1000条 14 到 7 天
            pageSize = 2000;
            endTime = starTime * 2;
        }

        log.info("分页配置：" + pageSize + "--时间范围" + starTime + "到" + endTime);


        CarParaVO carParaVO = new CarParaVO();
        //----------7 到 14天
        carParaVO.setStarTime(starTime);
        carParaVO.setEndTime(endTime);


        // 根据路段查询路线map
        List<OdsSzdnSection> sectionlist = sectionService.getSectionList();

        // 帅选
        List<String> sectionsQueryList = new ArrayList<>();
        for (OdsSzdnSection odsSzdnSection : sectionlist) {
            String roadCode = CommonUtil.isNull(odsSzdnSection.getRoadCode()); // 路线
            String sectionCode =  CommonUtil.isNull(odsSzdnSection.getSectionCode()); // 路段编码
            if (CommonUtil.isNotBlank(roadCode) && CommonUtil.isNotBlank(sectionCode)){
                // 大广高速
                if (roadCode.equals("G45")){
                    sectionsQueryList.add(sectionCode);
                }
            }
        }
        if (sectionsQueryList.size() == 0){
            sectionsQueryList.add("nosection");
        }


        for (int i = startNum; i <= endNum; i++) {
            // ----- 分页范围
            carParaVO.setStartNum(pageSize);
            if (i > 1){
                Integer endRange = (i -1) * pageSize; // 当前页 -1
                carParaVO.setEndNum(endRange);
            }
            log.info("数据查询范围：" + carParaVO.getStartNum() + "到" + carParaVO.getEndNum());

            Date now = new Date();
            SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
            String formattedDate = sdf.format(now);

            // ---------------------------------- 跨省全程屏蔽
            log.info("开始查询----------"+new Date());
            carParaVO.setFlag("ksqcpb");
            List<ZdataTrailTracks> carlist1 = zdataTrailTracksService.getLatestTrail(carParaVO);
            log.info("结束查询----------"+new Date());

            if (null != carlist1 && carlist1.size() > 0) {
                for (ZdataTrailTracks tracks : carlist1) {
                    String carNo = CommonUtil.isNull(tracks.getPlateKey());
                    String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                    String escapedType = "";
                    List<TrailBo> josnList = new ArrayList<TrailBo>();
                    if (CommonUtil.isNotBlank(keyValue)) {
                        josnList = this.getTrailBoList(keyValue);
                        tracks.setTrailPoints("");  // 行驶轨迹
                        // ---------------------------分析场景: 门架抓拍和流水抓拍 占比
                        int conutGantryCapture = 0;
                        int conutFeeRecord = 0;
                        for (TrailBo rtnTrailBo:josnList){
                            String locationId = CommonUtil.isNull(rtnTrailBo.getLocationId()); // 设备IP地址
                            String stateType = CommonUtil.isNull(rtnTrailBo.getStateType());
                            if(stateType.equals(GANTRY_CAPTURE)){
                                // 门架抓拍
                                conutGantryCapture ++;
                            }else if(stateType.equals(FeeRecord)){
                                // 卡口流水
                                conutFeeRecord ++;
                            }
                        }

                        // ---------------屏蔽:
                         /*if (conutGantryCapture > supoerMjnum && conutGantryCapture > conutFeeRecord ){
                        }*/
                        String escapedTypeRemark = "";
                        boolean addFlag = false;
                        if (conutFeeRecord == 0){
                            escapedTypeRemark = "跨省全程屏蔽：门架牌识流水数量:"+conutGantryCapture+"门架交易流水数量:"+conutFeeRecord;
                            addFlag = true;
                        }
                        if(addFlag){
                            escapedType = Constants.escapedType_20;
                            tracks.setEscapedType(escapedType); // 屏蔽
                            tracks.setEscapedTypeRemark(escapedTypeRemark);
                            tracks.setEscapedTfcj("1");  // 逃费场景

                            TrailInfo trailInfo = this.changeData(tracks, josnList); // 获取设备的经纬度
                            trailInfo.setTrailUuid(carNo);

                            String key = this.getSuspiciousKey(formattedDate,carNo);
                            redisCache.setCacheObject(key, trailInfo);
                        }
                    }
                }
            }

            // ---------------------------------- 关注路段屏蔽
            log.info("开始查询----------"+new Date());
            carParaVO.setFlag("ldtf");
            List<ZdataTrailTracks> carlist2 = zdataTrailTracksService.getLatestTrail(carParaVO);
            log.info("结束查询----------"+new Date());

            if (null != carlist2 && carlist2.size() > 0) {
                for (ZdataTrailTracks tracks : carlist2) {
                    String carNo = CommonUtil.isNull(tracks.getPlateKey());
                    String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                    String escapedType = "";
                    List<TrailBo> josnList = new ArrayList<TrailBo>();
                    if (CommonUtil.isNotBlank(keyValue)) {
                        josnList = this.getTrailBoList(keyValue);
                        tracks.setTrailPoints("");  // 行驶轨迹
                        // ---------------------------分析场景: 门架抓拍和流水抓拍 占比
                        int conutGantryCapture = 0;
                        int conutFeeRecord = 0;
                        for (TrailBo rtnTrailBo:josnList){
                            String locationId = CommonUtil.isNull(rtnTrailBo.getLocationId()); // 设备IP地址
                            String stateType = CommonUtil.isNull(rtnTrailBo.getStateType());

                            if(stateType.equals(GANTRY_CAPTURE)){
                                // 门架抓拍
                                conutGantryCapture ++;
                            }else if(stateType.equals(FeeRecord)){
                                // 卡口流水
                                conutFeeRecord ++;
                            }
                        }

                        // ---------------屏蔽:
                         /*if (conutGantryCapture > supoerMjnum && conutGantryCapture > conutFeeRecord ){
                        }*/
                        String escapedTypeRemark = "";
                        boolean addFlag = false;
                        if (conutFeeRecord == 0){
                            escapedTypeRemark = "路段屏蔽：门架牌识流水数量:"+conutGantryCapture+"门架交易流水数量:"+conutFeeRecord;
                            addFlag = true;
                        }
                        if(addFlag){
                            escapedType = Constants.escapedType_20;
                            tracks.setEscapedType(escapedType); // 屏蔽
                            tracks.setEscapedTypeRemark(escapedTypeRemark);
                            tracks.setEscapedTfcj("1");  // 逃费场景

                            TrailInfo trailInfo = this.changeData(tracks, josnList); // 获取设备的经纬度
                            trailInfo.setTrailUuid(carNo);

                            String key = this.getSuspiciousKey(formattedDate,carNo);
                            redisCache.setCacheObject(key, trailInfo);
                        }
                    }
                }
            }


        }

    }

    /**
     * 查询车俩历史记录
     * @param carParaVO
     * @return
     */
    @Override
    public List<TrailInfo> carTrackQuery(CarParaVO carParaVO) {

        List<CarVO> carlistPara = carParaVO.getCarlist();
        if (null != carlistPara && carlistPara.size() > 0) {
            List<String> carNoList = carlistPara.stream().map(CarVO::getCarNo).collect(Collectors.toList());
            carParaVO.setCarNoList(carNoList);
        }
        List<ZdataTrailTracks> carlist = zdataTrailTracksService.getHistoryTrail(carParaVO);
        List<TrailInfo> rtnList = new ArrayList<>();
        if (null != carlist && carlist.size() > 0) {
            for (ZdataTrailTracks tracks : carlist) {
                String carNo = CommonUtil.isNull(tracks.getPlateKey());
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = this.getTrailBoList(keyValue);
                    // tracks.setTrailPoints("");  // 行驶轨迹

                    TrailInfo trailInfo = this.changeData(tracks, josnList); // 获取设备的经纬度
                    trailInfo.setTrailUuid(carNo);
                    rtnList.add(trailInfo);
                }
            }
        }
        return rtnList;
    }

    /**
     * 轨迹查询 : 界面上查询-------------
     *
     * @param carParaVO
     * @return
     */
    public List<ZdataTrailTracks> carTrackQueryNew(CarParaVO carParaVO) {
        List<CarVO> carlistPara = carParaVO.getCarlist();
        if (null != carlistPara && carlistPara.size() > 0) {
            List<String> carNoList = carlistPara.stream().map(CarVO::getCarNo).collect(Collectors.toList());
            carParaVO.setCarNoList(carNoList);
        }
        List<ZdataTrailTracks> list = zdataTrailTracksService.getHistoryTrail(carParaVO);

        return list;
    }

    /**
     * dws josn2字符串转换
     * @param paraTrailPoints
     * @return
     */
    private String getTrailBoListString(String paraTrailPoints) {
        String trailPoints = CommonUtil.isNull(paraTrailPoints);
        if (CommonUtil.isNotBlank(trailPoints)) {
            trailPoints = trailPoints.replace("\\", "");
            trailPoints = trailPoints.replace("{\"{", "[{");
            trailPoints = trailPoints.replace("}\"}", "}]");
            trailPoints = trailPoints.replace("\",\"{", ",{");

            trailPoints = trailPoints.replace("ZdTrails:", "");
        }
        return trailPoints;
    }


    /**
     * 转josn
     * @param paraTrailPoints
     * @return
     */
    public List<TrailBo> getTrailBoList(String paraTrailPoints) {
        List<TrailBo> trailBoList = new ArrayList<>();
        String trailPoints = this.getTrailBoListString(paraTrailPoints);
        if (CommonUtil.isNotBlank(trailPoints) && !trailPoints.equals("{}")) {
            try {
                // 先转josn数组 然后循环 一个一个手动赋值
                JSONArray array = JSON.parseArray(trailPoints);
                SimpleDateFormat format1 = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss");
                SimpleDateFormat format2 = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
                for (Object o : array) {
                    JSONObject jsonObj = (JSONObject) o;
                    String captureTime = jsonObj.getString("captureTime");
                    String stateType = jsonObj.getString("stateType");
                    String platenumber = jsonObj.getString("platenumber");
                    String locationId = jsonObj.getString("locationId");
                    String locationCode = jsonObj.getString("locationCode");
                    String pointUuid = jsonObj.getString("pointUuid");
                    String sectionCode = jsonObj.getString("sectionCode");
                    String orgCode = jsonObj.getString("orgCode");
                    String pileNo = jsonObj.getString("pileNo");
                    String lon = jsonObj.getString("lon");
                    String lat = jsonObj.getString("lat");
                    TrailBo trailBo = new TrailBo();
                    captureTime = CommonUtil.isNull(captureTime);
                    if (captureTime.indexOf("T") > -1) {
                        Date dateTime = format1.parse(captureTime);
                        // 步骤2：使用DateTimeFormatter转字符串
                        String formattedDateStr = format2.format(dateTime);
                        trailBo.setCaptureTime(formattedDateStr);
                    }
                    trailBo.setStateType(stateType);
                    trailBo.setPlatenumber(platenumber);
                    trailBo.setLocationId(locationId);
                    trailBo.setLocationCode(locationCode);
                    trailBo.setPointUuid(pointUuid);
                    trailBo.setSectionCode(sectionCode);
                    trailBo.setOrgCode(orgCode);
                    trailBo.setPileno(pileNo);
                    if(CommonUtil.isNotBlank(lon)) {
                        trailBo.setLon(new BigDecimal(lon));
                    }
                    if(CommonUtil.isNotBlank(lat)) {
                        trailBo.setLat(new BigDecimal(lat));
                    }
                    trailBoList.add(trailBo);
                }
            } catch (Exception e) {
                e.printStackTrace();
                log.error("解析错误！");
            }
        }
        List<TrailBo>  rtnList = this.mapTrailBoList(trailBoList);

        return rtnList;
    }

    /**
     * 处理 : 合并门架抓拍和收费站抓拍流水------
     *
     * @param trailBoList
     * @return
     */
    private List<TrailBo> mapTrailBoList(List<TrailBo> trailBoList){
        List<TrailBo> mapList = new ArrayList<>();

        // 按照时间排序----------
       /* if (null != trailBoList && trailBoList.size() > 0){
            trailBoList =  trailBoList.stream().sorted(Comparator.comparing(TrailBo::getCaptureTime))
                    .collect(Collectors.toList());
        }*/

        // 去掉重合的
        SimpleDateFormat format2 = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        long threeMinutesInMillis = 4 * 60 * 1000; // 三分钟转换为毫秒

        Map<String,TrailBo> map = new HashMap<String,TrailBo>();
        if (null != trailBoList && trailBoList.size() > 0){
            for (TrailBo trailBo : trailBoList) {
                String stateType = CommonUtil.isNull(trailBo.getStateType()); // 类型
                String locationCode = CommonUtil.isNull(trailBo.getLocationCode()); // 设备IP地址
                String captureTime = CommonUtil.isNull(trailBo.getCaptureTime()); // 抓拍时间
                String imagesArry = CommonUtil.deleteEnd(trailBo.getImagesArry()); // 抓拍图片
                String mapKey = stateType + locationCode;
                if (map.containsKey(mapKey)){
                    TrailBo trailBoTemp = map.get(mapKey);
                    String captureTimeTemp = CommonUtil.isNull(trailBoTemp.getCaptureTime());
                    if (CommonUtil.isNotBlank(captureTime) && CommonUtil.isNotBlank(captureTimeTemp)){
                        try {
                            Date captureTimeDate1 = format2.parse(captureTime);
                            Date captureTimeDate2 = format2.parse(captureTimeTemp);
                            long diff = Math.abs(captureTimeDate2.getTime() - captureTimeDate1.getTime());
                            if (diff > threeMinutesInMillis) {
                                mapList.add(trailBo);
                            }else{
                                // 抓拍图片累加--------------
                                String imagesArryTemp = CommonUtil.deleteEnd(trailBoTemp.getImagesArry());
                                if (!imagesArry.equals("")){
                                    if (imagesArryTemp.equals("")) {
                                        trailBoTemp.setImagesArry(imagesArry);
                                    } else {
                                        trailBoTemp.setImagesArry(imagesArryTemp + "," + imagesArry);
                                    }
                                }
                            }
                        }catch (Exception e){
                            mapList.add(trailBo);
                            log.info("日期解析失败------------"+e.toString());
                        }
                    }else{
                        mapList.add(trailBo);
                    }
                }else{
                    mapList.add(trailBo);
                }

                if(stateType.equals(GANTRY_CAPTURE) || stateType.equals(STATION_CAPTURE)){
                    map.put(mapKey,trailBo);
                }

            }
        }
        return mapList;
    }





    /**
     * 提取jsonString
     * @param input
     * @return
     */
   /* public static List<TrailBo> extractJsonStringToTrailBo(String input) {
        String substring = input.substring(1);
        String processStr = substring.substring(0, substring.length() - 1);
        String[] split = processStr.split("\",\"");
        List<TrailBo> res = new ArrayList<>(split.length);
        for (int i = 0; i < split.length; i++) {
            String json, str;
            if(i == 0) {
                str = split[0].substring(1);
            } else if(i == split.length - 1) {
                str = split[split.length - 1].substring(0, split[split.length - 1].length() - 1);
            } else {
                str = split[i];
            }
            json = str.replace("\\", "");
            TrailBo trailBo = JSON.parseObject(json, TrailBo.class);
            res.add(trailBo);
        }
        return res;
    }*/




}
