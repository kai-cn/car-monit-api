package com.ruoyi.modules.vo.orders;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class OrderWareInfoVO {

    // 商品编号
    private String productId;

    private String productName;

    private String brandId;

    private String brandName;

    private String categoryId;

    private String categoryNames;

    private String itemNum;

    private BigDecimal jdPrice;

    private BigDecimal jdPriceMax;

    private BigDecimal jdPriceMin;

    private String logo;

}
