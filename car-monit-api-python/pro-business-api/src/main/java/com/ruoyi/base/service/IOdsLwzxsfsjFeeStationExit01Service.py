# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsLwzxsfsjFeeStationExit01Service.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01

__all__ = ["IOdsLwzxsfsjFeeStationExit01Service"]


class IOdsLwzxsfsjFeeStationExit01Service(IService[OdsLwzxsfsjFeeStationExit01], ABC):
    """收费站出口流水Service接口

    【Java→Python】
    1) `public interface IOdsLwzxsfsjFeeStationExit01Service extends IService<OdsLwzxsfsjFeeStationExit01>`
       → `class IOdsLwzxsfsjFeeStationExit01Service(IService[OdsLwzxsfsjFeeStationExit01], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationExit01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeStationExit01]:
        """查询收费站出口流水

        :param bigId: 收费站出口流水ID
        :return: 收费站出口流水

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationExit01List(self, odsLwzxsfsjFeeStationExit01: OdsLwzxsfsjFeeStationExit01) -> list[OdsLwzxsfsjFeeStationExit01]:
        """查询收费站出口流水列表

        :param odsLwzxsfsjFeeStationExit01: 收费站出口流水
        :return: 收费站出口流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(self, feeStationExitUUids: str) -> dict[str, OdsLwzxsfsjFeeStationExit01]:
        """selectOdsLwzxsfsjFeeStationExit01ByQueryUuids

        :param feeStationExitUUids: String
        :return: dict[str, OdsLwzxsfsjFeeStationExit01]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
