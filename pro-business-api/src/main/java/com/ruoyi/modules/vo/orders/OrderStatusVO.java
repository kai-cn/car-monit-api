package com.ruoyi.modules.vo.orders;

import lombok.Data;

@Data
public class OrderStatusVO {

    //订单状态
    private Integer orderStatus;

    //订单状态备注
    private String orderStatusDesc;

    // 订单状态（名称）
    private String orderStatusName;

}
