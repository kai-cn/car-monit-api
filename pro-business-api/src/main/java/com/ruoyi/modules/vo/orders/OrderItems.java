package com.ruoyi.modules.vo.orders;

import com.baomidou.mybatisplus.annotation.TableField;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class OrderItems {

    // 颜色选择
    private String color;

    // 图片地址
    private String imgUrl;

    // 货号
    private String itemId;

    // 价格
    private BigDecimal jdPrice;

    // 购买数量
    private Long num;

    // SKU
    private String skuId;

    // 商品标题
    private String skuName;

    // 商品链接地址
    private String skuUrl;

    private String skuUuid;

    // 商品类目
    private String categoryId;

    // 商品编号
    private String productId;

    // 商品编号
    private String productName;

    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private OrderWareInfoVO wareInfo;

    /**
     * 商铺id
     */
    @TableField(exist = false)
    private String shopId;

    /**
     * 商铺id
     */
    @TableField(exist = false)
    private String shopName;

    /**
     * 订单id
     */
    @TableField(exist = false)
    private String orderId;

    /**
     * 来源id
     */
    @TableField(exist = false)
    private String platformId;
}
