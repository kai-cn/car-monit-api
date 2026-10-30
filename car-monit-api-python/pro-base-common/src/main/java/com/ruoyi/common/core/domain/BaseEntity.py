# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.BaseEntity

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/BaseEntity.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class BaseEntity:
    """Entity 基类。

    【Java→Python】
    1) 普通 POJO（手写 getter/setter）→ @dataclass；Java 的 getXxx()/setXxx() 在 Python 中
       退化为属性读写，因此调用点 `entity.getCreateBy()` 需改写为 `entity.create_by`（已注释）。
    2) @JsonIgnore → Python 序列化时由序列化器忽略该字段（此处仅用 metadata 标记）。
    3) @JsonFormat(pattern="yyyy-MM-dd HH:mm:ss") → Python 用 strftime/isoformat 控制格式。
    4) @JsonInclude(NON_EMPTY) → 序列化时为空则跳过。
    5) java.util.Date → datetime.datetime（Java Date 含毫秒；datetime 同样含微秒）。
    6) getParams() 的“懒创建 HashMap”语义原样保留：字段初始为 None，首次调用才建 dict。
    """

    search_value: Optional[str] = None      # searchValue 搜索值（@JsonIgnore）
    create_by: Optional[str] = None         # 创建者
    create_time: Optional[datetime] = None  # 创建时间（@JsonFormat yyyy-MM-dd HH:mm:ss）
    update_by: Optional[str] = None         # 更新者
    update_time: Optional[datetime] = None  # 更新时间（@JsonFormat yyyy-MM-dd HH:mm:ss）
    remark: Optional[str] = None            # 备注
    params: Optional[dict[str, Any]] = None  # 请求参数（@JsonInclude NON_EMPTY）

    # ---- Java getter/setter 兼容层（便于逐行对照旧代码） -------------------
    def getSearchValue(self) -> Optional[str]:
        return self.search_value

    def setSearchValue(self, value: Optional[str]) -> None:
        self.search_value = value

    def getCreateBy(self) -> Optional[str]:
        return self.create_by

    def setCreateBy(self, value: Optional[str]) -> None:
        self.create_by = value

    def getCreateTime(self) -> Optional[datetime]:
        return self.create_time

    def setCreateTime(self, value: Optional[datetime]) -> None:
        self.create_time = value

    def getUpdateBy(self) -> Optional[str]:
        return self.update_by

    def setUpdateBy(self, value: Optional[str]) -> None:
        self.update_by = value

    def getUpdateTime(self) -> Optional[datetime]:
        return self.update_time

    def setUpdateTime(self, value: Optional[datetime]) -> None:
        self.update_time = value

    def getRemark(self) -> Optional[str]:
        return self.remark

    def setRemark(self, value: Optional[str]) -> None:
        self.remark = value

    def getParams(self) -> dict[str, Any]:
        # Java: if (params == null) params = new HashMap<>(); return params;
        if self.params is None:
            self.params = {}
        return self.params

    def setParams(self, params: Optional[dict[str, Any]]) -> None:
        self.params = params
