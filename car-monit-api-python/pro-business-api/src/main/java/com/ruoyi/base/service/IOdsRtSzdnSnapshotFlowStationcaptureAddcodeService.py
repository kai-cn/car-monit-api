# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import OdsRtSzdnSnapshotFlowStationcaptureAddcode

__all__ = ["IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService"]


class IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService(IService[OdsRtSzdnSnapshotFlowStationcaptureAddcode], ABC):
    """收费站抓拍Service接口

    【Java→Python】
    1) `public interface IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService extends IService<OdsRtSzdnSnapshotFlowStationcaptureAddcode>`
       → `class IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService(IService[OdsRtSzdnSnapshotFlowStationcaptureAddcode], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍

        :param bigId: 收费站抓拍ID
        :return: 收费站抓拍

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(self, odsRtSzdnSnapshotFlowStationcaptureAddcode: OdsRtSzdnSnapshotFlowStationcaptureAddcode) -> list[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍列表

        :param odsRtSzdnSnapshotFlowStationcaptureAddcode: 收费站抓拍
        :return: 收费站抓拍集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(self, queryUuids: str, applyTime1: str, applyTime2: str) -> dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """根据UUID 查询

        :param queryUuids: String
        :param applyTime1: String
        :param applyTime2: String
        :return: dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
