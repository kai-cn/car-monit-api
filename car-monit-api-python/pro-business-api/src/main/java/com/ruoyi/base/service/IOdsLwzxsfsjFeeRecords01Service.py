# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsLwzxsfsjFeeRecords01Service.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

__all__ = ["IOdsLwzxsfsjFeeRecords01Service"]


class IOdsLwzxsfsjFeeRecords01Service(IService[OdsLwzxsfsjFeeRecords01], ABC):
    """基础-收费流水Service接口

    【Java→Python】
    1) `public interface IOdsLwzxsfsjFeeRecords01Service extends IService<OdsLwzxsfsjFeeRecords01>`
       → `class IOdsLwzxsfsjFeeRecords01Service(IService[OdsLwzxsfsjFeeRecords01], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsLwzxsfsjFeeRecords01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水

        :param bigId: 基础-收费流水ID
        :return: 基础-收费流水

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeRecords01List(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水列表

        :param odsLwzxsfsjFeeRecords01: 基础-收费流水
        :return: 基础-收费流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeRecords01ByQueryUuids(self, uuids: str, applyTime1: str, applyTime2: str) -> dict[str, OdsLwzxsfsjFeeRecords01]:
        """selectOdsLwzxsfsjFeeRecords01ByQueryUuids

        :param uuids: String
        :param applyTime1: String
        :param applyTime2: String
        :return: dict[str, OdsLwzxsfsjFeeRecords01]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectGantryNum(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> int:
        """查询门架数量

        :param odsLwzxsfsjFeeRecords01: 基础-收费流水
        :return: 基础-收费流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeRecords01ListNew(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """selectOdsLwzxsfsjFeeRecords01ListNew

        :param odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01
        :return: list[OdsLwzxsfsjFeeRecords01]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
