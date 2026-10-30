# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IDwdLcztSfsjcxxService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IDwdLcztSfsjcxxService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.DwdLcztSfsjcxx import DwdLcztSfsjcxx

__all__ = ["IDwdLcztSfsjcxxService"]


class IDwdLcztSfsjcxxService(IService[DwdLcztSfsjcxx], ABC):
    """收费所基础信息Service接口

    【Java→Python】
    1) `public interface IDwdLcztSfsjcxxService extends IService<DwdLcztSfsjcxx>`
       → `class IDwdLcztSfsjcxxService(IService[DwdLcztSfsjcxx], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectDwdLcztSfsjcxxById(self, agentPk: str) -> Optional[DwdLcztSfsjcxx]:
        """查询收费所基础信息

        :param agentPk: 收费所基础信息ID
        :return: 收费所基础信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectDwdLcztSfsjcxxList(self, dwdLcztSfsjcxx: DwdLcztSfsjcxx) -> list[DwdLcztSfsjcxx]:
        """查询收费所基础信息列表

        :param dwdLcztSfsjcxx: 收费所基础信息
        :return: 收费所基础信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
