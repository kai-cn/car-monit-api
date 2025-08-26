package com.ruoyi.modules.service;


import com.ruoyi.modules.entity.EcCostSzDetail;

import java.util.List;

/**
 * 扣费费用明细Service接口
 *
 * @author ruoyi
 * @date 2024-08-16
 */
public interface IEcCostSzDetailService  {

    /**
     * 查询扣费费用明细列表
     *
     * @param ecCostSzDetail 扣费费用明细
     * @return 扣费费用明细集合
     */
    List<EcCostSzDetail> selectEcCostSzDetailList(EcCostSzDetail ecCostSzDetail);
}
