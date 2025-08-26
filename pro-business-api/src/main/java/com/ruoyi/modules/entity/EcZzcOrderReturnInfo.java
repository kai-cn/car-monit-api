package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.math.BigDecimal;
import java.util.Date;

/**
 * 中转仓订单返回信息对象 ec_zzc_order_return_info
 *
 * @author ruoyi
 * @date 2024-09-30
 */
@Data
@TableName("ec_zzc_order_return_info")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcZzcOrderReturnInfo extends BaseEntity {

    private String zzcOrderId;

    /**
     * autoId
     */
    private Long autoId;

    /**
     * 用户ID
     */
    private Long userId;

    /**
     * 店铺ID
     */
    private Long shopId;

    /**
     * 店铺名称
     */
    private String shopName;

    /**
     * 仓库ID
     */
    private Long storeId;

    /**
     * 物流ID
     */
    private String sendLogisticsId;

    /**
     * tsf类型
     */
    private String tsfType;

    /**
     * 中转运单号
     */
    private String expressageNo;

    /**
     * 退货物流编号
     */
    private String refundLogisticsNumber;

    /**
     * 退货物流名称
     */
    private String refundLogisticsName;

    /**
     * 父级订单ID
     */
    private String parentOrderId;

    /**
     * 父级中转运单号
     */
    private String parentExpressageNo;

    /**
     * 商品名称
     */
    private String goodsName;

    /**
     * 返回名称
     */
    private String returnName;

    /**
     * 返回电话
     */
    private String returnPhone;

    /**
     * 返回详细地址
     */
    private String returnDetailedAddress;

    /**
     * 实际扣费
     */
    private BigDecimal actualFee;

    /**
     * 预扣费
     */
    private BigDecimal holdingFee;

    /**
     * 返回省份
     */
    private String returnProvinceName;

    /**
     * 返回城市
     */
    private String returCityName;

    /**
     * 返回地区
     */
    private String returnDistrict;

    /**
     * 重量
     */
    private BigDecimal weight;

    /**
     * 平台
     */
    private String platform;

    /**
     * 是否超重
     */
    private String isOverWeight;

    /**
     * 超重费用
     */
    private BigDecimal overWeightFee;

    /**
     * tsf扣费
     */
    private BigDecimal tsfFee;

    /**
     * 包裹价格
     */
    private BigDecimal packPrice;

    /**
     * 是否删除
     */
    private String isDelete;

    /**
     * 到达时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd")
    private Date arrivalTime;

    /**
     * tsf预扣费
     */
    private BigDecimal tsfHoldingFee;

    /**
     * tsf实际扣费
     */
    private BigDecimal tsfActualFee;

    /**
     * tsf超重费用
     */
    private BigDecimal tsfOverWeightFee;

    /**
     * tsf包裹价格
     */
    private BigDecimal tsfPackPrice;

    /**
     * 代理编码
     */
    private String proxyCode;

    /**
     * 状态
     */
    private String status;

    @TableField(exist = false)
    private String zzcId;
    @TableField(exist = false)
    private String orderId;

}
