# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DwdLcztSfsjcxxServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DwdLcztSfsjcxxServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.DwdLcztSfsjcxx import DwdLcztSfsjcxx
from com.ruoyi.base.mapper.DwdLcztSfsjcxxMapper import DwdLcztSfsjcxxMapper
from com.ruoyi.base.service.IDwdLcztSfsjcxxService import IDwdLcztSfsjcxxService

__all__ = ["DwdLcztSfsjcxxServiceImpl"]


class DwdLcztSfsjcxxServiceImpl(ServiceImpl[DwdLcztSfsjcxxMapper, DwdLcztSfsjcxx], IDwdLcztSfsjcxxService):
    """收费所基础信息Service业务层处理

    【Java→Python】
    1) `@Service` → Python 无注解等价物；实例注册由 SpringUtils 承担（见 config 层），
       使用方式：`svc = DwdLcztSfsjcxxServiceImpl(mapper)`。
    2) `extends ServiceImpl<DwdLcztSfsjcxxMapper, DwdLcztSfsjcxx>` → `ServiceImpl[Mapper, Entity]`；
       `implements IDwdLcztSfsjcxxService` → 第二基类（MRO 先实现类后接口）。
    3) `@Autowired private DwdLcztSfsjcxxMapper dwdLcztSfsjcxxMapper;` → 构造器注入。
       ⚠️ 不传参时会 new 一个**独立空表**的 Mapper；多个 Service 需要共享同一份数据时，
       必须传入同一个 Mapper 实例（Java 中由 Spring 单例保证，Python 需显式传递）。
    4) `@Override` 在 Python 无编译期校验（3.12 可用 typing.override，本工程未强制）。
    5) Java 中 import 了 `AjaxResult`/`CommonUtil`/`@Transactional` 却未使用（代码生成器残留），
       Python 侧不引入无用 import（flake8 会告警）。
    """

    def __init__(self, dwdLcztSfsjcxxMapper: Optional[DwdLcztSfsjcxxMapper] = None) -> None:
        self.dwdLcztSfsjcxxMapper = dwdLcztSfsjcxxMapper or DwdLcztSfsjcxxMapper()
        super().__init__(self.dwdLcztSfsjcxxMapper)

    def selectDwdLcztSfsjcxxById(self, agentPk: str) -> Optional[DwdLcztSfsjcxx]:
        """查询收费所基础信息

        :param agentPk: 收费所基础信息ID
        :return: 收费所基础信息

        【Java→Python】单行委托 `return mapper.selectXxxById(id);` 原样保留，
        返回值可能是 None（Java 的 null）。
        """
        return self.dwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxById(agentPk)

    def selectDwdLcztSfsjcxxList(self, dwdLcztSfsjcxx: DwdLcztSfsjcxx) -> list[DwdLcztSfsjcxx]:
        """查询收费所基础信息列表

        :param dwdLcztSfsjcxx: 收费所基础信息
        :return: 收费所基础信息

        【Java→Python】`List<T>` → `list[T]`，空结果返回 `[]`（Java 也返回空 List 而非 null）。
        """
        return self.dwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxList(dwdLcztSfsjcxx)
