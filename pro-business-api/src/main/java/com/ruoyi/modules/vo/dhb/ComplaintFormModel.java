package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/28 10:56
 * @Return
 */
@Data
@Accessors(chain = true)
public class ComplaintFormModel{

    @ApiModelProperty(value = "单号宝账号",required = true)
    @NotEmpty(message = "单号宝账号不能为空")
    private String account;

    @ApiModelProperty(value = "上家快递单号",required = true)
    //@NotEmpty(message = "上家快递单号不能为空")
    private String copyExpressNo;

    @ApiModelProperty(value = "出单单号",required = true)
    @NotEmpty(message = "出单单号不能为空")
    private String expressNo;

    @ApiModelProperty(value = "投诉内容",required = true)
    @NotEmpty(message = "投诉内容不能为空")
    private String msgContent;

    @ApiModelProperty(value = "商家订单号",required = true)
    @NotEmpty(message = "商家订单号不能为空")
    private String shopOrderNo;
}
