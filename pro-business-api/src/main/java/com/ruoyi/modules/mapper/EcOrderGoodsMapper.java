package com.ruoyi.modules.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.modules.entity.EcOrderGoods;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 订单扩展Mapper接口
 *
 * @author ruoyi
 * @date 2024-06-21
 */
@Repository
public interface EcOrderGoodsMapper extends BaseMapper<EcOrderGoods> {
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

    /**
     * 新增订单扩展
     *
     * @param ecOrderGoods 订单扩展
     * @return 结果
     */
    int insertEcOrderGoods(EcOrderGoods ecOrderGoods);

    /**
     * 修改订单扩展
     *
     * @param ecOrderGoods 订单扩展
     * @return 结果
     */
    int updateEcOrderGoods(EcOrderGoods ecOrderGoods);

    /**
     * 删除订单扩展
     *
     * @param id
     * @return 结果
     */
    int deleteEcOrderGoodsById(String id);

    /**
     * 删除订单扩展
     *
     * @param orderId
     * @return 结果
     */
    int deleteEcOrderGoodsByOrderId(String orderId);

    /**
     * 批量删除订单扩展
     *
     * @param ids 需要删除的数据ID
     * @return 结果
     */
    int deleteEcOrderGoodsByIds(String[] ids);
}
