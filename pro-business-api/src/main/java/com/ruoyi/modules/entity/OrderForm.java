package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

/**
 * @Description: 下单单据信息
 * @Author: ret-boot
 * @Date: 2024-04-28
 * @Version: V1.0
 */
@Data
@TableName("ec_order_form")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
@ApiModel(value = "ec_order_form对象", description = "下单单据信息")
public class OrderForm extends BaseEntity {

    /**
     * 上家快递单号
     */
    @ApiModelProperty(value = "上家快递单号")
    private String copyExpressNo;

    /**
     * 出单单号
     */
    @ApiModelProperty(value = "出单单号")
    private String expressNo;

    /**
     * 商家订单号
     */
    @ApiModelProperty(value = "商家订单号")
    private String shopOrderNo;

    /**
     * 地址
     */
    @ApiModelProperty(value = "地址")
    private String address;

    /**
     * 余额
     */
    @ApiModelProperty(value = "余额")
    private String balance;

    @ApiModelProperty(value = "单据状态(1待处理,2出单失败,3出单成功,4已退款,5关联成功,6关联失败)")
    private String status;

    @ApiModelProperty(value = "推送状态(3-已出单,4-已退款)")
    private String setpStatus;

    @ApiModelProperty(value = "出库状态(1已出库,2-待出库)")
    private String jdStatus;

    @ApiModelProperty(value = "仓库物流")
    private String message;

    @ApiModelProperty(value = "店铺id")
    private String storeId;

    @ApiModelProperty(value = "店铺名称")
    private String storeName;

}
