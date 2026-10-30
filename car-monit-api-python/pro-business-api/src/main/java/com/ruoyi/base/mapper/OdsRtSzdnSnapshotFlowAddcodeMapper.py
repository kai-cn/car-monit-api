# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowAddcodeMapper.java
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode

__all__ = ["OdsRtSzdnSnapshotFlowAddcodeMapper"]


class OdsRtSzdnSnapshotFlowAddcodeMapper(BaseMapper[OdsRtSzdnSnapshotFlowAddcode]):
    """门架抓拍流水Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<OdsRtSzdnSnapshotFlowAddcode>` → 继承 BaseMapper[OdsRtSzdnSnapshotFlowAddcode]。
    2) 本接口是「亿级大表」主查询入口：含 UUID 批量查、游标分片查、最大值边界查三类优化手段，
       Python 侧全部保留原方法签名，内存实现仅用于结构对齐与单测。
    3) `ByUuidList` 的过滤列是业务 UUID `datauuid`，**不是**主键 `big_id`；
       因此不能用 selectBatchIds（那是按主键 IN）。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsRtSzdnSnapshotFlowAddcode)

    def selectOdsRtSzdnSnapshotFlowAddcodeById(self, bigId: str) -> Optional[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水

        :param bigId: 门架抓拍流水ID
        :return: 门架抓拍流水

        【Java→Python】复用 BaseMapper 主键查询（big_id 为 @TableId）。
        """
        return self.selectById(bigId)

    def selectOdsRtSzdnSnapshotFlowAddcodeList(self, odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水列表

        :param odsRtSzdnSnapshotFlowAddcode: 门架抓拍流水
        :return: 门架抓拍流水集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(odsRtSzdnSnapshotFlowAddcode)

    def selectOdsRtSzdnSnapshotFlowAddcodeByUuidList(self, uuidList: list[str]) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """通过UUID 查询

        :param uuidList: 业务 UUID（datauuid）集合
        :return: 匹配的抓拍流水

        【Java→Python】对应 SQL：
            SELECT * FROM ods_rt_szdn_snapshot_flow_addcode WHERE datauuid IN (#{uuidList})
        注意：
        1) Java 用 `<foreach>` 展开 IN 列表；Python 用集合成员判断。
        2) uuidList 为 null/空时，Java 的 `<if>` 可能生成非法 SQL 或空结果，这里统一返回空列表。
        """
        if not uuidList:
            return []
        wanted = set(uuidList)
        return self.selectWhere(lambda r: r.datauuid in wanted)

    def selectOdsRtSzdnSnapshotFlowAddcodeListNew(self, bo: OdsRtSzdnSnapshotFlowAddcode) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """查询门架抓拍流水列表（新版）

        :param bo: 查询条件对象
        :return: 门架抓拍流水集合

        【Java→Python】Java 侧 SQL 在 Mapper XML 中（未随仓库提供），
        此处按「非空字段等值过滤」实现，保持方法名作为 statement id。
        """
        return self.selectList(bo)

    def selectByCursorShard(
        self,
        startTime: str,
        endTime: str,
        cursorTime: str,
        cursorUuid: str,
        limit: int,
    ) -> list[OdsRtSzdnSnapshotFlowAddcode]:
        """游标分页按时间分片查询（用于大规模数据同步）

        :param startTime: 分片起始时间
        :param endTime: 分片结束时间
        :param cursorTime: 上批最后一条的 snapshottime（首次传 null）
        :param cursorUuid: 上批最后一条的 datauuid（首次传 null）
        :param limit: 本次拉取条数
        :return: 本次批量数据

        【Java→Python】对应的 keyset SQL 语义：
            SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode
             WHERE snapshottime >= #{startTime} AND snapshottime <= #{endTime}
               AND (snapshottime > #{cursorTime}
                    OR (snapshottime = #{cursorTime} AND datauuid > #{cursorUuid}))
             ORDER BY snapshottime ASC, datauuid ASC
             LIMIT #{limit}

        关键差异：
        1) Java 依赖 JDBC 把 String 隐式转 timestamp；Python 必须显式 toComparable 解析。
        2) keyset 双列比较 → Python 元组排序；同一时刻的多条记录靠 datauuid 保证唯一顺序。
        3) **三值逻辑**：`datauuid > #{cursorUuid}` 在 cursorUuid 为 NULL 时结果是 UNKNOWN，
           SQL 不会返回 `snapshottime = cursorTime` 的那些行。因此 cursorUuid 为 None 时
           必须把“等于游标时间”的行一并排除（早期实现漏了这一点，会多返回重复行）。
        """
        start = self.toComparable(startTime)
        end = self.toComparable(endTime)
        cursor = self.toComparable(cursorTime) if cursorTime else None

        def matched(row: OdsRtSzdnSnapshotFlowAddcode) -> bool:
            snapshottime = self.toComparable(row.snapshottime)
            if snapshottime is None:
                return False
            if start is not None and snapshottime < start:
                return False
            if end is not None and snapshottime > end:
                return False
            if cursor is not None:
                if snapshottime < cursor:
                    return False
                if snapshottime == cursor:
                    # SQL: datauuid > #{cursorUuid}；cursorUuid 为 NULL → UNKNOWN → 不匹配
                    if cursorUuid is None or (row.datauuid or "") <= cursorUuid:
                        return False
            return True

        return self.selectWhere(
            matched,
            order_by=lambda r: (self.toComparable(r.snapshottime), r.datauuid or ""),
            limit=limit,
        )

    def getMaxSnapshotTime(self) -> datetime:
        """查询表中的最大快照时间（用于分页查询的边界）

        设计思路：
        - 用于游标分页时，需要知道数据的上界（最大时间）
        - 返回最大快照时间作为分页查询的上界

        :return: 最大快照时间字符串（yyyy-MM-dd HH:mm:ss 格式）

        【Java→Python】原注解 SQL（逐字对照）：
            @Select("SELECT COALESCE(MAX(snapshottime), NOW()) FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode")
            java.util.Date getMaxSnapshotTime();

        关键差异：
        1) `COALESCE(MAX(x), NOW())`：表为空时回退到**数据库服务器当前时间**；
           Python 用 datetime.now()（本机时区），生产环境应保证应用与 DB 时区一致。
        2) Java 返回 java.util.Date；Python 返回 datetime（本工程统一映射）。
        """
        times = [row.snapshottime for row in self._rows if row.snapshottime is not None]
        # COALESCE(..., NOW())：无数据时取当前时间
        return max(times) if times else datetime.now()
