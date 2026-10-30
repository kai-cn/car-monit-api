# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsLwzxsfsjFeeGantryFusion01ServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeGantryFusion01ServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsLwzxsfsjFeeGantryFusion01 import OdsLwzxsfsjFeeGantryFusion01
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeGantryFusion01Mapper import OdsLwzxsfsjFeeGantryFusion01Mapper
from com.ruoyi.base.service.IOdsLwzxsfsjFeeGantryFusion01Service import IOdsLwzxsfsjFeeGantryFusion01Service

__all__ = ["OdsLwzxsfsjFeeGantryFusion01ServiceImpl"]


class OdsLwzxsfsjFeeGantryFusion01ServiceImpl(ServiceImpl[OdsLwzxsfsjFeeGantryFusion01Mapper, OdsLwzxsfsjFeeGantryFusion01], IOdsLwzxsfsjFeeGantryFusion01Service):
    """交易流水Service业务层处理

    【Java→Python】
    1) 类名较长（表名+`ServiceImpl`），Python 无长度限制，保持与 Java 完全一致。
    2) `@Service` → 构造器注入 + SpringUtils 注册；`@Autowired` → `__init__` 参数。
    3) 本实现只有两个纯委托方法，因此**没有** `@Transactional` 的必要；
       Java 源码 import 了 `Transactional` 但未使用（生成器残留）。
    """

    def __init__(self, odsLwzxsfsjFeeGantryFusion01Mapper: Optional[OdsLwzxsfsjFeeGantryFusion01Mapper] = None) -> None:
        self.odsLwzxsfsjFeeGantryFusion01Mapper = odsLwzxsfsjFeeGantryFusion01Mapper or OdsLwzxsfsjFeeGantryFusion01Mapper()
        super().__init__(self.odsLwzxsfsjFeeGantryFusion01Mapper)

    def selectOdsLwzxsfsjFeeGantryFusion01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeGantryFusion01]:
        """查询交易流水

        :param bigId: 交易流水ID
        :return: 交易流水

        【Java→Python】委托 Mapper；返回 None 对应 Java 的 null。
        """
        return self.odsLwzxsfsjFeeGantryFusion01Mapper.selectOdsLwzxsfsjFeeGantryFusion01ById(bigId)

    def selectOdsLwzxsfsjFeeGantryFusion01List(self, odsLwzxsfsjFeeGantryFusion01: OdsLwzxsfsjFeeGantryFusion01) -> list[OdsLwzxsfsjFeeGantryFusion01]:
        """查询交易流水列表

        :param odsLwzxsfsjFeeGantryFusion01: 交易流水
        :return: 交易流水

        【Java→Python】`List<T>` → `list[T]`。
        """
        return self.odsLwzxsfsjFeeGantryFusion01Mapper.selectOdsLwzxsfsjFeeGantryFusion01List(odsLwzxsfsjFeeGantryFusion01)
