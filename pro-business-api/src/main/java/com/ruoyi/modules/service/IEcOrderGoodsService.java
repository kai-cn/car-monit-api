package com.ruoyi.modules.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.modules.entity.EcOrderGoods;

import java.util.List;

/**
 * 订单扩展Service接口
 *
 * @author ruoyi
 * @date 2024-06-21
 */
public interface IEcOrderGoodsService extends IService<EcOrderGoods> {
    /**
     * 查询订单扩展
     *
     * @param id 订单扩展ID
     * @return 订单扩展
     */
    EcOrderGoods selectEcOrderGoodsById(String id);

    /**
     * 查询订单扩展列表
     *
     * @param ecOrderGoods 订单扩展
     * @return 订单扩展集合
     */
    List<EcOrderGoods> selectEcOrderGoodsList(EcOrderGoods ecOrderGoods);

    int deleteEcOrderGoodsByOrderId(String orderId);

}
