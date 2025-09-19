package com.ruoyi.base.controller;

import com.ruoyi.base.domain.CarParaVO;
import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

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
     * 同步轨迹
     */
    @PostMapping(value = "/syncTrack")
    public AjaxResult syncTrack(@RequestBody CarParaVO carParaVO) {
        return sysUtilService.syncTrack(carParaVO);
    }


    /**
     * 同步可疑车俩
     */
    @PostMapping(value = "/syncSuspiciousCar")
    public AjaxResult syncSuspiciousCar(@RequestBody CarParaVO carParaVO) {
        return AjaxResult.success();
    }


}
