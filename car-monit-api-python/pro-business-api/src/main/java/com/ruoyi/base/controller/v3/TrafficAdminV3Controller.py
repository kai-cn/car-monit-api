# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.v3.TrafficAdminV3Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/v3/TrafficAdminV3Controller.java

【Java→Python 差异 / 安全边界】
1) Java 的 ``InternalEndpointGuardConfig`` 是 Servlet Filter，按路径拦截；Python 侧
   由 ``app/middleware/internal_guard.py`` 实现（ASGI 中间件），见该文件说明。
2) ``@RequestParam(defaultValue="13") int monthsBack`` → Python ``monthsBack: int = 13``。
   registry 的绑定器会把 query string 的字符串转成 int（Java Spring 同样转换）。
3) ``result.putAll(activation)`` → ``result.update(activation)``。
4) Java ``TrafficTable.values()`` → Python ``for table in TrafficTable``（Enum 可迭代）。
5) ``Boolean.TRUE.equals(activation.get("success"))`` → Python ``is True``（避免 1 == True 的坑）。
6) 13 个端点全部返回 ``Map<String,Object>``，Python 返回 ``dict``，字段顺序与 Java 一致。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from com.ruoyi.base.service.v3.v3_services import (
    SERVICES,
    CarWarningBackfillService,
    CarWarningChangeProducer,
    DwsEtlService,
    EsBackfillService,
    OutboxRelayService,
    TrafficEsIndexService,
    TrafficQueryEngineService,
    TrafficReconciliationService,
    TrafficTable,
    TrafficTimeUtils,
)

__all__ = ["TrafficAdminV3Controller"]

log = logging.getLogger(__name__)


