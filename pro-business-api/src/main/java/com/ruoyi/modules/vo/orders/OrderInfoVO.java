package com.ruoyi.modules.vo.orders;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.List;

@Data
public class OrderInfoVO {

     //订单号
     private String orderId;

     //支付方式
     private String paymentType;

     private String paymentTypeName;

     // 店铺ID
     private String shopId;

    /// 店铺名称
    private String shopName;

    // 收货人
     private String consName;

    // 手机号
     private String consMobilePhone;

    // 地址（虚拟）
     private String consAddress;

     // 邮费
     private BigDecimal freight = BigDecimal.ZERO;

     // 应收金额
     private BigDecimal shouldPay = BigDecimal.ZERO;

     // 应付金额
     private BigDecimal receivables = BigDecimal.ZERO;

     // 订单状态
     private OrderStatusVO orderStatusVo;

     private OrderFlagVO orderFlagVo;

     // 商品信息
     private List<OrderItems> orderItems;

     private List<OrderSpecialViews> orderSpecialViews;

     // 订单金额
     private OrderPaymentVO paymentAmount;

     private String storeName;

     // 买家备注
     private String remark;

     // 隔离状态
     private String status;

     // 收货人账号
     private String userPin;

     // 最晚出库时间（接口读取）
     @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
     private Timestamp promiseOutShipDate;

     // 付款时间
     @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
     private Timestamp paymentConfirmTime;

    //订单完成时间（结算时间）
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Timestamp orderCompleteTime;

    //下单时间
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Timestamp orderCreateTime;

     /**
     * 订单类型
     */
    private String orderType;

    /**
     * 门店id
     */
    private String mendianId;

    /**
     * 订单状态
     */
    private String commission;

    /**
     * 取消选择标识
     */
    private String pickCancelFlag;

    /**
     * 自动输出标识
     */
    private String autoOutShipFlag;

    /**
     * 费用类型
     */
    private String feeType;

    /**
     * 商店id
     */
    private String storeId;

    /**
     * 省份id
     */
    private String provinceId;

    /**
     * 市id
     */
    private String cityId;

    /**
     * 县id
     */
    private String countyId;

    /**
     * 城镇id
     */
    private String townId;

    /**
     * 商品数量
     */
    private Long skuTotalNum;
}
