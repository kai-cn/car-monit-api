package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeGantryFusion01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeGantryFusion01Service;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 交易流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsLwzxsfsjFeeGantryFusion01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeGantryFusion01Mapper, OdsLwzxsfsjFeeGantryFusion01> implements IOdsLwzxsfsjFeeGantryFusion01Service {

    @Autowired
    private OdsLwzxsfsjFeeGantryFusion01Mapper odsLwzxsfsjFeeGantryFusion01Mapper;

    /**
     * 查询交易流水
     *
     * @param bigId 交易流水ID
     * @return 交易流水
     */
    @Override
    public OdsLwzxsfsjFeeGantryFusion01 selectOdsLwzxsfsjFeeGantryFusion01ById(String bigId) {
        return odsLwzxsfsjFeeGantryFusion01Mapper.selectOdsLwzxsfsjFeeGantryFusion01ById(bigId);
    }

    /**
     * 查询交易流水列表
     *
     * @param odsLwzxsfsjFeeGantryFusion01 交易流水
     * @return 交易流水
     */
    @Override
    public List<OdsLwzxsfsjFeeGantryFusion01> selectOdsLwzxsfsjFeeGantryFusion01List(OdsLwzxsfsjFeeGantryFusion01 odsLwzxsfsjFeeGantryFusion01) {
        return odsLwzxsfsjFeeGantryFusion01Mapper.selectOdsLwzxsfsjFeeGantryFusion01List(odsLwzxsfsjFeeGantryFusion01);
    }
}
