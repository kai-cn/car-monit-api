package com.ruoyi.modules.mapper;

import com.ruoyi.modules.entity.EcShopBind;

import java.util.List;

/**
 * 店铺绑定Mapper接口
 *
 * @author ruoyi
 * @date 2024-07-04
 */
public interface EcShopBindMapper {

    /**
     * 查询店铺绑定列表
     *
     * @param ecShopBind 店铺绑定
     * @return 店铺绑定集合
     */
    List<EcShopBind> selectEcShopBindList(EcShopBind ecShopBind);

    /**
     *  根据店铺id 获取绑定店铺信息
     *
     * @param ecShopBind 店铺绑定
     * @return 店铺绑定集合
     */
    List<EcShopBind> selectEcShopAccout(EcShopBind ecShopBind);
}
