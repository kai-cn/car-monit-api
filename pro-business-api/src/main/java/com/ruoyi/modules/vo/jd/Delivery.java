package com.ruoyi.modules.vo.jd;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.util.List;

/**
 * @Description: 普通发货参数类
 * @Author HuangJun
 * @Date 2024/4/17 15:04
 * @Return
 */
@Data
public class Delivery{

    @ApiModelProperty(value = "订单id",required = true)
    @NotNull(message = "订单id不能为空")
    private Long orderId;

    @ApiModelProperty(value = "勾选类型",notes = "选择物流公司时此处不为空，厂家自送和用户自提不传")
    private Integer checkType;

    private List<DeliveryModel> deliveryCompanyList;

    @Data
    public static class DeliveryModel{
        @ApiModelProperty(value = "物流id",notes = "参照 物流名称及编码.txt")
        private String deliveryId;

        @ApiModelProperty(value = "物流单号",notes = "选择物流公司时此处不为空")
        private List<String> deliveryNums;
    }
}



