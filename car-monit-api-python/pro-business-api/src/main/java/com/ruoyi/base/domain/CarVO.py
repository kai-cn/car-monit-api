# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.CarVO

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/CarVO.java
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class CarVO(JavaBean):
    """CarVO

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    car_id: Optional[str] = None  # Java: private String carId; // 车牌id

    car_no: Optional[str] = None  # Java: private String carNo; // 车牌号

    track_id: Optional[str] = None  # Java: private String trackId; // 行驶轨迹id

    track_josn: Optional[str] = None  # Java: private String trackJosn; // 行驶轨迹josn

    flag: Optional[str] = None  # Java: private String flag; // 是否有数据

