package com.ruoyi.modules.vo.jd;

import lombok.Data;

/**
 * @Description: 咚咚接口类
 * @Author HuangJun
 * @Date 2024/5/15 11:03
 * @Return
 */
@Data
public class JdApiRequest {
    //版本
    private String v = "1.0";
    //应用id -- 固定值
    private String appId = "COCX0HBWR4BA7RDVDBIQ";
    //调用方法
    private String api;

    public JdApiRequest() {
    }

    public JdApiRequest(String api) {
        this.api = api;
    }
    public JdApiRequest(String api,String appId) {
        this.api = api;
        this.appId = appId;
    }
}
