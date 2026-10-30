# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnGantry

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantry.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnGantry(JavaBean, Custom):
    """门架信息对象 ods_szdn_gantry

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_gantry") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_gantry"  # @TableName("ods_szdn_gantry")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[str] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private String id;

    # @Excel(name = "门架编号", readConverterExp = "分=离")
    gantry_code: Optional[str] = None  # Java: private String gantryCode; // 门架编号（分离）

    # @Excel(name = "门架名称")
    gantry_name: Optional[str] = None  # Java: private String gantryName; // 门架名称

    # @Excel(name = "所属路线编码")
    road_code: Optional[str] = None  # Java: private String roadCode; // 所属路线编码

    # @Excel(name = "所属路段编码")
    section_code: Optional[str] = None  # Java: private String sectionCode; // 所属路段编码

    # @Excel(name = "所属收费站编码")
    toll_code: Optional[str] = None  # Java: private String tollCode; // 所属收费站编码

    # @Excel(name = "所属管理中心机构编码")
    org_code: Optional[str] = None  # Java: private String orgCode; // 所属管理中心机构编码

    # @Excel(name = "门架二进制编号")
    hex_code: Optional[str] = None  # Java: private String hexCode; // 门架二进制编号

    # @Excel(name = "方向", readConverterExp = "0=:,上=行，1:,下=行")
    direction: Optional[str] = None  # Java: private String direction; // 方向（0: 上行，1: 下行）

    # @Excel(name = "桩号")
    pile_no: Optional[str] = None  # Java: private String pileNo; // 桩号

    # @Excel(name = "经度")
    lon: Optional[str] = None  # Java: private String lon; // 经度

    # @Excel(name = "纬度")
    lat: Optional[str] = None  # Java: private String lat; // 纬度

    # @Excel(name = "是否虚门架", readConverterExp = "0=：否，1：是")
    is_virtual: Optional[str] = None  # Java: private String isVirtual; // 是否虚门架（0：否，1：是）

    # @Excel(name = "里程")
    mileage: Optional[str] = None  # Java: private String mileage; // 里程

    # @Excel(name = "边界门架类型", readConverterExp = "0=：边界入口门架，1：边界出口门架")
    boundary_gantry_type: Optional[str] = None  # Java: private String boundaryGantryType; // 边界门架类型（0：边界入口门架，1：边界出口门架）

    # @Excel(name = "门架类型", readConverterExp = "0=：收费门架，1：交调门架")
    gantry_type: Optional[str] = None  # Java: private String gantryType; // 门架类型（0：收费门架，1：交调门架）

    # @Excel(name = "城市编码")
    city_code: Optional[str] = None  # Java: private String cityCode; // 城市编码

    # @Excel(name = "行政区名称")
    district_name: Optional[str] = None  # Java: private String districtName; // 行政区名称

    # @Excel(name = "是否属于集团，0：否；1：是")
    belong_group: Optional[str] = None  # Java: private String belongGroup; // 是否属于集团，0：否；1：是

    # @Excel(name = "门架编号")
    gantry_code_merge: Optional[str] = None  # Java: private String gantryCodeMerge; // 门架编号

    # @Excel(name = "门架别名")
    gantry_name_alias: Optional[str] = None  # Java: private String gantryNameAlias; // 门架别名

    # @Excel(name = "备注")
    remark: Optional[str] = None  # Java: private String remark; // 备注

    # @TableField(exist = false)
    is_data: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String isData; // 0没有1存在

