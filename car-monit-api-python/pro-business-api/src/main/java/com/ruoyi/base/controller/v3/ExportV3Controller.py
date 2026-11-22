# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.v3.ExportV3Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/v3/ExportV3Controller.java

【Java→Python 差异】
1) ``submitDisplay`` / ``submitFull`` 共用私有 ``submit(request, boolean display)``；
   Python 没有 boolean 重载，直接保留同名私有方法 ``_submit``（下划线是 Python 私有约定）。
2) ``publicView`` 里 Java 用 fastjson2 ``JSON.parseObject(JSON.toJSONString(task))``
   做深拷贝后删 ``filePath``；Python 用 ``dataclasses.asdict`` + ``pop``，避免暴露绝对路径。
3) Java ``JSONObject`` 是无序 Map，Python ``dict`` 3.7+ 保序；字段顺序以 dataclass 为准。
4) 异常分支 Java 统一 ``code=400``；Python 照抄（包括不区分 500 的行为）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from com.ruoyi.base.service.v3.v3_services import (
    SERVICES,
    ExportRequest,
    ExportTask,
    ExportTaskService,
)

__all__ = ["ExportV3Controller"]

log = logging.getLogger(__name__)


class ExportV3Controller(object):
    """V3 导出接口：展示字段（ES PIT）/ 全字段（GaussDB 游标），异步返回 taskId。"""

    # Java: @RequestMapping("/api/v3/export")
    BASE_PATH = "/api/v3/export"

    def __init__(self, exportTaskService: Optional[ExportTaskService] = None) -> None:
        self.exportTaskService = exportTaskService or SERVICES["exportTaskService"]

    def capabilities(self) -> Dict[str, Any]:
        """GET /api/v3/export/capabilities —— backend 据此放开维度过滤，不再硬编码。"""
        return self.exportTaskService.capabilities()

    def submitDisplay(self, request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /api/v3/export/display"""
        return self._submit(ExportRequest.from_body(request), True)

    def submitFull(self, request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /api/v3/export/full"""
        return self._submit(ExportRequest.from_body(request), False)

    def _submit(self, request: ExportRequest, display: bool) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        try:
            task = (self.exportTaskService.submit_display(request) if display
                    else self.exportTaskService.submit_full(request))
            result["code"] = 200
            result["message"] = "导出任务已提交"
            result["data"] = self.public_view(task)
        except Exception as e:
            log.error("[V3导出] 提交失败", exc_info=True)
            result["code"] = 400
            result["message"] = str(e)
        return result

    def status(self, taskId: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v3/export/status/{taskId}"""
        result: Dict[str, Any] = {}
        task = self.exportTaskService.get(taskId or "")
        if task is None:
            result["code"] = 404
            result["message"] = "task not found"
            return result
        result["code"] = 200
        result["data"] = self.public_view(task)
        return result

    @staticmethod
    def public_view(task: ExportTask) -> Dict[str, Any]:
        """Java: ``publicView(ExportTask)`` —— 删除 filePath，不向调用方暴露绝对路径。"""
        return ExportTaskService.public_view(task)

    @staticmethod
    def publicView(task: ExportTask) -> Dict[str, Any]:
        """Java 方法名别名；Python 内部用 ``public_view``（PEP 8）。"""
        return ExportV3Controller.public_view(task)

    def cancel(self, taskId: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v3/export/cancel/{taskId}"""
        ok = self.exportTaskService.cancel(taskId or "")
        return {
            "code": 200 if ok else 404,
            "message": "已请求取消" if ok else "task not found",
        }
