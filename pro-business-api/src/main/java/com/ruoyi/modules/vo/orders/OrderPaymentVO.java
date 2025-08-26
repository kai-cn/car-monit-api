package com.ruoyi.modules.vo.orders;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.math.BigDecimal;

//支付金额
@Data
public class OrderPaymentVO {

    // 应收金额
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal shouldPay = BigDecimal.ZERO;

    // 邮费
    private BigDecimal freight = BigDecimal.ZERO;

    // 实得金额 = 应付-邮费
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal actualPay = BigDecimal.ZERO;

    // 优惠
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal preferential = BigDecimal.ZERO;

    // 采购金额
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal purchasePrice = BigDecimal.ZERO;

    // 扣点金额
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal brokerage = BigDecimal.ZERO;

    // 利润
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal profit = BigDecimal.ZERO;

    // 应付金额
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private BigDecimal receivables = BigDecimal.ZERO;


    private String orderId;

    private String shopId;
}
