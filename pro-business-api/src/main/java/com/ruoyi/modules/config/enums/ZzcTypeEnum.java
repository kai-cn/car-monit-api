package com.ruoyi.modules.config.enums;

/**
 * @Description: 京东API接口方法详情
 * @Author HuangJun
 * @Date 2024/5/16 10:07
 * @Return
 */
public enum ZzcTypeEnum {

    重量扣费1("1"),
    包裹状态2("2"),
    退回件的超重扣费3("3"),
    提前揽件仓库已打包礼品发出4("4"),
    提前揽件仓库已打包礼品发出5("5"),
    推送疑难件的信息6("6"),
    推送不取单号下单7("7"),
    推送超重退回费用8("8");

    private String type;

    private ZzcTypeEnum(String type){
        this.type = type;
    }

    public String getZzcTypeEnum() {
        return type;
    }

}
