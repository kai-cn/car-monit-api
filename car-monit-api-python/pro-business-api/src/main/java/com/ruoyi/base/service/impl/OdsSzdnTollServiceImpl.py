# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnTollServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll
from com.ruoyi.base.mapper.OdsSzdnTollMapper import OdsSzdnTollMapper
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnTollServiceImpl"]


class OdsSzdnTollServiceImpl(ServiceImpl[OdsSzdnTollMapper, OdsSzdnToll], IOdsSzdnTollService):
    """收费站基础信息Service业务层处理

    【Java→Python】
    1) 一个收费站会向 map 写**两个** key：`tollCode`（注释写“大脑编码”，原文如此）与
       `stateCodeMerge`（国网编码），两次 put 指向同一个实体。
    2) `selectOdsSzdnTollMap` 直接查库；`getRedisMap` 走 `Constants.station_info` 全量缓存。
       两者 map 构建逻辑重复（Java 原样复制），Python 也保持两份。
    """

    def __init__(self,
                 odsSzdnTollMapper: Optional[OdsSzdnTollMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnTollMapper = odsSzdnTollMapper or OdsSzdnTollMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnTollMapper)

    def selectOdsSzdnTollById(self, id: str) -> Optional[OdsSzdnToll]:
        """查询收费站基础信息

        :param id: 收费站基础信息ID
        :return: 收费站基础信息

        【Java→Python】主键 `id` 为 String（ASSIGN_UUID）。
        """
        return self.odsSzdnTollMapper.selectOdsSzdnTollById(id)

    def selectOdsSzdnTollList(self, odsSzdnToll: OdsSzdnToll) -> list[OdsSzdnToll]:
        """查询收费站基础信息列表

        :param odsSzdnToll: 收费站基础信息
        :return: 收费站基础信息
        """
        return self.odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll)

    def selectOdsSzdnTollMap(self, odsSzdnToll: OdsSzdnToll) -> dict[str, OdsSzdnToll]:
        """查询收费站基础信息列表（实际返回：编号 → 实体 的字典）

        :param odsSzdnToll: 收费站基础信息（查询条件）
        :return: 编码 → 收费站实体（同时含 tollCode 与 stateCodeMerge 两种键）

        【Java→Python】`new HashMap<String, OdsSzdnToll>()` 的显式泛型 → `dict[str, OdsSzdnToll]`；
        key 统一经 `isNull` 处理（null → ""），因此两种编码都有可能是 ""，互相覆盖。
        """
        map_: dict[str, OdsSzdnToll] = {}
        list_ = self.odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll)
        for rtn in list_:
            # 大脑编码（原文如此，应为“大网编码”）
            map_[CommonUtil.isNull(rtn.toll_code)] = rtn
            # 国网编码
            map_[CommonUtil.isNull(rtn.state_code_merge)] = rtn
        return map_

    def updateRedis(self) -> list[OdsSzdnToll]:
        """跟新redis（原注释即为此，含错别字，保留）

        【Java→Python】`new OdsSzdnToll()` = 无条件全表查询，结果整体写入 `Constants.station_info`。
        """
        odsSzdnToll = OdsSzdnToll()
        list_ = self.odsSzdnTollMapper.selectOdsSzdnTollList(odsSzdnToll)
        self.redisCache.setCacheObject(Constants.station_info, list_)
        return list_

    def getRedisMap(self) -> dict[str, OdsSzdnToll]:
        """从缓存拿到carlist（原注释如此，实际是收费站字典）

        【Java→Python】`(List) obj` 裸强转 → 直接赋值；key 规则与 `selectOdsSzdnTollMap` 相同。
        """
        list_: Optional[list[OdsSzdnToll]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.station_info)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()

        map_: dict[str, OdsSzdnToll] = {}
        for rtn in list_:
            # 大脑编码（原文如此）
            map_[CommonUtil.isNull(rtn.toll_code)] = rtn
            # 国网编码
            map_[CommonUtil.isNull(rtn.state_code_merge)] = rtn
        return map_
