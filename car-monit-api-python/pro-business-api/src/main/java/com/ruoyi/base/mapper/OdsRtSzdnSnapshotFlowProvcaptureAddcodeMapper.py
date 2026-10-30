# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import OdsRtSzdnSnapshotFlowProvcaptureAddcode

__all__ = ["OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper"]


class OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper(BaseMapper[OdsRtSzdnSnapshotFlowProvcaptureAddcode]):
    """省界抓拍Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<OdsRtSzdnSnapshotFlowProvcaptureAddcode>` → 继承同名泛型基类。
    2) Java 的 `@TableId bigId` 是 `Long`，对应 Python `int`；
       但实体元信息里 `table_id` 写的是列名 `bigId`（驼峰），BaseMapper 以 metadata 为准。
    3) `ByUuidList` 按业务 UUID `datauuid` 过滤（非主键），故不复用 selectBatchIds。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsRtSzdnSnapshotFlowProvcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(self, bigId: int) -> Optional[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍

        :param bigId: 省界抓拍ID
        :return: 省界抓拍

        【Java→Python】`Long bigId` → `int`；复用 BaseMapper 主键查询。
        """
        return self.selectById(bigId)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(self, odsRtSzdnSnapshotFlowProvcaptureAddcode: OdsRtSzdnSnapshotFlowProvcaptureAddcode) -> list[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """查询省界抓拍列表

        :param odsRtSzdnSnapshotFlowProvcaptureAddcode: 省界抓拍
        :return: 省界抓拍集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(odsRtSzdnSnapshotFlowProvcaptureAddcode)

    def selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByUuidList(self, uuidList: list[str]) -> list[OdsRtSzdnSnapshotFlowProvcaptureAddcode]:
        """根据UUID 查询

        :param uuidList: 业务 UUID（datauuid）集合
        :return: 匹配的省界抓拍

        【Java→Python】对应 SQL：
            SELECT * FROM ods_rt_szdn_snapshot_flow_provcapture_addcode WHERE datauuid IN (#{uuidList})
        Java 用 `<foreach>` 展开 IN；Python 用集合成员判断，空列表直接返回空结果。
        """
        if not uuidList:
            return []
        wanted = set(uuidList)
        return self.selectWhere(lambda r: r.datauuid in wanted)
