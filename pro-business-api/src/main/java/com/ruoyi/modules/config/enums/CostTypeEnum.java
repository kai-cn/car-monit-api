package com.ruoyi.modules.config.enums;
/**
 * 费用类型
 */

public enum CostTypeEnum {

    cz("1", "充值"),
    dxxf("2", "短信消费"),
    qxgl_thkf("3", "取消关联退回扣费"),
    tbwl_cdykf("4", "同步物流出单预扣费"),
    tbwl_cdthykf("5", "同步物流出单退回预扣费"),
    tbwl_cdshkf("6", "同步物流出单实际扣费"),
    xnhkf("7", "虚拟号扣费"),
    thxnhkf("8", "退回虚拟号扣费"),
    tbwl_cktk("9", "同步物流出单退款"),
    dpsjxf("10", "店铺时间续费"),
    gmwldhkf_kyd("11", "购买物流单号扣费（快运单）"),
    zzczhczkf("12", "中转仓账号充值扣费"),
    kfgjcz("13", "客服工具充值"),
    gmwldhkf_lpd("14", "购买物流单号扣费（礼品单）"),
    ycddkf("15", "云仓订单扣费"),
    中转仓预扣费用("16", "中转仓预扣费用"),
    中转仓实际扣费("17", "中转仓实际扣费"),
    中转仓退回扣费("18", "中转仓退回扣费"),
    取消订单退回扣费("19", "取消订单退回扣费"),
    dpfzslgm("20","购买商品复制数量"),

    /**
     * 购买代理IP
     */
    BUY_PROXY_IP("21","购买代理IP"),

    qtlxkf("99", "其他类型"),
    ;


    private String code;
    private String name;

    private CostTypeEnum(String code, String name) {
        this.code = code;
        this.name = name;
    }

    public String getCode() {
        return code;
    }

    public String getName() {
        return name;
    }

    public static String getNameByCode(String code){
        for (CostTypeEnum value : CostTypeEnum.values()) {
            if (value.code.equals(code)){
                return value.name;
            }
        }
        return "";
    }
}
