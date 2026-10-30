# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnGantryIpService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnGantryIpService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp

__all__ = ["IOdsSzdnGantryIpService"]


class IOdsSzdnGantryIpService(IService[OdsSzdnGantryIp], ABC):
    """省界设备ipService接口

    【Java→Python】
    1) `public interface IOdsSzdnGantryIpService extends IService<OdsSzdnGantryIp>`
       → `class IOdsSzdnGantryIpService(IService[OdsSzdnGantryIp], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnGantryIpById(self, id: int) -> Optional[OdsSzdnGantryIp]:
        """查询省界设备ip

        :param id: 省界设备ipID
        :return: 省界设备ip

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnGantryIpList(self, odsSzdnGantryIp: OdsSzdnGantryIp) -> list[OdsSzdnGantryIp]:
        """查询省界设备ip列表

        :param odsSzdnGantryIp: 省界设备ip
        :return: 省界设备ip集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnGantryIpMap(self) -> dict[str, OdsSzdnGantryIp]:
        """查询省界设备ip列表

        :return: 省界设备ip集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectIPSet(self) -> set[str]:
        """selectIPSet

        :return: 设备 IP 集合

        【Java→Python】Java 签名 `Set<String> selectIPSet()` → `set[str]`；
        Set 语言内建、无重复无序，与 Java HashSet 语义对等。
        抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[OdsSzdnGantryIp]:
        """跟新redis

        :return: list[OdsSzdnGantryIp]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getRedisList(self) -> list[OdsSzdnGantryIp]:
        """从缓存拿到carlist

        :return: list[OdsSzdnGantryIp]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
