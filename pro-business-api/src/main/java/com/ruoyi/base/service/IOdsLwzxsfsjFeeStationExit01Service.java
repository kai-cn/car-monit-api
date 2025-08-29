package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 收费站出口流水Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IOdsLwzxsfsjFeeStationExit01Service extends IService<OdsLwzxsfsjFeeStationExit01> {
    /**
     * 查询收费站出口流水
     *
     * @param bigId 收费站出口流水ID
     * @return 收费站出口流水
     */
    OdsLwzxsfsjFeeStationExit01 selectOdsLwzxsfsjFeeStationExit01ById(String bigId);

    /**
     * 查询收费站出口流水列表
     *
     * @param odsLwzxsfsjFeeStationExit01 收费站出口流水
     * @return 收费站出口流水集合
     */
    List<OdsLwzxsfsjFeeStationExit01> selectOdsLwzxsfsjFeeStationExit01List(OdsLwzxsfsjFeeStationExit01 odsLwzxsfsjFeeStationExit01);
}
