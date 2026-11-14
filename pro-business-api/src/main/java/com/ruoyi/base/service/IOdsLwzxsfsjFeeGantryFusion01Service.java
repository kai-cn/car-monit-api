package com.ruoyi.base.service;

import com.baomidou.mybatisplus.spring.service.IService;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 交易流水Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IOdsLwzxsfsjFeeGantryFusion01Service extends IService<OdsLwzxsfsjFeeGantryFusion01> {
    /**
     * 查询交易流水
     *
     * @param bigId 交易流水ID
     * @return 交易流水
     */
    OdsLwzxsfsjFeeGantryFusion01 selectOdsLwzxsfsjFeeGantryFusion01ById(String bigId);

    /**
     * 查询交易流水列表
     *
     * @param odsLwzxsfsjFeeGantryFusion01 交易流水
     * @return 交易流水集合
     */
    List<OdsLwzxsfsjFeeGantryFusion01> selectOdsLwzxsfsjFeeGantryFusion01List(OdsLwzxsfsjFeeGantryFusion01 odsLwzxsfsjFeeGantryFusion01);
}
