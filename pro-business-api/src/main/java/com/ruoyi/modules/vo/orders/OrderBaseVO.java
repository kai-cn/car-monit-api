package com.ruoyi.modules.vo.orders;


import lombok.Data;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/9/2 14:14
 * @Return
 */
@Data
public class OrderBaseVO {


    private OrderInfoVO orderInfo;

    private OperateSignInfoVO operateSignInfo;

    // 商家备注
    private OrderRemarkVO orderRemark;

    //订单号
    private String orderId;

    // 店铺ID
    private String shopId;

}
