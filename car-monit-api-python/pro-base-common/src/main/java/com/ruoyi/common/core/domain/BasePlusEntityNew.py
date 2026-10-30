# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.BasePlusEntityNew

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/BasePlusEntityNew.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.CustomClass import CustomClass


@dataclass
class BasePlusEntityNew(CustomClass):
    """MyBatis-Plus 实体基类（新版：去掉插入/更新自动填充注解）。

    【Java→Python】与 BasePlusEntity 的差异只在于 @TableField(fill=...) 全部移除；
    移植后通过 metadata 里“没有 fill 键”来表达这一差异，其余语义一致。
    """

    id: Optional[str] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})
    eps_id: Optional[int] = None                                             # 创建人所在单位或科室
    del_flag: Optional[str] = field(
        default=None, metadata={"column": "del_flag", "select": False, "logic": ("0", "1")}
    )  # 删除标志
    create_by: Optional[int] = None                                          # 创建人
    create_time: Optional[datetime] = None                                   # 创建时间
    update_by: Optional[int] = None                                          # 更新人
    update_time: Optional[datetime] = None                                   # 更新时间
    sort: Optional[int] = None                                               # 排序
    tenant_id: Optional[int] = field(default=None, metadata={"column": "tenant_id"})  # 租户
