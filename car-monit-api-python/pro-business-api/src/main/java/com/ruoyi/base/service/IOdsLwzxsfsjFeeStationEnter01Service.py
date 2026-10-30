# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsLwzxsfsjFeeStationEnter01Service.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01

__all__ = ["IOdsLwzxsfsjFeeStationEnter01Service"]


class IOdsLwzxsfsjFeeStationEnter01Service(IService[OdsLwzxsfsjFeeStationEnter01], ABC):
    """收费站入口数据Service接口

    【Java→Python】
    1) `public interface IOdsLwzxsfsjFeeStationEnter01Service extends IService<OdsLwzxsfsjFeeStationEnter01>`
       → `class IOdsLwzxsfsjFeeStationEnter01Service(IService[OdsLwzxsfsjFeeStationEnter01], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationEnter01ById(self, bigId: int) -> Optional[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据

        :param bigId: 收费站入口数据ID
        :return: 收费站入口数据

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationEnter01List(self, odsLwzxsfsjFeeStationEnter01: OdsLwzxsfsjFeeStationEnter01) -> list[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据列表

        :param odsLwzxsfsjFeeStationEnter01: 收费站入口数据
        :return: 收费站入口数据集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(self, feeStationEnterUUids: str) -> dict[str, OdsLwzxsfsjFeeStationEnter01]:
        """selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids

        :param feeStationEnterUUids: String
        :return: dict[str, OdsLwzxsfsjFeeStationEnter01]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
