# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsRtSzdnSnapshotFlowAddcodeService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode

__all__ = ["IOdsRtSzdnSnapshotFlowAddcodeService"]


class IOdsRtSzdnSnapshotFlowAddcodeService(IService[OdsRtSzdnSnapshotFlowAddcode], ABC):
    """门架抓拍流水Service接口

    【Java→Python】
    1) `public interface IOdsRtSzdnSnapshotFlowAddcodeService extends IService<OdsRtSzdnSnapshotFlowAddcode>`
       → `class IOdsRtSzdnSnapshotFlowAddcodeService(IService[OdsRtSzdnSnapshotFlowAddcode], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowAddcodeById(self, bigId: str) -> Optional[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水

        :param bigId: 门架抓拍流水ID
        :return: 门架抓拍流水

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowAddcodeList(self, odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水列表

        :param odsRtSzdnSnapshotFlowAddcode: 门架抓拍流水
        :return: 门架抓拍流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(self, queryUuids: str, applyTime1: str, applyTime2: str) -> dict[str, OdsRtSzdnSnapshotFlowAddcode]:
        """通过UUID 查询

        :param queryUuids: String
        :param applyTime1: String
        :param applyTime2: String
        :return: dict[str, OdsRtSzdnSnapshotFlowAddcode]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsRtSzdnSnapshotFlowAddcodeListNew(self, odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """selectOdsRtSzdnSnapshotFlowAddcodeListNew

        :param odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode
        :return: list[OdsRtSzdnSnapshotFlowAddcode]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getMaxSnapshotTime(self) -> str:
        """getMaxSnapshotTime

        :return: str

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def queryByCursor(self, cursor: str, maxSnapshotTime: str, pageSize: int) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """queryByCursor

        :param cursor: String
        :param maxSnapshotTime: String
        :param pageSize: int
        :return: list[OdsRtSzdnSnapshotFlowAddcode]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
