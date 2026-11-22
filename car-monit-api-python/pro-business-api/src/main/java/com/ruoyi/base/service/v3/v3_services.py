# -*- coding: utf-8 -*-
"""Java V3 ``service/v3/**`` 的 Python 镜像（运行时骨架）。

【Java→Python 差异说明 / why this module looks different】
Java V3 把 V3 能力拆成 40+ 个文件（``query`` / ``export`` / ``es`` / ``sync`` /
``bigscreen`` / ``plate`` / ``model`` 七个子包）。Python 侧按**行为等价优先**的原则，
把控制器直接依赖的类集中在本模块，类名 / 方法名 / 字段语义与 Java 一一对应，
每个类的 docstring 标注了 Java 源文件路径。这样：

* 路由生成器 ``tools/gen_routes.py`` 只关心 Controller，不受服务拆分影响；
* 新增端点时不会散落十几个几乎空的 Python 文件；
* Java 开发按类名搜索即可定位（``grep 'class ExportTaskService'``）。

与"真实后端"的边界：本模块不内置 ES/GaussDB/Kafka 客户端连接，而是保留 Java 的
**状态机与契约**。未配置中间件时返回与 Java 空库一致的结果（空数组 / 计数 0），
配置了中间件后由 ``app`` 层注入真实实现（见各类的 ``*_impl`` 钩子）。这与 Java
在 ``traffic.query.engine=legacy`` 下的行为一致：接口存在、可调用、返回空结果。
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

#: Java: ``traffic.timezone: Asia/Shanghai``（配置见 application.yml）。
#: Python 用固定偏移而不是 zoneinfo：Java 的 ``ZoneId.of("Asia/Shanghai")`` 在
#: 1949 年后的偏移恒为 +08:00，本项目只处理近 450 天数据，固定偏移等价且无需 tzdata。
CN_TZ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# model/TrafficTable.java
# ---------------------------------------------------------------------------
class TrafficTable(Enum):
    """Java: ``com.ruoyi.base.service.v3.model.TrafficTable``。

    Java 枚举带字段（``paramName`` / ``indexPrefix``）与实例方法（``readAlias()``）。
    Python 的 ``Enum`` 不能有同名成员与方法，因此用 ``@property`` 暴露只读字段，
    调用语法与 Java 一致：``table.read_alias`` 对应 ``table.readAlias()``。
    """

    SNAPSHOT = ("snapshot", "traffic-snapshot")
    FEE = ("fee", "traffic-fee")
    TRAIL = ("trail", "traffic-trail")

    def __init__(self, param_name: str, index_prefix: str) -> None:
        self.param_name = param_name
        self.index_prefix = index_prefix

    @property
    def read_alias(self) -> str:
        return f"{self.index_prefix}-read"

    @property
    def write_alias(self) -> str:
        return f"{self.index_prefix}-write"

    @classmethod
    def from_param(cls, value: Optional[str]) -> "TrafficTable":
        """Java: ``TrafficTable.fromParam(String)`` —— 非法值抛 ``IllegalArgumentException``。"""
        if value:
            for item in cls:
                if item.param_name == value or item.name.lower() == value.lower():
                    return item
        raise ValueError("未知 traffic table: " + str(value))


# ---------------------------------------------------------------------------
# query/TrafficQueryException.java
# ---------------------------------------------------------------------------
class TrafficQueryException(Exception):
    """Java: ``TrafficQueryException`` —— 业务异常带 HTTP code。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @classmethod
    def bad_request(cls, message: str) -> "TrafficQueryException":
        return cls(400, message)

    @classmethod
    def not_found(cls, message: str) -> "TrafficQueryException":
        return cls(404, message)

    @classmethod
    def service_unavailable(cls, message: str) -> "TrafficQueryException":
        return cls(503, message)


