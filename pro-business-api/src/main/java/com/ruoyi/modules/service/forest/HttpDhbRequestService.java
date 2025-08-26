package com.ruoyi.modules.service.forest;

import com.alibaba.fastjson.JSONObject;
import com.dtflys.forest.annotation.*;
import com.ruoyi.modules.vo.dhb.*;

/**
 * @Description: 单号宝接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.dhb.baseUrl}")
public interface HttpDhbRequestService {

    /**
     * 下单接口
     *
     * @param dhbPlaceAnOrdersModel
     * @return
     */
    @Post(url = "/openapi/insert")
    @Headers({
            "Content-Type:application/json",
            "User-Agent:Apifox/1.0.0 (https://apifox.com)"
            })
    JSONObject placeAnOrder(@JSONBody DhbPlaceAnOrdersModel dhbPlaceAnOrdersModel);

    /**
     * 下单接口
     *
     * @param dhbUpdateAnOrdersModel
     * @return
     */
    @Post(url = "/openapi/update")
    @Headers({
            "Content-Type:application/json",
            "User-Agent:Apifox/1.0.0 (https://apifox.com)"
            })
    JSONObject updateAnOrder(@JSONBody DhbUpdateAnOrdersModel dhbUpdateAnOrdersModel);


    /**
     * 查询接口
     *
     * @param dhbSearchModel
     * @return
     */
    @Post(url = "/openapi/select")
    @Headers({
            "Content-Type:application/json",
            "User-Agent:Apifox/1.0.0 (https://apifox.com)"
    })
    JSONObject selectOrder(@JSONBody DhbSearchModel dhbSearchModel);


    /**
     * 查询用户信息接口
     *
     * @param dhbUserModel
     * @return
     */
    @Post(url = "/openapi/user")
    @Headers({
            "Content-Type:application/json",
            "User-Agent:Apifox/1.0.0 (https://apifox.com)"
    })
    JSONObject selectUser(@JSONBody DhbUserModel dhbUserModel);


    /**
     * 取件码推送接口
     *
     * @param dhbPickupModel
     * @return
     */
    @Post(url = "/openapi/pickup")
    @Headers({
            "Content-Type:application/json",
            "User-Agent:Apifox/1.0.0 (https://apifox.com)"
    })
    JSONObject sendPickup(@JSONBody DhbPickupModel dhbPickupModel);
}
