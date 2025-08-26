package com.ruoyi.modules.vo.orders;

import lombok.Data;

@Data
public class OrderRemarkVO {

    private Integer level;
    private String orderId;
    private String remark;

    // 本地备注
    private String localRemark;

    private String shopId;

    // 买家备注
    private String consRemark;
}
