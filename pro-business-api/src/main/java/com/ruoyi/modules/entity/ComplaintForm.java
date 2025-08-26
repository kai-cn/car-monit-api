package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

/**
 * @Description: 投诉单信息
 * @Author: ret-boot
 * @Date: 2024-04-28
 * @Version: V1.0
 */
@Data
@TableName("ec_complaint_form")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
@ApiModel(value = "ec_complaint_form对象", description = "投诉单信息")
public class ComplaintForm extends BaseEntity {

    /**
     * 单号宝账号
     */
    @ApiModelProperty(value = "单号宝账号")
    private String account;

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
     * 投诉内容
     */
    @ApiModelProperty(value = "投诉内容")
    private String msgContent;

    /**
     * 商家订单号
     */
    @ApiModelProperty(value = "商家订单号")
    private String shopOrderNo;

    /**
     * 单据状态(0-已处理,1-待处理)
     */
    @ApiModelProperty(value = "单据状态(0-已处理,1-待处理)")
    private Integer status;

    @ApiModelProperty(value = "店铺id")
    private String storeId;

    @ApiModelProperty(value = "店铺名称")
    private String storeName;
}
