# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.ZdataTrailFittingMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataTrailFittingMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting

__all__ = ["ZdataTrailFittingMapper"]


class ZdataTrailFittingMapper(BaseMapper[ZdataTrailFitting]):
    """车辆出入口拟合轨迹Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<ZdataTrailFitting>` → 继承 BaseMapper[ZdataTrailFitting]。
    2) 拟合轨迹表按 `extime`（出口时间）做月度分区，游标分片查询以 (extime, cid) 为复合游标，
       这与 `ZdataTrailFitting` 实体注释「extime 出口时间（分区键）」一致。
    3) 主键为 `cid`（字符串），故 selectZdataTrailFittingById(String cid) 直接走 selectById。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(ZdataTrailFitting)

    def selectZdataTrailFittingById(self, cid: str) -> Optional[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹

        :param cid: 车辆出入口拟合轨迹ID
        :return: 车辆出入口拟合轨迹

        【Java→Python】原方法由 Mapper XML 的 <select> 实现；此处复用 BaseMapper 主键查询。
        """
        return self.selectById(cid)

    def selectZdataTrailFittingList(self, zdataTrailFitting: ZdataTrailFitting) -> list[ZdataTrailFitting]:
        """查询车辆出入口拟合轨迹列表

        :param zdataTrailFitting: 车辆出入口拟合轨迹
        :return: 车辆出入口拟合轨迹集合

        【Java→Python】非空字段参与过滤，等价 XML 中 `<if test="xxx != null">` 拼接。
        """
        return self.selectList(zdataTrailFitting)

    def selectByCursorShard(
        self,
        startTime: str,
        endTime: str,
        cursorTime: str,
        cursorUuid: str,
        limit: int,
    ) -> list[ZdataTrailFitting]:
        """游标分页按时间分片查询（用于大规模数据同步到 ES）

        Keyset-paginated cursor query by time shard (for large-scale sync to ES).

        :param startTime: 分片起始时间 (yyyy-MM-dd HH:mm:ss)
        :param endTime: 分片结束时间
        :param cursorTime: 上批最后一条的 extime（首次传 null）
        :param cursorUuid: 上批最后一条的 cid（首次传 null）
        :param limit: 本次拉取条数
        :return: 本批轨迹

        【Java→Python】对应的 keyset SQL 语义：
            SELECT * FROM zdata_trail_fitting
             WHERE extime >= #{startTime} AND extime <= #{endTime}
               AND (extime > #{cursorTime}
                    OR (extime = #{cursorTime} AND cid > #{cursorUuid}))
             ORDER BY extime ASC, cid ASC
             LIMIT #{limit}
        （cursorTime 为 null 时为首批查询，不带游标条件）

        关键差异：
        1) `String` 时间参数在 Java 由 JDBC 隐式转型；Python 用 toComparable 显式解析为 datetime。
        2) 双列游标排序 → Python 元组排序；`cid` 为 NULL 时按空串处理（SQL 中 NULL 排序行为与 DB 相关，
           这里统一按「最小」处理，保证分页不重不漏）。
        3) **三值逻辑**：`cid > #{cursorUuid}` 在 cursorUuid 为 NULL 时为 UNKNOWN，
           所以 `extime = cursorTime` 的行在首次（cursorUuid 为空）时也必须排除。
        """
        start = self.toComparable(startTime)
        end = self.toComparable(endTime)
        cursor = self.toComparable(cursorTime) if cursorTime else None

        def matched(row: ZdataTrailFitting) -> bool:
            extime = self.toComparable(row.extime)
            if extime is None:
                # 分区键为空的记录不参与游标遍历
                return False
            if start is not None and extime < start:
                return False
            if end is not None and extime > end:
                return False
            if cursor is not None:
                if extime < cursor:
                    return False
                if extime == cursor:
                    # SQL: cid > #{cursorUuid}；cursorUuid 为 NULL → UNKNOWN → 不匹配
                    if cursorUuid is None or (row.cid or "") <= cursorUuid:
                        return False
            return True

        return self.selectWhere(
            matched,
            order_by=lambda r: (self.toComparable(r.extime), r.cid or ""),
            limit=limit,
        )
