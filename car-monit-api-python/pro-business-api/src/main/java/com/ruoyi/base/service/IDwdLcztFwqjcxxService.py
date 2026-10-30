# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IDwdLcztFwqjcxxService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IDwdLcztFwqjcxxService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.DwdLcztFwqjcxx import DwdLcztFwqjcxx

__all__ = ["IDwdLcztFwqjcxxService"]


class IDwdLcztFwqjcxxService(IService[DwdLcztFwqjcxx], ABC):
    """服务区基础信息Service接口

    【Java→Python】
    1) `public interface IDwdLcztFwqjcxxService extends IService<DwdLcztFwqjcxx>`
       → `class IDwdLcztFwqjcxxService(IService[DwdLcztFwqjcxx], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectDwdLcztFwqjcxxById(self, agentPk: str) -> Optional[DwdLcztFwqjcxx]:
        """查询服务区基础信息

        :param agentPk: 服务区基础信息ID
        :return: 服务区基础信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectDwdLcztFwqjcxxList(self, dwdLcztFwqjcxx: DwdLcztFwqjcxx) -> list[DwdLcztFwqjcxx]:
        """查询服务区基础信息列表

        :param dwdLcztFwqjcxx: 服务区基础信息
        :return: 服务区基础信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[DwdLcztFwqjcxx]:
        """跟新redis

        :return: list[DwdLcztFwqjcxx]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getServiceNameMap(self) -> dict[str, DwdLcztFwqjcxx]:
        """getServiceNameMap

        :return: dict[str, DwdLcztFwqjcxx]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
