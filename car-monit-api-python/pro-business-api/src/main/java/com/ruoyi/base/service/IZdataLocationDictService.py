# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IZdataLocationDictService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IZdataLocationDictService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict

__all__ = ["IZdataLocationDictService"]


class IZdataLocationDictService(IService[ZdataLocationDict], ABC):
    """车辆位置Service接口

    【Java→Python】
    1) `public interface IZdataLocationDictService extends IService<ZdataLocationDict>`
       → `class IZdataLocationDictService(IService[ZdataLocationDict], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectZdataLocationDictById(self, id: int) -> Optional[ZdataLocationDict]:
        """查询车辆位置

        :param id: 车辆位置ID
        :return: 车辆位置

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectZdataLocationDictList(self, zdataLocationDict: ZdataLocationDict) -> list[ZdataLocationDict]:
        """查询车辆位置列表

        :param zdataLocationDict: 车辆位置
        :return: 车辆位置集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[ZdataLocationDict]:
        """跟新redis

        :return: list[ZdataLocationDict]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getRedisList(self) -> dict[str, ZdataLocationDict]:
        """从缓存拿到carlist

        :return: dict[str, ZdataLocationDict]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
