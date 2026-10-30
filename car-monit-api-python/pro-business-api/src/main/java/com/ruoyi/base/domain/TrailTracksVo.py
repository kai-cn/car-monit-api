# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.TrailTracksVo

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/TrailTracksVo.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class TrailTracksVo(JavaBean, Custom):
    """轨迹数据对象 zdata_trail_tracks

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    plate_key: Optional[str] = None  # Java: private String plateKey; // 车牌唯一标识（可脱敏/加密存储，用于车辆关联）

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    enter_time: Optional[datetime] = None  # Java: private Date enterTime; // 进入时间（分区键，月度分区粒度）

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    exit_time: Optional[datetime] = None  # Java: private Date exitTime; // 离开时间（轨迹结束时间）

    trailpoints: Optional[str] = None  # Java: private String trailpoints; // 轨迹点

    envehicletype: Optional[str] = None  # Java: private String envehicletype; // 车牌型号

