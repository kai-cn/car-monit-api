package com.ruoyi.modules.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.modules.entity.EcGoodsInfo;
import com.ruoyi.modules.entity.ShopInfo;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 商品信息Mapper接口
 *
 * @author ruoyi
 * @date 2024-05-27
 */
@Repository
public interface EcGoodsInfoMapper extends BaseMapper<EcGoodsInfo> {


    /**
     * 批量新增商品信息
     *
     * @param list 商品信息
     * @return 结果
     */
    int insertEcGoodsInfoBatch(List<EcGoodsInfo> list);

    /**
     * 查询商品信息根据skuid
     * @param goodsNo
     * @param storeId
     * @return
     */
    EcGoodsInfo selectEcGoodsInfoByGoodsNoAndStoreId(@Param("goodsNo") String goodsNo,@Param("storeId") String storeId);


    List<ShopInfo> getShopInfoList(List<String> shopId);
}
