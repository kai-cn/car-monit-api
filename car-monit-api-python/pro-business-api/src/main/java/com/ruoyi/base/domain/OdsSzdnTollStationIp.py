# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnTollStationIp

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnTollStationIp.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnTollStationIp(JavaBean, Custom):
    """收费站ip对象 ods_szdn_toll_station_ip

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_toll_station_ip") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_toll_station_ip"  # @TableName("ods_szdn_toll_station_ip")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[int] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private Long id;

    toll_code: Optional[str] = None  # Java: private String tollCode;

    toll_name: Optional[str] = None  # Java: private String tollName;

    org_code: Optional[str] = None  # Java: private String orgCode;

    ip: Optional[str] = None  # Java: private String ip;

    brand: Optional[str] = None  # Java: private String brand;

    # @TableField(exist = false)
    ods_szdn_toll: Optional[Any] = field(default=None, metadata={"exist": False})  # Java: private OdsSzdnToll odsSzdnToll; // 收费站对象

