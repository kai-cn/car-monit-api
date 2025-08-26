package com.ruoyi.modules.entity;

import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import java.math.BigDecimal;

/**
 * 账单流水对象 ec_billing_statement
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Data
public class EcBillingStatement  extends BaseEntity {

    /** 订单id */
    private String orderId;

    /** 店铺id */
    private String storeId;

    /** 店铺名称 */
    private String storeName;

    /** 增值账号id */
    private String accountId;

    /** 增值账号 */
    private String accountName;

    /** 1充值2短信消费3取消关联退回扣费4同步物流出单预扣费5同步物流出单退回预扣费6同步物流出单实际扣费7虚拟号扣费" +
     "8退回虚拟号扣费9同步物流出单退款10店铺时间续费11购买物流单号扣费（快运单）12中转仓账号充值扣费13客服工具充值14购买物流单号扣费（礼品单）15云仓订单扣费99其他类型 */
    private String costType;

    /** 费用金额 */
    private BigDecimal costMoney;

    /** 业务类型(1扣费2充值) */
    private String bussType;

    /** 是否已退款 */
    private String backCol1;

    /** 退款id */
    private String backCol2;

    /**
     * 扣费小类标识
     */
    private String kfType;

    /** 状态（0正常1停用） */
    private String status;


    /** 我的店铺字符串 */
    private String myShopIds;

    /**
     * 查询条件 统计时间
     */
    private String startTime;
    private String endTime;

    /**
     * 备注
     */
    private String remark;

}
