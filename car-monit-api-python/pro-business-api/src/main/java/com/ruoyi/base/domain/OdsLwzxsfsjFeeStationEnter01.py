# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeStationEnter01.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsLwzxsfsjFeeStationEnter01(JavaBean, Custom):
    """收费站入口数据对象 ods_lwzxsfsj_fee_station_enter_01

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_lwzxsfsj_fee_station_enter_01") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_lwzxsfsj_fee_station_enter_01"  # @TableName("ods_lwzxsfsj_fee_station_enter_01")

    # @TableId(value = "bigId", type = IdType.ASSIGN_UUID)
    big_id: Optional[int] = field(default=None, metadata={"table_id": "bigId", "id_type": "ASSIGN_UUID"})  # Java: private Long bigId;

    # @Excel(name = "CPC卡或ETC卡的编号")
    cardid: Optional[str] = None  # Java: private String cardid; // CPC卡或ETC卡的编号

    # @Excel(name = "单片式OBU/CPC卡电量百分比")
    electricalpercentage: Optional[int] = None  # Java: private Long electricalpercentage; // 单片式OBU/CPC卡电量百分比

    # @Excel(name = "入站车轴数")
    enaxlecount: Optional[int] = None  # Java: private Long enaxlecount; // 入站车轴数

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "入站时间", width = 30, dateFormat = "yyyy-MM-dd")
    entime: Optional[datetime] = None  # Java: private Date entime; // 入站时间

    # @Excel(name = "入口车道hex")
    entolllanehex: Optional[str] = None  # Java: private String entolllanehex; // 入口车道hex

    # @Excel(name = "入口车道id")
    entolllaneid: Optional[str] = None  # Java: private String entolllaneid; // 入口车道id

    # @Excel(name = "入口收费站编码")
    entollstationid: Optional[str] = None  # Java: private String entollstationid; // 入口收费站编码

    # @Excel(name = "入口称重")
    enweight: Optional[float] = None  # Java: private BigDecimal enweight; // 入口称重

    # @Excel(name = "车牌号+车牌类型")
    identifyvehicleid: Optional[str] = None  # Java: private String identifyvehicleid; // 车牌号+车牌类型

    # @Excel(name = "车道类型")
    lanetype: Optional[str] = None  # Java: private String lanetype; // 车道类型

    # @Excel(name = "介质类型")
    mediatype: Optional[str] = None  # Java: private String mediatype; // 介质类型

    # @Excel(name = "操作id")
    operid: Optional[str] = None  # Java: private String operid; // 操作id

    # @Excel(name = "作业媒介")
    operationmedia: Optional[str] = None  # Java: private String operationmedia; // 作业媒介

    # @Excel(name = "参数")
    params: Optional[str] = None  # Java: private String params; // 参数

    # @Excel(name = "通行id")
    passid: Optional[str] = None  # Java: private String passid; // 通行id

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "接收时间", width = 30, dateFormat = "yyyy-MM-dd")
    receivetime: Optional[datetime] = None  # Java: private Date receivetime; // 接收时间

    # @Excel(name = "工班号")
    shift: Optional[str] = None  # Java: private String shift; // 工班号

    # @Excel(name = "标记状态")
    signstatus: Optional[str] = None  # Java: private String signstatus; // 标记状态

    # @Excel(name = "特殊类型")
    specialtype: Optional[str] = None  # Java: private String specialtype; // 特殊类型

    # @Excel(name = "TAC码")
    tac: Optional[str] = None  # Java: private String tac; // TAC码

    # @Excel(name = "终端机编号")
    terminalno: Optional[str] = None  # Java: private String terminalno; // 终端机编号

    # @Excel(name = "PSAM卡脱机交易序列号")
    terminaltransno: Optional[str] = None  # Java: private String terminaltransno; // PSAM卡脱机交易序列号

    # @Excel(name = "交易金额")
    transfee: Optional[float] = None  # Java: private BigDecimal transfee; // 交易金额

    # @Excel(name = "交易类型")
    transtype: Optional[str] = None  # Java: private String transtype; // 交易类型

    # @Excel(name = "总数")
    vcount: Optional[int] = None  # Java: private Long vcount; // 总数

    # @Excel(name = "车种")
    vehicleclass: Optional[str] = None  # Java: private String vehicleclass; // 车种

    # @Excel(name = "车牌号+车牌类型")
    vehicleid: Optional[str] = None  # Java: private String vehicleid; // 车牌号+车牌类型

    # @Excel(name = "车辆识别标识")
    vehiclesign: Optional[str] = None  # Java: private String vehiclesign; // 车辆识别标识

    # @Excel(name = "车牌识别流水号")
    vehiclesignid: Optional[str] = None  # Java: private String vehiclesignid; // 车牌识别流水号

    # @Excel(name = "车辆类型")
    vehicletype: Optional[str] = None  # Java: private String vehicletype; // 车辆类型

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    load_time: Optional[datetime] = None  # Java: private Date loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[str] = None  # Java: private String gradeLevel; // 分类分级

    # @Excel(name = "cid")
    cid: Optional[str] = None  # Java: private String cid; // cid

    # @TableField(exist = false)
    cid_list: Optional[list[str]] = field(default=None, metadata={"exist": False})  # Java: private List<String> cidList;

