package com.ruoyi.modules.vo.kdn;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;
import java.util.List;

/**
 * @Description: 快递鸟API调用接口参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class KdnRequestModel {

    @ApiModelProperty(value = "快递公司编码:免费版本仅支持申通[STO]、圆通[YTO]",required = true)
    @NotEmpty(message = "快递公司编码不能为空")
    @JsonProperty("ShipperCode")
    private String ShipperCode;

    @ApiModelProperty(value = "快递单号",required = true)
    @NotEmpty(message = "快递单号不能为空")
    @JsonProperty("LogisticCode")
    private String LogisticCode;

    @ApiModelProperty(value = "订单编号")
    @JsonProperty("OrderCode")
    private String OrderCode;
}


