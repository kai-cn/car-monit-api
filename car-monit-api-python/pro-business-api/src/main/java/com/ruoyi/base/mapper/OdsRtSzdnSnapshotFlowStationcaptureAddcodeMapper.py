# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import OdsRtSzdnSnapshotFlowStationcaptureAddcode

__all__ = ["OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper"]


class OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper(BaseMapper[OdsRtSzdnSnapshotFlowStationcaptureAddcode]):
    """收费站抓拍Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<OdsRtSzdnSnapshotFlowStationcaptureAddcode>` → 继承同名泛型基类。
    2) 与「省界抓拍」Mapper 结构完全对称：标准 CRUD + 按业务 UUID 批量查，
       区别仅在表与实体（收费站抓拍 vs 省界抓拍）。
    3) `ByUuidList` 过滤列是 `datauuid`，不是主键 `big_id`。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsRtSzdnSnapshotFlowStationcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍

        :param bigId: 收费站抓拍ID
        :return: 收费站抓拍

        【Java→Python】`Long bigId` → `int`；复用 BaseMapper 主键查询。
        """
        return self.selectById(bigId)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(self, odsRtSzdnSnapshotFlowStationcaptureAddcode: OdsRtSzdnSnapshotFlowStationcaptureAddcode) -> list[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """查询收费站抓拍列表

        :param odsRtSzdnSnapshotFlowStationcaptureAddcode: 收费站抓拍
        :return: 收费站抓拍集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(odsRtSzdnSnapshotFlowStationcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByUuidList(self, uuidList: list[str]) -> list[OdsRtSzdnSnapshotFlowStationcaptureAddcode]:
        """根据UUID查询

        :param uuidList: 业务 UUID（datauuid）集合
        :return: 匹配的收费站抓拍

        【Java→Python】对应 SQL：
            SELECT * FROM ods_rt_szdn_snapshot_flow_stationcapture_addcode WHERE datauuid IN (#{uuidList})
        Java 用 `<foreach>` 展开 IN；Python 用集合成员判断，空列表直接返回空结果。
        """
        if not uuidList:
            return []
        wanted = set(uuidList)
        return self.selectWhere(lambda r: r.datauuid in wanted)
