# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsYhglVBaseOrgServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsYhglVBaseOrgServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsYhglVBaseOrg import OdsYhglVBaseOrg
from com.ruoyi.base.mapper.OdsYhglVBaseOrgMapper import OdsYhglVBaseOrgMapper
from com.ruoyi.base.service.IOdsYhglVBaseOrgService import IOdsYhglVBaseOrgService

__all__ = ["OdsYhglVBaseOrgServiceImpl"]


class OdsYhglVBaseOrgServiceImpl(ServiceImpl[OdsYhglVBaseOrgMapper, OdsYhglVBaseOrg], IOdsYhglVBaseOrgService):
    """机构信息Service业务层处理

    【Java→Python】
    1) `extends ServiceImpl<OdsYhglVBaseOrgMapper, OdsYhglVBaseOrg> implements IOdsYhglVBaseOrgService`
       → 双基类写法，泛型参数顺序与 Java 一致（Mapper 在前、实体在后）。
    2) `@Service` → 构造器注入；`@Autowired` → 可选参数 `mapper=None`。
    3) 纯委托实现，无状态、无事务，天然线程安全（与 Java 单例 Bean 行为一致）。
    """

    def __init__(self, odsYhglVBaseOrgMapper: Optional[OdsYhglVBaseOrgMapper] = None) -> None:
        self.odsYhglVBaseOrgMapper = odsYhglVBaseOrgMapper or OdsYhglVBaseOrgMapper()
        super().__init__(self.odsYhglVBaseOrgMapper)

    def selectOdsYhglVBaseOrgById(self, bigId: str) -> Optional[OdsYhglVBaseOrg]:
        """查询机构信息

        :param bigId: 机构信息ID
        :return: 机构信息

        【Java→Python】委托 Mapper；返回 None 对应 Java 的 null。
        """
        return self.odsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgById(bigId)

    def selectOdsYhglVBaseOrgList(self, odsYhglVBaseOrg: OdsYhglVBaseOrg) -> list[OdsYhglVBaseOrg]:
        """查询机构信息列表

        :param odsYhglVBaseOrg: 机构信息
        :return: 机构信息

        【Java→Python】`List<T>` → `list[T]`。
        """
        return self.odsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgList(odsYhglVBaseOrg)
