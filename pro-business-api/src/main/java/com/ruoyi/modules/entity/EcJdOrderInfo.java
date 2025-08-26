package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.JSONHandler;
import com.ruoyi.common.config.base.BaseEntity;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.ruoyi.modules.vo.orders.*;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.List;
import java.util.Objects;

/**
 * 京东订单信息对象 ec_jd_order_info
 *
 * @author huangjun
 * @date 2024-08-30
 */
@Data
@TableName("ec_jd_order_info")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcJdOrderInfo extends BaseEntity {

    /**
     * 订单类型
     */
    private String orderType;

    /**
     * 门店id
     */
    private String mendianId;

    /**
     * 订单id
     */
    private String orderId;

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
     * 支付方式
     */
    private String paymentType;

    /**
     * 支付方式名称
     */
    private String paymentTypeName;

    /**
     * 订单下单时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Timestamp orderCreateTime;

    /**
     * 订单结算时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Timestamp orderCompleteTime;

    /**
     * 订单确认时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Timestamp paymentConfirmTime;

    /**
     * 商店id
     */
    private String storeId;

    /**
     * 商店名称
     */
    private String storeName;

    /**
     * 应付金额
     */
    private BigDecimal shouldPay;

    /**
     * 应收金额
     */
    private BigDecimal receivables;

    /**
     * 邮费
     */
    private BigDecimal freight;

    /**
     * 买家账号
     */
    private String userPin;

    /**
     * 买家姓名
     */
    private String consName;

    /**
     * 买家电话
     */
    private String consMobilePhone;

    /**
     * 买家收货地址
     */
    private String consAddress;

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

    /**
     * 商品数组
     */
    @TableField(value = "order_items", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private List<OrderItems> orderItems;

    /**
     * 订单状态对象
     */
    @TableField(value = "order_status_vo", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private OrderStatusVO orderStatusVo;

    /**
     * 物流信息数组
     */
    @TableField(value = "logistics_info_list", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private List<OrderLogisticsVO> logisticsInfoList;

    /**
     * 订单特殊显示数组
     */
    @TableField(value = "order_special_views", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private List<OrderSpecialViews> orderSpecialViews;

    /**
     * 订单标识对象
     */
    @TableField(value = "order_flag_vo", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private OrderFlagVO orderFlagVo;

    /**
     * 操作签名数组
     */
    @TableField(value = "operate_sign_info", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private OperateSignInfoVO operateSignInfo;

    /**
     * 商家备注对象
     */
    @TableField(value = "order_remark", typeHandler = JSONHandler.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    private OrderRemarkVO orderRemark;

    /**
     * 商铺id
     */
    private String shopId;

    /**
     * 商铺名称
     */
    private String shopName;

    //店铺类型
    @TableField(exist = false)
    private String merchantType;

    public boolean pEquals(EcJdOrderInfo jdOrderInfo) {
        orderStatusVo = orderStatusVo != null?orderStatusVo:new OrderStatusVO();
        jdOrderInfo.setOrderStatusVo(jdOrderInfo.getOrderStatusVo() != null?jdOrderInfo.getOrderStatusVo():new OrderStatusVO());
        orderRemark = orderRemark != null?orderRemark:new OrderRemarkVO();
        jdOrderInfo.setOrderRemark(jdOrderInfo.getOrderRemark() != null?jdOrderInfo.getOrderRemark():new OrderRemarkVO());
        return Objects.equals(orderStatusVo.getOrderStatus(),jdOrderInfo.getOrderStatusVo().getOrderStatus()) &&
                Objects.equals(orderRemark.getRemark(),jdOrderInfo.getOrderRemark().getRemark())&&
                Objects.equals(jdOrderInfo.getOrderCompleteTime(),jdOrderInfo.getOrderCompleteTime())&&
                Objects.equals(jdOrderInfo.getPaymentConfirmTime(),jdOrderInfo.getPaymentConfirmTime());
    }

    @Override
    public int hashCode() {
        return Objects.hash(super.hashCode(), orderStatusVo, orderRemark);
    }

    // 买家备注
    private String remark;

}
