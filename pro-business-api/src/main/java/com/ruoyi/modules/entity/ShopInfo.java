package com.ruoyi.modules.entity;

import com.ruoyi.common.config.base.BaseEntity;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.Date;

/**
 * 店铺管理对象 shop_info
 *
 * @author ruoyi
 * @date 2024-04-23
 */
@Data
public class ShopInfo extends BaseEntity {

    /**
     * 所属平台ID（字典：1京东2淘宝3抖音4拼多多）
     */
    private String platformId;

    /**
     * 商家id
     */
    private String merchantId;

    /**
     * 店铺id
     */
    private String shopId;

    /**
     * 商家类型
     */
    private String merchantType;

    /**
     * 店铺层级
     */
    private String shopLevel;

    /**
     * 店铺名称
     */
    private String shopName;

    /**
     * 店铺账号
     */
    private String shopAccount;

    /**
     * 店铺密码：需要加密
     */
    private String shopPwd;

    /**
     * 图片
     */
    private String imageIds;

    /**
     * 附件
     */
    private String fileIds;

    /**
     * 店铺多开(0不允许1允许)
     */
    private String isMore;

    /**
     * 消息提示(0否1是)
     */
    private String isMsg;

    /**
     * 同步缓存(0同步1不同步)
     */
    private String isCache;

    /**
     * 同步cookie(0同步1不同步)
     */
    private String isCookie;

    /**
     * MAC地址(下拉框)
     */
    private String macAddr;

    /**
     * UA(下拉框)
     */
    private String ua;

    /**
     * 分辨率(下拉框)
     */
    private String resolution;

    /**
     * Windows
     */
    private String windows;

    /**
     * MAC OS
     */
    private String macOs;

    /**
     * Android
     */
    private String android;

    /**
     * 授权人员
     */
    private String authPerson;

    /**
     * 使用期限
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date usefulLife;

    /**
     * 是否登录（0否1是）
     */
    private String isLogin;

    /**
     * 登录日期
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date loginDate;

    /**
     * 备用字段1
     */
    private String backCol1;

    /**
     * 备用字段2
     */
    private String backCol2;

    /**
     * 状态（0正常1停用）
     */
    private String status;

    private String flag;

    private String shopIds;

    // 店铺cookie
    private String cookie;


    /**
     * 状态（0正常1停用）
     */
    private String ktStatus;


    /**
     * 是否过期（0否1是）
     */
    private String isGq;

}
