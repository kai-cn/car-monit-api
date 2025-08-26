package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.service.IEcOrderGoodsService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcOrderGoods;
import com.ruoyi.modules.mapper.EcOrderGoodsMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 订单扩展Service业务层处理
 *
 * @author ruoyi
 * @date 2024-06-21
 */
@Service
public class EcOrderGoodsServiceImpl extends ServiceImpl<EcOrderGoodsMapper, EcOrderGoods> implements IEcOrderGoodsService {
    @Autowired
    private EcOrderGoodsMapper ecOrderGoodsMapper;

    /**
     * 查询订单扩展
     *
     * @param id 订单扩展ID
     * @return 订单扩展
     */
    @Override
    public EcOrderGoods selectEcOrderGoodsById(String id) {
        return ecOrderGoodsMapper.selectEcOrderGoodsById(id);
    }

    /**
     * 查询订单扩展列表
     *
     * @param ecOrderGoods 订单扩展
     * @return 订单扩展
     */
    @Override
    public List<EcOrderGoods> selectEcOrderGoodsList(EcOrderGoods ecOrderGoods) {
        return ecOrderGoodsMapper.selectEcOrderGoodsList(ecOrderGoods);
    }

    @Override
    public int deleteEcOrderGoodsByOrderId(String orderId) {
        return ecOrderGoodsMapper.deleteEcOrderGoodsByOrderId(orderId);
    }
}
