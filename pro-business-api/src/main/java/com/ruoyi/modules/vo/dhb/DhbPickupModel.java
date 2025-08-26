package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;

/**
 * @Description: 单号宝请求参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class DhbPickupModel {

    @ApiModelProperty(value = "账号：前端不传",hidden = true)
    private String appKey;

    @ApiModelProperty(value = "签名：前端不传",hidden = true)
    private String sign;

    @ApiModelProperty(value = "取件地址")
    private String address;

    @ApiModelProperty(value = "取件码")
    @NotEmpty(message = "取件码不能为空")
    private String code;

    @ApiModelProperty(value = "商家订单号")
    @NotEmpty(message = "商家订单号不能为空")
    private String shopOrderNo;
}


