# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.ZdataTrailTracksMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataTrailTracksMapper.java
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks

__all__ = ["ZdataTrailTracksMapper"]


class ZdataTrailTracksMapper(BaseMapper[ZdataTrailTracks]):
    """轨迹数据Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<ZdataTrailTracks>` → 继承同名泛型基类。
    2) 本接口 4 个轨迹查询均以 `CarParaVO` 作为「查询参数包」（不是表实体），
       其字段含义取自已移植的服务实现：
         - applyTime1/applyTime2：时间范围（yyyy-MM-dd HH:mm:ss 字符串）
         - carNoList：车牌集合（IN 条件）
         - startNum / endNum：偏移分页的 LIMIT / OFFSET（注意顺序与命名相反，见方法注释）
         - lastExitTime：游标分页的上一批最后出站时间
         - pageSize：游标分页每批条数
    3) Java 侧这些 SQL 在 Mapper XML 中（未随仓库提供），
       Python 实现按调用方 `SysUtilServiceImpl` / `HighPerformanceSyncService` 的真实用法还原，
       每处推导都在方法注释中标注依据。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(ZdataTrailTracks)

    def selectZdataTrailTracksById(self, uuid: str) -> Optional[ZdataTrailTracks]:
        """查询轨迹数据

        :param uuid: 轨迹数据ID
        :return: 轨迹数据

        【Java→Python】复用 BaseMapper 主键查询（uuid 为 @TableId）。
        """
        return self.selectById(uuid)

    def selectZdataTrailTracksList(self, zdataTrailTracks: ZdataTrailTracks) -> list[ZdataTrailTracks]:
        """查询轨迹数据列表

        :param zdataTrailTracks: 轨迹数据
        :return: 轨迹数据集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(zdataTrailTracks)

    def getLatestTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩（按时间范围分批拉取轨迹点）

        :param carParaVO: 查询条件包
        :return: 轨迹列表（按出站时间升序）

        【Java→Python】依据调用方 `SysUtilServiceImpl`（L1412-1422）：
            carParaVO.setStartNum(6000);              // 每页条数
            carParaVO.setEndNum((i - 1) * 6000);      // 偏移量
            carParaVO.setApplyTime1(queryStartTime);
            carParaVO.setApplyTime2(queryEndTime);
        对应 SQL 语义：
            SELECT * FROM zdata_trail_tracks
             WHERE exit_time >= #{applyTime1} AND exit_time <= #{applyTime2}
             ORDER BY exit_time ASC
             LIMIT #{startNum} OFFSET #{endNum}

        注意：Java 里 `startNum` 被当作 LIMIT、`endNum` 被当作 OFFSET，
        命名与 SQL 含义相反，这里**刻意保持原语义**，不做「纠正」。
        """
        start, end = self._timeRange(carParaVO)
        limit = carParaVO.start_num
        offset = carParaVO.end_num or 0
        return self.selectWhere(
            lambda r: self._inRange(r.exit_time, start, end),
            order_by=lambda r: self.toComparable(r.exit_time),
            limit=limit,
            offset=offset,
        )

    def getHistoryTrail(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """轨迹查询（历史轨迹：按车牌集合 + 时间范围）

        :param carParaVO: 查询条件包
        :return: 轨迹列表（按出站时间升序）

        【Java→Python】依据调用方 `SysUtilServiceImpl.carTrackQuery`（L1962-1969）：
        先把 `carlist` 里的车牌抽取成 `carNoList`，再查历史轨迹。对应 SQL 语义：
            SELECT * FROM zdata_trail_tracks
             WHERE plate_key IN (#{carNoList})
               AND exit_time >= #{applyTime1} AND exit_time <= #{applyTime2}
             ORDER BY exit_time ASC

        注意：
        1) `carNoList` 为空列表时：SQL 的 `IN ()` 是非法语法，MyBatis 会抛错；
           Python 侧放宽为「不做车牌过滤」，避免空集合导致异常（可读性优先的业务折中）。
        2) plate_key 对应实体的「车牌唯一标识（可脱敏/加密存储）」。
        """
        start, end = self._timeRange(carParaVO)
        plate_keys = carParaVO.car_no_list or []

        def matched(row: ZdataTrailTracks) -> bool:
            if plate_keys and row.plate_key not in plate_keys:
                return False
            return self._inRange(row.exit_time, start, end)

        return self.selectWhere(matched, order_by=lambda r: self.toComparable(r.exit_time))

    def getUnFitting(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """同步可疑车俩（未拟合轨迹）

        :param carParaVO: 查询条件包
        :return: 轨迹类型为 0（不完整轨迹）的记录

        【Java→Python】依据 `ZdataTrailTracks.type` 字段注释
        「轨迹类型（如 0=不完整, 1=完整，后续可扩展更多状态码）」，
        「未拟合」即尚未成功拟合出入口的轨迹，因此过滤 `type = 0`：
            SELECT * FROM zdata_trail_tracks
             WHERE type = 0
               AND exit_time >= #{applyTime1} AND exit_time <= #{applyTime2}
        若后续 `type` 语义扩展，应同步修改此处。
        """
        start, end = self._timeRange(carParaVO)
        return self.selectWhere(
            lambda r: r.type == 0 and self._inRange(r.exit_time, start, end),
            order_by=lambda r: self.toComparable(r.exit_time),
        )

    def getLatestTrailByCursor(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """使用游标分页查询轨迹数据（高性能版本）

        :param carParaVO: 查询条件包
        :return: 本批轨迹（按出站时间升序）

        【Java→Python】依据调用方 `HighPerformanceSyncService.queryTrailTracksWithCursor`：
            carParaVO.setApplyTime1(dateRange.startTime);
            carParaVO.setApplyTime2(dateRange.endTime);
            carParaVO.setPageSize(pageSize);
            carParaVO.setLastExitTime(lastExitTime);   // 上一批最后一条的 exit_time
        对应 keyset SQL 语义：
            SELECT * FROM zdata_trail_tracks
             WHERE exit_time >= #{applyTime1} AND exit_time <= #{applyTime2}
               AND exit_time > #{lastExitTime}
             ORDER BY exit_time ASC
             LIMIT #{pageSize}

        关键差异：
        1) `lastExitTime` 是 `Date`（Java）/ `datetime`（Python），首屏为 null → 不带游标条件；
        2) 游标用「严格大于」避免重复取到上一批最后一条；
           若同一出站时间存在多条记录，keyset 需再用 uuid 兜底（原 Java 实现仅用时间，
           因此极端情况下可能丢同秒记录，此处保持原行为并在注释中标注）。
        """
        start, end = self._timeRange(carParaVO)
        cursor = self.toComparable(carParaVO.last_exit_time)

        def matched(row: ZdataTrailTracks) -> bool:
            exit_time = self.toComparable(row.exit_time)
            if not self._inRange(exit_time, start, end):
                return False
            if cursor is not None and (exit_time is None or exit_time <= cursor):
                return False
            return True

        return self.selectWhere(
            matched,
            order_by=lambda r: self.toComparable(r.exit_time),
            limit=carParaVO.page_size,
        )

    # ------------------------------------------------------------------ 内部工具
    def _timeRange(self, carParaVO: CarParaVO):
        """把 CarParaVO 的字符串时间条件转成可比较的 datetime。"""
        return self.toComparable(carParaVO.apply_time1), self.toComparable(carParaVO.apply_time2)

    def _inRange(self, value: datetime, start: datetime, end: datetime) -> bool:
        """等价 SQL 的 `col >= start AND col <= end`（NULL 一律不匹配）。"""
        comparable = self.toComparable(value)
        if comparable is None:
            return False
        if start is not None and comparable < start:
            return False
        if end is not None and comparable > end:
            return False
        return True
