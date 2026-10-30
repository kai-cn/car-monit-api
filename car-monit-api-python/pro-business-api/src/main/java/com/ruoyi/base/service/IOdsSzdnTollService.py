# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnTollService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnTollService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll

__all__ = ["IOdsSzdnTollService"]


class IOdsSzdnTollService(IService[OdsSzdnToll], ABC):
    """收费站基础信息Service接口

    【Java→Python】
    1) `public interface IOdsSzdnTollService extends IService<OdsSzdnToll>`
       → `class IOdsSzdnTollService(IService[OdsSzdnToll], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnTollById(self, id: str) -> Optional[OdsSzdnToll]:
        """查询收费站基础信息

        :param id: 收费站基础信息ID
        :return: 收费站基础信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnTollList(self, odsSzdnToll: OdsSzdnToll) -> list[OdsSzdnToll]:
        """查询收费站基础信息列表

        :param odsSzdnToll: 收费站基础信息
        :return: 收费站基础信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnTollMap(self, odsSzdnToll: OdsSzdnToll) -> dict[str, OdsSzdnToll]:
        """查询收费站基础信息列表

        :param odsSzdnToll: 收费站基础信息
        :return: 收费站基础信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[OdsSzdnToll]:
        """跟新redis

        :return: list[OdsSzdnToll]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getRedisMap(self) -> dict[str, OdsSzdnToll]:
        """从缓存拿到carlist

        :return: dict[str, OdsSzdnToll]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
