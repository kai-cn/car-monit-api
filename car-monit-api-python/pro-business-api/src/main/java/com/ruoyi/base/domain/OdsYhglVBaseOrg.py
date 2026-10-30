# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsYhglVBaseOrg

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsYhglVBaseOrg.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsYhglVBaseOrg(JavaBean, Custom):
    """机构信息对象 ods_yhgl_v_base_org

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_yhgl_v_base_org") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_yhgl_v_base_org"  # @TableName("ods_yhgl_v_base_org")

    # @TableId(value = "big_id", type = IdType.ASSIGN_UUID)
    big_id: Optional[str] = field(default=None, metadata={"table_id": "big_id", "id_type": "ASSIGN_UUID"})  # Java: private String bigId; // 主键

    # @Excel(name = "机构代码")
    org_code: Optional[str] = None  # Java: private String orgCode; // 机构代码

    # @Excel(name = "机构名称")
    org_name: Optional[str] = None  # Java: private String orgName; // 机构名称

    # @Excel(name = "机构简称")
    org_short_name: Optional[str] = None  # Java: private String orgShortName; // 机构简称

    # @Excel(name = "上级机构ID")
    org_parent_id: Optional[str] = None  # Java: private String orgParentId; // 上级机构ID

    # @Excel(name = "层级代码")
    org_level_code: Optional[str] = None  # Java: private String orgLevelCode; // 层级代码

    # @Excel(name = "是否虚机构 1：虚机构，0：非需机构")
    org_is_virtual: Optional[str] = None  # Java: private String orgIsVirtual; // 是否虚机构 1：虚机构，0：非需机构

    # @Excel(name = "是否是养护类", readConverterExp = "1=：是，0否")
    org_maintenance: Optional[str] = None  # Java: private String orgMaintenance; // 是否是养护类（1：是，0否）

    # @Excel(name = "机构顺序")
    org_sequence: Optional[int] = None  # Java: private Long orgSequence; // 机构顺序

    # @Excel(name = "是否管理单位，主要指是否是路段管理单位(1：是,0：否)")
    org_is_manager: Optional[str] = None  # Java: private String orgIsManager; // 是否管理单位，主要指是否是路段管理单位(1：是,0：否)

    # @Excel(name = "是否删除 1：是 0：否")
    org_is_deleted: Optional[str] = None  # Java: private String orgIsDeleted; // 是否删除 1：是 0：否

    # @Excel(name = "机构分类： 01集团 02公司 03管理中心 10部门 11所 12服务区 13养护区 14站 15项目办 16信息中心 17项目部  99其它", width = 30, dateFormat = "yyyy-MM-dd")
    org_category: Optional[str] = None  # Java: private String orgCategory; // 机构分类： 01集团 02公司 03管理中心 10部门 11所 12服务区 13养护区 14站 15项目办 16信息中心 17项目部 99其它

    # @Excel(name = "是否授权机构 1：是 0：否")
    org_is_authorized: Optional[str] = None  # Java: private String orgIsAuthorized; // 是否授权机构 1：是 0：否

    # @Excel(name = "机构地址")
    org_address: Optional[str] = None  # Java: private String orgAddress; // 机构地址

    # @Excel(name = "是自营养护单位")
    org_is_yh_autarky: Optional[str] = None  # Java: private String orgIsYhAutarky; // 是自营养护单位

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    load_time: Optional[datetime] = None  # Java: private Date loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[int] = None  # Java: private Integer gradeLevel; // 分类分级

