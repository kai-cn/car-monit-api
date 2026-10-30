# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IZdataTrailTracksService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IZdataTrailTracksService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks

__all__ = ["IZdataTrailTracksService"]


class IZdataTrailTracksService(IService[ZdataTrailTracks], ABC):
    """轨迹数据Service接口

    【Java→Python】
    1) `public interface IZdataTrailTracksService extends IService<ZdataTrailTracks>`
       → `class IZdataTrailTracksService(IService[ZdataTrailTracks], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectZdataTrailTracksById(self, uuid: str) -> Optional[ZdataTrailTracks]:
        """查询轨迹数据

        :param uuid: 轨迹数据ID
        :return: 轨迹数据

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectZdataTrailTracksList(self, zdataTrailTracks: ZdataTrailTracks) -> list[ZdataTrailTracks]:
        """查询轨迹数据列表

        :param zdataTrailTracks: 轨迹数据
        :return: 轨迹数据集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getLatestTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩

        :param carParaVO: CarParaVO
        :return: list[ZdataTrailTracks]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getHistoryTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """查询车俩历史记录

        :param carParaVO: CarParaVO
        :return: list[ZdataTrailTracks]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getUnFitting(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩：不在轨迹点

        :param carParaVO: CarParaVO
        :return: list[ZdataTrailTracks]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getLatestTrailByCursor(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """使用游标分页查询轨迹数据（高性能版本）

        <p>
        相比offset分页，游标分页的优势：
        1. 避免大offset导致的全表扫描
        2. 性能更稳定，不受数据量影响
        3. 适合大数据量场景的分批处理
        </p>

        :param carParaVO: 包含 lastId（游标）、pageSize、applyTime1、applyTime2 等参数
        :return: 轨迹数据列表

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
