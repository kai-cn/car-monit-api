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
import com.ruoyi.common.utils.StringUtils;
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
    public static final String redisTimeKey = "sys_config:syncSuspiciousCar_time"; // 默认2天
    public static final String supoer_mjnum = "sys_config:supoer_mjnum"; //  跨省：门架数量 5个
    public static final String road_supoer_mjnum = "sys_config:road_supoer_mjnum"; // 路段： 门架数量 3个


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

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;


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
     * 门架抓拍流水
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String snapshotFlowListKey(String curData, String configKey) {
        return Constants.snapshotFlowList + curData + ":" + configKey;
    }

    /**
     *  门架流水key
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String feeRecordsListKey(String curData, String configKey) {
        return Constants.feeRecordsList + curData + ":" + configKey;
    }

    /**
     * 轨迹点key
     *
     * @param configKey 参数键
     * @return 缓存键key
     */
    private String trailFittingKey(String curData, String configKey) {
        return Constants.trailFittingList + curData + ":" + configKey;
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
                        trailBo.setLocationId(jsonObj.getString("locationId"));
                        trailBo.setPlatenumber(jsonObj.getString("platenumber"));

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

                    List<TrailBo> rtnList = this.mapTrailBoList(josnList);
                    // 最后一个轨迹点需要查询
                    if (null != rtnList && rtnList.size() > 0) {

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
                   /* if(fwqcllsMap.containsKey(pointUuid)) {
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
                    }*/
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
                        tracks.setEntollstationid(CommonUtil.isNull(stationIpBO.getTollCode()));
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
                            tracks.setEntollstationid(CommonUtil.isNull(gantryIpBO.getGantryCode()));
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
                        tracks.setExtollstationid(CommonUtil.isNull(stationIpBO.getTollCode()));
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
                            tracks.setExtollstationid(CommonUtil.isNull(gantryIpBO.getGantryCode()));
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

        String captureTime = CommonUtil.isNull(trailBo.getCaptureTime());
        String applyTime1 = "";
        String applyTime2 = "";
        if (CommonUtil.isNotBlank(captureTime)) {
            // 获取开始时间
            SimpleDateFormat format2 = new SimpleDateFormat("yyyy-MM-dd");
            try {
                Date captureTimeDate1 = format2.parse(captureTime);
                String baseQueryTime = format2.format(captureTimeDate1);
                applyTime1 = baseQueryTime + " 00:00:00";
                applyTime2 = baseQueryTime + " 23:59:59";
            }catch (Exception e){

                log.info("日期解析失败------------"+e.toString());
            }
        }


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
            snapshotFlowAddcodeMap = snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(gantryCaptureUUids,applyTime1,applyTime2);
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
            stationcaptureAddcodeMap = stationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(stationCaptureUUids,applyTime1,applyTime2);
        }

        // 卡口流水
        Map<String, OdsLwzxsfsjFeeRecords01> feeRecordMap = new HashMap<>();
        feeRecordUUids = CommonUtil.deleteEnd(feeRecordUUids);
        if (CommonUtil.isNotBlank(feeRecordUUids)) {
            feeRecordMap = feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ByQueryUuids(feeRecordUUids,applyTime1,applyTime2);
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

                    // 车牌颜色
                    trailBo.setPlatecolor(CommonUtil.isNull(gantryCaptureBO.getPlatecolor()));
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
        Integer starTime = 2;
        Integer endTime = 4;
        BigDecimal bite = new BigDecimal("0.3");  // 门架抓拍和流水抓拍占比

        int supoerMjnum = 5; // 跨省：同步可疑车辆门架抓拍数量5个以上
        int roadSupoerMjnum = 3; // 路段：门架抓拍数量和门架流水数量对比


        // -------------- 从缓存取得对应的配置
        String redisTimeValue = redisCache.getCacheObject(redisTimeKey); // 默认2天
        if (CommonUtil.isNotBlank(redisTimeValue)){
            starTime = Integer.parseInt(redisTimeValue);
            log.info("从缓存取得时间配置--------："+redisTimeValue);
        }

        String redisBiteValue = redisCache.getCacheObject(redisBiteKey); // 比例默认为0.3
        if (CommonUtil.isNotBlank(redisBiteValue)){
            bite = new BigDecimal(redisBiteValue);
            log.info("从缓存取得占比配置------："+bite);
        }

        String supoerMjnumValue = redisCache.getCacheObject(supoer_mjnum); // 比例默认为5
        if (CommonUtil.isNotBlank(supoerMjnumValue)){
            supoerMjnum = Integer.parseInt(supoerMjnumValue);
            log.info("从缓存取得跨省：门架抓拍数量------："+supoerMjnum);
        }

        String roadSupoeMjnumValue = redisCache.getCacheObject(road_supoer_mjnum); // 比例默认为3
        if (CommonUtil.isNotBlank(roadSupoeMjnumValue)){
            roadSupoerMjnum = Integer.parseInt(roadSupoeMjnumValue);
            log.info("从缓存路段：取得门架抓拍数量------："+roadSupoeMjnumValue);
        }


        if (CommonUtil.isNull(isLocalhost).equals("local")) {
            log.info("本地配置------："+CommonUtil.isNull(isLocalhost));
            // 本地  分页1000条 30 到 1 天
            pageSize = 2000;
            endTime = starTime * 2;
           /* starTime = 1;
            endTime = 60;*/
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


        List<OdsSzdnGantry>  gantryList = odsSzdnGantryService.getGantryRedis();
        Map<String,OdsSzdnGantry> gantryMao = new HashMap<>();
        for (OdsSzdnGantry rtnOdsSzdnGantry:gantryList){
            gantryMao.put(CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode()),rtnOdsSzdnGantry);
        }


        // 位置信息
        Map<String,ZdataLocationDict> locationMap = zdataLocationDictService.getRedisList();

        // 根据路段查询路线map
        Map<String, OdsSzdnSection> sectionMap = sectionService.getSectionMap();

        // 查询路段list
        List<OdsSzdnSection> sectionlist = sectionService.getSectionList();

        // 筛选的路段信息-------------
       //  String indexRoadCode = "G45"; // 大广高速
        String indexSectionCode = "200R500450649000"; // 泰赣路段编码
        String indexSectionName = "泰赣路段"; //  泰赣路段
        Map<String,String> indexRoadCodeMap = new HashMap<>();
        List<String> sectionsQueryList = new ArrayList<>();
        for (OdsSzdnSection odsSzdnSection : sectionlist) {
            String roadCode = CommonUtil.isNull(odsSzdnSection.getRoadCode()); // 路线
            String sectionCode =  CommonUtil.isNull(odsSzdnSection.getSectionCode()); // 路段编码
            if (CommonUtil.isNotBlank(roadCode) && CommonUtil.isNotBlank(sectionCode)){
                // 大广高速
                if (sectionCode.equals(indexSectionCode)){
                    sectionsQueryList.add(sectionCode);
                    indexRoadCodeMap.put(sectionCode,roadCode);
                }
            }
        }

        List<String> sectionCodeList = new ArrayList<>();
        sectionCodeList.add(indexSectionCode);


        // -------可疑车辆存储时间
        Date now = new Date();
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
        String formattedDate = sdf.format(now);

        // -------获取当前时间的前2天
        Date currentDate = new Date();
        Calendar calendar = Calendar.getInstance();
        calendar.setTime(currentDate);
        calendar.add(Calendar.DAY_OF_MONTH, -starTime);
        Date twoDaysAgo = calendar.getTime();
        SimpleDateFormat sdf1 = new SimpleDateFormat("yyyy-MM-dd");
        String queryDate = sdf1.format(twoDaysAgo);

        String queryStartTime = queryDate + " 00:00:00";
        String queryEndTime = queryDate + " 23:59:59";
        log.info("查询时间范围" + queryStartTime + "到" + queryEndTime);


        // 门架抓拍流水
        OdsRtSzdnSnapshotFlowAddcode snapshotFlow = new OdsRtSzdnSnapshotFlowAddcode();
        snapshotFlow.setPlatecolor("黄色");
        snapshotFlow.setSectionList(sectionCodeList);
        snapshotFlow.setApplyTime1(queryStartTime);
        snapshotFlow.setApplyTime2(queryEndTime);


        // 门架交易流水
        OdsLwzxsfsjFeeRecords01 feeRecords01 = new OdsLwzxsfsjFeeRecords01();
        feeRecords01.setSectionList(sectionCodeList);
        feeRecords01.setInApplyTime1(queryStartTime);
        feeRecords01.setInApplyTime2(queryEndTime);



        for (int i = startNum; i <= endNum; i++) {
            // ----- 分页范围 ： 2000一次性查询
            carParaVO.setStartNum(pageSize);
            if (i > 1){
                Integer endRange = (i -1) * pageSize; // 当前页 -1
                carParaVO.setEndNum(endRange);
            }

            // 查询门架抓拍流水
            snapshotFlow.setStartNum(carParaVO.getStartNum());
            snapshotFlow.setEndNum(carParaVO.getEndNum());
            this.syncSnapshotFlow(snapshotFlow);


            // 门架交易流水
            feeRecords01.setStartNum(carParaVO.getStartNum());
            feeRecords01.setEndNum(carParaVO.getEndNum());
            this.syncFeeRecords(feeRecords01);


            // -------------轨迹点6000一次查询
            Integer pageSizeNew = 6000;
            carParaVO.setStartNum(pageSizeNew);
            if (i > 1){
                Integer endRange = (i -1) * pageSizeNew; // 当前页 -1
                carParaVO.setEndNum(endRange);
            }

            carParaVO.setApplyTime1(queryStartTime);
            carParaVO.setApplyTime2(queryEndTime);
            log.info("轨迹点SQL开始查询----------"+new Date());
            List<ZdataTrailTracks> carlistAll = zdataTrailTracksService.getLatestTrail(carParaVO);
            log.info("轨迹点SQL结束查询----------"+new Date()+"--数据："+carlistAll.size());


            // ---------------------------------- 跨省全程屏蔽
            List<ZdataTrailTracks> carlistQspb = new ArrayList<>();
            // ---------------------------------- 关注路段屏蔽
            List<ZdataTrailTracks> carlistLdpb = new ArrayList<>();

            for (ZdataTrailTracks zdataTrailTracksVo : carlistAll) {
                String trailtype = CommonUtil.isNull(zdataTrailTracksVo.getTrailtype());

                String firstCode = CommonUtil.isNull(zdataTrailTracksVo.getEntollstationid()); // 入口收费站编号
                String firstName = CommonUtil.repalaceSzdnTollName(zdataTrailTracksVo.getEntollstationname()); // 入口收费站名称
                String endCode = CommonUtil.isNull(zdataTrailTracksVo.getExtollstationid()); // 出口收费站编号
                String endName = CommonUtil.repalaceSzdnTollName(zdataTrailTracksVo.getExtollstationname()); // 出口收费站名称

                String carNo = CommonUtil.isNull(zdataTrailTracksVo.getPlateKey());

                // 外省进 外省出的车
                if (trailtype.equals("0") && firstName.indexOf("门架") > -1 && endName.indexOf("门架") > -1) {
                    carlistQspb.add(zdataTrailTracksVo);
                }else{
                    // 判断是否包含大广路段
                    String keyValue = zdataTrailTracksVo.getTrailPoints(); // 行驶轨迹
                    if (CommonUtil.isNotBlank(keyValue)) {
                        boolean exflag = false;
                        for (String sectionCodeValue: sectionsQueryList){
                            if (keyValue.indexOf(sectionCodeValue) > -1){
                                exflag = true;
                            }
                        }
                        if (exflag){
                            carlistLdpb.add(zdataTrailTracksVo);
                            TrailTracksVo trailTracksVo = new TrailTracksVo();
                            trailTracksVo.setPlateKey(carNo);
                            trailTracksVo.setEnterTime(zdataTrailTracksVo.getEnterTime());
                            trailTracksVo.setExitTime(zdataTrailTracksVo.getExitTime());

                            // 按照车牌存放当天轨迹
                            List<TrailTracksVo> keyList = new ArrayList<>();

                            String trailFittingRedisKey = this.trailFittingKey(formattedDate, carNo);
                            List<TrailTracksVo> oldFittingList = redisCache.getCacheObject(trailFittingRedisKey);
                            if (null != oldFittingList && oldFittingList.size() > 0) {
                                keyList = oldFittingList;
                            }
                            keyList.add(trailTracksVo);
                            redisCache.setCacheObject(trailFittingRedisKey, keyList);

                        }
                    }
                }
            }


            // ---------------------------------- 跨省全程屏蔽
            if (null != carlistQspb && carlistQspb.size() > 0) {
                for (ZdataTrailTracks tracks : carlistQspb) {
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
                        if (conutGantryCapture > supoerMjnum) {
                            String escapedTypeRemark = "";
                            boolean addFlag = false;
                            if (conutFeeRecord == 0) {
                                escapedTypeRemark = "跨省全程屏蔽：其中门架牌识流水数量:" + conutGantryCapture + "，门架交易流水数量:" + conutFeeRecord+"。";
                                addFlag = true;
                            }
                            if (addFlag) {
                                escapedType = Constants.escapedType_20;
                                tracks.setEscapedType(escapedType); // 屏蔽
                                tracks.setEscapedTypeRemark(escapedTypeRemark);
                                tracks.setEscapedTfcj("1");  // 逃费场景

                                TrailInfo trailInfo = this.changeData(tracks, josnList); // 获取设备的经纬度
                                // 车牌颜色
                                tracks.setPlateColor(this.getPlateColor(trailInfo.getTrailList()));
                                trailInfo.setTrailUuid(carNo);

                                String key = this.getSuspiciousKey(formattedDate, carNo);
                                redisCache.setCacheObject(key, trailInfo);
                            }
                        }
                    }
                }
            }

            // ---------------------------------- 关注路段屏蔽
            if (null != carlistLdpb && carlistLdpb.size() > 0) {
                for (ZdataTrailTracks tracks : carlistLdpb) {
                    String carNo = CommonUtil.isNull(tracks.getPlateKey());
                    String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                    String escapedType = "";
                    List<TrailBo> josnList = new ArrayList<TrailBo>();
                    if (CommonUtil.isNotBlank(keyValue)) {
                        josnList = this.getTrailBoList(keyValue);
                        tracks.setTrailPoints("");  // 行驶轨迹

                        // ---------------------------分析场景: 路段抓拍和流水抓拍 占比
                        int conutGantryCapture = 0;
                        int conutFeeRecord = 0;

                        for (TrailBo rtnTrailBo : josnList) {
                            String sectionCode = CommonUtil.isNull(rtnTrailBo.getSectionCode()); // 路段信息
                            String stateType = CommonUtil.isNull(rtnTrailBo.getStateType());
                            /*
                            String locationCode = CommonUtil.isNull(rtnTrailBo.getLocationCode()); // 设备IP地址
                            String devLocatCode = "";
                            if (locationMap.containsKey(locationCode)){
                                devLocatCode = CommonUtil.isNull(locationMap.get(locationCode).getStandardCode()); // 收费站/门架code
                            }*/

                            if (CommonUtil.isNotBlank(sectionCode)) {
                                if (indexRoadCodeMap.containsKey(sectionCode)) {
                                    if (stateType.equals(GANTRY_CAPTURE)) {
                                        // 门架抓拍
                                        conutGantryCapture++;

                                       /* boolean isNotXymjFlag = true;
                                        // 判断是否是虚拟门架---------
                                        if (CommonUtil.isNotBlank(devLocatCode)){
                                            // 找到门架信息
                                            if (gantryMao.containsKey(devLocatCode)){
                                                OdsSzdnGantry gantry = gantryMao.get(devLocatCode);
                                                if (CommonUtil.isNull(gantry.getIsVirtual()).equals("1")){
                                                    isNotXymjFlag = false;
                                                }
                                            }
                                        }
                                        if (isNotXymjFlag){
                                            // 门架抓拍
                                            conutGantryCapture++;
                                        }*/
                                    } else if (stateType.equals(FeeRecord)) {
                                        // 卡口流水
                                        conutFeeRecord++;
                                    }
                                }
                            }
                        }
                        // 该路段门架比例一定的数值--------- conutGantryCapture > 0 && conutGantryCapture > conutFeeRecord
                        if (conutGantryCapture > roadSupoerMjnum){
                           //  BigDecimal costBite = new BigDecimal(conutFeeRecord).divide(new BigDecimal(conutGantryCapture), 4, BigDecimal.ROUND_HALF_UP);
                            String escapedTypeRemark = "";
                            boolean addFlag = false;
                            if (conutFeeRecord == 0) {
                                escapedTypeRemark = indexSectionName+"全程屏蔽：其中门架牌识流水数量:" + conutGantryCapture + "，门架交易流水数量:" + conutFeeRecord+"。";
                                addFlag = true;
                            }

                           /* else{
                                if (bite.compareTo(costBite) >= 0){
                                    escapedTypeRemark = indexSectionName+"部分屏蔽：其中门架牌识流水数量:" + conutGantryCapture + "，门架交易流水数量:" + conutFeeRecord+"。";
                                    addFlag = true;
                                }
                            }*/

                            if (addFlag) {
                                escapedType = Constants.escapedType_20;
                                tracks.setEscapedType(escapedType); // 屏蔽
                                tracks.setEscapedTypeRemark(escapedTypeRemark);
                                tracks.setEscapedTfcj("2");  // 路段屏蔽

                                TrailInfo trailInfo = this.changeData(tracks, josnList); // 获取设备的经纬度

                                // 车牌颜色
                                tracks.setPlateColor(this.getPlateColor(trailInfo.getTrailList()));
                                trailInfo.setTrailUuid(carNo);

                                String key = this.getSuspiciousKey(formattedDate, carNo);
                                redisCache.setCacheObject(key, trailInfo);
                            }
                        }
                    }
                }
            }

        }

    }

    /**
     * 获取车牌颜色
     *
     * @param trailList
     * @return
     */
    private String getPlateColor(List<TrailBo> trailList) {
        String plateColor = "";
        if (null != trailList && trailList.size() > 0) {
            int countNum = 0;
            for (TrailBo trailBo : trailList) {
                String stateType = CommonUtil.isNull(trailBo.getStateType());
                if (stateType.equals(GANTRY_CAPTURE)) {
                    // 查询第一个门架抓拍的车牌号
                    if (countNum == 0) {
                        TrailBo changeTrailBo = this.getByTrailBo(trailBo);
                        if (null != changeTrailBo) {
                            plateColor = CommonUtil.isNull(changeTrailBo.getPlatecolor());
                            return plateColor;
                        }
                    }
                    countNum++;
                }
            }
        }
        return plateColor;
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
     * 获取门架抓拍流水
     *
     * @param snapshotFlow
     */
    @Override
    public void syncSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode snapshotFlow) {
        log.info("门架抓拍流水SQL开始查询----------"+new Date());
        Date now = new Date();
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
        String redisDate = sdf.format(now);
        // ----- 分页范围
        List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeListNew(snapshotFlow);
        log.info("门架抓拍流水SQL结束查询----------"+new Date()+"--数据："+list.size());
        for (OdsRtSzdnSnapshotFlowAddcode snapshotFlowAddcode : list) {
            if (CommonUtil.isNotBlank(snapshotFlowAddcode.getPlatenumber()) && null != snapshotFlowAddcode.getSnapshottime()) {
                List<OdsRtSzdnSnapshotFlowAddcode> keyList = new ArrayList<>();
                // 按照路段和车牌
                String key = CommonUtil.isNull(snapshotFlowAddcode.getSectioncode()) + "@@" + CommonUtil.isNull(snapshotFlowAddcode.getPlatenumber());
                String redisKey = this.snapshotFlowListKey(redisDate, key);
                List<OdsRtSzdnSnapshotFlowAddcode> oldList = redisCache.getCacheObject(redisKey);
                if (null != oldList && oldList.size() > 0) {
                    keyList = oldList;
                }
                keyList.add(snapshotFlowAddcode);
                redisCache.setCacheObject(redisKey, keyList);
            }
        }
    }


    /**
     * 获取门架交易流水
     *
     * @param feeRecords
     */
    @Override
    public void syncFeeRecords(OdsLwzxsfsjFeeRecords01 feeRecords) {
        log.info("门架交易流水SQL开始查询----------"+new Date());
        Date now = new Date();
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
        String redisDate = sdf.format(now);
        // ----- 分页范围
        List<OdsLwzxsfsjFeeRecords01> list = feeRecords01Service.selectOdsLwzxsfsjFeeRecords01ListNew(feeRecords);
        log.info("门架交易流水SQL开始查询----------" + new Date() + "数据--" + list.size());
        for (OdsLwzxsfsjFeeRecords01 feeRecords01 : list) {
            String vehicleplate = CommonUtil.isNull(feeRecords01.getVehicleplate()); // 车牌号_颜色
            if (vehicleplate.indexOf("_") > -1){
                String[] vehicleplateStr = vehicleplate.split("_");
                String vehicleplateChange = CommonUtil.isNull(vehicleplateStr[0]);
                if (CommonUtil.isNotBlank(vehicleplateChange)){
                    // 按照路段和车牌
                    List<OdsLwzxsfsjFeeRecords01> keyList = new ArrayList<>();
                    String key = CommonUtil.isNull(feeRecords01.getSectioncode()) + "@@" + CommonUtil.isNull(vehicleplateChange);
                    String redisKey = this.feeRecordsListKey(redisDate, key);
                    List<OdsLwzxsfsjFeeRecords01> oldList = redisCache.getCacheObject(redisKey);
                    if (null != oldList && oldList.size() > 0) {
                        keyList = oldList;
                    }
                    keyList.add(feeRecords01);
                    redisCache.setCacheObject(redisKey, keyList);
                }
            };
        }
    }

    /**
     * 门架抓拍流水 和 获取门架交易流水 对比
     */
    @Override
    public void separateSnapshotFlowTimeList() {

        Date now = new Date();
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
        String redisDate = sdf.format(now);

        int roadSupoerMjnum = 3; // 路段：门架抓拍数量和门架流水数量对比
        String roadSupoeMjnumValue = redisCache.getCacheObject(road_supoer_mjnum); // 比例默认为3
        if (CommonUtil.isNotBlank(roadSupoeMjnumValue)){
            roadSupoerMjnum = Integer.parseInt(roadSupoeMjnumValue);
            log.info("从缓存路段：取得门架抓拍数量------："+roadSupoeMjnumValue);
        }

        long thirtyMinutesInMillis = 60 * 60 * 1000; // 30分钟转换为毫秒

        Collection<String> keys = redisCache.keys(Constants.snapshotFlowList + redisDate + "*");
        if (null != keys && keys.size() > 0) {
            for (String key : keys) {
                List<OdsRtSzdnSnapshotFlowAddcode> keyList = redisCache.getCacheObject(key);
                if (null != keyList && keyList.size() >= roadSupoerMjnum) {
                    // 按照车辆时间排序
                    keyList =  keyList.stream().sorted(Comparator.comparing(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime))
                            .collect(Collectors.toList());

                    // 判断有几次通行
                    List<OdsRtSzdnSnapshotFlowAddcode> snapshotList = new ArrayList<>();
                    for (int i = 0; i < keyList.size(); i++) {
                        OdsRtSzdnSnapshotFlowAddcode rtndata = keyList.get(i);
                        if (i == 0) {
                            snapshotList.add(rtndata);
                        } else {
                            // 时间相差1个小时之内为同一组
                            Date preSnapshottime = keyList.get(i - 1).getSnapshottime();
                            Date snapshottime = rtndata.getSnapshottime();

                            long diff = Math.abs(snapshottime.getTime() - preSnapshottime.getTime());
                            if (diff > thirtyMinutesInMillis) {
                                // 超过了60分钟
                                this.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum,redisDate);

                                // 重新计算---------------
                                snapshotList = new ArrayList<>();
                                snapshotList.add(rtndata);

                            } else {
                                snapshotList.add(rtndata);
                            }
                        }
                    }
                    this.isFeeRecordsExist(key, snapshotList, roadSupoerMjnum,redisDate);
                }
            }
        }

        // 删除redis
        if (null != keys && keys.size() > 0){
            // 删除redis
            redisCache.deleteObject(keys);
        }

        Collection<String> freeKeys = redisCache.keys(Constants.feeRecordsList + redisDate + "*");
        if (null != freeKeys && freeKeys.size() > 0){
            // 删除redis
            redisCache.deleteObject(freeKeys);
        }

        Collection<String> trailFittingKeys = redisCache.keys(Constants.trailFittingList + redisDate + "*");
        if (null != trailFittingKeys && trailFittingKeys.size() > 0){
            // 删除redis
            redisCache.deleteObject(trailFittingKeys);
        }


    }

    /**
     * 对比找到可疑车辆
     * @param key
     * @param snapshotList
     * @param roadSupoerMjnum
     */
    private void isFeeRecordsExist(String key, List<OdsRtSzdnSnapshotFlowAddcode> snapshotList, int roadSupoerMjnum, String redisDate) {

        if (CommonUtil.isNotBlank(key) && null != snapshotList && snapshotList.size() >= roadSupoerMjnum && snapshotList.size() >= 2) {
            String[] roadCarKeyStr = key.split(":");

            // 门架----------
            List<OdsSzdnGantry>  gantryList = odsSzdnGantryService.getGantryRedis();
            Map<String,OdsSzdnGantry> gantryMao = new HashMap<>();
            for (OdsSzdnGantry rtnOdsSzdnGantry:gantryList){
                gantryMao.put(CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode()),rtnOdsSzdnGantry);
            }

            // 根据路段查询路线map
            Map<String, OdsSzdnSection> sectionMap = sectionService.getSectionMap();

            String stateType = GANTRY_CAPTURE; // 门架抓拍
            SimpleDateFormat format2 = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

            if (roadCarKeyStr.length > 1) {

                OdsRtSzdnSnapshotFlowAddcode firstBo = snapshotList.get(0); // 第一个
                OdsRtSzdnSnapshotFlowAddcode endBo = snapshotList.get(snapshotList.size() -1); // 最后一个

                Date startTime = firstBo.getSnapshottime();
                Date endTime = endBo.getSnapshottime();

                long startTimeLong = startTime.getTime();
                long endTimeLong = endTime.getTime();

                String roadCarKey = roadCarKeyStr[1];
                String sectionCode = CommonUtil.isNull(firstBo.getSectioncode());

                String sectionName = "";
                String roadCode ="";
                if (sectionMap.containsKey(sectionCode)){
                    OdsSzdnSection odsSzdnSection = sectionMap.get(sectionCode);
                    sectionName = odsSzdnSection.getSectionName();
                    roadCode = odsSzdnSection.getRoadCode();
                }


                String redisKey = this.feeRecordsListKey(redisDate,roadCarKey);
                boolean isAddFlag = false;
                List<OdsLwzxsfsjFeeRecords01> oldList = redisCache.getCacheObject(redisKey);
                if (null != oldList && oldList.size() > 0) {
                    int freeCountNum = 0; // 计费模块响应计费结果 0 成功 1失败
                    for (OdsLwzxsfsjFeeRecords01 feeRecords01 : oldList) {
                        Date transtime = feeRecords01.getTranstime();
                        if (null != transtime) {
                            long transtimelong = transtime.getTime();
                            if (transtimelong >= startTimeLong && transtimelong <= endTimeLong) {
                                //时间在范围里
                                BigDecimal fee = feeRecords01.getFee();
                                if (null != fee && fee.compareTo(BigDecimal.ZERO) > 0) {
                                    freeCountNum = freeCountNum + 1;
                                }
                            }
                        }
                    }
                    if (freeCountNum > 0) {
                        // 有数据 后续做部分
                    } else {
                        isAddFlag = true;
                    }
                }else{
                    // 无数据------------
                    isAddFlag = true;
                }

                if(isAddFlag) {
                    String carNo = firstBo.getPlatenumber();

                    int  trailFitting = 0; // 是否有轨迹点

                    // ------------ 判断是否有出入口轨迹
                    String trailFittingRedisKey = this.trailFittingKey(redisDate, carNo);
                    List<TrailTracksVo> oldFittingList = redisCache.getCacheObject(trailFittingRedisKey);
                    if (null != oldFittingList && oldFittingList.size() > 0) {
                        for (TrailTracksVo trailTracksVo : oldFittingList) {
                            Date trailTtartTime = trailTracksVo.getEnterTime(); // 进入时间
                            Date trailEndTime = trailTracksVo.getExitTime(); // 离开时间
                            if (null != trailTtartTime && null != trailEndTime) {
                                if (endTimeLong >= trailTtartTime.getTime() && endTimeLong <= trailEndTime.getTime()) {
                                    trailFitting = trailFitting + 1;
                                }
                            }
                        }
                    }

                    if (trailFitting == 0) {
                        String platecolor = firstBo.getPlatecolor();

                        ZdataTrailTracks tracks = new ZdataTrailTracks();
                        tracks.setUuid(StringUtils.getUUID());
                        tracks.setPlateKey(carNo);
                        // tracks.setEnvehicleid(carNo);
                        // tracks.setEnaxlecount(0);
                        tracks.setEnterTime(startTime);

                        String startGantryid = CommonUtil.isNull(firstBo.getGantrycode());
                        tracks.setEntollstationid(startGantryid);
                        if (gantryMao.containsKey(startGantryid)) {
                            OdsSzdnGantry odsSzdnGantry = gantryMao.get(startGantryid);
                            tracks.setEntollstationname(odsSzdnGantry.getGantryName()); // 门架名称

                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                tracks.setStartLon(odsSzdnGantry.getLon()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                tracks.setStratLat(odsSzdnGantry.getLat()); // 经度
                            }
                        }

                        tracks.setEnvehicletype(CommonUtil.isNull(firstBo.getCartypecode())); // 车型
                        tracks.setEnvehicleid(carNo); // 车牌号


                        tracks.setExitTime(endTime);

                        String endGantryid = CommonUtil.isNull(endBo.getGantrycode());
                        tracks.setExtollstationid(endGantryid);
                        if (gantryMao.containsKey(endGantryid)) {
                            OdsSzdnGantry odsSzdnGantry = gantryMao.get(endGantryid);
                            tracks.setExtollstationname(odsSzdnGantry.getGantryName()); // 门架名称

                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLon())) {
                                tracks.setEndLon(odsSzdnGantry.getLon()); // 经度
                            }
                            if (CommonUtil.isNotBlank(odsSzdnGantry.getLat())) {
                                tracks.setEndLat(odsSzdnGantry.getLat()); // 经度
                            }
                        }

                        tracks.setExvehicleid(carNo); // 车牌号

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


                        // -------------- 车辆轨迹点
                        List<TrailBo> josnList = new ArrayList<>();
                        for (OdsRtSzdnSnapshotFlowAddcode snapshotBo : snapshotList){
                            TrailBo trailBo = new TrailBo();

                            String gantryCode = CommonUtil.isNull(snapshotBo.getGantrycode());

                            trailBo.setStateType(stateType);
                            trailBo.setPlatenumber(snapshotBo.getPlatenumber());
                            trailBo.setLocationId(gantryCode);
                            trailBo.setLocationCode(gantryCode);
                            trailBo.setPointUuid(snapshotBo.getDatauuid());
                            trailBo.setSectionCode(snapshotBo.getSectioncode());


                            Date captureTime = snapshotBo.getSnapshottime();
                            if (null != captureTime) {
                                trailBo.setCaptureTime(format2.format(captureTime));
                            }

                            trailBo.setDevCode(gantryCode); // 设备编号
                            if (gantryMao.containsKey(gantryCode)) {
                                OdsSzdnGantry odsSzdnGantry = gantryMao.get(gantryCode);
                                String lon = odsSzdnGantry.getLon();
                                String lat = odsSzdnGantry.getLat();

                                trailBo.setPileno(odsSzdnGantry.getPileNo()); // 桩号
                                if(CommonUtil.isNotBlank(lon)) {
                                    trailBo.setLon(new BigDecimal(lon));
                                }
                                if(CommonUtil.isNotBlank(lat)) {
                                    trailBo.setLat(new BigDecimal(lat));
                                }

                                trailBo.setDevName(odsSzdnGantry.getGantryName());  // 设备名称
                            }

                            // 设备名称没有默认位置信息--------------
                            if (CommonUtil.isBlank(trailBo.getDevName())){
                                trailBo.setDevName(gantryCode);
                            }

                            trailBo.setRoadCode(roadCode);
                            josnList.add(trailBo);
                        }



                        String  escapedTypeRemark = sectionName+"路段全程屏蔽：其中门架牌识流水数量:" +snapshotList.size() + "，门架交易成功流水数量:0。";
                        String escapedType = Constants.escapedType_20;
                        tracks.setEscapedType(escapedType); // 屏蔽
                        tracks.setEscapedTypeRemark(escapedTypeRemark);
                        tracks.setEscapedTfcj("3");  // 路段屏蔽

                        // 车牌颜色
                        tracks.setPlateColor(platecolor);


                        TrailInfo trailInfo = new TrailInfo();
                        trailInfo.setTracks(tracks);
                        trailInfo.setTrailList(josnList);
                        trailInfo.setTrailUuid(carNo);

                        String kykey = this.getSuspiciousKey(redisDate, carNo);
                        Object isExistObj = redisCache.getCacheObject(kykey);
                        if (isExistObj == null) {
                            redisCache.setCacheObject(kykey, trailInfo);
                        }
                    }
                }
            }
        }
    }

}
