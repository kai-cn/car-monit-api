# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.IOdsYhglVBaseOrgService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/IOdsYhglVBaseOrgService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from com.baomidou.mybatisplus.extension.service.IService import IService
from com.ruoyi.base.domain.OdsYhglVBaseOrg import OdsYhglVBaseOrg

__all__ = ["IOdsYhglVBaseOrgService"]


class IOdsYhglVBaseOrgService(IService[OdsYhglVBaseOrg], ABC):
    """机构信息Service接口

    【Java→Python】
    1) `public interface IOdsYhglVBaseOrgService extends IService<OdsYhglVBaseOrg>`
       → `class IOdsYhglVBaseOrgService(IService[OdsYhglVBaseOrg], ABC)`：用 abc.ABC + @abstractmethod 还原 Java interface
       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。
    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；
       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。
    """

    @abstractmethod
    def selectOdsYhglVBaseOrgById(self, bigId: str) -> Optional[OdsYhglVBaseOrg]:
        """查询机构信息

        :param bigId: 机构信息ID
        :return: 机构信息

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """

    @abstractmethod
    def selectOdsYhglVBaseOrgList(self, odsYhglVBaseOrg: OdsYhglVBaseOrg) -> list[OdsYhglVBaseOrg]:
        """查询机构信息列表

        :param odsYhglVBaseOrg: 机构信息
        :return: 机构信息集合

        【Java→Python】抽象方法：实现见对应 *ServiceImpl。
        """
