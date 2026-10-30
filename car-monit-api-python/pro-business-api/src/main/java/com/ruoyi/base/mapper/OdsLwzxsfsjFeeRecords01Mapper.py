# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeRecords01Mapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

__all__ = ["OdsLwzxsfsjFeeRecords01Mapper"]


class OdsLwzxsfsjFeeRecords01Mapper(BaseMapper[OdsLwzxsfsjFeeRecords01]):
    """基础-收费流水Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<OdsLwzxsfsjFeeRecords01>` → 继承 BaseMapper[OdsLwzxsfsjFeeRecords01]。
    2) 除两个标准 CRUD 外，另有 3 个自定义查询（门架数量、新列表、游标分片），
       原工程对应 SQL 位于 Mapper XML（未随仓库提供），此处按方法注释与调用方用法推导等价实现，
       并在各方法注释中写明推导依据。
    3) 游标分页的 `cursorTime/cursorUuid` 是「上一批最后一条」的 (transtime, big_id)，
       用于 keyset pagination，避免大 OFFSET 全表扫描。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsLwzxsfsjFeeRecords01)

    def selectOdsLwzxsfsjFeeRecords01ById(self, bigId: str) -> Optional[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水

        :param bigId: 基础-收费流水ID
        :return: 基础-收费流水

        【Java→Python】原方法由 Mapper XML 的 <select> 实现；此处复用 BaseMapper 主键查询。
        """
        return self.selectById(bigId)

    def selectOdsLwzxsfsjFeeRecords01List(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水列表

        :param odsLwzxsfsjFeeRecords01: 基础-收费流水
        :return: 基础-收费流水集合

        【Java→Python】XML 中的 `where` 使用 `<if test="xxx != null">` 拼接非空条件，
        与 BaseMapper._matches（实体非空字段参与过滤）语义一致。
        """
        return self.selectList(odsLwzxsfsjFeeRecords01)

    def selectGantryNum(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> int:
        """查询门架数量

        :param odsLwzxsfsjFeeRecords01: 查询条件（非空字段参与过滤）
        :return: 不同门架（gantryid）的数量

        【Java→Python】原 SQL 推测为：
            SELECT COUNT(DISTINCT gantryid) FROM ods_lwzxsfsj_fee_records_01 WHERE ...
        因此 Python 侧先按实体非空字段过滤，再对 gantryid 去重计数。
        注意：SQL 的 COUNT(DISTINCT) 会忽略 NULL，这里同样跳过 gantryid 为空的行。
        """
        codes = {
            row.gantryid
            for row in self.selectList(odsLwzxsfsjFeeRecords01)
            if row.gantryid is not None
        }
        return len(codes)

    def selectOdsLwzxsfsjFeeRecords01ListNew(self, bo: OdsLwzxsfsjFeeRecords01) -> list[OdsLwzxsfsjFeeRecords01]:
        """查询基础-收费流水列表（新版，无 XML 伴随，语义与旧列表一致）

        :param bo: 查询条件对象（非空字段参与过滤）
        :return: 基础-收费流水集合

        【Java→Python】Java 侧该方法没有注释也没有注解 SQL，说明 SQL 在 XML 中；
        为保证上层服务可运行，这里按「同名字段等值过滤」实现，并保留方法名作为 statement id。
        """
        return self.selectList(bo)

    def selectByCursorShard(
        self,
        startTime: str,
        endTime: str,
        cursorTime: str,
        cursorUuid: str,
        limit: int,
    ) -> list[OdsLwzxsfsjFeeRecords01]:
        """游标分页按时间分片查询（用于大规模数据同步到 ES）

        Keyset-paginated cursor query by time shard (for large-scale sync to ES).

        :param startTime: 分片起始时间 (yyyy-MM-dd HH:mm:ss)
        :param endTime: 分片结束时间
        :param cursorTime: 上批最后一条的 transtime（首次传 null）
        :param cursorUuid: 上批最后一条的 big_id（首次传 null）
        :param limit: 本次拉取条数
        :return: 本批收费流水

        【Java→Python】对应的 keyset SQL 语义：
            SELECT * FROM ods_lwzxsfsj_fee_records_01
             WHERE transtime >= #{startTime} AND transtime <= #{endTime}
               AND (transtime > #{cursorTime}
                    OR (transtime = #{cursorTime} AND big_id > #{cursorUuid}))
             ORDER BY transtime ASC, big_id ASC
             LIMIT #{limit}
        （cursorTime 为 null 时省略游标条件，即首批查询）

        关键差异：
        1) Java 用 `String startTime` 交给 JDBC 隐式转 timestamp；Python 必须用
           BaseMapper.toComparable 显式把字符串解析成 datetime，否则 datetime 与 str 无法比较。
        2) 复合排序 (transtime, big_id) → Python 元组排序，语义与 ORDER BY 双列一致。
        3) keyset 条件用「大于」而非「大于等于」，配合双列游标保证不重不漏。
        4) **三值逻辑**：`big_id > #{cursorUuid}` 在 cursorUuid 为 NULL 时是 UNKNOWN，
           所以 `transtime = cursorTime` 的行在首次（cursorUuid 为空）时也必须排除。
        """
        start = self.toComparable(startTime)
        end = self.toComparable(endTime)
        cursor = self.toComparable(cursorTime) if cursorTime else None

        def matched(row: OdsLwzxsfsjFeeRecords01) -> bool:
            transit = self.toComparable(row.transtime)
            if transit is None:
                return False
            # SQL 对 NULL 时间列的比较结果为 UNKNOWN → 行被过滤
            if start is not None and transit < start:
                return False
            if end is not None and transit > end:
                return False
            if cursor is not None:
                if transit < cursor:
                    return False
                if transit == cursor:
                    # SQL: big_id > #{cursorUuid}；cursorUuid 为 NULL → UNKNOWN → 不匹配
                    if cursorUuid is None or (row.big_id or "") <= cursorUuid:
                        return False
            return True

        return self.selectWhere(
            matched,
            order_by=lambda r: (self.toComparable(r.transtime), r.big_id or ""),
            limit=limit,
        )
