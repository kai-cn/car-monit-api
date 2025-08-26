package com.ruoyi.modules.vo.dd;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/5/15 10:31
 * @Return
 */
@Data
public class ImCustomer {
    //{"skuId":"10089338043477","customer":"MUFDNzkxMkIwODA1REU4MDlBNURFM0Q4RDYzRkE0RUM=","orderId":"296546349775","params":{"appid":"im.customer","BPOPmpin":"","BPOPvid":"","BPOPcustomer":"","BPOPstoreId":""},"encryptNew":"true","authType":4}
    //{"skuId":"0","customer":customerId,"orderId":"293378411369","params":{"appid":"im.customer","BPOPmpin":"","BPOPvid":"","BPOPcustomer":"","BPOPstoreId":""},"encryptNew":"true","authType":4}
    @ApiModelProperty(value = "商品id",notes = "商品id", required = true)
    @NotEmpty(message = "商品id不能为空")
    private String skuId = "0";

    @ApiModelProperty(value = "userPin加密密文",notes = "userPin加密密文", required = true)
    @NotNull(message = "密文不能为空")
    private String customer;

    @ApiModelProperty(value = "订单id",notes = "订单id", required = true)
    @NotNull(message = "订单id不能为空")
    private String orderId;

    @ApiModelProperty(value = "新加密",notes = "新加密", required = true)
    @NotNull(message = "新加密不能为空")
    private String encryptNew = "true";

    @ApiModelProperty(value = "校验类型",notes = "校验类型", required = true)
    @NotNull(message = "校验类型不能为空")
    private Integer authType = 4;

    private ImParams params;


}
