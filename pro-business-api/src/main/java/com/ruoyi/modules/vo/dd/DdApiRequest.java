package com.ruoyi.modules.vo.dd;

import lombok.Data;

/**
 * @Description: 咚咚接口类
 * @Author HuangJun
 * @Date 2024/5/15 11:03
 * @Return
 */
@Data
public class DdApiRequest {
    //方法名称
    private String functionId;
    //应用id
    private String appid = "customerAssistant";
    //连接版本
    private String clientVersion = "20230720";
    //语言
    private String lang = "zh_CN";
    //参数
    private String body;
    //参数
    private String client = "assistant_web";
    //参数
    private String h5st = "assistant_web";

}
