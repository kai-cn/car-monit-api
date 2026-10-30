# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationExit01ServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeStationExit01ServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationExit01Mapper import OdsLwzxsfsjFeeStationExit01Mapper
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service import IOdsLwzxsfsjFeeStationExit01Service
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsLwzxsfsjFeeStationExit01ServiceImpl"]


class OdsLwzxsfsjFeeStationExit01ServiceImpl(
        ServiceImpl[OdsLwzxsfsjFeeStationExit01Mapper, OdsLwzxsfsjFeeStationExit01],
        IOdsLwzxsfsjFeeStationExit01Service):
    """收费站出口流水Service业务层处理

    【Java→Python】
    1) 与“入口”实现（`OdsLwzxsfsjFeeStationEnter01ServiceImpl`）几乎逐行对称，
       仅实体类名、Mapper 名与缓存 key 前缀（`Constants.DATE_FeeStationExit`）不同。
    2) 注意主键类型差异：入口 `bigId` 是 `Long`，出口 `bigId` 是 `String`
       （两个表建模不一致，属原库设计，Python 侧如实反映在类型标注上）。
    """

    def __init__(self,
                 odsLwzxsfsjFeeStationExit01Mapper: Optional[OdsLwzxsfsjFeeStationExit01Mapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsLwzxsfsjFeeStationExit01Mapper = odsLwzxsfsjFeeStationExit01Mapper or OdsLwzxsfsjFeeStationExit01Mapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsLwzxsfsjFeeStationExit01Mapper)

    def selectOdsLwzxsfsjFeeStationExit01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeStationExit01]:
        """查询收费站出口流水

        :param bigId: 收费站出口流水ID
        :return: 收费站出口流水

        【Java→Python】Java `String bigId` → Python `str`。
        """
        return self.odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01ById(bigId)

    def selectOdsLwzxsfsjFeeStationExit01List(
            self, odsLwzxsfsjFeeStationExit01: OdsLwzxsfsjFeeStationExit01) -> list[OdsLwzxsfsjFeeStationExit01]:
        """查询收费站出口流水列表

        :param odsLwzxsfsjFeeStationExit01: 收费站出口流水
        :return: 收费站出口流水
        """
        return self.odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(odsLwzxsfsjFeeStationExit01)

    def selectOdsLwzxsfsjFeeStationExit01ByQueryUuids(
            self, queryUuids: str) -> dict[str, OdsLwzxsfsjFeeStationExit01]:
        """按逗号分隔的 uuid 串批量取收费站出口流水（带 Redis 缓存）

        :param queryUuids: 逗号分隔的 cid 串
        :return: cid → 实体（缓存/库中不存在的 cid 不会出现在结果里）

        【Java→Python】
        1) `String[] split = queryUuids.split(",")` + stream 收集 → Python `split(",")` 直接返回 list。
        2) Java 循环体末尾多了一个空行（`}` 前），属于原始格式，不影响逻辑。
        3) 空值占位缓存（写入只带 cid 的空实体）原样保留，语义见同包 `OdsCxztFwqcllsServiceImpl`。
        """
        map_: dict[str, OdsLwzxsfsjFeeStationExit01] = {}
        if CommonUtil.isNotBlank(queryUuids):
            split = queryUuids.split(",")
            uuidList = split
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    key = Constants.DATE_FeeStationExit + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsLwzxsfsjFeeStationExit01()
                        querybo.cid = uuid
                        list_ = self.odsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)

        return map_
