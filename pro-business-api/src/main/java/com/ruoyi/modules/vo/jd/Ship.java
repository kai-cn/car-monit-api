package com.ruoyi.modules.vo.jd;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.util.List;

/**
 * @Description: 电子面单参数接口类
 * @Author HuangJun
 * @Date 2024/4/17 15:04
 * @Return
 */
@Data
public class Ship {
    //{"request":{"source":"2000","data":[{"venderTaskAddressId":21318561,"deliveryType":203,"deliveryNumber":{"deliveryId":"2170","deliveryName":"邮政快递包裹","packageNum":1,"guaranteeValue":"0","epsOutShip":{"operationType":1,"branchCode":"1100099447061","insureValue":"0"}},"orderIds":[289651098551]}]}}
    @ApiModelProperty(value = "订单id集合",required = true)
    @NotNull(message = "订单id集合不能为空")
    private List<Long> orderIds;

    @ApiModelProperty(value = "任务地址id",notes = "默认值：21318561", required = true)
    @NotEmpty(message = "任务地址id不能为空")
    private Long venderTaskAddressId;

    @ApiModelProperty(value = "交货类型",notes = "默认值：203", required = true)
    @NotNull(message = "交货类型不能为空")
    private Long deliveryType;

    private DeliveryNumber deliveryNumber;

    @Data
    public static class DeliveryNumber{
        @ApiModelProperty(value = "物流公司",notes = "示例：2170", required = true)
        private String deliveryId;
        @ApiModelProperty(value = "物流公司",notes = "示例：邮政快递包裹", required = true)
        private String deliveryName;
        @ApiModelProperty(value = "包裹数量",notes = "示例：1", required = true)
        private Integer packageNum;
        @ApiModelProperty(value = "保证值",notes = "示例：0", required = true)
        private String guaranteeValue;
        private EpsOutShip epsOutShip;
    }

    @Data
    public static class EpsOutShip{
        @ApiModelProperty(value = "物流公司",notes = "邮政快递包裹：1", required = true)
        private Integer operationType;
        @ApiModelProperty(value = "月结编码",required = true)
        private String branchCode;
        @ApiModelProperty(value = "运单数量",required = true)
        private String insureValue;
    }
}



