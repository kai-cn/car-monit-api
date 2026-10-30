# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeGantryFusion01.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsLwzxsfsjFeeGantryFusion01(JavaBean, Custom):
    """交易流水对象 ods_lwzxsfsj_fee_gantry_fusion_01

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_lwzxsfsj_fee_gantry_fusion_01") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_lwzxsfsj_fee_gantry_fusion_01"  # @TableName("ods_lwzxsfsj_fee_gantry_fusion_01")

    big_id: Optional[str] = None  # Java: private String bigId; // $column.columnComment

    # @Excel(name = "实际计费方式")
    actualfeeclass: Optional[str] = None  # Java: private String actualfeeclass; // 实际计费方式

    # @Excel(name = "车轴数")
    axlecount: Optional[int] = None  # Java: private Long axlecount; // 车轴数

    # @Excel(name = "创建时间")
    createtime: Optional[datetime] = None  # Java: private Date createtime;

    # @Excel(name = "优惠金额")
    discountfee: Optional[int] = None  # Java: private Long discountfee; // 优惠金额

    # @Excel(name = "单片式OBU/CPC卡电量百分比")
    electricalpercentage: Optional[int] = None  # Java: private Long electricalpercentage; // 单片式OBU/CPC卡电量百分比

    # @Excel(name = "入口车轴数")
    enaxlecount: Optional[int] = None  # Java: private Long enaxlecount; // 入口车轴数

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "入站时间", width = 30, dateFormat = "yyyy-MM-dd")
    entime: Optional[datetime] = None  # Java: private Date entime; // 入站时间

    # @Excel(name = "入口车道hex")
    entolllanehex: Optional[str] = None  # Java: private String entolllanehex; // 入口车道hex

    # @Excel(name = "入口车道ID")
    entolllaneid: Optional[str] = None  # Java: private String entolllaneid; // 入口车道ID

    # @Excel(name = "入口收费站编码")
    entollstationid: Optional[str] = None  # Java: private String entollstationid; // 入口收费站编码

    # @Excel(name = "入口收费站名称")
    entollstationname: Optional[str] = None  # Java: private String entollstationname; // 入口收费站名称

    # @Excel(name = "入口车种")
    envehicleclass: Optional[int] = None  # Java: private Long envehicleclass; // 入口车种

    # @Excel(name = "入口车牌号+车牌类型")
    envehicleid: Optional[str] = None  # Java: private String envehicleid; // 入口车牌号+车牌类型

    # @Excel(name = "入口车牌号+颜色")
    envehicleidcolor: Optional[str] = None  # Java: private String envehicleidcolor; // 入口车牌号+颜色

    # @Excel(name = "入口车型")
    envehicletype: Optional[int] = None  # Java: private Long envehicletype; // 入口车型

    # @Excel(name = "入口称重")
    enweight: Optional[int] = None  # Java: private Long enweight; // 入口称重

    # @Excel(name = "入口操作人员id")
    entryoperatorid: Optional[str] = None  # Java: private String entryoperatorid; // 入口操作人员id

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "出站时间", width = 30, dateFormat = "yyyy-MM-dd")
    extime: Optional[datetime] = None  # Java: private Date extime; // 出站时间

    # @Excel(name = "出口车道号编码")
    extolllaneid: Optional[str] = None  # Java: private String extolllaneid; // 出口车道号编码

    # @Excel(name = "出口收费站编码")
    extollstationid: Optional[str] = None  # Java: private String extollstationid; // 出口收费站编码

    # @Excel(name = "出口收费站名称")
    extollstationname: Optional[str] = None  # Java: private String extollstationname; // 出口收费站名称

    # @Excel(name = "出口车种")
    exvehicleclass: Optional[int] = None  # Java: private Long exvehicleclass; // 出口车种

    # @Excel(name = "出口车牌号+车牌类型")
    exvehicleid: Optional[str] = None  # Java: private String exvehicleid; // 出口车牌号+车牌类型

    # @Excel(name = "出口车型")
    exvehicletype: Optional[int] = None  # Java: private Long exvehicletype; // 出口车型

    # @Excel(name = "出口称重")
    exweight: Optional[int] = None  # Java: private Long exweight; // 出口称重

    # @Excel(name = "出口id")
    exitid: Optional[str] = None  # Java: private String exitid; // 出口id

    # @Excel(name = "费用")
    fee: Optional[int] = None  # Java: private Long fee; // 费用

    # @Excel(name = "费显显示信息")
    feeboardplay: Optional[str] = None  # Java: private String feeboardplay; // 费显显示信息

    # @Excel(name = "收费里程")
    feemileage: Optional[int] = None  # Java: private Long feemileage; // 收费里程

    # @Excel(name = "交易金额占比")
    feerate: Optional[str] = None  # Java: private String feerate; // 交易金额占比

    # @Excel(name = "融合描述")
    fusiondesc: Optional[str] = None  # Java: private String fusiondesc; // 融合描述

    # @Excel(name = "融合标识,")
    fusionflag: Optional[str] = None  # Java: private String fusionflag; // 融合标识,

    # @Excel(name = "id")
    id: Optional[str] = None  # Java: private String id;

    # @Excel(name = "开票标识")
    identification: Optional[str] = None  # Java: private String identification; // 开票标识

    # @Excel(name = "出口识别车牌号+车牌类型")
    identifyvehicleid: Optional[str] = None  # Java: private String identifyvehicleid; // 出口识别车牌号+车牌类型

    # @Excel(name = "出口识别车牌号+颜色")
    identifyvehicleidcolor: Optional[str] = None  # Java: private String identifyvehicleidcolor; // 出口识别车牌号+颜色

    # @Excel(name = "出口车道类型")
    lanetype: Optional[str] = None  # Java: private String lanetype; // 出口车道类型

    # @Excel(name = "介质编码")
    mediano: Optional[str] = None  # Java: private String mediano; // 介质编码

    # @Excel(name = "通行介质")
    mediatype: Optional[str] = None  # Java: private String mediatype; // 通行介质

    # @Excel(name = "标签无卡累计次数")
    nocardcount: Optional[int] = None  # Java: private Long nocardcount; // 标签无卡累计次数

    # @Excel(name = "OBU序号编码")
    obuid: Optional[str] = None  # Java: private String obuid; // OBU序号编码

    # @Excel(name = "OBU 单/双片标识")
    obusign: Optional[str] = None  # Java: private String obusign; // OBU 单/双片标识

    # @Excel(name = "0BU 总累计交易金额")
    obutotalamount: Optional[int] = None  # Java: private Long obutotalamount; // 0BU 总累计交易金额

    # @Excel(name = "OBU累计优惠后通行费金额")
    obutotaldiscountamount: Optional[int] = None  # Java: private Long obutotaldiscountamount; // OBU累计优惠后通行费金额

    # @Excel(name = "操作id")
    operid: Optional[str] = None  # Java: private String operid; // 操作id

    # @Excel(name = "参数")
    params: Optional[str] = None  # Java: private String params; // 参数

    # @Excel(name = "通行id")
    passid: Optional[str] = None  # Java: private String passid; // 通行id

    # @Excel(name = "支付id")
    paycardid: Optional[str] = None  # Java: private String paycardid; // 支付id

    # @Excel(name = "应收总额")
    payfee: Optional[int] = None  # Java: private Long payfee; // 应收总额

    # @Excel(name = "支付类型")
    paytype: Optional[str] = None  # Java: private String paytype; // 支付类型

    # @Excel(name = "${comment}", readConverterExp = "$column.readConverterExp()")
    provfee: Optional[int] = None  # Java: private Long provfee; // $column.columnComment

    # @Excel(name = "本省交易成功次数")
    provtranscount: Optional[int] = None  # Java: private Long provtranscount; // 本省交易成功次数

    # @Excel(name = "通行省份个数")
    provincecount: Optional[int] = None  # Java: private Long provincecount; // 通行省份个数

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "接收时间", width = 30, dateFormat = "yyyy-MM-dd")
    receivetime: Optional[datetime] = None  # Java: private Date receivetime; // 接收时间

    # @Excel(name = "工班号")
    shift: Optional[str] = None  # Java: private String shift; // 工班号

    # @Excel(name = "最短收费金额")
    shortfee: Optional[int] = None  # Java: private Long shortfee; // 最短收费金额

    # @Excel(name = "最短路径里程数")
    shortfeemileage: Optional[int] = None  # Java: private Long shortfeemileage; // 最短路径里程数

    # @Excel(name = "标记状态")
    signstatus: Optional[str] = None  # Java: private String signstatus; // 标记状态

    # @Excel(name = "全网最小费额费率版本号")
    spcrateversion: Optional[str] = None  # Java: private String spcrateversion; // 全网最小费额费率版本号

    # @Excel(name = "特殊类型")
    specialtype: Optional[str] = None  # Java: private String specialtype; // 特殊类型

    # @Excel(name = "多条省内交易信息")
    splitprovince: Optional[str] = None  # Java: private String splitprovince; // 多条省内交易信息

    # @Excel(name = "TAC码")
    tac: Optional[str] = None  # Java: private String tac; // TAC码

    # @Excel(name = "终端机编号")
    terminalno: Optional[str] = None  # Java: private String terminalno; // 终端机编号

    # @Excel(name = "PSAM卡脱机交易序列号")
    terminaltransno: Optional[str] = None  # Java: private String terminaltransno; // PSAM卡脱机交易序列号

    # @Excel(name = "卡面扣费金额")
    transfee: Optional[int] = None  # Java: private Long transfee; // 卡面扣费金额

    # @Excel(name = "交易支付类型")
    transpaytype: Optional[str] = None  # Java: private String transpaytype; // 交易支付类型

    # @Excel(name = "交易类型")
    transtype: Optional[str] = None  # Java: private String transtype; // 交易类型

    # @Excel(name = "车辆识别标识")
    vehiclesign: Optional[str] = None  # Java: private String vehiclesign; // 车辆识别标识

    # @Excel(name = "车牌识别流水号")
    vehiclesignid: Optional[str] = None  # Java: private String vehiclesignid; // 车牌识别流水号

    # @Excel(name = "车牌号ID")
    vid: Optional[str] = None  # Java: private String vid; // 车牌号ID

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    load_time: Optional[datetime] = None  # Java: private Date loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[int] = None  # Java: private Long gradeLevel; // 分类分级

    # @TableField(exist = false)
    in_apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String inApplyTime1; // 时间查询

    # @TableField(exist = false)
    in_apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String inApplyTime2;

    # @TableField(exist = false)
    out_apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String outApplyTime1;

    # @TableField(exist = false)
    out_apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String outApplyTime2;

