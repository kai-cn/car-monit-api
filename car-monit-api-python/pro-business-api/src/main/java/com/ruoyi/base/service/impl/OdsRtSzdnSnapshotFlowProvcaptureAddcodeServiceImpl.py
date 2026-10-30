# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import OdsRtSzdnSnapshotFlowProvcaptureAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper import (
    OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper,
)
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService import (
    IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService,
)
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl"]


class OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl(
        ServiceImpl[OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper, OdsRtSzdnSnapshotFlowProvcaptureAddcode],
        IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService):
    """省界抓拍Service业务层处理

    【Java→Python】
    1) 缓存 key 前缀 `Constants.DATE_PROV_CAPTURE`（省界抓拍），逐 uuid 缓存 + 空值占位。
    2) 方法 `selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids` 的 Javadoc
       只写了 `@param queryUuids`/`@return`，无说明文字 —— 原样保留。
    """

    def __init__(self,
                 odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper:
                 Optional[OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper = (
            odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper or OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper()
        )
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(
            self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍

        :param bigId: 省界抓拍ID
        :return: 省界抓拍

        【Java→Python】`Long bigId` → `int`。
        """
        return self.odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper \
            .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(bigId)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(
            self, odsRtSzdnSnapshotFlowProvcaptureAddcode: OdsRtSzdnSnapshotFlowProvcaptureAddcode
    ) -> list[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍列表

        :param odsRtSzdnSnapshotFlowProvcaptureAddcode: 省界抓拍
        :return: 省界抓拍
        """
        return self.odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper \
            .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(odsRtSzdnSnapshotFlowProvcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(
            self, queryUuids: str) -> dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """根据UUID 查询

        :param queryUuids: 逗号分隔的 datauuid 串
        :return: datauuid → 实体

        【Java→Python】
        1) `Arrays.stream(queryUuids.split(",")).collect(Collectors.toList())` → `split(",")`。
        2) `(OdsRtSzdnSnapshotFlowProvcaptureAddcode) obj` 强转 → 直接使用缓存副本。
        3) 查无数据时写入只带 datauuid 的空实体占位，原样保留。
        """
        map_: dict[str, OdsRtSzdnSnapshotFlowProvcaptureAddcode] = {}
        if CommonUtil.isNotBlank(queryUuids):
            uuidList = queryUuids.split(",")
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_PROV_CAPTURE + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsRtSzdnSnapshotFlowProvcaptureAddcode()
                        querybo.datauuid = uuid
                        list_ = self.odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper \
                            .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_
