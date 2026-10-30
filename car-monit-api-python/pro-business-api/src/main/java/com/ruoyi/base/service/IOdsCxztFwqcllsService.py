# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsCxztFwqcllsService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsCxztFwqcllsService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsCxztFwqclls import OdsCxztFwqclls

__all__ = ["IOdsCxztFwqcllsService"]


class IOdsCxztFwqcllsService(IService[OdsCxztFwqclls], ABC):
    """服务区车辆流水Service接口

    【Java→Python】
    1) `public interface IOdsCxztFwqcllsService extends IService<OdsCxztFwqclls>`
       → `class IOdsCxztFwqcllsService(IService[OdsCxztFwqclls], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsCxztFwqcllsById(self, bigId: int) -> Optional[OdsCxztFwqclls]:
        """查询服务区车辆流水

        :param bigId: 服务区车辆流水ID
        :return: 服务区车辆流水

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsCxztFwqcllsList(self, odsCxztFwqclls: OdsCxztFwqclls) -> list[OdsCxztFwqclls]:
        """查询服务区车辆流水列表

        :param odsCxztFwqclls: 服务区车辆流水
        :return: 服务区车辆流水集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsCxztFwqcllsByQueryUuids(self, provCaptureUUids: str) -> dict[str, OdsCxztFwqclls]:
        """selectOdsCxztFwqcllsByQueryUuids

        :param provCaptureUUids: String
        :return: dict[str, OdsCxztFwqclls]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
