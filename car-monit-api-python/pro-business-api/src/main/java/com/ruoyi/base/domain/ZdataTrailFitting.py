# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.ZdataTrailFitting

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailFitting.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class ZdataTrailFitting(JavaBean, Custom):
    """车辆出入口拟合轨迹对象 zdata_trail_fitting

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("zdata_trail_fitting") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "zdata_trail_fitting"  # @TableName("zdata_trail_fitting")

    cid: Optional[str] = None  # Java: private String cid; // 轨迹唯一标识（cid）

    # @Excel(name = "入口车轴数")
    enaxlecount: Optional[int] = None  # Java: private Integer enaxlecount; // 入口车轴数

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "入口时间", width = 30, dateFormat = "yyyy-MM-dd")
    entime: Optional[datetime] = None  # Java: private Date entime; // 入口时间

    # @Excel(name = "入口车道编号")
    entolllaneid: Optional[str] = None  # Java: private String entolllaneid; // 入口车道编号

    # @Excel(name = "入口收费站编号")
    entollstationid: Optional[str] = None  # Java: private String entollstationid; // 入口收费站编号

    # @Excel(name = "入口收费站名称")
    entollstationname: Optional[str] = None  # Java: private String entollstationname; // 入口收费站名称

    # @Excel(name = "入口车型分类", readConverterExp = "收=费车型")
    envehicleclass: Optional[int] = None  # Java: private Integer envehicleclass; // 入口车型分类（收费车型）

    # @Excel(name = "入口车辆编号")
    envehicleid: Optional[str] = None  # Java: private String envehicleid; // 入口车辆编号

    # @Excel(name = "入口车辆类型代码")
    envehicletype: Optional[int] = None  # Java: private Integer envehicletype; // 入口车辆类型代码

    # @Excel(name = "入口称重", readConverterExp = "k=g")
    enweight: Optional[int] = None  # Java: private Long enweight; // 入口称重（kg）

    # @Excel(name = "出口时间", readConverterExp = "分=区键")
    extime: Optional[datetime] = None  # Java: private Date extime; // 出口时间（分区键）

    # @Excel(name = "出口车道编号")
    extolllaneid: Optional[str] = None  # Java: private String extolllaneid; // 出口车道编号

    # @Excel(name = "出口收费站编号")
    extollstationid: Optional[str] = None  # Java: private String extollstationid; // 出口收费站编号

    # @Excel(name = "出口收费站名称")
    extollstationname: Optional[str] = None  # Java: private String extollstationname; // 出口收费站名称

    # @Excel(name = "出口车型分类", readConverterExp = "收=费车型")
    exvehicleclass: Optional[int] = None  # Java: private Integer exvehicleclass; // 出口车型分类（收费车型）

    # @Excel(name = "出口车辆编号")
    exvehicleid: Optional[str] = None  # Java: private String exvehicleid; // 出口车辆编号

    # @Excel(name = "出口车辆类型代码")
    exvehicletype: Optional[int] = None  # Java: private Integer exvehicletype; // 出口车辆类型代码

    # @Excel(name = "出口称重", readConverterExp = "k=g")
    exweight: Optional[int] = None  # Java: private Long exweight; // 出口称重（kg）

    # @Excel(name = "拟合轨迹点集合")
    trailpoints: Optional[str] = None  # Java: private String trailpoints; // 拟合轨迹点集合

