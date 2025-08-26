package com.ruoyi.modules.util;

import com.ruoyi.common.util.MD5Example;
import com.ruoyi.modules.vo.dhb.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.util.Objects;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/19 11:12
 * @Return
 */
@Slf4j
@Component
public class DhbRequestUtil {

    @Value(value = "${ret.dhb.appKey}")
    public String APP_KEY;

    @Value(value = "${ret.dhb.appSecret}")
    public String APP_SECRET;

    public static void main(String[] args) {
        String newSign = MD5Example.toMD5("293179598768428144811569522" + MD5Example.toMD5("abRUO6dupghyhHAJCgQISIHWWNdX0rUG"));
        System.out.println(newSign);
    }

    public boolean verifySign(String dataStr,String sign){
        String newSign = MD5Example.toMD5(dataStr + MD5Example.toMD5(APP_SECRET));
        return Objects.equals(sign,newSign);
    }

    public void getPlaceAnOrdersModel(DhbPlaceAnOrdersModel dhbPlaceAnOrdersModel){
        dhbPlaceAnOrdersModel.setAppKey(APP_KEY);
        String sign = MD5Example.toMD5(APP_KEY + dhbPlaceAnOrdersModel.getBuyPlatform() + dhbPlaceAnOrdersModel.getExpressCode() + dhbPlaceAnOrdersModel.getNotifyUrl() + MD5Example.toMD5(APP_SECRET));
        dhbPlaceAnOrdersModel.setSign(sign);
    }

    public void getUpdateAnOrderModel(DhbUpdateAnOrdersModel dhbUpdateAnOrdersModel){
        dhbUpdateAnOrdersModel.setAppKey(APP_KEY);
        String sign = MD5Example.toMD5(APP_KEY + dhbUpdateAnOrdersModel.getCopyExpressNo() + dhbUpdateAnOrdersModel.getShopOrderNo() + MD5Example.toMD5(APP_SECRET));
        dhbUpdateAnOrdersModel.setSign(sign);
    }

    public void getSearchModel(DhbSearchModel dhbSearchModel){
        dhbSearchModel.setAppKey(APP_KEY);
        String sign = MD5Example.toMD5(APP_KEY + dhbSearchModel.getShopOrderNo() + MD5Example.toMD5(APP_SECRET));
        dhbSearchModel.setSign(sign);
    }

    public void getDhbUserModel(DhbUserModel dhbUserModel){
        dhbUserModel.setAppKey(APP_KEY);
        String sign = MD5Example.toMD5(APP_KEY + dhbUserModel.getSt() + MD5Example.toMD5(APP_SECRET));
        dhbUserModel.setSign(sign);
    }

    public void getDhbPickupModel(DhbPickupModel dhbPickupModel){
        dhbPickupModel.setAppKey(APP_KEY);
        String sign = MD5Example.toMD5(dhbPickupModel.getAddress() + APP_KEY + dhbPickupModel.getCode() + dhbPickupModel.getShopOrderNo() + MD5Example.toMD5(APP_SECRET));
        dhbPickupModel.setSign(sign);
    }
}
