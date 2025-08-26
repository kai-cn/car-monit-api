package com.ruoyi.modules.vo.orders;

import lombok.Data;

// 订单物流信息
@Data
public class OrderLogisticsVO {

    private String logiCoprId;

    // 快递名称
    private String logiCoprName;

    // 运单号
    private String[] logiNoList;

    private String storeName;
}
