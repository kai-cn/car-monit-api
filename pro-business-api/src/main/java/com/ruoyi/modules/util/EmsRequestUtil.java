package com.ruoyi.modules.util;

import com.ruoyi.modules.vo.ems.EmsRequestModel;
import com.ruoyi.common.util.MD5Example;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/19 11:12
 * @Return
 */
@Component
public class EmsRequestUtil {

    @Value(value = "${ret.cyb.appKey}")
    public String APP_KEY;

    @Value(value = "${ret.cyb.appSecret}")
    public String APP_SECRET;

    public void getRequestModel(EmsRequestModel requestModel){
        Long timeStamp = System.currentTimeMillis();
        String appSecret = MD5Example.toMD5(requestModel.getAppKey() + MD5Example.toMD5(requestModel.getAppSecret())+ timeStamp);
        requestModel.setAppSecret(appSecret).setTimeStamp(timeStamp.toString());
    }
}
