# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsLwzxsfsjFeeGantryFusion01Service

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsLwzxsfsjFeeGantryFusion01Service.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01 import OdsLwzxsfsjFeeGantryFusion01

__all__ = ["IOdsLwzxsfsjFeeGantryFusion01Service"]


class IOdsLwzxsfsjFeeGantryFusion01Service(IService[OdsLwzxsfsjFeeGantryFusion01], ABC):
    """交易流水Service接口

    【Java→Python】
    1) `public interface IOdsLwzxsfsjFeeGantryFusion01Service extends IService<OdsLwzxsfsjFeeGantryFusion01>`
       → `class IOdsLwzxsfsjFeeGantryFusion01Service(IService[OdsLwzxsfsjFeeGantryFusion01], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsLwzxsfsjFeeGantryFusion01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeGantryFusion01]:
        """查询交易流水

        :param bigId: 交易流水ID
        :return: 交易流水

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsLwzxsfsjFeeGantryFusion01List(self, odsLwzxsfsjFeeGantryFusion01: OdsLwzxsfsjFeeGantryFusion01) -> list[OdsLwzxsfsjFeeGantryFusion01]:
        """查询交易流水列表

        :param odsLwzxsfsjFeeGantryFusion01: 交易流水
        :return: 交易流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
