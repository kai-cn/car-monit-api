package com.ruoyi.modules.service.forest;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.modules.vo.dd.DdApiRequest;
import com.dtflys.forest.annotation.*;

/**
 * @Description: 京东接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.dd.baseUrl}")
public interface HttpDdRequestService {

    /**
     * 查询用户信息
     *
     * @return
     */
    @Get(url = "/client.action")
    @Headers({"Referer:https://xi.jd.com/customerassistant/index.html"})
    JSONObject baseGetRequest(@Query DdApiRequest apiDdRequest, @Header("Cookie") String cookie);
}
