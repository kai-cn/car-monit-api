package com.ruoyi.base.controller;

import com.github.pagehelper.PageInfo;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.base.service.v3.query.TrafficListFacade;
import com.ruoyi.base.service.v3.query.TrafficQueryEngineService;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficSearchResult;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import com.ruoyi.base.service.v3.query.TrailPointLoader;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.constant.HttpStatus;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.PageDomain;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.core.page.TableSupport;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@Slf4j
@RestController
@RequestMapping("/base/sysutil")
public class SysUtilController extends BaseController {

    @Autowired
    private ISysUtilService sysUtilService;

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private TrafficListFacade trafficListFacade;

    @Autowired
    private TrailPointLoader trailPointLoader;

    @Autowired
    private TrafficQueryEngineService queryEngineService;

    /**
     * 获取收费站基础信息详细信息
     */
    @GetMapping(value = "/saveRedis")
    public AjaxResult saveRedis(SysUtil sysUtil) {
        return sysUtilService.saveRedis(sysUtil);
    }


  /*  *//**
     * 同步车俩实时轨迹
     *//*
    @PostMapping(value = "/syncTrack")
    public Map<String, List<TrailBo>> syncTrack(@RequestBody CarParaVO carParaVO) {
        Map<ZdataTrailTracks, List<TrailBo>> carMap = sysUtilService.syncTrack(carParaVO);

        Map<String, List<TrailBo>> josnMap = new HashMap<>(); // 返回对象
        if (null != carMap) {
            for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : carMap.entrySet()) {
                josnMap.put(JSON.toJSONString(entry.getKey()), entry.getValue());
            }
        }
        return josnMap;
    }


    *//**
     * 同步可疑车俩
     *//*
    @PostMapping(value = "/syncSuspiciousCar")
    public Map<String, List<TrailBo>> syncSuspiciousCar(@RequestBody CarParaVO carParaVO) {
        Map<ZdataTrailTracks, List<TrailBo>> carMap = sysUtilService.syncSuspiciousCar(carParaVO);

        Map<String, List<TrailBo>> josnMap = new HashMap<>(); // 返回对象
        if (null != carMap) {
            for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : carMap.entrySet()) {
                josnMap.put(JSON.toJSONString(entry.getKey()), entry.getValue());
            }
        }
        return josnMap;
    }*/

    /**
     * 车俩历史轨迹：根据车牌号查询
     *
     * <p>V3：默认 legacy；显式切 es 后由 ES 取轨迹元数据（车牌 + extime 范围），
     * 再按 (cid, extime) 回 GaussDB 取 trailpoints。</p>
     */
    @GetMapping(value = "/carTrackQueryByCarNo")
    public TableDataInfo carTrackQueryByCarNo(CarParaVO carParaVO) {
        if (!queryEngineService.isEsActive()) {
            return carTrackQueryByCarNoLegacy(carParaVO);
        }
        return carTrackQueryByCarNoFromEs(carParaVO);
    }

