package com.ruoyi.modules.service.impl;

import com.ruoyi.modules.service.IEcGoodsInfoService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.EcGoodsInfo;
import com.ruoyi.modules.entity.ShopInfo;
import com.ruoyi.modules.mapper.EcGoodsInfoMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;

/**
 * 商品信息Service业务层处理
 *
 * @author ruoyi
 * @date 2024-05-27
 */
@Service
public class EcGoodsInfoServiceImpl extends ServiceImpl<EcGoodsInfoMapper, EcGoodsInfo> implements IEcGoodsInfoService {
    @Autowired
    private EcGoodsInfoMapper ecGoodsInfoMapper;

    /**
     * 查询商品信息根据skuid
     * @param goodsNo
     * @return
     */
    @Override
    public EcGoodsInfo selectEcGoodsInfoByGoodsNoAndStoreId(String goodsNo, String storeId) {
        return ecGoodsInfoMapper.selectEcGoodsInfoByGoodsNoAndStoreId(goodsNo,storeId);
    }

    @Override
    public int insertEcGoodsInfoBatch(List<EcGoodsInfo> list) {
        return ecGoodsInfoMapper.insertEcGoodsInfoBatch(list);
    }

    @Override
    public List<ShopInfo> getShopInfoList(List<String> shopId) {
        return ecGoodsInfoMapper.getShopInfoList(shopId);
    }
}
