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
public class DhbSearchModel {

    @ApiModelProperty(value = "账号：前端不传",hidden = true)
    private String appKey;

    @ApiModelProperty(value = "签名：前端不传",hidden = true)
    private String sign;

    @ApiModelProperty(value = "店铺商家订单号(唯一订单号)",required = true)
    @NotEmpty(message = "店铺商家订单号不能为空")
    private String shopOrderNo;
}