    private TableDataInfo carTrackQueryByCarNoFromEs(CarParaVO carParaVO) {
        TableDataInfo rspData = new TableDataInfo();
        rspData.setCode(HttpStatus.SUCCESS);
        rspData.setMsg("查询成功");
        if (CommonUtil.isBlank(carParaVO.getCarNo())) {
            rspData.setRows(new ArrayList<>());
            rspData.setTotal(0);
            return rspData;
        }
        try {
            PageDomain page = TableSupport.buildPageRequest();
            int pageNum = page.getPageNum() == null ? 1 : page.getPageNum();
            int pageSize = page.getPageSize() == null ? 10 : page.getPageSize();

            TrafficSearchResult result = trafficListFacade.queryTrail(
                    carParaVO.getCarNo(), carParaVO.getApplyTime1(), carParaVO.getApplyTime2(),
                    pageNum, pageSize);

            Long start = TrafficTimeUtils.parse(carParaVO.getApplyTime1(), false);
            Long end = TrafficTimeUtils.parse(carParaVO.getApplyTime2(), true);
            long now = System.currentTimeMillis();
            if (start == null) {
                start = now - TimeUnit.DAYS.toMillis(180);
            }
            if (end == null) {
                end = now;
            }

            List<ZdataTrailTracks> tracksList = toTrailTracks(result);
            // 批量回查轨迹点，避免 N+1（设计 §5.8.4）
            List<String> cids = new ArrayList<>();
            for (ZdataTrailTracks tracks : tracksList) {
                if (CommonUtil.isNotBlank(tracks.getUuid())) {
                    cids.add(tracks.getUuid());
                }
            }
            Map<String, String> points = trailPointLoader.load(cids, start, end);
            for (ZdataTrailTracks tracks : tracksList) {
                tracks.setTrailPoints(points.get(tracks.getUuid()));
            }

            List<TrailInfo> rtnList = buildTrailInfos(tracksList);
            rspData.setRows(rtnList);
            rspData.setTotal(result.getTotal());
            return rspData;
        } catch (TrafficQueryException e) {
            log.warn("[轨迹查询-V3] {}", e.getMessage());
            rspData.setCode(e.getCode());
            rspData.setMsg(e.getMessage());
            rspData.setRows(new ArrayList<>());
            rspData.setTotal(0);
            return rspData;
        } catch (Exception e) {
            log.error("[轨迹查询-V3] 查询异常", e);
            rspData.setCode(500);
            rspData.setMsg("查询失败: " + e.getMessage());
            rspData.setRows(new ArrayList<>());
            rspData.setTotal(0);
            return rspData;
        }
    }

    private List<ZdataTrailTracks> toTrailTracks(TrafficSearchResult result) {
        List<ZdataTrailTracks> list = new ArrayList<>();
        for (Map<String, Object> row : result.getRows()) {
            ZdataTrailTracks t = new ZdataTrailTracks();
            t.setUuid(asString(row.get("cid")));
            t.setPlateKey(asString(row.get("envehicleid")));
            t.setEnvehicleid(asString(row.get("envehicleid")));
            t.setExvehicleid(asString(row.get("exvehicleid")));
            t.setEnterTime(toDate(row.get("entime")));
            t.setExitTime(toDate(row.get("extime")));
            t.setEntollstationid(asString(row.get("entollstationid")));
            t.setExtollstationid(asString(row.get("extollstationid")));
            t.setEnterLocationcode(asString(row.get("entollstationid")));
            t.setExitLocationcode(asString(row.get("extollstationid")));
            t.setEntollstationname(asString(row.get("entollstationname")));
            t.setExtollstationname(asString(row.get("extollstationname")));
            Object pointCount = row.get("point_count");
            if (pointCount instanceof Number) {
                t.setPointCount(((Number) pointCount).longValue());
            }
            Object enaxle = row.get("enaxlecount");
            if (enaxle instanceof Number) {
                t.setEnaxlecount(((Number) enaxle).intValue());
            }
            t.setEnvehicleclass(asString(row.get("envehicleclass")));
            t.setEnvehicletype(asString(row.get("envehicletype")));
            t.setExvehicleclass(asString(row.get("exvehicleclass")));
            t.setExvehicletype(asString(row.get("exvehicletype")));
            t.setEnweight(toBigDecimal(row.get("enweight")));
            t.setExweight(toBigDecimal(row.get("exweight")));
            Object trailtype = row.get("trailtype");
            if (trailtype != null) {
                t.setTrailtype(String.valueOf(trailtype));
            }
            list.add(t);
        }
        return list;
    }

    private List<TrailInfo> buildTrailInfos(List<ZdataTrailTracks> list) {
        List<TrailInfo> rtnList = new ArrayList<>();
        if (list == null || list.isEmpty()) {
            return rtnList;
        }
        for (ZdataTrailTracks tracks : list) {
            String carNo = CommonUtil.isNull(tracks.getPlateKey());
            String keyValue = tracks.getTrailPoints();
            List<TrailBo> josnList = new ArrayList<>();
            if (CommonUtil.isNotBlank(keyValue)) {
                josnList = sysUtilService.getTrailBoList(keyValue);
                tracks.setTrailPoints("");
                TrailInfo trailInfo = sysUtilService.changeData(tracks, josnList);
                trailInfo.setTrailUuid(carNo);
                rtnList.add(trailInfo);
            }
        }
        return rtnList;
    }

