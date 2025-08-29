package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationExit01Mapper;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 收费站出口流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsLwzxsfsjFeeStationExit01ServiceImpl extends ServiceImpl<OdsLwzxsfsjFeeStationExit01Mapper, OdsLwzxsfsjFeeStationExit01> implements IOdsLwzxsfsjFeeStationExit01Service {

    @Autowired
    private OdsLwzxsfsjFeeStationExit01Mapper odsLwzxsfsjFeeStationExit01Mapper;

    /**
     * 查询收费站出口流水
     *
     * @param bigId 收费站出口流水ID
     * @return 收费站出口流水
     */
    @Override
    public OdsLwzxsfsjFeeStationExit01 selectOdsLwzxsfsjFeeStationExit01ById(String bigId) {
        return odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01ById(bigId);
    }

    /**
     * 查询收费站出口流水列表
     *
     * @param odsLwzxsfsjFeeStationExit01 收费站出口流水
     * @return 收费站出口流水
     */
    @Override
    public List<OdsLwzxsfsjFeeStationExit01> selectOdsLwzxsfsjFeeStationExit01List(OdsLwzxsfsjFeeStationExit01 odsLwzxsfsjFeeStationExit01) {
        return odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(odsLwzxsfsjFeeStationExit01);
    }
}
