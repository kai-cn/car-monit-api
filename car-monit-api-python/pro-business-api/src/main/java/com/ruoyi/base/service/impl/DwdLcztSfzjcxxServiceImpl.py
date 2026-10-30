# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DwdLcztSfzjcxxServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DwdLcztSfzjcxxServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.DwdLcztSfzjcxx import DwdLcztSfzjcxx
from com.ruoyi.base.mapper.DwdLcztSfzjcxxMapper import DwdLcztSfzjcxxMapper
from com.ruoyi.base.service.IDwdLcztSfzjcxxService import IDwdLcztSfzjcxxService

__all__ = ["DwdLcztSfzjcxxServiceImpl"]


class DwdLcztSfzjcxxServiceImpl(ServiceImpl[DwdLcztSfzjcxxMapper, DwdLcztSfzjcxx], IDwdLcztSfzjcxxService):
    """收费站基础信息Service业务层处理

    【Java→Python】
    1) `@Service` + `@Autowired` → 构造器注入（Spring DI 的 Python 等价写法）。
    2) `extends ServiceImpl<Mapper, Entity> implements IXxxService` → 双基类：
       `ServiceImpl[DwdLcztSfzjcxxMapper, DwdLcztSfzjcxx]` 提供通用 CRUD，
       `IDwdLcztSfzjcxxService` 提供抽象契约。
    3) 两个查询方法都是单行委托给 Mapper，与 Java 完全一致，无额外逻辑。
    """

    def __init__(self, dwdLcztSfzjcxxMapper: Optional[DwdLcztSfzjcxxMapper] = None) -> None:
        self.dwdLcztSfzjcxxMapper = dwdLcztSfzjcxxMapper or DwdLcztSfzjcxxMapper()
        super().__init__(self.dwdLcztSfzjcxxMapper)

    def selectDwdLcztSfzjcxxById(self, agentPk: str) -> Optional[DwdLcztSfzjcxx]:
        """查询收费站基础信息

        :param agentPk: 收费站基础信息ID
        :return: 收费站基础信息

        【Java→Python】委托 Mapper；返回 None 对应 Java 的 null。
        """
        return self.dwdLcztSfzjcxxMapper.selectDwdLcztSfzjcxxById(agentPk)

    def selectDwdLcztSfzjcxxList(self, dwdLcztSfzjcxx: DwdLcztSfzjcxx) -> list[DwdLcztSfzjcxx]:
        """查询收费站基础信息列表

        :param dwdLcztSfzjcxx: 收费站基础信息
        :return: 收费站基础信息

        【Java→Python】`List<T>` → `list[T]`。
        """
        return self.dwdLcztSfzjcxxMapper.selectDwdLcztSfzjcxxList(dwdLcztSfzjcxx)
