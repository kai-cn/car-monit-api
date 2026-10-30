# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsSzdnTollStationIpService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsSzdnTollStationIpService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp

__all__ = ["IOdsSzdnTollStationIpService"]


class IOdsSzdnTollStationIpService(IService[OdsSzdnTollStationIp], ABC):
    """收费站ipService接口

    【Java→Python】
    1) `public interface IOdsSzdnTollStationIpService extends IService<OdsSzdnTollStationIp>`
       → `class IOdsSzdnTollStationIpService(IService[OdsSzdnTollStationIp], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsSzdnTollStationIpById(self, id: int) -> Optional[OdsSzdnTollStationIp]:
        """查询收费站ip

        :param id: 收费站ipID
        :return: 收费站ip

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsSzdnTollStationIpList(self, odsSzdnTollStationIp: OdsSzdnTollStationIp) -> list[OdsSzdnTollStationIp]:
        """查询收费站ip列表

        :param odsSzdnTollStationIp: 收费站ip
        :return: 收费站ip集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def updateRedis(self) -> list[OdsSzdnTollStationIp]:
        """跟新redis

        :return: list[OdsSzdnTollStationIp]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def getRedisList(self) -> list[OdsSzdnTollStationIp]:
        """从缓存拿到carlist

        :return: list[OdsSzdnTollStationIp]

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectStationIpMap(self) -> dict[str, OdsSzdnTollStationIp]:
        """查询收费站ip列表

        :return: 收费站ip集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
