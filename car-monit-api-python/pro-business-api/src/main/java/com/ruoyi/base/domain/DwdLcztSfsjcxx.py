# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.DwdLcztSfsjcxx

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/DwdLcztSfsjcxx.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class DwdLcztSfsjcxx(JavaBean, Custom):
    """收费所基础信息对象 dwd_lczt_sfsjcxx

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("dwd_lczt_sfsjcxx") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "dwd_lczt_sfsjcxx"  # @TableName("dwd_lczt_sfsjcxx")

    # @TableId(value = "agent_pk", type = IdType.ASSIGN_UUID)
    agent_pk: Optional[str] = field(default=None, metadata={"table_id": "agent_pk", "id_type": "ASSIGN_UUID"})  # Java: private String agentPk; // 代理主键

    # @Excel(name = "源系统主键")
    yxtzj: Optional[str] = None  # Java: private String yxtzj; // 源系统主键

    # @Excel(name = "收费所编码")
    sfsbm: Optional[str] = None  # Java: private String sfsbm; // 收费所编码

    # @Excel(name = "收费所名称")
    sfsmc: Optional[str] = None  # Java: private String sfsmc; // 收费所名称

    # @Excel(name = "经度")
    jd: Optional[str] = None  # Java: private String jd; // 经度

    # @Excel(name = "纬度")
    wd: Optional[str] = None  # Java: private String wd; // 纬度

    # @Excel(name = "所属路线编号")
    sslxbh: Optional[str] = None  # Java: private String sslxbh; // 所属路线编号

    # @Excel(name = "所属路线名称")
    sslxmc: Optional[str] = None  # Java: private String sslxmc; // 所属路线名称

    # @Excel(name = "所属路段编号")
    ssldbh: Optional[str] = None  # Java: private String ssldbh; // 所属路段编号

    # @Excel(name = "所属路段名称")
    ssldmc: Optional[str] = None  # Java: private String ssldmc; // 所属路段名称

    # @Excel(name = "所处桩号(K格式)")
    sczh_k: Optional[str] = None  # Java: private String sczhK; // 所处桩号(K格式)

    # @Excel(name = "所处桩号(数值格式)")
    sczh_n: Optional[str] = None  # Java: private String sczhN; // 所处桩号(数值格式)

    # @Excel(name = "所属管理中心编码")
    ssglzxbm: Optional[str] = None  # Java: private String ssglzxbm; // 所属管理中心编码

    # @Excel(name = "所属管理中心名称")
    ssglzxmc: Optional[str] = None  # Java: private String ssglzxmc; // 所属管理中心名称

    # @Excel(name = "来源系统")
    lyxt: Optional[str] = None  # Java: private String lyxt; // 来源系统

    # @Excel(name = "加载日期")
    load_time: Optional[str] = None  # Java: private String loadTime; // 加载日期

    # @Excel(name = "全字段MD5")
    all_col_pk: Optional[str] = None  # Java: private String allColPk; // 全字段MD5