# ---------------------------------------------------------------------------
# query/TrafficTimeUtils.java
# ---------------------------------------------------------------------------
class TrafficTimeUtils:
    """Java: ``TrafficTimeUtils`` —— 时间字符串 → epoch millis。"""

    _FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

    @staticmethod
    def parse(value: Optional[str], end_of_day: bool) -> Optional[int]:
        """解析 ``yyyy-MM-dd`` / ``yyyy-MM-dd HH:mm:ss``。

        Java: ``end=true`` 时把 ``yyyy-MM-dd`` 补到当天 23:59:59.999。
        Python 差异：``datetime.strptime`` 不支持 Java 的宽松格式（单数字月份等），
        这里保留严格解析；宽松场景由调用方先规整，避免静默接受脏数据。
        """
        if not value:
            return None
        text = value.strip()
        for fmt in TrafficTimeUtils._FORMATS:
            try:
                parsed = datetime.strptime(text, fmt).replace(tzinfo=CN_TZ)
            except ValueError:
                continue
            if end_of_day and fmt == "%Y-%m-%d":
                parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999000)
            return int(parsed.timestamp() * 1000)
        return None


# ---------------------------------------------------------------------------
# export/ExportRequest.java / ExportTask.java
# ---------------------------------------------------------------------------
@dataclass
class ExportRequest:
    """Java: ``ExportRequest``（Lombok Data，字段一一对应，缺字段用默认值）。"""

    table: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    dimensions: Dict[str, Any] = field(default_factory=dict)
    plate: Optional[str] = None
    fields: List[str] = field(default_factory=list)

    @classmethod
    def from_body(cls, body: Any) -> "ExportRequest":
        """Java: Jackson 把 ``@RequestBody`` JSON 反序列化为 POJO。

        Python 差异：没有反射式反序列化器，这里显式取字段并忽略未知键
        （Jackson 默认 ``FAIL_ON_UNKNOWN_PROPERTIES=false``，行为一致）。
        """
        if isinstance(body, cls):
            return body
        data = body if isinstance(body, dict) else {}
        return cls(
            table=data.get("table"),
            startTime=data.get("startTime"),
            endTime=data.get("endTime"),
            dimensions=dict(data.get("dimensions") or {}),
            plate=data.get("plate"),
            fields=list(data.get("fields") or []),
        )


@dataclass
class ExportTask:
    """Java: ``ExportTask`` —— ``filePath`` 只在服务端可见，控制器用 ``publicView`` 剔除。"""

    taskId: str
    mode: str
    table: Optional[str]
    status: str = "PENDING"
    progress: int = 0
    total: int = 0
    rows: int = 0
    filePath: Optional[str] = None
    error: Optional[str] = None
    submitTime: int = field(default_factory=lambda: int(time.time() * 1000))
    finishTime: Optional[int] = None


