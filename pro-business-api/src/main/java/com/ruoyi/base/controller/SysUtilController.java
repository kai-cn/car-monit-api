package com.ruoyi.base.controller;

import com.alibaba.fastjson2.JSON;
import com.github.pagehelper.PageInfo;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.constant.HttpStatus;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/base/sysutil")
public class SysUtilController extends BaseController {

    @Autowired
    private ISysUtilService sysUtilService;

    @Autowired
    private RedisCache redisCache;

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
     * @param carParaVO
     * @return
     */
    @GetMapping(value = "/carTrackQueryByCarNo")
    public TableDataInfo carTrackQueryByCarNo(CarParaVO carParaVO) {
        startPage();
        List<ZdataTrailTracks> list = new ArrayList<>();
        if(CommonUtil.isNotBlank(carParaVO.getCarNo())){
            list = sysUtilService.carTrackQueryNew(carParaVO);
        }
        List<TrailInfo> rtnList = new ArrayList<>();
        if (null != list && list.size() > 0) {
            Map<ZdataTrailTracks, List<TrailBo>> rtnCar = new HashMap<>();
            Map<ZdataTrailTracks, List<TrailBo>> mapCar = new HashMap<>();
            for (ZdataTrailTracks tracks : list) {
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                    tracks.setTrailPoints("");  // 行驶轨迹
                    mapCar.put(tracks, josnList);
                }
            }
            rtnCar = sysUtilService.changeData(mapCar);


            for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : rtnCar.entrySet()) {
                ZdataTrailTracks tracksBo = entry.getKey();
                List<TrailBo> josnList = entry.getValue();

                String carNo = CommonUtil.isNull(tracksBo.getPlateKey());
                TrailInfo trailInfo = new TrailInfo();

                trailInfo.setTrailUuid(carNo);
                trailInfo.setEnterTime(tracksBo.getEnterTime());
                trailInfo.setTracks(tracksBo);
                trailInfo.setTrailList(josnList);

                rtnList.add(trailInfo);
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
            Map<ZdataTrailTracks, List<TrailBo>> rtnCar = new HashMap<>();
            Map<ZdataTrailTracks, List<TrailBo>> mapCar = new HashMap<>();
            for (ZdataTrailTracks tracks : list) {
                String keyValue = tracks.getTrailPoints(); // 行驶轨迹
                List<TrailBo> josnList = new ArrayList<TrailBo>();
                if (CommonUtil.isNotBlank(keyValue)) {
                    josnList = JSON.parseArray(keyValue, TrailBo.class);
                    tracks.setTrailPoints("");  // 行驶轨迹
                    mapCar.put(tracks, josnList);
                }
            }
            rtnCar =  sysUtilService.changeData(mapCar);


            for (Map.Entry<ZdataTrailTracks, List<TrailBo>> entry : rtnCar.entrySet()) {
                ZdataTrailTracks tracksBo = entry.getKey();
                List<TrailBo> josnList = entry.getValue();

                String carNo = CommonUtil.isNull(tracksBo.getPlateKey());
                TrailInfo trailInfo = new TrailInfo();
                trailInfo.setTrailUuid(carNo);
                trailInfo.setEnterTime(tracksBo.getEnterTime());
                trailInfo.setTracks(tracksBo);
                trailInfo.setTrailList(josnList);

                rtnList.add(trailInfo);
            }
        }


        TableDataInfo rspData = new TableDataInfo();
        rspData.setCode(HttpStatus.SUCCESS);
        rspData.setMsg("查询成功");
        rspData.setRows(rtnList);
        rspData.setTotal(new PageInfo(list).getTotal());
        return rspData;


    }





}
