package com.ruoyi.base.controller;

import com.ruoyi.base.domain.SysUtil;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
     * 获取收费站基础信息详细信息
     */
    @GetMapping(value = "/getRedis")
    public AjaxResult getRedis(SysUtil sysUtil) {
        return sysUtilService.getRedis(sysUtil);
    }


}
