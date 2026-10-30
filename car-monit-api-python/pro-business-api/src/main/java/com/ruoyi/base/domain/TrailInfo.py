# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.TrailInfo

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/TrailInfo.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class TrailInfo(JavaBean):
    """TrailInfo

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) ``tracks`` / ``trailList`` **保留具体类型**（不像 TrailBo 的包级私有字段
       那样退化为 Any）：Jackson 反序列化 ``@RequestBody TrailInfo`` 时会
       递归构造 ``ZdataTrailTracks`` 和每个 ``TrailBo``，
       ``SysUtilController#changeTrailInfo`` 直接在它们身上调 getter。
       嵌套绑定由 ``app.web.binding.coerce`` 的 dataclass 分支完成。
    """
    trail_uuid: Optional[str] = None  # Java: private String trailUuid; // 轨迹ID

    enter_time: Optional[datetime] = None  # Java: private Date enterTime; // 进入时间（分区键，月度分区粒度）

    tracks: Optional[ZdataTrailTracks] = None  # Java: private ZdataTrailTracks tracks; // 轨迹对象

    trail_list: Optional[List[TrailBo]] = None  # Java: private List<TrailBo> trailList; // 轨迹详情

