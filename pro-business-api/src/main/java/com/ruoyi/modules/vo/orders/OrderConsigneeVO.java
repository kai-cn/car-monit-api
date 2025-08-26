package com.ruoyi.modules.vo.orders;

import lombok.Data;

@Data
public class OrderConsigneeVO {

    private String consName;

    private String consMobilePhone;

    private String consAddress;

    //买家备注
    private String remark;

    // 买家账号
    private String userPin;
}
