# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.SysUtil

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/SysUtil.java
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class SysUtil(JavaBean):
    """SysUtil

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    buss_type: Optional[str] = None  # Java: private String bussType; // 业务类型

    buss_code: Optional[str] = None  # Java: private String bussCode; // 编码code

    query_condtion: Optional[str] = None  # Java: private String queryCondtion; // 查询条件

