# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnSectionServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.mapper.OdsSzdnSectionMapper import OdsSzdnSectionMapper
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnSectionServiceImpl"]


class OdsSzdnSectionServiceImpl(ServiceImpl[OdsSzdnSectionMapper, OdsSzdnSection], IOdsSzdnSectionService):
    """路段信息Service业务层处理

    【Java→Python】
    1) 三个方法 `getSectionMap` / `getSectionList` / `updateRedis` 共用同一个缓存 key
       `Constants.SECTION_ROAD_MAP`（整表缓存）。
    2) `getSectionMap` 与 `getSectionList` 的“取缓存/回填”代码在 Java 里是**复制粘贴**的两份，
       Python 侧同样保留两份（不做 DRY 重构），以便逐行对照。
    3) 注意 Javadoc 与实际不符：`getSectionList` 的注释写“获取路段map”，返回的却是 `List` ——
       原样保留。
    """

    def __init__(self,
                 odsSzdnSectionMapper: Optional[OdsSzdnSectionMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnSectionMapper = odsSzdnSectionMapper or OdsSzdnSectionMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnSectionMapper)

    def selectOdsSzdnSectionById(self, id: str) -> Optional[OdsSzdnSection]:
        """查询路段信息

        :param id: 路段信息ID
        :return: 路段信息

        【Java→Python】本表主键是 String（ASSIGN_UUID）而非 Long。
        """
        return self.odsSzdnSectionMapper.selectOdsSzdnSectionById(id)

    def selectOdsSzdnSectionList(self, odsSzdnSection: OdsSzdnSection) -> list[OdsSzdnSection]:
        """查询路段信息列表

        :param odsSzdnSection: 路段信息
        :return: 路段信息
        """
        return self.odsSzdnSectionMapper.selectOdsSzdnSectionList(odsSzdnSection)

    def getSectionMap(self) -> dict[str, OdsSzdnSection]:
        """路段编码 → 路段实体

        【Java→Python】`(List) obj` 裸强转 → 直接赋值；key 用 `isNull(sectionCode)`，
        sectionCode 为 null 的记录会落到 "" 键并互相覆盖（原实现如此）。
        """
        list_: Optional[list[OdsSzdnSection]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.SECTION_ROAD_MAP)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()
        map_: dict[str, OdsSzdnSection] = {}
        for section in list_:
            map_[CommonUtil.isNull(section.section_code)] = section
        return map_

    def getSectionList(self) -> list[OdsSzdnSection]:
        """获取路段map（原注释如此，实际返回列表）

        :return: 路段信息列表
        """
        list_: Optional[list[OdsSzdnSection]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.SECTION_ROAD_MAP)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()
        return list_

    def updateRedis(self) -> list[OdsSzdnSection]:
        """刷新路段缓存（Java 侧带 @Override，即接口声明的方法，非私有辅助方法）"""
        sectionList = self.odsSzdnSectionMapper.selectOdsSzdnSectionList(OdsSzdnSection())
        self.redisCache.setCacheObject(Constants.SECTION_ROAD_MAP, sectionList)
        return sectionList
