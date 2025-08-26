package com.ruoyi.modules.service;

import com.alibaba.fastjson.JSONObject;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
public interface IJdApiService {

    JSONObject commonApiRequest(String api, JSONObject jsonObject,String cookie);

    boolean syncChildCategory(String api,String cookie);
}
