# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.ZdataLocationDict

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataLocationDict.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class ZdataLocationDict(JavaBean, Custom):
    """车辆位置对象 zdata_location_dict

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("zdata_location_dict") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "zdata_location_dict"  # @TableName("zdata_location_dict")

    id: Optional[int] = None  # Java: private Long id; // 主键

    # @Excel(name = "类型")
    type: Optional[str] = None  # Java: private String type; // 类型

    # @Excel(name = "收费站")
    name: Optional[str] = None  # Java: private String name; // 收费站

    # @Excel(name = "轨迹表和实时轨迹code")
    raw_code: Optional[str] = None  # Java: private String rawCode; // 轨迹表和实时轨迹code

    # @Excel(name = "收费站/门架code")
    standard_code: Optional[str] = None  # Java: private String standardCode; // 收费站/门架code

    # @Excel(name = "路线编码")
    roadcode: Optional[str] = None  # Java: private String roadcode; // 路线编码

    # @Excel(name = "路线名称")
    roadname: Optional[str] = None  # Java: private String roadname; // 路线名称

    # @Excel(name = "路段编码")
    sectioncode: Optional[str] = None  # Java: private String sectioncode; // 路段编码

    # @Excel(name = "路段名称")
    sectionname: Optional[str] = None  # Java: private String sectionname; // 路段名称

    # @Excel(name = "收费站编码")
    tollcode: Optional[str] = None  # Java: private String tollcode; // 收费站编码

    # @Excel(name = "收费站名称")
    tollname: Optional[str] = None  # Java: private String tollname; // 收费站名称

    # @Excel(name = "组织机构编码")
    orgcode: Optional[str] = None  # Java: private String orgcode; // 组织机构编码

    # @Excel(name = "组织机构名称")
    orgname: Optional[str] = None  # Java: private String orgname; // 组织机构名称

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "创建时间", width = 30, dateFormat = "yyyy-MM-dd")
    created_at: Optional[datetime] = None  # Java: private Date createdAt; // 创建时间

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "修改时间", width = 30, dateFormat = "yyyy-MM-dd")
    updated_at: Optional[datetime] = None  # Java: private Date updatedAt; // 修改时间

    latitude: Optional[float] = None  # Java: private BigDecimal latitude; // 维度

    longitude: Optional[float] = None  # Java: private BigDecimal longitude; // 经度

    pile_no_k: Optional[str] = None  # Java: private String pileNoK; // 桩号K

    pile_no: Optional[str] = None  # Java: private String pileNo; // 桩号

    direction: Optional[str] = None  # Java: private String direction; // 方向

    # @Excel(name = "备注")
    remark: Optional[str] = None  # Java: private String remark; // 备注

