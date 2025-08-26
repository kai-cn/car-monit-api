package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.service.IEcJdOrderInfoService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcJdOrderInfo;
import com.ruoyi.modules.mapper.EcJdOrderInfoMapper;
import org.apache.ibatis.annotations.Param;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 京东订单信息Service业务层处理
 *
 * @author huangjun
 * @date 2024-08-30
 */
@Service
public class EcJdOrderInfoServiceImpl extends ServiceImpl<EcJdOrderInfoMapper, EcJdOrderInfo> implements IEcJdOrderInfoService {
    @Autowired
    private EcJdOrderInfoMapper ecJdOrderInfoMapper;

    /**
     * 查询京东订单信息
     *
     * @param id 京东订单信息ID
     * @return 京东订单信息
     */
    @Override
    public EcJdOrderInfo selectEcJdOrderInfoById(String id) {
        return ecJdOrderInfoMapper.selectEcJdOrderInfoById(id);
    }

    /**
     * 查询京东订单信息列表
     *
     * @param ecJdOrderInfo 京东订单信息
     * @return 京东订单信息
     */
    @Override
    public List<EcJdOrderInfo> selectEcJdOrderInfoList(EcJdOrderInfo ecJdOrderInfo) {
        return ecJdOrderInfoMapper.selectEcJdOrderInfoList(ecJdOrderInfo);
    }

    @Override
    public List<EcJdOrderInfo> getJdOrderInfoList(@Param("orderIds") List<String> orderIds) {
        return ecJdOrderInfoMapper.getJdOrderInfoList(orderIds);
    }

}
