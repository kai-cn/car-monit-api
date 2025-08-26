package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.config.base.BaseEntity;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.math.BigDecimal;
import java.util.Date;

/**
 * 中转仓订单对象 ec_zzc_order_info
 *
 * @author ruoyi
 * @date 2024-09-30
 */
@Data
@TableName("ec_zzc_order_info")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcZzcOrderInfo extends BaseEntity {

    /** 来源平台 字典：1京东2淘宝3抖音4拼多多 */
    private String platform;

    /** 中转仓编号 */
    private String zzcId;

    /** 店铺id */
    private String shopId;

    /** 店铺名称 */
    private String shopName;

    /** 中转类型 */
    private String tsfType;

    /** 用户id */
    private String userId;

    /** 仓库id */
    private String storeId;

    /** 仓库名称 */
    private String storeName;

    /** 仓库类型（2国际店） */
    private String storeType;

    /** 仓库地址 */
    private String storeAddress;

    /** 仓库电话 */
    private String storePhone;

    /** 扣点 */
    private BigDecimal point;

    /**
     * 状态
     * status = 1 未到达
     * status = 2 已到达
     * status = 2 订单退货
     * status = 4 已转运
     * */
    private String status;

    /**
     * 中转订单状态
     * orderStatus=1 未到达
     * orderStatus=2 发出
     * orderStatus=3 异常
     * orderStatus=4 拒收
     * orderStatus=5 完成
     */
    private String orderStatus;

    // 中转订单是否发出
    private String fcStatus;

    /** 订单id */
    private String orderId;

    /** 物流名称 */
    private String expressageName;

    /** 物流编号 */
    private String expressageNo;

    /** 收件人名称 */
    private String recvName;

    /** 收件人电话 */
    private String recvPhone;

    /** 收件人地址 */
    private String recvAddress;

    /** 收件人省份 */
    private String receiveProvinceName;

    /** 收件人地市 */
    private String receiveCityName;

    /** 收件人区县 */
    private String receiveDistrict;

    /** 下单时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date buyTime;

    /** 重量 */
    private String weight;

    /** 打印快递面单 */
    private String printExpressageFace;

    /** 警告类型 */
    private String warning;

    /** 警告消息 */
    private String warningMsg;

    /** 本地备注 */
    private String marks;

    /** 购买店铺地址 */
    private String buyShopAddress;

    /** 是否退回 */
    private String isReturn;

    /** 是否拒收 */
    private String rejection;

    /** 退回地址 */
    private String returnAddress;

    /** 退回子订单 */
    private String returnChildOrder;

    /** 退回名称 */
    private String returnName;

    /** 退回手机号 */
    private String returnPhone;

    /** 退回详细地址 */
    private String returnDetailedAddress;

    /** 退回件取消 cancel:是否取消 0否1是  */
    private String cancel;

    /** 预扣费 */
    private BigDecimal holdingFee;

    /** 实际扣费 */
    private BigDecimal actualFee;

    /** 是否超重 */
    private String isOverWeight;

    /** 超重费用 */
    private BigDecimal overWeightFee;

    /** 中转费用 */
    private BigDecimal tsfFee;

    /** 是否礼品单 0否1是 */
    private String lipin;

    /** 新发送物流单号 */
    private String newSendLogisticsNumber;

    /** 包装价格 */
    private BigDecimal packPrice;

    /** 到达时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date arrivalTime;

    /** 中转手续费用 */
    private BigDecimal tsfHoldingFee;

    /** 中转实际费用 */
    private BigDecimal tsfActualFee;

    /** 中转超重费用 */
    private BigDecimal tsfOverWeightFee;

    /** 中转包装价格 */
    private BigDecimal tsfPackPrice;

    /** 代理编码 */
    private String proxyCode;

    /** 取消快递单号 */
    private String cancelExpressageNo;

    /** 中转仓备注 */
    private String remarks;

    /** 打印标签标识 */
    private String printFlag;

    /** 中转快递单号 没用*/
    private String storeExpressageNo;

    /** 接收时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date receiveTime;

    // 短码
    private String sortIndex;

    /**
     * 销售平台 1京东 2淘宝 3抖音 4拼多多 5其他
     * ==》如果是京东的平台，下京东物流的一定要填写京东的销售订单号，不然仓库无法打印面单
     */
    private String salePlat;

    /**
     * 权限参数
     */
    @TableField(exist = false)
    private String myShopIds;

}
