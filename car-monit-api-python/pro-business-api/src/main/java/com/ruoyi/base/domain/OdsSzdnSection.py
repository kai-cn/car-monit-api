# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnSection

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnSection.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnSection(JavaBean, Custom):
    """路段信息对象 ods_szdn_section

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_section") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_section"  # @TableName("ods_szdn_section")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[str] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private String id;

    # @Excel(name = "路线编码")
    road_code: Optional[str] = None  # Java: private String roadCode; // 路线编码

    # @Excel(name = "路线名称")
    road_name: Optional[str] = None  # Java: private String roadName; // 路线名称

    # @Excel(name = "路段编码")
    section_code: Optional[str] = None  # Java: private String sectionCode; // 路段编码

    # @Excel(name = "路段名称")
    section_name: Optional[str] = None  # Java: private String sectionName; // 路段名称

    # @Excel(name = "起点桩号")
    start_pile_no: Optional[int] = None  # Java: private Long startPileNo; // 起点桩号

    # @Excel(name = "终点桩号")
    end_pile_no: Optional[int] = None  # Java: private Long endPileNo; // 终点桩号

    # @Excel(name = "机构代码")
    org_code: Optional[str] = None  # Java: private String orgCode; // 机构代码

    # @Excel(name = "机构名称")
    org_name: Optional[str] = None  # Java: private String orgName; // 机构名称

    # @Excel(name = "层级代码")
    org_level_code: Optional[str] = None  # Java: private String orgLevelCode; // 层级代码

    # @Excel(name = "机构分类")
    org_category: Optional[str] = None  # Java: private String orgCategory; // 机构分类

    # @Excel(name = "里程")
    mileage: Optional[int] = None  # Java: private Long mileage; // 里程

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "通车日期", width = 30, dateFormat = "yyyy-MM-dd")
    open_date: Optional[datetime] = None  # Java: private Date openDate; // 通车日期

