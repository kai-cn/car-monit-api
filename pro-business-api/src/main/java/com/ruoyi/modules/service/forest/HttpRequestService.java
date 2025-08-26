package com.ruoyi.modules.service.forest;

import com.ruoyi.modules.vo.ems.EmsRequestModel;
import com.ruoyi.modules.vo.ems.EmsResponseModel;
import com.dtflys.forest.annotation.*;

/**
 * @Description: 畅邮宝接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.cyb.baseUrl}")
public interface HttpRequestService {

    /**
     * 订单导入
     *
     * @param emsRequestModel
     * @return
     */
    @Post(url = "/open/order/import")
    EmsResponseModel importOrder(@JSONBody EmsRequestModel emsRequestModel);


    /**
     * 用户信息查询
     *
     * @param emsRequestModel
     * @return
     */
    @Get(url = "/open/user/info")
    EmsResponseModel getUserInfo(@Query EmsRequestModel emsRequestModel);
}
