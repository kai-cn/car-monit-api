# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationEnter01ServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeStationEnter01ServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationEnter01Mapper import OdsLwzxsfsjFeeStationEnter01Mapper
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service import IOdsLwzxsfsjFeeStationEnter01Service
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsLwzxsfsjFeeStationEnter01ServiceImpl"]


class OdsLwzxsfsjFeeStationEnter01ServiceImpl(
        ServiceImpl[OdsLwzxsfsjFeeStationEnter01Mapper, OdsLwzxsfsjFeeStationEnter01],
        IOdsLwzxsfsjFeeStationEnter01Service):
    """收费站入口数据Service业务层处理

    【Java→Python】
    1) 类名很长，Java 单行写法；Python 按 PEP 8 拆成多行（基类列表过长），
       类名本身一字符不差。
    2) 与 `OdsCxztFwqcllsServiceImpl` 同一套“逐 key 缓存 + 空值占位”模式，
       区别只在缓存 key 前缀（`Constants.DATE_FeeStationEnter`）与查询列（`cid` 而非 `datauuid`）。
    """

    def __init__(self,
                 odsLwzxsfsjFeeStationEnter01Mapper: Optional[OdsLwzxsfsjFeeStationEnter01Mapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsLwzxsfsjFeeStationEnter01Mapper = odsLwzxsfsjFeeStationEnter01Mapper or OdsLwzxsfsjFeeStationEnter01Mapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsLwzxsfsjFeeStationEnter01Mapper)

    def selectOdsLwzxsfsjFeeStationEnter01ById(self, bigId: int) -> Optional[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据

        :param bigId: 收费站入口数据ID
        :return: 收费站入口数据

        【Java→Python】Java `Long bigId` → Python `int`。
        """
        return self.odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01ById(bigId)

    def selectOdsLwzxsfsjFeeStationEnter01List(
            self, odsLwzxsfsjFeeStationEnter01: OdsLwzxsfsjFeeStationEnter01) -> list[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据列表

        :param odsLwzxsfsjFeeStationEnter01: 收费站入口数据
        :return: 收费站入口数据
        """
        return self.odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(odsLwzxsfsjFeeStationEnter01)

    def selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids(
            self, queryUuids: str) -> dict[str, OdsLwzxsfsjFeeStationEnter01]:
        """按逗号分隔的 uuid 串批量取收费站入口数据（带 Redis 缓存）

        :param queryUuids: 逗号分隔的 cid 串
        :return: cid → 实体（缓存/库中不存在的 cid 不会出现在结果里）

        【Java→Python】
        1) `String[] split = queryUuids.split(","); Arrays.stream(split).collect(toList())`
           → Python `queryUuids.split(",")`；Java 丢弃末尾空串、Python 保留，
           但后续 `isNotBlank` 过滤，结果一致。
        2) 查库条件用 `querybo.setCid(uuid)`：实体非空字段即 SQL 的 WHERE 条件，
           Python 侧直接给 dataclass 字段赋值（不会触发 Java 那样的 setter 副作用）。
        3) 查不到时写入只带 `cid` 的空对象做占位缓存，原样保留。
        """
        map_: dict[str, OdsLwzxsfsjFeeStationEnter01] = {}
        if CommonUtil.isNotBlank(queryUuids):
            split = queryUuids.split(",")
            uuidList = split
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    key = Constants.DATE_FeeStationEnter + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsLwzxsfsjFeeStationEnter01()
                        querybo.cid = uuid
                        list_ = self.odsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_
