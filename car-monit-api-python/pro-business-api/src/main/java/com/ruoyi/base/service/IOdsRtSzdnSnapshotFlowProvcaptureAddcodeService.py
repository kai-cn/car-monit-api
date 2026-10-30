# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import OdsRtSzdnSnapshotFlowProvcaptureAddcode

__all__ = ["IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService"]


class IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService(IService[OdsRtSzdnSnapshotFlowProvcaptureAddcode], ABC):
    """省界抓拍Service接口

    【Java→Python】
    1) `public interface IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService extends IService<OdsRtSzdnSnapshotFlowProvcaptureAddcode>`
       → `class IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService(IService[OdsRtSzdnSnapshotFlowProvcaptureAddcode], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍

        :param bigId: 省界抓拍ID
        :return: 省界抓拍

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(self, odsRtSzdnSnapshotFlowProvcaptureAddcode: OdsRtSzdnSnapshotFlowProvcaptureAddcode) -> list[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍列表

        :param odsRtSzdnSnapshotFlowProvcaptureAddcode: 省界抓拍
        :return: 省界抓拍集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(self, queryUuids: str) -> dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """根据UUID 查询

        :param queryUuids: String
        :return: dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
