package com.ruoyi.base.controller;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.CarVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/base/sysutil")
public class SysUtilController extends BaseController {

    @Autowired
    private ISysUtilService sysUtilService;

    /**
     * 获取收费站基础信息详细信息
     */
    @GetMapping(value = "/saveRedis")
    public AjaxResult saveRedis(SysUtil sysUtil) {
        return sysUtilService.saveRedis(sysUtil);
    }


    /**
     * 同步车俩实时轨迹
     */
    @PostMapping(value = "/syncTrack")
    public Map<String, List<TrailBo>> syncTrack(@RequestBody CarParaVO carParaVO) {
        return sysUtilService.syncTrack(carParaVO);
    }


    /**
     * 同步可疑车俩
     */
    @PostMapping(value = "/syncSuspiciousCar")
    public Map<String, List<TrailBo>> syncSuspiciousCar(@RequestBody CarParaVO carParaVO) {
        return sysUtilService.syncSuspiciousCar(carParaVO);
    }

    /**
     * 车俩历史轨迹：根据车牌号查询
     */
    @PostMapping(value = "/carTrackQueryByCarNo")
    public Map<String, List<TrailBo>> carTrackQueryByCarNo(@RequestBody CarParaVO carParaVO) {
        Map<String, List<TrailBo>> carMap = new HashMap<>();
        if(CommonUtil.isNotBlank(carParaVO.getCarNo())){
            carMap =  sysUtilService.carTrackQuery(carParaVO);
        }
        return  carMap;
    }

    /**
     * 车俩历史轨迹：根据时间端查询
     */
    @PostMapping(value = "/carTrackQueryByTime")
    public Map<String, List<TrailBo>> carTrackQuery(@RequestBody CarParaVO carParaVO) {

        Map<String, List<TrailBo>> carMap = new HashMap<>();

        if (CommonUtil.isNotBlank(carParaVO.getApplyTime1()) && CommonUtil.isNotBlank(carParaVO.getApplyTime2())) {
            List<CarVO> carlist = carParaVO.getCarlist(); // 重点车俩库
            if (null != carlist && carlist.size() > 0) {
                carMap =  sysUtilService.carTrackQuery(carParaVO);
            }
        }

        return  carMap;
    }


}
