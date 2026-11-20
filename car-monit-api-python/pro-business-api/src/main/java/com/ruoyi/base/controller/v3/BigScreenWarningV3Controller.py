# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.v3.BigScreenWarningV3Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/v3/BigScreenWarningV3Controller.java

【Java→Python 差异】
1) ``private List<String> parseCaptureTypes(String)`` 里 Java 用 ``String.split(",")``
   （正则）→ Python ``str.split(",")``（字面量）。两者对普通逗号一致；Java 对
   正则特殊字符有语义差异，但这里 token 是固定哨兵值，无影响。
2) ``if (!result.contains(token)) result.add(token)`` → Python ``if token not in result``。
3) ``String.join(",", captureTypes)`` → ``",".join(captureTypes)``。
4) ``HttpStatus.resolve(e.getCode())`` → Python 直接把 ``code`` 放回 body（见 registry 约定）。
5) Java 的 ``logger.warn("[V3预警] 查询失败: {}", e.getMessage())`` → Python
   ``log.warning("[V3预警] 查询失败: %s", e.message)``（占位符风格差异）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from com.ruoyi.base.service.v3.v3_services import (
    SERVICES,
    CarWarningSearchService,
    TrafficQueryException,
)

__all__ = ["BigScreenWarningV3Controller"]

log = logging.getLogger(__name__)

#: Java: ``isCaptureType`` 的三个字面量哨兵，来自旧前端 ``type`` 选择但没选具体编码的情况。
CAPTURE_TYPES = ("StationCapture", "GantryCapture", "ServiceAreaCapture")


class BigScreenWarningV3Controller(object):
    """大屏实时预警列表（backend → api），返回裸 JSON 数组。"""

    BASE_PATH = "/api/v1/bigscreen"

    def __init__(self, warningSearchService: Optional[CarWarningSearchService] = None) -> None:
        self.warningSearchService = warningSearchService or SERVICES["carWarningSearchService"]

    def warningList(self, roadCode: Optional[str] = None, sectionCode: Optional[str] = None,
                    tollCode: Optional[str] = None, gantryCode: Optional[str] = None,
                    fwqbm: Optional[str] = None, escapedType: Optional[str] = None,
                    carNo: Optional[str] = None, captureType: Optional[str] = None,
                    limit: int = 100) -> Any:
        """GET /api/v1/bigscreen/warning/list —— 9 个参数，与 Java 签名逐一对应。"""
        try:
            capture_types = self.parse_capture_types(captureType)
            tollCode = self.strip_capture_type_sentinel(tollCode, capture_types)
            gantryCode = self.strip_capture_type_sentinel(gantryCode, capture_types)
            fwqbm = self.strip_capture_type_sentinel(fwqbm, capture_types)

            rows = self.warningSearchService.search(
                roadCode, sectionCode, tollCode, gantryCode, fwqbm, escapedType, carNo,
                ",".join(capture_types) if capture_types else None, limit)
            return rows
        except TrafficQueryException as e:
            log.warning("[V3预警] 查询失败: %s", e.message)
            return {"code": e.code, "message": e.message, "data": []}
        except Exception:
            log.error("[V3预警] 未预期异常", exc_info=True)
            return {"code": 500, "message": "预警列表查询失败", "data": []}

    @staticmethod
    def strip_capture_type_sentinel(value: Optional[str], capture_types: List[str]) -> Optional[str]:
        """Java: ``stripCaptureTypeSentinel`` —— 从维度编码里摘出哨兵；全被摘空则返回 None。"""
        if value is None or not value.strip():
            return value
        keep: List[str] = []
        for item in value.split(","):
            token = (item or "").strip()
            if not token:
                continue
            if token in CAPTURE_TYPES:
                BigScreenWarningV3Controller._add_capture_types(capture_types, token)
            else:
                keep.append(token)
        return ",".join(keep) if keep else None

    @staticmethod
    def parse_capture_types(capture_type: Optional[str]) -> List[str]:
        """Java: ``parseCaptureTypes`` —— 非法值直接 400（不静默返回全量）。"""
        result: List[str] = []
        if capture_type is None or not capture_type.strip():
            return result
        for item in capture_type.split(","):
            token = (item or "").strip()
            if not token:
                continue
            if token not in CAPTURE_TYPES:
                raise TrafficQueryException.bad_request(
                    "captureType 非法: " + token
                    + "，允许值: StationCapture/GantryCapture/ServiceAreaCapture")
            if token not in result:
                result.append(token)
        return result

    @staticmethod
    def _add_capture_types(capture_types: List[str], value: Optional[str]) -> None:
        if value is None:
            return
        for item in value.split(","):
            token = (item or "").strip()
            if token in CAPTURE_TYPES and token not in capture_types:
                capture_types.append(token)

    # ---- Java 方法名别名（保持方法级 parity；Python 内部用 snake_case 实现） ----
    @classmethod
    def stripCaptureTypeSentinel(cls, value: Optional[str], capture_types: List[str]) -> Optional[str]:
        """Java: ``stripCaptureTypeSentinel`` —— 别名，见 :meth:`strip_capture_type_sentinel`。"""
        return cls.strip_capture_type_sentinel(value, capture_types)

    @classmethod
    def parseCaptureTypes(cls, capture_type: Optional[str]) -> List[str]:
        """Java: ``parseCaptureTypes`` —— 别名，见 :meth:`parse_capture_types`。"""
        return cls.parse_capture_types(capture_type)

    @classmethod
    def addCaptureTypes(cls, capture_types: List[str], value: Optional[str]) -> None:
        """Java: ``addCaptureTypes`` —— 别名，见 :meth:`_add_capture_types`。"""
        cls._add_capture_types(capture_types, value)

    @staticmethod
    def isCaptureType(token: str) -> bool:
        """Java: ``isCaptureType(String)`` —— 三个哨兵值之一。"""
        return token in CAPTURE_TYPES
