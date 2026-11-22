# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.v3.BigScreenStatsV3Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/v3/BigScreenStatsV3Controller.java

【Java→Python 差异】
1) Java 返回 ``ResponseEntity<?>``（状态 + body），Python 侧 registry 统一返回 200，
   因此把 Java 的异常状态码放进 body 的 ``code`` 字段（调用方 backend 读 body.code）。
2) ``HttpStatus.resolve(code)`` → Python 只做 ``code`` 透传；非法 code 回落 500（Java 同）。
3) ``Collections.emptyList()`` → ``[]``。
4) ``@RequestParam(defaultValue="10") int topN`` → Python ``topN: int = 10``。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from com.ruoyi.base.service.v3.v3_services import (
    SERVICES,
    BigScreenStatsService,
    TrafficQueryException,
)

__all__ = ["BigScreenStatsV3Controller"]

log = logging.getLogger(__name__)


class BigScreenStatsV3Controller(object):
    """大屏预聚合查询契约（backend → api）。路径是 ``/api/v1/bigscreen`` 而不是 ``/api/v3``。"""

    BASE_PATH = "/api/v1/bigscreen"

    def __init__(self, statsService: Optional[BigScreenStatsService] = None) -> None:
        self.statsService = statsService or SERVICES["bigScreenStatsService"]

    def escape(self, startDate: Optional[str] = None, endDate: Optional[str] = None,
               orgId: Optional[str] = None, escapedType: Optional[str] = None) -> Any:
        """GET /api/v1/bigscreen/stats/escape —— 返回裸 JSON 数组。"""
        try:
            return self.statsService.escape(startDate, endDate, orgId, escapedType)
        except Exception as e:
            return self._error("escape", e)

    def audit(self, startDate: Optional[str] = None, endDate: Optional[str] = None) -> Any:
        """GET /api/v1/bigscreen/stats/audit —— 返回裸 JSON 对象。"""
        try:
            return self.statsService.audit(startDate, endDate)
        except Exception as e:
            return self._error("audit", e)

    def income(self, queryDateType: Optional[str] = None, startDate: Optional[str] = None,
               applyTime1: Optional[str] = None, applyTime2: Optional[str] = None) -> Any:
        """GET /api/v1/bigscreen/stats/income"""
        try:
            return self.statsService.income(queryDateType, startDate, applyTime1, applyTime2)
        except Exception as e:
            return self._error("income", e)

    def warningTop(self, startTime: Optional[str] = None, endTime: Optional[str] = None,
                   topN: int = 10) -> Any:
        """GET /api/v1/bigscreen/stats/warning-top"""
        try:
            return self.statsService.warning_top(startTime, endTime, topN)
        except Exception as e:
            return self._error("warningTop", e)

    @staticmethod
    def _error(endpoint: str, e: Exception) -> Dict[str, Any]:
        """Java: ``error(String endpoint, Exception e)`` → ResponseEntity(body with code)."""
        if isinstance(e, TrafficQueryException):
            code, message = e.code, e.message
        else:
            log.error("[V3大屏] %s 未预期异常", endpoint, exc_info=True)
            code, message = 500, "大屏预聚合查询失败"
        return {"code": code, "message": message, "data": []}
