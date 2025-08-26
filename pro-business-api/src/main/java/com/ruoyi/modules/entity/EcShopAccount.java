package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 增值账号对象 ec_shop_account
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Data
public class EcShopAccount extends BaseEntity {

    /** 账号 */
    private String account;

    /** 密码 */
    private String accountPassword;

    /** 剩余金额（元） */
    private BigDecimal totalMoney;

    /** 充值总金额（元） */
    private BigDecimal czTotalMoney;

    /** 店铺ids */
    private String storeIds;

    /** 店铺名称s */
    private String storeNames;

    /** 备用字段1 */
    private String backCol1;

    /** 备用字段2 */
    private String backCol2;

    /** 状态（0正常1停用） */
    private String status;

    /** 我的店铺字符串 */
    private String myShopIds;


    /** 金额（元） */
    private BigDecimal payTotalMoney;


    /** 金额（元） */
    private BigDecimal czMoney;

    /** 店铺ID */
    private String shopId;

    /** 店铺ID */
    private String shopName;

    /**
     * 备注
     */
    private String remark;

    /**
     * 扣费小类标识
     */
    private String kfType;

    /** 订单id */
    @TableField(exist = false)
    private String orderId;

    /** 费用明细 */
    @TableField(exist = false)
    private String costType;

}
