package com.ruoyi.modules.service;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.vo.dhb.*;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
public interface IDhbApiService {

    /**
     * 轨迹单下单接口
     */
    Result placeAnOrder(DhbPlaceAnOrdersModel dhbPlaceAnOrdersModel);

    /**
     * 更新转寄快递单号 v2.0
     */
    Result updateAnOrder(DhbUpdateAnOrdersModel dhbUpdateAnOrdersModel);

    /**
     * 轨迹单下单回调接口
     */
    String callBackByOrder(DhbOrderCallBack orderCallBack);

    /**
     * 退款回调接口
     */
    String callBackByRefund(DhbOrderCallBack orderCallBack);

    /**
     * 下单宝投诉单回调接口
     */
    String syncComplaintForm(DhbFormCallBack formCallBack);

    /**
     * 轨迹单下单查询
     */
    Result selectOrder(DhbSearchModel dhbSearchModel);

    /**
     * 查询用户信息
     */
    JSONObject selectUser(DhbUserModel dhbUserModel);

    /**
     * 取件码推送
     */
    Result sendPickup(DhbPickupModel dhbPickupModel);


    void syngOrderStatus(String orderId);
}
