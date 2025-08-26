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
public class DhbUpdateAnOrdersModel {

    @ApiModelProperty(value = "账号：前端不传",hidden = true)
    private String appKey;

    @ApiModelProperty(value = "签名：前端不传",hidden = true)
    private String sign;

    @ApiModelProperty(value = "店铺订单号",required = true)
    @NotEmpty(message = "店铺订单号不能为空")
    private String shopOrderNo;

    @ApiModelProperty(value = "转寄快递单号(上游快递单号)[目前只支持快递 韵达,申通,中通, 圆通,极兔,邮政,韵达快运,京东,德邦,丰网,安能物流]",required = true)
    @NotEmpty(message = "转寄快递单号(上游快递单号)不能为空")
    private String copyExpressNo;

    @ApiModelProperty(value = "上家快递公司代码（韵达[YUNDA]，申通[STO]，中通[ZTO],圆通[YTO]，极兔[JTSD]，邮政EMS[YZPY]，韵达快运[YDKY]，京东[JD]，德邦[DBL]，丰网[FWX]，安能物流[ANE]，中通快运[ZTOKY]）")
    private String copyExpressCode;

    @ApiModelProperty(value = "上家快递公司代码（韵达[YUNDA]，申通[STO]，中通[ZTO],圆通[YTO]，极兔[JTSD]，邮政EMS[YZPY]，韵达快运[YDKY]，京东[JD]，德邦[DBL]，丰网[FWX]，安能物流[ANE]，中通快运[ZTOKY]）")
    private String copyExpressName;
}


