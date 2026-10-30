# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.TreeEntity

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/TreeEntity.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from com.ruoyi.common.core.domain.BaseEntity import BaseEntity


@dataclass
class TreeEntity(BaseEntity):
    """Tree 基类（extends BaseEntity）。

    【Java→Python】
    1) 继承 BaseEntity → dataclass 继承；父类字段先出现，子类字段追加在后，
       实例化时按“父类字段 → 子类字段”顺序传参（建议用关键字参数，避免顺序陷阱）。
    2) `List<?> children = new ArrayList<>()` 是“字段初始化即创建”语义，
       对应 field(default_factory=list)（不能直接用 [] 作为默认值，否则所有实例共享同一列表）。
    3) Java 的 getter/setter 保留同名方法以便逐行对照。
    """

    parent_name: Optional[str] = None                        # 父菜单名称
    parent_id: Optional[int] = None                          # 父菜单ID（java.lang.Long）
    order_num: Optional[int] = None                          # 显示顺序（java.lang.Integer）
    ancestors: Optional[str] = None                           # 祖级列表
    children: list[Any] = field(default_factory=list)         # 子部门

    def getParentName(self) -> Optional[str]:
        return self.parent_name

    def setParentName(self, value: Optional[str]) -> None:
        self.parent_name = value

    def getParentId(self) -> Optional[int]:
        return self.parent_id

    def setParentId(self, value: Optional[int]) -> None:
        self.parent_id = value

    def getOrderNum(self) -> Optional[int]:
        return self.order_num

    def setOrderNum(self, value: Optional[int]) -> None:
        self.order_num = value

    def getAncestors(self) -> Optional[str]:
        return self.ancestors

    def setAncestors(self, value: Optional[str]) -> None:
        self.ancestors = value

    def getChildren(self) -> list[Any]:
        return self.children

    def setChildren(self, value: list[Any]) -> None:
        self.children = value
