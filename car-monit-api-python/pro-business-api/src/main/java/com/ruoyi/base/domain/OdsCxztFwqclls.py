# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsCxztFwqclls

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsCxztFwqclls.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsCxztFwqclls(JavaBean, Custom):
    """服务区车辆流水对象 ods_cxzt_fwqclls

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_cxzt_fwqclls") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_cxzt_fwqclls"  # @TableName("ods_cxzt_fwqclls")

    big_id: Optional[int] = None  # Java: private Long bigId;

    datauuid: Optional[str] = None  # Java: private String datauuid;

    # @Excel(name = "抓拍照片url")
    targetpicurl: Optional[str] = None  # Java: private String targetpicurl; // 抓拍照片url

    # @Excel(name = "车辆品牌")
    vehiclebrand: Optional[str] = None  # Java: private String vehiclebrand; // 车辆品牌

    # @Excel(name = "车牌照片")
    platepicurl: Optional[str] = None  # Java: private String platepicurl; // 车牌照片

    # @Excel(name = "车类型")
    rollvehiclestype: Optional[str] = None  # Java: private String rollvehiclestype; // 车类型

    # @Excel(name = "车牌")
    plateno: Optional[str] = None  # Java: private String plateno; // 车牌

    # @Excel(name = "方向名称")
    directionname: Optional[str] = None  # Java: private String directionname; // 方向名称

    # @Excel(name = "车牌类型")
    platetype: Optional[str] = None  # Java: private String platetype; // 车牌类型

    # @Excel(name = "是否危化品车")
    dangmark: Optional[str] = None  # Java: private String dangmark; // 是否危化品车

    # @Excel(name = "通过时间", readConverterExp = "分=区字段")
    crosstime: Optional[datetime] = None  # Java: private Date crosstime; // 通过时间（分区字段）

    # @Excel(name = "坐标")
    axles: Optional[str] = None  # Java: private String axles; // 坐标

    # @Excel(name = "设备名称")
    devicename: Optional[str] = None  # Java: private String devicename; // 设备名称

    # @Excel(name = "IP地址")
    ipaddress: Optional[str] = None  # Java: private String ipaddress; // IP地址

    # @Excel(name = "服务区名称")
    servicename: Optional[str] = None  # Java: private String servicename; // 服务区名称

    # @Excel(name = "车辆类型")
    vehicletype: Optional[str] = None  # Java: private String vehicletype; // 车辆类型

    # @Excel(name = "加载时间")
    load_time: Optional[str] = None  # Java: private String loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[str] = None  # Java: private String gradeLevel; // 分类分级

    # @TableField(exist = false)
    uuid_list: Optional[list[str]] = field(default=None, metadata={"exist": False})  # Java: private List<String> uuidList;

