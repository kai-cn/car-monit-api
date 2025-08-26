package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.math.BigDecimal;

/**
 * 订单扩展对象 ec_order_goods
 *
 * @author ruoyi
 * @date 2024-06-21
 */
@Data
@TableName("ec_order_goods")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcOrderGoods extends BaseEntity {
    /**
     * 所属平台ID（字典：1京东2淘宝3抖音4拼多多）
     */
    private String platformId;

    /**
     * 店铺id
     */
    private String shopId;

    /**
     * 店铺名称
     */
    private String shopName;

    /**
     * 订单id
     */
    private String orderId;

    /**
     * 商品名称
     */
    private String skuName;

    /**
     * skuId
     */
    private String skuId;

    /**
     * 商品编号
     */
    private String productId;

    /**
     * 货号
     */
    private String itemId;

    /**
     * 商品数量
     */
    private Long num;

    /**
     * 商品价格
     */
    private BigDecimal jdPrice;

    /**
     * 颜色选择
     */
    private String color;

    /**
     * 图片地址
     */
    private String imgUrl;

    /**
     * 商品链接地址
     */
    private String skuUrl;

    /**
     * skuUuid
     */
    private String skuUuid;

    // 类别id
    private String categoryId;

    /**
     * 状态（0正常1隔离）
     */
    private String status;

    private String remark;

}
