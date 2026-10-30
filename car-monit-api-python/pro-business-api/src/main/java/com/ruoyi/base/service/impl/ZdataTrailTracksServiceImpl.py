# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.ZdataTrailTracksServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/ZdataTrailTracksServiceImpl.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.mapper.ZdataTrailTracksMapper import ZdataTrailTracksMapper
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService

__all__ = ["ZdataTrailTracksServiceImpl"]


class ZdataTrailTracksServiceImpl(ServiceImpl[ZdataTrailTracksMapper, ZdataTrailTracks], IZdataTrailTracksService):
    """轨迹数据Service业务层处理

    【Java→Python】
    1) 本类**只有纯委托**，没有任何 @Autowired 的 Redis 或其他 Service，
       因此除 Mapper 外不需要额外依赖注入。
    2) 「最新轨迹 / 历史轨迹 / 未拟合 / 游标分页」四个查询全部把 `CarParaVO` 原样透传给 Mapper，
       具体 SQL 语义（含 LIMIT/OFFSET 与 keyset 游标）在 Mapper 侧实现。
    """

    def __init__(self, zdataTrailTracksMapper: Optional[ZdataTrailTracksMapper] = None) -> None:
        self.zdataTrailTracksMapper = zdataTrailTracksMapper or ZdataTrailTracksMapper()
        super().__init__(self.zdataTrailTracksMapper)

    def selectZdataTrailTracksById(self, uuid: str) -> Optional[ZdataTrailTracks]:
        """查询轨迹数据

        :param uuid: 轨迹数据ID
        :return: 轨迹数据

        【Java→Python】主键 `uuid` 为 String。
        """
        return self.zdataTrailTracksMapper.selectZdataTrailTracksById(uuid)

    def selectZdataTrailTracksList(self, zdataTrailTracks: ZdataTrailTracks) -> list[ZdataTrailTracks]:
        """查询轨迹数据列表

        :param zdataTrailTracks: 轨迹数据
        :return: 轨迹数据
        """
        return self.zdataTrailTracksMapper.selectZdataTrailTracksList(zdataTrailTracks)

    def getLatestTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩（原注释如此，含错别字“车俩”，保留）

        :param carParaVO: 查询参数
        :return: 轨迹数据集合
        """
        return self.zdataTrailTracksMapper.getLatestTrail(carParaVO)

    def getHistoryTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """轨迹查询（Java 的 Javadoc 只有这一句，没有 @param/@return，原样保留）"""
        return self.zdataTrailTracksMapper.getHistoryTrail(carParaVO)

    def getUnFitting(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩：不在轨迹点

        :param carParaVO: 查询参数
        :return: 轨迹数据集合
        """
        return self.zdataTrailTracksMapper.getUnFitting(carParaVO)

    def getLatestTrailByCursor(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """使用游标分页查询轨迹数据（高性能版本）

        【Java→Python】Java 的 Javadoc 只有标题句、无 @param/@return（原样保留）；
        游标逻辑（lastExitTime + pageSize 的 keyset 分页）在 Mapper 内实现。
        """
        return self.zdataTrailTracksMapper.getLatestTrailByCursor(carParaVO)
