package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

/**
 * 类目扣点管理对象 ec_category_points_info
 *
 * @author huangjun
 * @date 2024-06-24
 */
@Data
@TableName("ec_category_points_info")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class CategoryPointsInfo extends BaseEntity {

    /**
     * 类目Id
     */
    private String categoryId;

    /**
     * 类目名称
     */
    private String name;

    /**
     * 店铺类型：pop：pop店铺，small：小店，international国际店铺
     */
    private String storeType;

    /**
     * 类目父id
     */
    private String parentId;

    /**
     * 类目等级
     */
    private String level;

    /**
     * 一级类目id
     */
    private String oneCategoryId;

    /**
     * 二级类目id
     */
    private String twoCategoryId;

    /**
     * 三级类目id
     */
    private String threeCategoryId;

    /**
     * 一级类目名称
     */
    private String oneCategoryName;

    /**
     * 二级类目名称
     */
    private String twoCategoryName;

    /**
     * 三级类目名称
     */
    private String threeCategoryName;

    /**
     * 是否需计算项：1是2否
     */
    private String isCount;

    /**
     * 技术服务费率（SOP）
     */
    private String supportRates;

    /**
     * 交易服务费率（SOP）
     */
    private String transactionRates;

    /**
     * 扣点
     */
    private String pointsRates;

}