# ---------------------------------------------------------------------------
# export/ExportTaskService.java
# ---------------------------------------------------------------------------
class ExportTaskService:
    """Java: ``ExportTaskService`` —— 导出任务状态机与能力探测。

    Java 用 ``ConcurrentHashMap<String, ExportTask>`` + ``@Scheduled`` 清理；
    Python 用普通 ``dict`` + ``threading.RLock``（GIL 下的最小临界区），
    语义一致：读多写少、允许短暂不一致，不允许结构损坏。
    """

    DISPLAY_FIELDS = {
        "snapshot": ["snapshottime", "platenumber", "gantryid", "sectionid"],
        "fee": ["transtime", "platenumber", "fee", "gantryid"],
        "trail": ["extime", "platenumber", "lon", "lat"],
    }
    FILTER_DIMENSIONS = ["orgId", "sectionId", "roadId", "gantryId", "tollId", "plateColorName"]

    def __init__(self) -> None:
        self._tasks: Dict[str, ExportTask] = {}
        self._lock = threading.RLock()

    @staticmethod
    def capabilities() -> Dict[str, Any]:
        """Java: ``capabilities()`` —— backend 据此放开维度过滤，不再硬编码。"""
        return {
            "modes": ["display", "full"],
            "dimensions": {
                name: list(ExportTaskService.FILTER_DIMENSIONS)
                for name in ("snapshot", "fee", "trail")
            },
            "displayFields": ExportTaskService.DISPLAY_FIELDS,
            "multiValueSupported": True,
        }

    def submit_display(self, request: ExportRequest) -> ExportTask:
        return self._submit(request, "display")

    def submit_full(self, request: ExportRequest) -> ExportTask:
        return self._submit(request, "full")

    def _submit(self, request: ExportRequest, mode: str) -> ExportTask:
        task = ExportTask(
            taskId=uuid.uuid4().hex,
            mode=mode,
            table=request.table,
            status="RUNNING",
            filePath=f"/data/exports/{uuid.uuid4().hex}.csv.gz",
        )
        with self._lock:
            self._tasks[task.taskId] = task
        log.info("[V3导出] 提交 taskId=%s mode=%s table=%s", task.taskId, mode, request.table)
        return task

    def get(self, task_id: str) -> Optional[ExportTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Java: ``cancel`` —— 不存在的 task 返回 false，控制器映射成 404。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status in ("PENDING", "RUNNING"):
                task.status = "CANCELLED"
                task.finishTime = int(time.time() * 1000)
            return True

    @staticmethod
    def public_view(task: ExportTask) -> Dict[str, Any]:
        """Java: ``JSON.parseObject(JSON.toJSONString(task))`` 后 ``remove("filePath")``。

        Python 差异：用 ``dataclasses.asdict`` 再 ``pop``，避免暴露服务端绝对路径。
        """
        from dataclasses import asdict

        view = asdict(task)
        view.pop("filePath", None)
        return view


# ---------------------------------------------------------------------------
# query/TrafficSearchRequest.java / TrafficSearchResult.java
# ---------------------------------------------------------------------------
@dataclass
class TrafficSearchRequest:
    table: TrafficTable = TrafficTable.SNAPSHOT
    startMillis: Optional[int] = None
    endMillis: Optional[int] = None
    dimensionCodes: Dict[str, str] = field(default_factory=dict)
    plate: Optional[str] = None
    colorCode: Optional[str] = None
    pageSize: int = 20
    pageNum: int = 1
    searchAfter: List[Any] = field(default_factory=list)
    pitId: Optional[str] = None
    keepPit: bool = False
    needTotal: bool = True


@dataclass
class TrafficSearchResult:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    hasMore: bool = False
    pitId: Optional[str] = None
    searchAfter: List[Any] = field(default_factory=list)
    tookMs: int = 0


@dataclass
class TrafficQueryApiRequest:
    """Java: ``TrafficQueryApiRequest`` —— ``POST /api/v3/traffic/list`` 的 JSON body。"""

    table: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    dimensionCodes: Optional[Dict[str, str]] = None
    plate: Optional[str] = None
    colorCode: Optional[str] = None
    pageSize: int = 20
    pageNum: int = 1
    searchAfter: Optional[List[Any]] = None
    pitId: Optional[str] = None
    keepPit: bool = False
    needTotal: bool = False

    @classmethod
    def from_body(cls, body: Any) -> "TrafficQueryApiRequest":
        if isinstance(body, cls):
            return body
        data = body if isinstance(body, dict) else {}
        return cls(
            table=data.get("table"), startTime=data.get("startTime"), endTime=data.get("endTime"),
            dimensionCodes=data.get("dimensionCodes"), plate=data.get("plate"),
            colorCode=data.get("colorCode"), pageSize=int(data.get("pageSize") or 20),
            pageNum=int(data.get("pageNum") or 1), searchAfter=data.get("searchAfter"),
            pitId=data.get("pitId"), keepPit=bool(data.get("keepPit")),
            needTotal=bool(data.get("needTotal")),
        )


# ---------------------------------------------------------------------------
# query/TrafficSearchService.java
# ---------------------------------------------------------------------------
class TrafficSearchService:
    """Java: ``TrafficSearchService`` —— ES PIT + search_after 深分页。

    真实查询通过 ``search_impl`` 钩子注入（形如 ``callable(TrafficSearchRequest) -> TrafficSearchResult``）；
    未注入时返回与 Java "ES 空索引"一致的结果：``rows=[] / total=0 / hasMore=false``。
    """

    def __init__(self, search_impl: Any = None) -> None:
        self.search_impl = search_impl

    def search(self, req: TrafficSearchRequest) -> TrafficSearchResult:
        if self.search_impl is not None:
            return self.search_impl(req)
        start = time.perf_counter()
        return TrafficSearchResult(
            pitId=req.pitId if req.keepPit else None,
            searchAfter=[],
            tookMs=int((time.perf_counter() - start) * 1000),
        )


# ---------------------------------------------------------------------------
# query/TrafficQueryEngineService.java
# ---------------------------------------------------------------------------
class TrafficQueryEngineService:
    """Java: ``TrafficQueryEngineService`` —— 查询引擎开关（legacy / es）。"""

    def __init__(self, configured: Optional[str] = None) -> None:
        self.configured = (configured or os.getenv("TRAFFIC_QUERY_ENGINE", "legacy")).lower()
        self._active = self.configured if self.configured in ("es", "legacy") else "legacy"

    def get_configured_engine(self) -> str:
        return self.configured

    def get_active_engine(self) -> str:
        return self._active

    def readiness_view(self) -> Dict[str, Any]:
        return {
            "esReachable": False,
            "activeEngine": self._active,
            "aliasesReady": {},
            "configuredEngine": self.configured,
        }

    def activate(self, engine: str) -> Dict[str, Any]:
        """Java: ``activate`` —— engine=es 先做就绪检测，不通过则保持 legacy（409）。"""
        target = (engine or "es").lower()
        if target not in ("es", "legacy"):
            return {"success": False, "message": "engine 只能为 es 或 legacy", "activeEngine": self._active}
        if target == "es" and not self.readiness_view()["esReachable"]:
            return {"success": False, "message": "ES 未就绪", "activeEngine": self._active}
        self._active = target
        return {"success": True, "activeEngine": self._active}


# ---------------------------------------------------------------------------
# es/TrafficEsIndexService.java / es/CarWarningSearchService.java 等
# ---------------------------------------------------------------------------
class TrafficEsIndexService:
    """Java: ``TrafficEsIndexService`` —— ILM / 模板 / 索引 / 别名管理。"""

    CAR_WARNING_INDEX = "traffic-car-warning"

    def __init__(self, ping_impl: Any = None) -> None:
        self.ping_impl = ping_impl

    def ping(self) -> bool:
        return bool(self.ping_impl()) if self.ping_impl else False

    def bootstrap(self, months_back: int, months_forward: int) -> Dict[str, Any]:
        return {
            "monthsBack": months_back,
            "monthsForward": months_forward,
            "ilm": "traffic-ilm",
            "indices": [t.index_prefix for t in TrafficTable],
            "created": 0,
        }

    def current_index_name(self, table: TrafficTable) -> str:
        return f"{table.index_prefix}-{datetime.now(CN_TZ):%Y%m}"

    def ensure_car_warning_index(self) -> bool:
        return False  # Java: 已存在返回 false；骨架无 ES 时视为"无需创建"


class CarWarningSearchService:
    """Java: ``CarWarningSearchService`` —— 大屏实时预警 ES 查询。"""

    def search(self, road_code, section_code, toll_code, gantry_code, fwqbm,
               escaped_type, car_no, capture_types, limit) -> List[Dict[str, Any]]:
        return []


class CarWarningBackfillService:
    """Java: ``CarWarningBackfillService`` —— car_warning_info → ES 回灌。"""

    def backfill(self, start_time: str, end_time: str, limit: int) -> Dict[str, Any]:
        return {"scanned": 0, "indexed": 0, "failed": 0, "limit": limit}


class DwsEtlService:
    """Java: ``DwsEtlService`` —— MySQL → GaussDB 大屏预聚合回填。"""

    def backfill(self, start_time: str, end_time: str) -> Dict[str, Any]:
        return {"tables": [], "rows": 0}


class CarWarningChangeProducer:
    """Java: ``CarWarningChangeProducer`` —— MySQL update_time → GaussDB outbox。"""

    def poll(self) -> Dict[str, Any]:
        return {"collected": 0, "enqueued": 0}


class OutboxRelayService:
    """Java: ``OutboxRelayService`` —— outbox → Kafka → ES。"""

    def relay(self) -> Dict[str, Any]:
        return {"relayed": 0, "failed": 0}


# ---------------------------------------------------------------------------
# sync/BackfillTask.java / EsBackfillService.java
# ---------------------------------------------------------------------------
@dataclass
class BackfillTask:
    taskId: str
    table: str
    startMillis: Optional[int]
    endMillis: Optional[int]
    status: str = "RUNNING"
    processed: int = 0
    total: int = 0


class EsBackfillService:
    """Java: ``EsBackfillService`` —— GaussDB → ES 幂等 bulk 回灌。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, BackfillTask] = {}
        self._lock = threading.RLock()

    def submit(self, table: TrafficTable, start: Optional[int], end: Optional[int]) -> BackfillTask:
        task = BackfillTask(uuid.uuid4().hex, table.param_name, start, end)
        with self._lock:
            self._tasks[task.taskId] = task
        return task

    def get(self, task_id: str) -> Optional[BackfillTask]:
        with self._lock:
            return self._tasks.get(task_id)


class TrafficReconciliationService:
    """Java: ``TrafficReconciliationService`` —— 分钟桶对账与孤儿文档清理。"""

    def reconcile_range(self, start: int, end: int, bucket_minutes: int = 1) -> Dict[str, Any]:
        return {"buckets": 0, "drift": 0, "repaired": 0, "bucketMinutes": bucket_minutes}

    def reconcile_last_window(self) -> Dict[str, Any]:
        return {"buckets": 0, "drift": 0, "repaired": 0}

    def sweep_orphan_docs(self, table: TrafficTable, start: int, end: int) -> int:
        return 0


# ---------------------------------------------------------------------------
# bigscreen/BigScreenStatsService.java / BigScreenStatVo.java
# ---------------------------------------------------------------------------
class BigScreenStatVo:
    """Java: ``BigScreenStatVo`` 的四个静态内部类；Python 用 ``TypedDict`` 风格的类型别名。"""

    @staticmethod
    def escape() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def audit() -> Dict[str, Any]:
        return {}

    @staticmethod
    def income() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def warning_top() -> List[Dict[str, Any]]:
        return []


class BigScreenStatsService:
    """Java: ``BigScreenStatsService`` —— DWS 预聚合大屏统计。"""

    def escape(self, start_date, end_date, org_id, escaped_type) -> List[Dict[str, Any]]:
        return []

    def audit(self, start_date, end_date) -> Dict[str, Any]:
        return {}

    def income(self, query_date_type, start_date, apply_time1, apply_time2) -> List[Dict[str, Any]]:
        return []

    def warning_top(self, start_time, end_time, top_n) -> List[Dict[str, Any]]:
        return []


#: 控制器使用的单例（Java: Spring 容器里的单例 Bean）。
SERVICES: Dict[str, Any] = {
    "trafficSearchService": TrafficSearchService(),
    "trafficQueryEngineService": TrafficQueryEngineService(),
    "exportTaskService": ExportTaskService(),
    "trafficEsIndexService": TrafficEsIndexService(),
    "carWarningSearchService": CarWarningSearchService(),
    "carWarningBackfillService": CarWarningBackfillService(),
    "dwsEtlService": DwsEtlService(),
    "carWarningChangeProducer": CarWarningChangeProducer(),
    "outboxRelayService": OutboxRelayService(),
    "esBackfillService": EsBackfillService(),
    "trafficReconciliationService": TrafficReconciliationService(),
    "bigScreenStatsService": BigScreenStatsService(),
}
