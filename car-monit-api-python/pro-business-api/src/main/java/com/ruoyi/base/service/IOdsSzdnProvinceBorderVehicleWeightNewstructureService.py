# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnProvinceBorderVehicleWeightNewstructureService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import OdsSzdnProvinceBorderVehicleWeightNewstructure

__all__ = ["IOdsSzdnProvinceBorderVehicleWeightNewstructureService"]


class IOdsSzdnProvinceBorderVehicleWeightNewstructureService(IService[OdsSzdnProvinceBorderVehicleWeightNewstructure], ABC):
    """省界称重Service接口

    【Java→Python】
    1) `public interface IOdsSzdnProvinceBorderVehicleWeightNewstructureService extends IService<OdsSzdnProvinceBorderVehicleWeightNewstructure>`
       → `class IOdsSzdnProvinceBorderVehicleWeightNewstructureService(IService[OdsSzdnProvinceBorderVehicleWeightNewstructure], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(self, dataSource: str) -> Optional[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重

        :param dataSource: 省界称重ID
        :return: 省界称重

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(self, odsSzdnProvinceBorderVehicleWeightNewstructure: OdsSzdnProvinceBorderVehicleWeightNewstructure) -> list[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重列表

        :param odsSzdnProvinceBorderVehicleWeightNewstructure: 省界称重
        :return: 省界称重集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(self, queryUuids: str) -> dict[str, OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重 : 通过IDS查询

        :param queryUuids: String
        :return: 省界称重

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
