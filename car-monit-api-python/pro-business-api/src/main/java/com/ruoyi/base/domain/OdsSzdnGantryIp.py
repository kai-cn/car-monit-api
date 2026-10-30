# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnGantryIp

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantryIp.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnGantryIp(JavaBean, Custom):
    """省界设备ip对象 ods_szdn_gantry_ip

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_gantry_ip") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_gantry_ip"  # @TableName("ods_szdn_gantry_ip")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[int] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private Long id; // 主键

    # @Excel(name = "门架编号")
    gantry_code: Optional[str] = None  # Java: private String gantryCode; // 门架编号

    # @Excel(name = "门架名称")
    gantry_name: Optional[str] = None  # Java: private String gantryName; // 门架名称

    # @Excel(name = "机构编码")
    org_code: Optional[str] = None  # Java: private String orgCode; // 机构编码

    # @Excel(name = "设备ip")
    ip: Optional[str] = None  # Java: private String ip; // 设备ip

    brand: Optional[str] = None  # Java: private String brand;

    # @Excel(name = "类型1是省界门架")
    type: Optional[str] = None  # Java: private String type; // 类型1是省界门架

    # @TableField(exist = false)
    ods_szdn_gantry: Optional[Any] = field(default=None, metadata={"exist": False})  # Java: private OdsSzdnGantry odsSzdnGantry; // 收费站对象

