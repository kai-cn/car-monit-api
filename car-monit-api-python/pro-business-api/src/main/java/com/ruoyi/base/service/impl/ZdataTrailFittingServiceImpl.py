# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.ZdataTrailFittingServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/ZdataTrailFittingServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from com.ruoyi.base.service.IZdataTrailFittingService import IZdataTrailFittingService

__all__ = ["ZdataTrailFittingServiceImpl"]


class ZdataTrailFittingServiceImpl(ServiceImpl[ZdataTrailFittingMapper, ZdataTrailFitting], IZdataTrailFittingService):
    """车辆出入口拟合轨迹Service业务层处理

    【Java→Python】
    1) Java 的 import 顺序（先 common 后 base）与 Python 的字母序不同；
       Python 侧统一按 `com.baomidou` → `com.ruoyi.base.domain` → `mapper` → `service` 排序。
    2) 主键为 `cid`（字符串），因此 `selectZdataTrailFittingById(String cid)`
       直接透传给 Mapper 的 `selectById`。
    3) 纯委托实现，无额外逻辑。
    """

    def __init__(self, zdataTrailFittingMapper: Optional[ZdataTrailFittingMapper] = None) -> None:
        self.zdataTrailFittingMapper = zdataTrailFittingMapper or ZdataTrailFittingMapper()
        super().__init__(self.zdataTrailFittingMapper)

    def selectZdataTrailFittingById(self, cid: str) -> Optional[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹

        :param cid: 车辆出入口拟合轨迹ID
        :return: 车辆出入口拟合轨迹

        【Java→Python】委托 Mapper；返回 None 对应 Java 的 null。
        """
        return self.zdataTrailFittingMapper.selectZdataTrailFittingById(cid)

    def selectZdataTrailFittingList(self, zdataTrailFitting: ZdataTrailFitting) -> list[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹列表

        :param zdataTrailFitting: 车辆出入口拟合轨迹
        :return: 车辆出入口拟合轨迹

        【Java→Python】`List<T>` → `list[T]`。
        """
        return self.zdataTrailFittingMapper.selectZdataTrailFittingList(zdataTrailFitting)
