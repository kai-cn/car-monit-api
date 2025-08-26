package com.ruoyi.modules.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.modules.entity.EcJdOrderInfo;

import java.util.List;

/**
 * 京东订单信息Service接口
 *
 * @author huangjun
 * @date 2024-08-30
 */
public interface IEcJdOrderInfoService extends IService<EcJdOrderInfo> {
    /**
     * 查询京东订单信息
     *
     * @param id 京东订单信息ID
     * @return 京东订单信息
     */
    EcJdOrderInfo selectEcJdOrderInfoById(String id);

    /**
     * 查询京东订单信息列表
     *
     * @param ecJdOrderInfo 京东订单信息
     * @return 京东订单信息集合
     */
    List<EcJdOrderInfo> selectEcJdOrderInfoList(EcJdOrderInfo ecJdOrderInfo);

    List<EcJdOrderInfo> getJdOrderInfoList(List<String> orderIds);
}
