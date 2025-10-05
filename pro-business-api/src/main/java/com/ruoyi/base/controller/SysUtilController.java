package com.ruoyi.base.controller;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.CarVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.domain.TrailInfo;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.constant.Constants;
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
import java.util.List;

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

  /*  *//**
     * 车俩历史轨迹：根据车牌号查询
     *//*
    @GetMapping(value = "/carTrackQueryByCarNo")
    public TableDataInfo carTrackQueryByCarNo(CarParaVO carParaVO) {
        startPage();
        List<TrailInfo> list = new ArrayList<>();
        if(CommonUtil.isNotBlank(carParaVO.getCarNo())){
            list = sysUtilService.carTrackQuery(carParaVO);
        }
        return getDataTable(list);
    }


    *//**
     * 车俩历史轨迹：根据时间端查询
     *//*
    @GetMapping(value = "/carTrackQueryByTime")
    public TableDataInfo carTrackQueryByTime(CarParaVO carParaVO) {
        startPage();
        List<TrailInfo> list = new ArrayList<>();

        // 重点车俩库
        List<CarVO> carlist = new ArrayList<>();
        Object obj = redisCache.getCacheObject(Constants.car_list_jc);
        if (null != obj) {
            carlist = (List) obj;
        }

        if (null != carlist && carlist.size() > 0) {
            carParaVO.setCarlist(carlist);
            list = sysUtilService.carTrackQuery(carParaVO);
        }

        return getDataTable(list);
    }*/





}
