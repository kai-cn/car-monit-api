# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.v3.TrafficQueryV3Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/v3/TrafficQueryV3Controller.java

【Java→Python 差异】
1) Java 的构造器注入 ``public TrafficQueryV3Controller(TrafficSearchService)`` 在 Spring
   里由容器完成；Python 侧注册表用无参构造，因此这里提供默认参数并从 ``SERVICES``
   单例表取 Bean（等价的"单例注入"）。
2) ``new LinkedHashMap<>()`` → Python ``dict``（3.7+ 保序），响应字段顺序与 Java 一致。
3) ``api.getDimensionCodes() != null`` → Python ``is not None``；``putAll`` → ``update``。
4) ``api.isKeepPit()`` / ``isNeedTotal()`` 是 Lombok boolean getter → Python 实例属性。
5) ``catch (TrafficQueryException e)`` 与 ``catch (Exception e)`` → 两个 ``except``；
   Java 的 ``log.error("[V3查询] 异常", e)`` 末参是 Throwable →
   ``log.error(..., exc_info=True)``。
6) Java 返回 ``Map<String,Object>``（裸 JSON），Python 返回 ``dict``，由 registry 的
   ``JacksonResponse`` 序列化，形状一致。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from com.ruoyi.base.service.v3.v3_services import (
    SERVICES,
    TrafficQueryApiRequest,
    TrafficQueryException,
    TrafficQueryEngineService,
    TrafficSearchRequest,
    TrafficSearchService,
    TrafficTable,
    TrafficTimeUtils,
)

__all__ = ["TrafficQueryV3Controller"]

log = logging.getLogger(__name__)


class TrafficQueryV3Controller(object):
    """V3 组合查询接口（PIT + search_after）—— 深分页/导出游标，不在 ES 故障时回退。"""

    # Java: @RequestMapping("/api/v3/traffic")
    BASE_PATH = "/api/v3/traffic"

    def __init__(self, searchService: Optional[TrafficSearchService] = None,
                 queryEngineService: Optional[TrafficQueryEngineService] = None) -> None:
        self.searchService = searchService or SERVICES["trafficSearchService"]
        self.queryEngineService = queryEngineService or SERVICES["trafficQueryEngineService"]

    def list(self, api: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /api/v3/traffic/list —— Java 方法名 ``list``，在 Python 里遮蔽内置同名人不是问题。"""
        request: TrafficQueryApiRequest = TrafficQueryApiRequest.from_body(api)
        response: Dict[str, Any] = {}
        try:
            req = TrafficSearchRequest()
            req.table = TrafficTable.from_param(request.table)
            req.startMillis = TrafficTimeUtils.parse(request.startTime, False)
            req.endMillis = TrafficTimeUtils.parse(request.endTime, True)
            if request.dimensionCodes is not None:
                req.dimensionCodes.update(request.dimensionCodes)
            req.plate = request.plate
            req.colorCode = request.colorCode
            req.pageSize = request.pageSize
            req.pageNum = request.pageNum
            deep = bool(request.searchAfter)
            req.searchAfter = list(request.searchAfter) if deep else []
            req.pitId = request.pitId
            # P1-4：仅深分页或显式要求时保留 PIT，避免每个请求遗留 2 分钟上下文。
            req.keepPit = deep or request.keepPit
            req.needTotal = (not deep) and request.needTotal

            result = self.searchService.search(req)
            response["code"] = 200
            response["message"] = "ok"
            response["rows"] = result.rows
            response["total"] = result.total
            response["hasMore"] = result.hasMore
            response["pitId"] = result.pitId
            response["searchAfter"] = result.searchAfter
            response["tookMs"] = result.tookMs
        except TrafficQueryException as e:
            response["code"] = e.code
            response["message"] = e.message
            response["rows"] = []
            response["total"] = 0
        except Exception as e:
            log.error("[V3查询] 异常", exc_info=True)
            response["code"] = 500
            response["message"] = str(e)
            response["rows"] = []
            response["total"] = 0
        return response
