# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IEsService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IEsService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode

__all__ = ["IEsService"]


class IEsService(ABC):
    """IEsService

    【Java→Python】
    1) `public interface IEsService`
       → `class IEsService(ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def saveSnapshotFlow(self, flowData: OdsRtSzdnSnapshotFlowAddcode) -> bool:
        """saveSnapshotFlow

        :param flowData: OdsRtSzdnSnapshotFlowAddcode
        :return: bool

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def deleteSnapshotFlow(self, dataId: str) -> bool:
        """deleteSnapshotFlow

        :param dataId: String
        :return: bool

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
