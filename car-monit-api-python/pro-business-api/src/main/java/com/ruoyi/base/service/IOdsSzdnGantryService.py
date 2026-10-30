# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnGantryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnGantryService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

__all__ = ["IOdsSzdnGantryService"]


class IOdsSzdnGantryService(IService[OdsSzdnGantry], ABC):
    """门架信息Service接口

    【Java→Python】
    1) `public interface IOdsSzdnGantryService extends IService<OdsSzdnGantry>`
       → `class IOdsSzdnGantryService(IService[OdsSzdnGantry], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnGantryById(self, id: str) -> Optional[OdsSzdnGantry]:
        """查询门架信息

        :param id: 门架信息ID
        :return: 门架信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnGantryList(self, odsSzdnGantry: OdsSzdnGantry) -> list[OdsSzdnGantry]:
        """查询门架信息列表

        :param odsSzdnGantry: 门架信息
        :return: 门架信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnGantryMap(self, odsSzdnGantry: OdsSzdnGantry) -> dict[str, OdsSzdnGantry]:
        """查询门架信息列表

        :param odsSzdnGantry: 门架信息
        :return: 门架信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def saveGantryRedis(self) -> list[OdsSzdnGantry]:
        """查询门架信息列表

        :return: 门架信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getGantryRedis(self) -> list[OdsSzdnGantry]:
        """查询门架信息列表

        :return: 门架信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
