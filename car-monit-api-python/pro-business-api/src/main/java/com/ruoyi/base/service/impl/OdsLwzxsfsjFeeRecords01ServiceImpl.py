# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeRecords01ServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import OdsLwzxsfsjFeeRecords01Mapper
from com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service import IOdsLwzxsfsjFeeRecords01Service
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsLwzxsfsjFeeRecords01ServiceImpl"]


class OdsLwzxsfsjFeeRecords01ServiceImpl(
        ServiceImpl[OdsLwzxsfsjFeeRecords01Mapper, OdsLwzxsfsjFeeRecords01],
        IOdsLwzxsfsjFeeRecords01Service):
    """基础-收费流水Service业务层处理

    【Java→Python】
    1) `import java.util.*;` → Python 逐个显式 import（`Any`/`Optional`），不使用星号导入。
    2) 接口声明 `selectOdsLwzxsfsjFeeRecords01ByQueryUuids(String uuids, ...)`，
       实现类却写成 `(String queryUuids, ...)` —— **形参名不同、位置一致**，Java 合法；
       Python 同为位置参数，保持实现类的 `queryUuids` 命名。
    3) `selectGantryNum` 在接口中声明为 `int` 返回，实现直接透传 Mapper 的 COUNT(DISTINCT gantryid)。
    4) `selectGantryNum` 的 Javadoc 写的是“查询基础-收费流水列表”、`@return 基础-收费流水集合`，
       与方法实际语义（统计门架数量）不符 —— 原代码的复制粘贴错误，原样保留。
    """

    def __init__(self,
                 odsLwzxsfsjFeeRecords01Mapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsLwzxsfsjFeeRecords01Mapper = odsLwzxsfsjFeeRecords01Mapper or OdsLwzxsfsjFeeRecords01Mapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsLwzxsfsjFeeRecords01Mapper)

    def selectOdsLwzxsfsjFeeRecords01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水

        :param bigId: 基础-收费流水ID
        :return: 基础-收费流水

        【Java→Python】本表主键是 String（`big_id`，ASSIGN_UUID），不是自增 Long。
        """
        return self.odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ById(bigId)

    def selectOdsLwzxsfsjFeeRecords01List(
            self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水列表

        :param odsLwzxsfsjFeeRecords01: 基础-收费流水
        :return: 基础-收费流水
        """
        return self.odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01)

    def selectOdsLwzxsfsjFeeRecords01ByQueryUuids(
            self, queryUuids: str, applyTime1: str, applyTime2: str) -> dict[str, OdsLwzxsfsjFeeRecords01]:
        """按逗号分隔的 CID 批量取收费流水（带 Redis 缓存）

        :param queryUuids: 逗号分隔的 cid 串
        :param applyTime1: 入口时间下界（`in_apply_time1`，exist=False 查询辅助字段）
        :param applyTime2: 入口时间上界（`in_apply_time2`，exist=False 查询辅助字段）
        :return: cid → 实体

        【Java→Python】
        1) `String[] split = ...` + stream → Python `split(",")`；空串过滤一致。
        2) `setInApplyTime1/2(...)` 赋的是 `@TableField(exist = false)` 字段，
           不参与内存 WHERE 构造（详见 `OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl` 类注释）。
        3) 查无结果时写入只带 cid 的空实体占位，原样保留。
        """
        map_: dict[str, OdsLwzxsfsjFeeRecords01] = {}
        if CommonUtil.isNotBlank(queryUuids):
            split = queryUuids.split(",")
            uuidList = split
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_FeeRecord + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsLwzxsfsjFeeRecords01()
                        querybo.cid = uuid
                        querybo.in_apply_time1 = applyTime1
                        querybo.in_apply_time2 = applyTime2
                        list_ = self.odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_

    def selectGantryNum(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> int:
        """查询基础-收费流水列表（Javadoc 与原实现不符，保留原文）

        :param odsLwzxsfsjFeeRecords01: 基础-收费流水
        :return: 基础-收费流水集合（实际返回 int，即 DISTINCT 门架数）

        【Java→Python】COUNT(DISTINCT gantryid) 的语义在 Mapper 内用 set 去重实现；
        无匹配行时 SQL 返回 0，Python 侧同样返回 0（`len(set())`）。
        """
        return self.odsLwzxsfsjFeeRecords01Mapper.selectGantryNum(odsLwzxsfsjFeeRecords01)

    def selectOdsLwzxsfsjFeeRecords01ListNew(
            self, bo: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水列表（New 版本，对应 Mapper 里手写 SQL 的变体）

        :param bo: 基础-收费流水（查询条件）
        :return: 基础-收费流水集合

        【Java→Python】形参名 `bo` 与接口里的 `odsLwzxsfsjFeeRecords01` 不同（Java 允许），保持实现类命名。
        """
        return self.odsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew(bo)
