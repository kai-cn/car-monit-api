# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnSectionService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnSectionService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection

__all__ = ["IOdsSzdnSectionService"]


class IOdsSzdnSectionService(IService[OdsSzdnSection], ABC):
    """路段信息Service接口

    【Java→Python】
    1) `public interface IOdsSzdnSectionService extends IService<OdsSzdnSection>`
       → `class IOdsSzdnSectionService(IService[OdsSzdnSection], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnSectionById(self, id: str) -> Optional[OdsSzdnSection]:
        """查询路段信息

        :param id: 路段信息ID
        :return: 路段信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnSectionList(self, odsSzdnSection: OdsSzdnSection) -> list[OdsSzdnSection]:
        """查询路段信息列表

        :param odsSzdnSection: 路段信息
        :return: 路段信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getSectionMap(self) -> dict[str, OdsSzdnSection]:
        """获取路段map

        :return: dict[str, OdsSzdnSection]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getSectionList(self) -> list[OdsSzdnSection]:
        """获取路段map

        :return: list[OdsSzdnSection]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[OdsSzdnSection]:
        """跟新路段信息

        :return: list[OdsSzdnSection]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
