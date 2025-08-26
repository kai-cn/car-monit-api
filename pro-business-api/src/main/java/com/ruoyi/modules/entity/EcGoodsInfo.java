package com.ruoyi.modules.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.ruoyi.common.config.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.math.BigDecimal;

/**
 * 商品信息对象 ec_goods_info
 *
 * @author ruoyi
 * @date 2024-05-27
 */
@Data
@TableName("ec_goods_info")
@Accessors(chain = true)
@EqualsAndHashCode(callSuper = false)
public class EcGoodsInfo extends BaseEntity {

    /**
     * 来源平台
     */
    private String outsideSource;

    /**
     * 店铺id
     */
    private String storeId;

    /**
     * 店铺名称
     */
    private String storeName;

    /**
     * 商品名称
     */
    private String goodsName;

    /**
     * 商品编号
     */
    private String goodsNo;

    /**
     * 货号
     */
    private String itemNo;

    /**
     * 一级类目
     */
    private String oneCategoryName;

    /**
     * 二级类目
     */
    private String twoCategoryName;

    /**
     * 三级类目
     */
    private String threeCategoryName;

    /**
     * 四级类目
     */
    private String fourCategoryName;

    /**
     * 品牌
     */
    private String brand;

    /**
     * 京东价
     */
    private BigDecimal jdMoney;

    /**
     * 商品总库存
     */
    private String inventory;

    /**
     * 商品状态
     */
    private String goodStatus;

    /**
     * 商品分类
     */
    private String goodsCategory;

    /**
     * 商品分类名称
     */
    @TableField(exist = false)
    private String goodsCategoryName;

    /**
     * 图片链接
     */
    private String picUrl;

    /**
     * 状态（0正常1停用）
     */
    private String status;

    /**
     * 备注
     */
    private String remark;


}
