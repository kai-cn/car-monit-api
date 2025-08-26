package com.ruoyi.modules.service;


import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.modules.entity.ComplaintForm;
import com.ruoyi.modules.entity.EcShopBind;

import java.util.List;

/**
 * 店铺绑定Service接口
 *
 * @author ruoyi
 * @date 2024-07-04
 */
public interface IEcShopBindService {

    /**
     * 根据店铺id 获取绑定店铺信息
     *
     * @return 店铺绑定
     */
    EcShopBind selectByShopId(String shopId);

    /**
     * 查询店铺绑定列表
     *
     * @param ecShopBind 店铺绑定
     * @return 店铺绑定集合
     */
    List<EcShopBind> selectEcShopBindList(EcShopBind ecShopBind);

}
