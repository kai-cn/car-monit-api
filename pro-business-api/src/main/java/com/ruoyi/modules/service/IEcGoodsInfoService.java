package com.ruoyi.modules.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.modules.entity.EcGoodsInfo;
import com.ruoyi.modules.entity.ShopInfo;

import java.util.List;

/**
 * 商品信息Service接口
 *
 * @author ruoyi
 * @date 2024-05-27
 */
public interface IEcGoodsInfoService extends IService<EcGoodsInfo> {

    /**
     * 查询商品信息根据skuid
     * @param goodsNo
     * @param storeId
     * @return
     */
    EcGoodsInfo selectEcGoodsInfoByGoodsNoAndStoreId(String goodsNo, String storeId);


    /**
     * 批量新增商品信息
     *
     * @param list 商品信息
     * @return 结果
     */
    int insertEcGoodsInfoBatch(List<EcGoodsInfo> list);

    List<ShopInfo> getShopInfoList(List<String> shopId);
}
