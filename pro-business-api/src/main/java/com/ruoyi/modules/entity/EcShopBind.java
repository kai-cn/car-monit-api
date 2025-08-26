package com.ruoyi.modules.entity;

import com.ruoyi.common.config.base.BaseEntity;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;
import lombok.experimental.Accessors;

import java.math.BigDecimal;
import java.util.Date;
import java.util.List;

/**
 * 店铺绑定对象 ec_shop_bind
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Data
@Accessors(chain = true)
public class EcShopBind extends BaseEntity {

    /**
     * 店铺id
     */
    private String storeId;

    /**
     * 店铺名称
     */
    private String storeName;

    /**
     * 增值账号id
     */
    private String accountId;

    /**
     * 增值账号
     */
    private String accountName;

    /**
     * 备用字段1
     */
    private String backCol1;

    /**
     * 备用字段2
     */
    private String backCol2;

    /**
     * 是否开通,(0未开通1开通)
     */
    private String ktStatus;

    /**
     * 有效期
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date expireTime;

    /**
     * 店铺ids
     */
    private String shopIds;

    /**
     * 续费时间
     */
    private String xfTime;


    List<EcShopBind> boList;

    /**
     * 金额（元）
     */
    private BigDecimal totalMoney;


    private BigDecimal czTotalMoney;

    /**
     * 备注
     */
    private String remark;
}
