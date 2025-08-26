package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.util.Date;

/**
 * 中转仓疑难件对象 ec_zzc_difficult
 *
 * @author ruoyi
 * @date 2024-11-01
 */
@Data
@TableName("ec_zzc_difficult")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcZzcDifficult extends BaseEntity {

    /**
     * 中转仓id
     */
    private Long zzcId;

    /**
     * 疑难件ID
     */
    private String difficultId;

    /**
     * 用户ID
     */
    private Long userId;

    /**
     * 店铺ID
     */
    private String shopId;

    /**
     * 店铺名称
     */
    private String saleShopName;

    /**
     * 仓库ID
     */
    private String cangId;

    /**
     * 仓库名称
     */
    private String cangName;

    /**
     * 订单号
     */
    private String saleOrderId;

    /**
     * 货源物流单号
     */
    private String huoyuanLogisticsNumber;

    /**
     * 仓库处理状态(1未处理2已处理)
     */
    private String state;

    /**
     * 包裹状态
     */
    private String packState;

    /**
     * 异常原因
     */
    private String reason;

    /**
     * 发货人电话
     */
    private String sendPhone;

    /**
     * 用户处理状态(1未处理2已处理)
     */
    private String userState;

    /**
     * 客服处理状态(1未处理2已处理)
     */
    private String kefuState;

    /**
     * 其他备注
     */
    private String indexRemark;

    /**
     * 用户备注
     */
    private String userRemark;

    /**
     * 包裹照片
     */
    private String image;

    /**
     * 仓库类型
     */
    private String storeType;

    /**
     * 疑难件创建时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date difficultTime;

    /**
     * 备注
     */
    private String remark;
}
