# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IZdataTrailFittingService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IZdataTrailFittingService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting

__all__ = ["IZdataTrailFittingService"]


class IZdataTrailFittingService(IService[ZdataTrailFitting], ABC):
    """车辆出入口拟合轨迹Service接口

    【Java→Python】
    1) `public interface IZdataTrailFittingService extends IService<ZdataTrailFitting>`
       → `class IZdataTrailFittingService(IService[ZdataTrailFitting], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectZdataTrailFittingById(self, cid: str) -> Optional[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹

        :param cid: 车辆出入口拟合轨迹ID
        :return: 车辆出入口拟合轨迹

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectZdataTrailFittingList(self, zdataTrailFitting: ZdataTrailFitting) -> list[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹列表

        :param zdataTrailFitting: 车辆出入口拟合轨迹
        :return: 车辆出入口拟合轨迹集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
