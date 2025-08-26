package com.ruoyi.modules.entity;

import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 费用设置对象 ec_cost_sz
 *
 * @author ruoyi
 * @date 2024-07-09
 */
@Data
public class EcCostSz extends BaseEntity {

    /** 业务类型 */
    private String bussType;

    /** 费用类型 */
    private String costType;

    /** 费用金额 */
    private BigDecimal costMoney;

    /** 开始范围 */
    private BigDecimal beginRange;

    /** 结束范围 */
    private BigDecimal endRange;

    /** 其他参数 */
    private String otherParas;

    /** 状态（0正常1停用） */
    private String status;

    /** 备用字段1 */
    private String backCol1;

    /** 备用字段2 */
    private String backCol2;

    /**
     * 备注
     */
    private String remark;
}
