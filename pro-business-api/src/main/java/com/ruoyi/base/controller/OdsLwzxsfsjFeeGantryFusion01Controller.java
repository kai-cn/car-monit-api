package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeGantryFusion01Service;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 交易流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/feeGantry")
public class OdsLwzxsfsjFeeGantryFusion01Controller extends BaseController {

    @Autowired
    private IOdsLwzxsfsjFeeGantryFusion01Service odsLwzxsfsjFeeGantryFusion01Service;

    /**
     * 查询交易流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsLwzxsfsjFeeGantryFusion01 odsLwzxsfsjFeeGantryFusion01) {
        startPage();
        List<OdsLwzxsfsjFeeGantryFusion01> list = odsLwzxsfsjFeeGantryFusion01Service.selectOdsLwzxsfsjFeeGantryFusion01List(odsLwzxsfsjFeeGantryFusion01);
        if (null !=list && list.size() > 0){
            for (OdsLwzxsfsjFeeGantryFusion01 rtn :list){
                rtn.setId(StringUtils.getUUID());
            }
        }

        return getDataTable(list);
    }

    /**
     * 获取交易流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public OdsLwzxsfsjFeeGantryFusion01 getInfo(@PathVariable("bigId") String bigId) {
        return  odsLwzxsfsjFeeGantryFusion01Service.selectOdsLwzxsfsjFeeGantryFusion01ById(bigId);
    }
}
