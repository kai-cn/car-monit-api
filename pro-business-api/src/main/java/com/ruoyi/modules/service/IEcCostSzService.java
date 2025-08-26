package com.ruoyi.modules.service;

import com.ruoyi.modules.entity.EcCostSz;

/**
 * 费用设置Service接口
 *
 * @author ruoyi
 * @date 2024-07-09
 */
public interface IEcCostSzService {

    /**
     * 根据费用类型获取扣款明细
     * @param costType
     * @param tenantId
     * @return
     */
    EcCostSz getByCostType(String costType, Long tenantId);

}
