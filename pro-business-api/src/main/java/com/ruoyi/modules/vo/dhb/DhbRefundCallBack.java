package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/25 11:18
 * @Return
 */
@Data
public class DhbRefundCallBack {

    @ApiModelProperty(value = "标识：0 成功,  其他皆是错误",required = true)
    //@NotNull(message = "标识不能为空")
    private Integer code;

    @ApiModelProperty(value = "响应信息",required = true)
    //@NotEmpty(message = "响应信息不能为空")
    private String message;

    @ApiModelProperty(value = "店铺订单号",required = true)
    //@NotEmpty(message = "店铺订单号不能为空")
    private String shopOrderNo;

    @ApiModelProperty(value = "快递单号",notes = "code等于0的时候才有值",required = true)
    //@NotEmpty(message = "出单单号不能为空")
    private String expressNo;

    @ApiModelProperty(value = "签名",required = true)
    //@NotEmpty(message = "签名不能为空")
    private String sign;

}
