# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnGantryServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.mapper.OdsSzdnGantryMapper import OdsSzdnGantryMapper
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnGantryServiceImpl"]


class OdsSzdnGantryServiceImpl(ServiceImpl[OdsSzdnGantryMapper, OdsSzdnGantry], IOdsSzdnGantryService):
    """门架信息Service业务层处理

    【Java→Python】
    1) `saveGantryRedis()` / `getGantryRedis()` 都受接口约束（Java 侧 `saveGantryRedis` 省写了
       `@Override`），缓存 key 为 `Constants.gantry_list`。
    2) 与 `OdsSzdnSectionServiceImpl` 一样存在“复制粘贴式”的缓存读取代码，不做 DRY 重构，
       以便与原文件逐行对照。
    """

    def __init__(self,
                 odsSzdnGantryMapper: Optional[OdsSzdnGantryMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnGantryMapper = odsSzdnGantryMapper or OdsSzdnGantryMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnGantryMapper)

    def selectOdsSzdnGantryById(self, id: str) -> Optional[OdsSzdnGantry]:
        """查询门架信息

        :param id: 门架信息ID
        :return: 门架信息

        【Java→Python】主键 `id` 为 String（ASSIGN_UUID）。
        """
        return self.odsSzdnGantryMapper.selectOdsSzdnGantryById(id)

    def selectOdsSzdnGantryList(self, odsSzdnGantry: OdsSzdnGantry) -> list[OdsSzdnGantry]:
        """查询门架信息列表

        :param odsSzdnGantry: 门架信息
        :return: 门架信息
        """
        return self.odsSzdnGantryMapper.selectOdsSzdnGantryList(odsSzdnGantry)

    def saveGantryRedis(self) -> list[OdsSzdnGantry]:
        """全量刷入门架缓存

        :return: 门架信息集合

        【Java→Python】`new OdsSzdnGantry()` = 无条件全表查询。
        Java 原文 `return  list;` 里有两个空格，属格式细节，不影响语义。
        """
        list_ = self.odsSzdnGantryMapper.selectOdsSzdnGantryList(OdsSzdnGantry())
        self.redisCache.setCacheObject(Constants.gantry_list, list_)
        return list_

    def getGantryRedis(self) -> list[OdsSzdnGantry]:
        """取门架缓存（未命中则回填）

        :return: 门架信息集合

        【Java→Python】`(List) obj` 裸强转 → 直接赋值。
        """
        list_: Optional[list[OdsSzdnGantry]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.gantry_list)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.saveGantryRedis()
        return list_

    def selectOdsSzdnGantryMap(self, odsSzdnGantry: OdsSzdnGantry) -> dict[str, OdsSzdnGantry]:
        """按条件查询并转成“门架编号 → 门架”字典

        :param odsSzdnGantry: 门架信息（查询条件）
        :return: 门架编号 → 门架实体

        【Java→Python】Java 显式写了 `new HashMap<String, OdsSzdnGantry>()` 的冗余泛型，
        Python 用 `dict[str, OdsSzdnGantry]` 标注表达同样的类型约束；
        key 用 `isNull(gantryCode)`，null 编号会落到 "" 键并互相覆盖（原实现如此）。
        """
        map_: dict[str, OdsSzdnGantry] = {}
        list_ = self.odsSzdnGantryMapper.selectOdsSzdnGantryList(odsSzdnGantry)
        for rtn in list_:
            map_[CommonUtil.isNull(rtn.gantry_code)] = rtn
        return map_