class TrafficAdminV3Controller(object):
    """V3 运维接口：ES 初始化、回灌、对账、Outbox relay 手动触发。

    这些端点可切换查询引擎、触发重负载回灌、删除 ES 孤儿文档，必须受内部端点守卫保护
    （``X-Internal-Token`` / 回环地址），与 Java ``InternalEndpointGuardConfig`` 一致。
    """

    BASE_PATH = "/api/v3"

    def __init__(self,
                 indexService: Optional[TrafficEsIndexService] = None,
                 queryEngineService: Optional[TrafficQueryEngineService] = None,
                 backfillService: Optional[EsBackfillService] = None,
                 carWarningBackfillService: Optional[CarWarningBackfillService] = None,
                 dwsEtlService: Optional[DwsEtlService] = None,
                 carWarningChangeProducer: Optional[CarWarningChangeProducer] = None,
                 reconciliationService: Optional[TrafficReconciliationService] = None,
                 outboxRelayService: Optional[OutboxRelayService] = None) -> None:
        self.indexService = indexService or SERVICES["trafficEsIndexService"]
        self.queryEngineService = queryEngineService or SERVICES["trafficQueryEngineService"]
        self.backfillService = backfillService or SERVICES["esBackfillService"]
        self.carWarningBackfillService = carWarningBackfillService or SERVICES["carWarningBackfillService"]
        self.dwsEtlService = dwsEtlService or SERVICES["dwsEtlService"]
        self.carWarningChangeProducer = carWarningChangeProducer or SERVICES["carWarningChangeProducer"]
        self.reconciliationService = reconciliationService or SERVICES["trafficReconciliationService"]
        self.outboxRelayService = outboxRelayService or SERVICES["outboxRelayService"]

    # ---- ES ----------
    def bootstrap(self, monthsBack: int = 13, monthsForward: int = 1) -> Dict[str, Any]:
        """POST /api/v3/es/bootstrap —— 创建 ILM + 模板 + 最近 N 个月索引/别名（幂等）。"""
        result: Dict[str, Any] = {}
        try:
            result["code"] = 200
            result["message"] = "ok"
            result["data"] = self.indexService.bootstrap(monthsBack, monthsForward)
        except Exception as e:
            log.error("[V3运维] ES 初始化失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def esStatus(self) -> Dict[str, Any]:
        """GET /api/v3/es/status"""
        result: Dict[str, Any] = {
            "code": 200,
            "available": self.indexService.ping(),
            "configuredEngine": self.queryEngineService.get_configured_engine(),
            "activeEngine": self.queryEngineService.get_active_engine(),
        }
        indices: Dict[str, Any] = {}
        for table in TrafficTable:
            indices[table.param_name] = {
                "currentIndex": self.indexService.current_index_name(table),
                "readAlias": table.read_alias,
                "writeAlias": table.write_alias,
            }
        result["indices"] = indices
        return result

    def readiness(self) -> Dict[str, Any]:
        """GET /api/v3/es/readiness"""
        return {"code": 200, "data": self.queryEngineService.readiness_view()}

    def activate(self, engine: str = "es") -> Dict[str, Any]:
        """POST /api/v3/es/activate —— engine=es 先就绪检测，不通过保持 legacy（409）。"""
        activation = self.queryEngineService.activate(engine)
        result: Dict[str, Any] = {
            "code": 200 if activation.get("success") is True else 409,
        }
        result.update(activation)
        return result

    def bootstrapCarWarning(self) -> Dict[str, Any]:
        """POST /api/v3/es/car-warning/bootstrap"""
        result: Dict[str, Any] = {}
        try:
            created = self.indexService.ensure_car_warning_index()
            result["code"] = 200
            result["index"] = TrafficEsIndexService.CAR_WARNING_INDEX
            result["status"] = "created" if created else "exists"
        except Exception as e:
            log.error("[V3运维] car-warning 索引创建失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    # ---- Sync ----------
    def backfillCarWarning(self, startTime: Optional[str] = None, endTime: Optional[str] = None,
                           limit: int = 1000) -> Dict[str, Any]:
        """POST /api/v3/sync/car-warning/backfill"""
        result: Dict[str, Any] = {}
        try:
            result["code"] = 200
            result["message"] = "car-warning 回灌完成"
            result["data"] = self.carWarningBackfillService.backfill(startTime, endTime, limit)
        except Exception as e:
            log.error("[V3运维] car-warning 回灌失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def backfillDws(self, startTime: Optional[str] = None, endTime: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v3/sync/dws/backfill"""
        result: Dict[str, Any] = {}
        try:
            result["code"] = 200
            result["message"] = "DWS 回填完成"
            result["data"] = self.dwsEtlService.backfill(startTime, endTime)
        except Exception as e:
            log.error("[V3运维] DWS 回填失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def pollCarWarningOutbox(self) -> Dict[str, Any]:
        """POST /api/v3/sync/car-warning/outbox/poll"""
        result: Dict[str, Any] = {}
        try:
            result["code"] = 200
            result["message"] = "car-warning 增量采集完成"
            result["data"] = self.carWarningChangeProducer.poll()
        except Exception as e:
            log.error("[V3运维] car-warning 增量采集失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def backfill(self, table: Optional[str] = None, startTime: Optional[str] = None,
                 endTime: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v3/sync/backfill"""
        result: Dict[str, Any] = {}
        try:
            parsed_table = TrafficTable.from_param(table)
            start = TrafficTimeUtils.parse(startTime, False)
            end = TrafficTimeUtils.parse(endTime, True)
            task = self.backfillService.submit(parsed_table, start, end)
            result["code"] = 200
            result["message"] = "回灌任务已提交"
            result["taskId"] = task.taskId
            result["table"] = parsed_table.param_name
        except Exception as e:
            log.error("[V3运维] 回灌提交失败", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def backfillStatus(self, taskId: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v3/sync/backfill/status/{taskId}"""
        task = self.backfillService.get(taskId or "")
        if task is None:
            return {"code": 404, "message": "task not found"}
        return {"code": 200, "data": task}

    def reconcile(self, startTime: Optional[str] = None, endTime: Optional[str] = None,
                  bucketMinutes: int = 0) -> Dict[str, Any]:
        """POST /api/v3/sync/reconcile"""
        result: Dict[str, Any] = {}
        try:
            if startTime is not None and endTime is not None:
                start = TrafficTimeUtils.parse(startTime, False)
                end = TrafficTimeUtils.parse(endTime, True)
                if start is None or end is None:
                    raise ValueError("时间格式非法，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss")
                summary = (self.reconciliationService.reconcile_range(start, end, bucketMinutes)
                           if bucketMinutes > 0
                           else self.reconciliationService.reconcile_range(start, end))
            else:
                summary = self.reconciliationService.reconcile_last_window()
            result["code"] = 200
            result["message"] = "对账完成"
            result["data"] = summary
        except Exception as e:
            log.error("[V3运维] 手工对账失败", exc_info=True)
            result["code"] = 400
            result["message"] = str(e)
        return result

    def relay(self) -> Dict[str, Any]:
        """POST /api/v3/sync/outbox/relay —— 需 ``traffic.sync.enabled=true``。"""
        self.outboxRelayService.relay()
        return {"code": 200, "message": "relay 已执行一次"}

    def sweepOrphans(self, table: Optional[str] = None, startTime: Optional[str] = None,
                     endTime: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v3/sync/reconcile/orphans"""
        result: Dict[str, Any] = {}
        try:
            parsed_table = TrafficTable.from_param(table)
            start = TrafficTimeUtils.parse(startTime, False)
            end = TrafficTimeUtils.parse(endTime, True)
            if start is None or end is None:
                raise ValueError("时间格式非法，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss")
            deleted = self.reconciliationService.sweep_orphan_docs(parsed_table, start, end)
            result["code"] = 200
            result["message"] = "孤儿文档清理完成"
            result["table"] = parsed_table.param_name
            result["deleted"] = deleted
        except Exception as e:
            log.error("[V3运维] 孤儿清理失败", exc_info=True)
            result["code"] = 400
            result["message"] = str(e)
        return result