    private String asString(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private Date toDate(Object value) {
        if (value instanceof Date) {
            return (Date) value;
        }
        if (value instanceof Number) {
            return new Date(((Number) value).longValue());
        }
        if (value instanceof CharSequence) {
            Long millis = TrafficTimeUtils.parse(value.toString(), false);
            return millis == null ? null : new Date(millis);
        }
        return null;
    }

    private BigDecimal toBigDecimal(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof BigDecimal) {
            return (BigDecimal) value;
        }
        try {
            return new BigDecimal(String.valueOf(value));
        } catch (Exception e) {
            return null;
        }
    }

    private TableDataInfo carTrackQueryByCarNoLegacy(CarParaVO carParaVO) {
        startPage();
        List<ZdataTrailTracks> list = new ArrayList<>();
        if (CommonUtil.isNotBlank(carParaVO.getCarNo())) {
            carParaVO.setFlag("bannian");  // 默认查询半年的数据
            list = sysUtilService.carTrackQueryNew(carParaVO);
        }
        List<TrailInfo> rtnList = new ArrayList<>();
        if (null != list && list.size() > 0) {
            for (ZdataTrailTracks tracks : list) {
                String carNo = CommonUtil.isNull(tracks.getPlateKey());
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = sysUtilService.getTrailBoList(keyValue);
                    tracks.setTrailPoints("");  // 行驶轨迹

                    TrailInfo trailInfo = sysUtilService.changeData(tracks, josnList); // 获取设备的经纬度
                    trailInfo.setTrailUuid(carNo);
                    rtnList.add(trailInfo);
                }
            }
        }

        TableDataInfo rspData = new TableDataInfo();
        rspData.setCode(HttpStatus.SUCCESS);
        rspData.setMsg("查询成功");
        rspData.setRows(rtnList);
        rspData.setTotal(new PageInfo(list).getTotal());
        return rspData;
    }


    /**
     * 车俩历史轨迹：根据车牌号时间段查询
     * @param carParaVO
     * @return
     */
    @GetMapping(value = "/carTrackQueryByTime")
    public TableDataInfo carTrackQueryByTime(CarParaVO carParaVO) {
        startPage();
        List<ZdataTrailTracks> list = new ArrayList<>();
        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            carParaVO.setCarlist(carlist);
            list = sysUtilService.carTrackQueryNew(carParaVO);
        }

        List<TrailInfo> rtnList = new ArrayList<>();
        if (null != list && list.size() > 0) {
            for (ZdataTrailTracks tracks : list) {
                String carNo = CommonUtil.isNull(tracks.getPlateKey());
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = sysUtilService.getTrailBoList(keyValue);
                    // tracks.setTrailPoints("");  // 行驶轨迹

                    TrailInfo trailInfo = sysUtilService.changeData(tracks, josnList); // 获取设备的经纬度
                    trailInfo.setTrailUuid(carNo);
                    rtnList.add(trailInfo);
                }
            }
        }


        TableDataInfo rspData = new TableDataInfo();
        rspData.setCode(HttpStatus.SUCCESS);
        rspData.setMsg("查询成功");
        rspData.setRows(rtnList);
        rspData.setTotal(new PageInfo(list).getTotal());
        return rspData;
    }


    /**
     * 对象转换
     */
    @PostMapping(value = "/changeTrailInfo")
    public TrailInfo changeTrailInfo(@RequestBody TrailInfo trailInfo) {
        if (null != trailInfo) {
            ZdataTrailTracks tracks = trailInfo.getTracks();
            List<TrailBo> trailList = trailInfo.getTrailList();
            if (null != tracks && null != trailList && trailList.size() > 0) {
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
                for (TrailBo trailBo : trailList) {
                    trailBo.setIsQuery("1"); // 需要查询数据-----------
                }
                String carNo = CommonUtil.isNull(tracks.getPlateKey());
                TrailInfo changeBo = sysUtilService.changeData(trailInfo.getTracks(), trailInfo.getTrailList()); // 获取设备的经纬度
                changeBo.setTrailUuid(carNo);
                return changeBo;
            }
        }
        return trailInfo;
    }

    /**
     * 获取抓拍对象
     *
     * @param trailBo
     * @return
     */
    @GetMapping(value = "/getByTrailBo")
    public TrailBo getByTrailBo(TrailBo trailBo) {
        return sysUtilService.getByTrailBo(trailBo);
    }


}
