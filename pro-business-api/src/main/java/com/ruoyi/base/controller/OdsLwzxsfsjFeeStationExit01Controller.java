package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 收费站出口流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/feestationexit")
public class OdsLwzxsfsjFeeStationExit01Controller extends BaseController {

    @Autowired
    private IOdsLwzxsfsjFeeStationExit01Service odsLwzxsfsjFeeStationExit01Service;

    /**
     * 查询收费站出口流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsLwzxsfsjFeeStationExit01 odsLwzxsfsjFeeStationExit01) {
        startPage();
        List<OdsLwzxsfsjFeeStationExit01> list = odsLwzxsfsjFeeStationExit01Service.selectOdsLwzxsfsjFeeStationExit01List(odsLwzxsfsjFeeStationExit01);
        return getDataTable(list);
    }

    /**
     * 获取收费站出口流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") String bigId) {
        return AjaxResult.success(odsLwzxsfsjFeeStationExit01Service.selectOdsLwzxsfsjFeeStationExit01ById(bigId));
    }
}
