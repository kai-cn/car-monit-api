package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 扣费费用明细对象 ec_cost_sz_detail
 *
 * @author ruoyi
 * @date 2024-08-16
 */
@Data
public class EcCostSzDetail extends BaseEntity {

    /** 费用设置id */
    private String costSzId;

    /** 开始范围 */
    private BigDecimal beginRange;

    /** 结束范围 */
    private BigDecimal endRange;

    /** 其他参数 */
    private String otherParas;

    /** 费用金额 */
    private BigDecimal costMoney;

    /** 状态（0正常1停用） */
    private String status;

    /** 备用字段1 */
    private String backCol1;

    /** 备用字段2 */
    private String backCol2;

    /** 开始范围 */
    @TableField(exist = false)
    private BigDecimal queryRange;

    /**
     * 备注
     */
    private String remark;


}
