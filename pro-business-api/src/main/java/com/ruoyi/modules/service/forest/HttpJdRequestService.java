package com.ruoyi.modules.service.forest;

import com.alibaba.fastjson.JSONObject;
import com.ruoyi.modules.vo.jd.JdApiRequest;
import com.dtflys.forest.annotation.*;

import java.util.Map;

/**
 * @Description: 京东接口
 * @Author: HuangJun
 * @Date: 2022-08-10 10:16:41
 * @Return
 */
@BaseRequest(baseURL = "#{ret.jd.baseUrl}")
public interface HttpJdRequestService {

    /**
     * 通用京麦查询方法
     *
     * @return
     */
    @Post(url = "/api")
    @Headers({"dsm-platform:pc"})
    JSONObject jdPostRequest(@Query JdApiRequest jdApiRequest, @JSONBody Map<String, Object> params, @Header("Cookie") String cookie);
}
