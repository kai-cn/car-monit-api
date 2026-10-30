# -*- coding: utf-8 -*-
"""org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest``
及其静态内部类 ``IndicesAliasesRequest.AliasActions``。
本工程用法（EsIndexManageService.addAlias）：
    AliasActions action = new AliasActions(AliasActions.Type.ADD)
            .alias(aliasName).index(indexName);
    IndicesAliasesRequest request = new IndicesAliasesRequest();
    request.addAliasAction(action);
    AcknowledgedResponse resp = esClient.indices().updateAliases(request, RequestOptions.DEFAULT);

【Java→Python 关键差异】
1) Java 的 ``AliasActions`` 是**静态内部类**，通过
   ``IndicesAliasesRequest.AliasActions`` 访问；这里定义在模块级，并在文件末尾
   `IndicesAliasesRequest.AliasActions = AliasActions` 挂回，保持访问路径一致。
2) ``AliasActions.Type`` 是内部枚举（ADD / REMOVE / REMOVE_INDEX）；同样用
   模块级 Enum + 类属性挂回。
3) Java 的 ``alias(String...)`` / ``index(String...)`` 是可变参数（一个 alias
   可对应多个 index）；Python 用 ``*values``，调用写法一致。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List

__all__ = ["IndicesAliasesRequest", "AliasActions", "AliasActionsType"]


class AliasActionsType(Enum):
    """``AliasActions.Type`` 内部枚举的替身。"""

    ADD = "ADD"
    REMOVE = "REMOVE"
    REMOVE_INDEX = "REMOVE_INDEX"

    def __str__(self) -> str:
        # 与 Java 枚举的 toString() 一致（输出常量名）
        return self.name


class AliasActions(object):
    """``IndicesAliasesRequest.AliasActions`` 的替身（别名动作）。"""

    #: 【Java→Python】内部枚举挂到类属性上：AliasActions.Type.ADD
    Type = AliasActionsType

    def __init__(self, action_type: AliasActionsType) -> None:
        self._type = action_type
        self._aliases: List[str] = []
        self._indices: List[str] = []

    # ------------------------------------------------------------------ 链式 setter
    def alias(self, *aliases: str) -> "AliasActions":
        """对应 ``alias(String... aliases)``。"""
        self._aliases.extend(aliases)
        return self

    def index(self, *indices: str) -> "AliasActions":
        """对应 ``index(String... indices)``。"""
        self._indices.extend(indices)
        return self

    # ------------------------------------------------------------------ getter
    def getType(self) -> AliasActionsType:
        return self._type

    def getAliases(self) -> List[str]:
        return list(self._aliases)

    def getIndices(self) -> List[str]:
        return list(self._indices)

    def __repr__(self) -> str:
        return "AliasActions(type=%s, aliases=%r, indices=%r)" % (
            self._type, self._aliases, self._indices)


class IndicesAliasesRequest(object):
    """``IndicesAliasesRequest`` 的替身（收集别名动作）。"""

    def __init__(self) -> None:
        self._actions: List[AliasActions] = []

    def addAliasAction(self, action: AliasActions) -> "IndicesAliasesRequest":
        """对应 ``addAliasAction(AliasActions action)``。"""
        self._actions.append(action)
        return self

    def getAliasActions(self) -> List[AliasActions]:
        """Java 返回 ``List<AliasActions>``；替身同样返回副本。"""
        return list(self._actions)

    def __repr__(self) -> str:
        return "IndicesAliasesRequest(actions=%d)" % len(self._actions)


# 【Java→Python】静态内部类挂回，保持 `IndicesAliasesRequest.AliasActions.Type.ADD` 写法
IndicesAliasesRequest.AliasActions = AliasActions
