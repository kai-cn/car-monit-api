# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.SuspiciousCarVO

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/SuspiciousCarVO.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class SuspiciousCarVO(JavaBean):
    """SuspiciousCarVO

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) 【易遗漏】Java 源 L27 的 `List<TrailInfo> trailInfoList = new ArrayList<>();`
       **无 private 修饰符**，但 Lombok @Data 仍会生成 getter/setter，必须保留。
       元素类型用 Any（TrailInfo 反向依赖本模块，避免循环 import）。
    """
    signature_key: Optional[str] = None  # Java: private String signatureKey; // 签名key

    time_stamp: Optional[int] = None  # Java: private Long timeStamp; // 时间戳

    signature: Optional[str] = None  # Java: private String signature; // 签名

    # Java: List<TrailInfo> trailInfoList = new ArrayList<>();（默认空列表，非 null）
    trail_info_list: list[Any] = field(default_factory=list)  # Java: List<TrailInfo> trailInfoList;

