# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import OdsRtSzdnSnapshotFlowStationcaptureAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper import (
    OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper,
)
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService import (
    IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService,
)
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl"]


class OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl(
        ServiceImpl[OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper, OdsRtSzdnSnapshotFlowStationcaptureAddcode],
        IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService):
    """收费站抓拍Service业务层处理

    【Java→Python】
    1) 与“省界抓拍”实现对称，但本类的批量查询多了两个参数 `applyTime1/applyTime2`
       （时间区间）。它们对应实体里 `@TableField(exist = false)` 的查询辅助字段
       `apply_time1/apply_time2`，**不是数据库列**：
       - Java 侧该条件依赖 RuoYi 生成的 Mapper XML（本工程 resources 下没有对应 XML，
         因此实际不会拼进 SQL）；
       - Python 侧 `BaseMapper._matches` 只遍历真实表字段（`exist != False`），
         这两个字段同样不参与 WHERE 构造 —— 行为一致。
       这里仍保留赋值动作，是为了在补上 XML 等价实现时能直接生效。
    2) **注意**：Java 侧这两个字段若真参与了过滤，就必须基于同样的值才能命中 Redis key；
       而缓存 key 只含 uuid（不含时间段），属于原有的缓存键设计缺陷，Python 侧如实复刻。
    """

    def __init__(self,
                 odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper:
                 Optional[OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper = (
            odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper or OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper()
        )
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(
            self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍

        :param bigId: 收费站抓拍ID
        :return: 收费站抓拍
        """
        return self.odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper \
            .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(bigId)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(
            self, odsRtSzdnSnapshotFlowStationcaptureAddcode: OdsRtSzdnSnapshotFlowStationcaptureAddcode
    ) -> list[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍列表

        :param odsRtSzdnSnapshotFlowStationcaptureAddcode: 收费站抓拍
        :return: 收费站抓拍
        """
        return self.odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper \
            .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(odsRtSzdnSnapshotFlowStationcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(
            self, queryUuids: str, applyTime1: str, applyTime2: str
    ) -> dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """根据UUID 查询

        :param queryUuids: 逗号分隔的 datauuid 串
        :param applyTime1: 时间区间下界（查询辅助字段，非表列）
        :param applyTime2: 时间区间上界（查询辅助字段，非表列）
        :return: datauuid → 实体

        【Java→Python】
        1) `String[] split = queryUuids.split(",")` → Python `split(",")`，空串过滤一致。
        2) `querybo.setApplyTime1/2(...)` 赋的是 `exist = False` 的字段（仅参与 Mapper XML 条件），
           Python 侧保留赋值但内存过滤不使用（详见类注释）。
        3) 原来的两层空行（`}` 前有两个空行）为原始格式，这里合并为一处空行，逻辑不变。
        """
        map_: dict[str, OdsRtSzdnSnapshotFlowStationcaptureAddcode] = {}
        if CommonUtil.isNotBlank(queryUuids):
            split = queryUuids.split(",")
            uuidList = split
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_STATION_CAPTURE + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsRtSzdnSnapshotFlowStationcaptureAddcode()
                        querybo.datauuid = uuid
                        querybo.apply_time1 = applyTime1
                        querybo.apply_time2 = applyTime2
                        list_ = self.odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper \
                            .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_
