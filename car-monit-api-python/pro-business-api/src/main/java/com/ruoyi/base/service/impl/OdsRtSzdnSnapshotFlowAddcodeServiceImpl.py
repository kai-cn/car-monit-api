# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsRtSzdnSnapshotFlowAddcodeServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import IOdsRtSzdnSnapshotFlowAddcodeService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils.DateUtils import DateUtils

__all__ = ["OdsRtSzdnSnapshotFlowAddcodeServiceImpl"]


class OdsRtSzdnSnapshotFlowAddcodeServiceImpl(
        ServiceImpl[OdsRtSzdnSnapshotFlowAddcodeMapper, OdsRtSzdnSnapshotFlowAddcode],
        IOdsRtSzdnSnapshotFlowAddcodeService):
    """门架抓拍流水Service业务层处理

    【Java→Python】
    1) `import java.util.*;` + `java.util.stream.Collectors` → Python 显式 import，不使用星号导入。
    2) 本类包含大表游标分页的关键入口 `queryByCursor` 与 `getMaxSnapshotTime`，
       这两个方法是大表（亿级）增量同步的基础，注释见各自方法。
    """

    def __init__(self,
                 odsRtSzdnSnapshotFlowAddcodeMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsRtSzdnSnapshotFlowAddcodeMapper = odsRtSzdnSnapshotFlowAddcodeMapper or OdsRtSzdnSnapshotFlowAddcodeMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsRtSzdnSnapshotFlowAddcodeMapper)

    def selectOdsRtSzdnSnapshotFlowAddcodeById(self, bigId: str) -> Optional[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水

        :param bigId: 门架抓拍流水ID
        :return: 门架抓拍流水

        【Java→Python】`String bigId`（`big_id` 为 ASSIGN_UUID 主键）。
        """
        return self.odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId)

    def selectOdsRtSzdnSnapshotFlowAddcodeList(
            self, odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水列表

        :param odsRtSzdnSnapshotFlowAddcode: 门架抓拍流水
        :return: 门架抓拍流水
        """
        return self.odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode)

    def selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(
            self, queryUuids: str, applyTime1: str, applyTime2: str) -> dict[str, OdsRtSzdnSnapshotFlowAddcode]:
        """通过UUID 查询

        :param queryUuids: 逗号分隔的 datauuid 串
        :param applyTime1: 时间区间下界（`apply_time1`，exist=False 查询辅助字段）
        :param applyTime2: 时间区间上界（`apply_time2`，exist=False 查询辅助字段）
        :return: datauuid → 实体

        【Java→Python】
        1) `Arrays.stream(queryUuids.split(",")).collect(Collectors.toList())` → `split(",")`。
        2) `setApplyTime1/2(...)` 赋的是 `@TableField(exist = false)` 字段，
           不参与内存 WHERE 构造（原因见 `OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl` 类注释）。
        3) 查无结果时写入只带 datauuid 的空实体占位，原样保留。
        """
        map_: dict[str, OdsRtSzdnSnapshotFlowAddcode] = {}
        if CommonUtil.isNotBlank(queryUuids):
            uuidList = queryUuids.split(",")
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_GANTRY_CAPTURE + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsRtSzdnSnapshotFlowAddcode()
                        querybo.datauuid = uuid
                        querybo.apply_time1 = applyTime1
                        querybo.apply_time2 = applyTime2
                        list_ = self.odsRtSzdnSnapshotFlowAddcodeMapper \
                            .selectOdsRtSzdnSnapshotFlowAddcodeList(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_

    def selectOdsRtSzdnSnapshotFlowAddcodeListNew(
            self, bo: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水列表（新版 SQL 变体）

        :param bo: 查询条件
        :return: 门架抓拍流水集合

        【Java→Python】Java 里先赋给局部变量 `snapshotList` 再返回（多余的中间变量），
        为逐行对照保留该局部变量。
        """
        snapshotList = self.odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeListNew(bo)
        return snapshotList

    def queryByCursor(self, cursor: str, maxSnapshotTime: str, pageSize: int) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """游标分页查询

        设计思路：
        - 基于游标（cursor）实现高效分页查询，避免 LIMIT OFFSET 的性能问题
        - cursor 参数通常表示上次查询最后一条记录的时间戳或 UUID，
          本次查询从该游标位置向后扫描，保证分页性能稳定
        - 适用于大表（亿级）分页查询，时间复杂度 O(log n) + O(pageSize)

        :param cursor: 游标（起始位置，如 UUID 或时间戳字符串）
        :param maxSnapshotTime: 最大快照时间（分页查询的上界）
        :param pageSize: 每页大小
        :return: 查询结果列表

        【Java→Python】
        1) Java 用 `null` 占位跳过 startTime 与 cursorUuid 两个参数；
           Python 同样传 `None`（Mapper 内部按 "未指定" 处理）。
        2) `selectByCursorShard` 的 5 个位置参数顺序必须与 Java 一致：
           (startTime, endTime, cursorTime, cursorUuid, limit) —— 顺序错位是本方法最易出错处。
        """
        return self.odsRtSzdnSnapshotFlowAddcodeMapper.selectByCursorShard(
            None,
            maxSnapshotTime,
            cursor,
            None,
            pageSize
        )

    def getMaxSnapshotTime(self) -> str:
        """查询表中的最大快照时间

        调用 Mapper 层 SQL：SELECT MAX(snapshottime) FROM ...
        将返回的 java.util.Date 格式化为 "yyyy-MM-dd HH:mm:ss" 字符串

        :return: 格式化后的时间字符串；异常时返回 None

        【Java→Python】
        1) `SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(date)`
           → `DateUtils.parseDateToStr(...)`（内部把 Java 模式转成 strftime 模式）。
           Java 的 `SimpleDateFormat` 非线程安全，每次 new；Python `strftime` 无此问题。
        2) `maxDate == null` 的分支在 Java 里**实际不可达**：
           Mapper 的 SQL 是 `COALESCE(MAX(snapshottime), NOW())`，永远返回非 null。
           但为逐行对照保留该判断（Python 侧 Mapper 同样永不返回 None）。
        3) `catch (Exception e) { return null; }` → `except Exception: return None`：
           吞异常的写法原样保留，不记录日志（原实现如此）。
        """
        try:
            maxDate = self.odsRtSzdnSnapshotFlowAddcodeMapper.getMaxSnapshotTime()
            if maxDate is None:
                return None
            return DateUtils.parseDateToStr("yyyy-MM-dd HH:mm:ss", maxDate)
        except Exception:
            return None
