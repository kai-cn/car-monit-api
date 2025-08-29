package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 基础-收费流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/feerecords")
public class OdsLwzxsfsjFeeRecords01Controller extends BaseController {

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service odsLwzxsfsjFeeRecords01Service;

    /**
     * 查询基础-收费流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        startPage();
        // odsLwzxsfsjFeeRecords01.setTenantId(SecurityUtils.getTenantId()); // 查询我自己单位的租户
        List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);
        return getDataTable(list);
    }

    /**
     * 获取基础-收费流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") String bigId) {
        return AjaxResult.success(odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01ById(bigId));
    }
}
