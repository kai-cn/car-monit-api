# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnToll

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnToll.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnToll(JavaBean, Custom):
    """收费站基础信息对象 ods_szdn_toll

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_toll") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_toll"  # @TableName("ods_szdn_toll")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[str] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private String id;

    # @Excel(name = "路线编号")
    road_code: Optional[str] = None  # Java: private String roadCode; // 路线编号

    # @Excel(name = "收费站业务唯一编码")
    id_card: Optional[str] = None  # Java: private String idCard; // 收费站业务唯一编码

    # @Excel(name = "收费站编号", readConverterExp = "内=部")
    toll_code: Optional[str] = None  # Java: private String tollCode; // 收费站编号（内部）

    # @Excel(name = "收费站名称", readConverterExp = "内=部")
    toll_name: Optional[str] = None  # Java: private String tollName; // 收费站名称（内部）

    # @Excel(name = "桩号")
    pile_no: Optional[str] = None  # Java: private String pileNo; // 桩号

    # @Excel(name = "所属机构名称")
    org_name: Optional[str] = None  # Java: private String orgName; // 所属机构名称

    # @Excel(name = "收费站HEX编码")
    hex_code: Optional[str] = None  # Java: private String hexCode; // 收费站HEX编码

    # @Excel(name = "国网编号", readConverterExp = "内=部")
    state_code: Optional[str] = None  # Java: private String stateCode; // 国网编号（内部）

    # @Excel(name = "机构编码")
    org_code: Optional[str] = None  # Java: private String orgCode; // 机构编码

    # @Excel(name = "经度")
    longitude: Optional[str] = None  # Java: private String longitude; // 经度

    # @Excel(name = "纬度")
    latitude: Optional[str] = None  # Java: private String latitude; // 纬度

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "开通日期", width = 30, dateFormat = "yyyy-MM-dd")
    open_date: Optional[datetime] = None  # Java: private Date openDate; // 开通日期

    # @Excel(name = "收费站别名")
    toll_alias_name: Optional[str] = None  # Java: private String tollAliasName; // 收费站别名

    # @Excel(name = "入口治超监控资源，多个以英文逗号分割")
    in_monitor_resource: Optional[str] = None  # Java: private String inMonitorResource; // 入口治超监控资源，多个以英文逗号分割

    # @Excel(name = "车道抓拍监控资源，多个以英文逗号分割")
    lane_monitor_resource: Optional[str] = None  # Java: private String laneMonitorResource; // 车道抓拍监控资源，多个以英文逗号分割

    # @Excel(name = "广场监控资源，多个以英文逗号分割")
    square_monitor_resource: Optional[str] = None  # Java: private String squareMonitorResource; // 广场监控资源，多个以英文逗号分割

    # @Excel(name = "动环监控资源，多个以英文逗号分割")
    dynamic_monitor_resource: Optional[str] = None  # Java: private String dynamicMonitorResource; // 动环监控资源，多个以英文逗号分割

    # @Excel(name = "收费站编号")
    toll_code_merge: Optional[str] = None  # Java: private String tollCodeMerge; // 收费站编号

    # @Excel(name = "国网编号")
    state_code_merge: Optional[str] = None  # Java: private String stateCodeMerge; // 国网编号

    # @Excel(name = "收费站名称")
    toll_name_merge: Optional[str] = None  # Java: private String tollNameMerge; // 收费站名称

    # @Excel(name = "所属路段编码")
    section_code: Optional[str] = None  # Java: private String sectionCode; // 所属路段编码

    # @Excel(name = "收费站对应机构编码")
    toll_org_code: Optional[str] = None  # Java: private String tollOrgCode; // 收费站对应机构编码

    # @Excel(name = "流水是否接入")
    is_access: Optional[str] = None  # Java: private String isAccess; // 流水是否接入

