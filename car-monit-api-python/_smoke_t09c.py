# -*- coding: utf-8 -*-
"""t09c 冒烟测试：7 个复杂 Controller。

覆盖要点
1) ProgressiveQueryController：3 个查询接口把 10 个参数逐项写入 QueryRequest、
   ``getDataTable`` 后再把 ``"策略: " + strategy`` 写进 msg；scaleLevel 组装 3 张表的级别。
2) UnifiedQueryController：
   - list() 过滤 ``fuzzyFields.`` 前缀、ds 大小写不敏感、非法 ds → 400、None → 400；
   - 服务抛 ValueError → 400（对应 IllegalArgumentException），抛其它异常 → 500；
   - submitExport() **不**过滤 fuzzyFields（原工程行为，原对象透传）；
   - getExportStatus() 404 / COMPLETED（costSeconds 向零截断）/ FAILED / RUNNING。
3) LargeScaleQueryController：
   - 三表路由到 SNAPSHOT/FEE/TRAIL，dataSource 返回 ``ds.name``；
   - carTrackQueryByCarNo 把 carNo 映射为 platenumber，但**会被 extractFuzzyFields 丢弃**
     （原工程缺陷：key 缺少 ``fuzzyFields.`` 前缀，Java 行为相同）；
   - submitExport() **会**过滤 fuzzyFields（与 Unified 相反，逐源码对齐）；
   - getExportStatus 用 endTime（LargeScale 的 ExportTaskStatus）；
   - triggerFullSync / triggerRepairSync 真正起后台线程（java.lang.Thread 替身），
     triggerIncrementalSync 同步执行。
4) java.lang.Thread 替身：new Thread(runnable).start() / Runnable 对象 / 重复 start 抛错 /
   静态 API（currentThread/sleep）不受影响。
5) SysTest / SysUtil / FeeRecords01 / SnapshotFlowAddcode 的基础路径（syncTrack 入参、
   7 个 updateRedis 调用顺序、车牌下划线拆分、门架名称回填、UUID 回填 32 位）。

前置说明（重要）
``com.ruoyi.base.service.optimization`` 下 13 个服务属于 t10，尚未移植。
本脚本在导入 controller 之前，用 ``sys.modules`` 注入同名**桩模块**，
使 ``from com.ruoyi.base.service.optimization.X import X`` 与真实包结构完全一致。
t10 完成后删除 ``_install_optimization_stubs()`` 的调用即可复用本脚本。

运行：python refactor/_smoke_t09c.py
"""
from __future__ import annotations

import enum
import importlib
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
for _path in (
    ROOT,
    os.path.join(ROOT, "pro-base-common", "src", "main", "java"),
    os.path.join(ROOT, "pro-business-api", "src", "main", "java"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{label} {detail}")
        print(f"  FAIL  {label} {detail}")


def check_eq(label: str, actual, expected) -> None:
    check(label, actual == expected, f"(actual={actual!r}, expected={expected!r})")


def _wait(predicate, timeout: float = 3.0) -> bool:
    """等待后台线程里的调用发生（Java 里 new Thread(...).start() 是异步的）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ======================================================================
# 一、optimization 桩模块（t10 移植前的临时替身）
# ======================================================================

class DataSource(enum.Enum):
    """UnifiedQueryService.DataSource（Java 静态嵌套枚举）。"""
    SNAPSHOT = "SNAPSHOT"
    FEE = "FEE"
    TRAIL = "TRAIL"


class UnifiedQueryService:
    """桩：记录 query 调用，可注入错误。"""

    DataSource = DataSource  # 对齐 Java 的 UnifiedQueryService.DataSource 访问方式

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.rows: list = []
        self.error: Exception | None = None

    def query(self, ds, startTime, endTime, fuzzyFields, pageNum, pageSize):
        self.calls.append(("query", ds, startTime, endTime, dict(fuzzyFields), pageNum, pageSize))
        if self.error is not None:
            raise self.error
        return self.rows


class _UnifiedExportStatus:
    """桩：UnifiedExportService.ExportTaskStatus（有 finishTime / filePaths）。"""

    def __init__(self) -> None:
        self.taskId = "TASK-1"
        self.dataSource = "snapshot"
        self.startTime = ""
        self.endTime = ""
        self.status = "RUNNING"
        self.submitTime = 1000
        self.finishTime = 0
        self.totalExported = 0
        self.filePartCount = 0
        self.errorMessage = None
        self.filePaths: list[str] = []


class UnifiedExportService:
    """桩：提交导出 + 查询状态。"""

    ExportTaskStatus = _UnifiedExportStatus

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.status = None
        self.taskId = "TASK-1"

    def submitExportTask(self, source, startTime, endTime, fuzzyFields):
        self.calls.append(("submitExportTask", source, startTime, endTime, fuzzyFields))
        return self.taskId

    def getExportStatus(self, taskId):
        self.calls.append(("getExportStatus", taskId))
        return self.status


class _LargeExportStatus:
    """桩：LargeScaleQueryService.ExportTaskStatus（有 endTime，无 finishTime）。"""

    def __init__(self) -> None:
        self.taskId = "TASK-2"
        self.status = "RUNNING"
        self.submitTime = 1000
        self.endTime = 0
        self.totalExported = 0
        self.filePartCount = 0
        self.errorMessage = None


class LargeScaleQueryService:
    """桩：统计 / 导出 / 状态。"""

    ExportTaskStatus = _LargeExportStatus

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.stats: dict = {}
        self.taskId = "TASK-2"
        self.status = None
        self.error: Exception | None = None

    def aggregationStats(self, type, startTime, endTime, groupBy, countField, fields, topN):
        self.calls.append(
            ("aggregationStats", type, startTime, endTime, groupBy, countField, dict(fields), topN))
        if self.error is not None:
            raise self.error
        return self.stats

    def submitExportTask(self, type, startTime, endTime, fields):
        self.calls.append(("submitExportTask", type, startTime, endTime, dict(fields)))
        if self.error is not None:
            raise self.error
        return self.taskId

    def getExportStatus(self, taskId):
        self.calls.append(("getExportStatus", taskId))
        return self.status


class LargeScaleDataSyncService:
    """桩：全量 / 增量 / 补同步。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def fullSyncOneYear(self):
        self.calls.append(("fullSyncOneYear",))

    def incrementalSync(self):
        self.calls.append(("incrementalSync",))

    def repairSync(self, ds, startTime, endTime):
        self.calls.append(("repairSync", ds, startTime, endTime))


class DataScaleLevel(enum.Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    HUGE = "HUGE"


class QueryRequest:
    """桩：Java 的 QueryRequest 只有 setter，这里用 __getattr__ 记录字段。"""

    def __init__(self) -> None:
        object.__setattr__(self, "fields", {})

    def __getattr__(self, item: str):
        if item.startswith("set") and len(item) > 3:
            key = item[3].lower() + item[4:]

            def setter(value):
                self.fields[key] = value
                return self

            return setter
        raise AttributeError(f"QueryRequest has no attribute {item}")


class QueryResult:
    def __init__(self, data=None, strategy="") -> None:
        self.data = data if data is not None else []
        self.strategy = strategy

    def getData(self):
        return self.data

    def getStrategy(self):
        return self.strategy


class ProgressiveQueryArchitectureService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.data: list = []
        self.strategy = "ES"
        self.level = DataScaleLevel.LARGE

    def querySnapshotFlow(self, request):
        self.calls.append(("querySnapshotFlow", request))
        return QueryResult(self.data, self.strategy)

    def queryFeeRecords(self, request):
        self.calls.append(("queryFeeRecords", request))
        return QueryResult(self.data, self.strategy)

    def queryTrailFitting(self, request):
        self.calls.append(("queryTrailFitting", request))
        return QueryResult(self.data, self.strategy)

    def detectScaleLevel(self, tableName):
        self.calls.append(("detectScaleLevel", tableName))
        return self.level


def _install_optimization_stubs() -> None:
    """把 5 个桩模块注册到 ``com.ruoyi.base.service.optimization`` 包下。"""
    import com.ruoyi.base.service as service_pkg

    pkg_name = "com.ruoyi.base.service.optimization"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = []  # 声明为包，等价于 Java 的 package
    sys.modules[pkg_name] = pkg
    service_pkg.optimization = pkg

    def _register(module_name: str, **members) -> None:
        full_name = pkg_name + "." + module_name
        module = types.ModuleType(full_name)
        for key, value in members.items():
            setattr(module, key, value)
        sys.modules[full_name] = module
        setattr(pkg, module_name, module)

    _register("UnifiedQueryService",
              DataSource=DataSource, UnifiedQueryService=UnifiedQueryService)
    _register("UnifiedExportService", UnifiedExportService=UnifiedExportService)
    _register("LargeScaleQueryService", LargeScaleQueryService=LargeScaleQueryService)
    _register("LargeScaleDataSyncService",
              LargeScaleDataSyncService=LargeScaleDataSyncService)
    _register("ProgressiveQueryArchitectureService",
              DataScaleLevel=DataScaleLevel,
              QueryRequest=QueryRequest,
              QueryResult=QueryResult,
              ProgressiveQueryArchitectureService=ProgressiveQueryArchitectureService)


# ======================================================================
# 二、通用替身
# ======================================================================

class _AnyStub:
    """任意方法都可调用并记录（返回 None），用于 redisCache / 不关心的 service。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __getattr__(self, name: str):
        def _call(*args, **kwargs):
            self.calls.append((name, args))
            return None

        return _call


def _install_request_context() -> None:
    """给 startPage() 安装假请求上下文（pageNum=2 / pageSize=20）。"""
    from com.ruoyi.common.utils.ServletUtils import (
        RequestContextHolder,
        _HttpServletRequest,
        _ServletRequestAttributes,
    )
    request = _HttpServletRequest(parameters={"pageNum": ["2"], "pageSize": ["20"]})
    RequestContextHolder.setRequestAttributes(_ServletRequestAttributes(request))


def _controller(module_name: str):
    module = importlib.import_module("com.ruoyi.base.controller." + module_name)
    cls = getattr(module, module_name)
    check_eq(f"{module_name}.__all__", list(getattr(module, "__all__")), [module_name])
    return cls


# ======================================================================
# 三、用例
# ======================================================================

def test_progressive_query() -> None:
    print("[ProgressiveQueryController]")
    from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
    from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

    cls = _controller("ProgressiveQueryController")
    stub = ProgressiveQueryArchitectureService()
    stub.data = [{"id": "1"}, {"id": "2"}]
    stub.strategy = "ES_NGRAM"
    controller = cls(stub)

    check_eq("ProgressiveQueryController.BASE_PATH", cls.BASE_PATH, "/progressive")

    for method_name, service_method in (("snapshotFlowList", "querySnapshotFlow"),
                                        ("feeRecordsList", "queryFeeRecords"),
                                        ("trailFittingList", "queryTrailFitting")):
        rsp = getattr(controller, method_name)(
            startTime="2026-01-01 00:00:00", endTime="2026-01-31 23:59:59",
            platenumber="赣A", gantryname="长安", roadname="R", sectionname="S",
            orgname="O", tollname="T", cursor="C", pageSize=5)
        check(f"{method_name} 返回 TableDataInfo", isinstance(rsp, TableDataInfo))
        check_eq(f"{method_name}.msg", rsp.getMsg(), "策略: ES_NGRAM")
        check(f"{method_name}.rows 即服务返回的 data", rsp.getRows() is stub.data)
        called_name, request = stub.calls[-1]
        check_eq(f"{method_name} 调用 {service_method}", called_name, service_method)
        check_eq(f"{method_name} 写入 Request.pageSize", request.fields.get("pageSize"), 5)
        check_eq(f"{method_name} 写入 Request.cursor", request.fields.get("cursor"), "C")
        check_eq(f"{method_name} 写入 Request.tollname", request.fields.get("tollname"), "T")

    ajax = controller.scaleLevel()
    check("scaleLevel 返回 AjaxResult", isinstance(ajax, AjaxResult))
    check_eq("scaleLevel.code", ajax.get("code"), 200)
    levels = ajax.get("data")
    check_eq("scaleLevel 三张表", sorted(levels.keys()),
             ["ods_lwzxsfsj_fee_records_01", "ods_rt_szdn_snapshot_flow_addcode",
              "zdata_trail_fitting"])
    check_eq("scaleLevel 枚举名", levels["zdata_trail_fitting"], "LARGE")

    # 缺省参数构造：不传参时自建服务实例（对应 Spring 注入）
    default_controller = cls(ProgressiveQueryArchitectureService())
    check_eq("ProgressiveQueryController 注入字段名",
             "progressiveQueryService" in vars(default_controller), True)


def test_unified_query() -> None:
    print("[UnifiedQueryController]")
    cls = _controller("UnifiedQueryController")
    query_service = UnifiedQueryService()
    export_service = UnifiedExportService()
    controller = cls(query_service, export_service)

    check_eq("UnifiedQueryController.BASE_PATH", cls.BASE_PATH, "/api/v1/unified")

    # ---- list：正常 ----
    query_service.rows = [{"bigId": "1"}]
    rsp = controller.list(
        "snapshot", "S", "E",
        {"fuzzyFields.platenumber": "赣A", "junk": "x", "fuzzyFields.blank": ""}, 2, 10)
    check_eq("list.code", rsp.get("code"), 200)
    check_eq("list.message", rsp.get("message"), "ok")
    check_eq("list.dataSource 回显原始 ds", rsp.get("dataSource"), "snapshot")
    check_eq("list.pageNum", rsp.get("pageNum"), 2)
    check_eq("list.pageSize", rsp.get("pageSize"), 10)
    check("list.data 即服务返回值", rsp.get("data") is query_service.rows)
    _, ds, _, _, fields, page_num, page_size = query_service.calls[-1]
    check("list 路由到 DataSource.SNAPSHOT", ds is DataSource.SNAPSHOT)
    check_eq("list 过滤 fuzzyFields 前缀", fields, {"platenumber": "赣A"})
    check_eq("list 透传 pageNum/pageSize", (page_num, page_size), (2, 10))

    # ---- list：ds 大小写不敏感 ----
    query_service.calls.clear()
    rsp = controller.list("FEE", "S", "E", None, 1, 20)
    check_eq("list 大小写不敏感 code", rsp.get("code"), 200)
    check("list 大小写不敏感 → FEE", query_service.calls[-1][1] is DataSource.FEE)

    # ---- list：非法 ds / ds 为 None → 400 ----
    query_service.calls.clear()
    rsp = controller.list("bad", "S", "E", None, 1, 20)
    check_eq("list 非法 ds code", rsp.get("code"), 400)
    check_eq("list 非法 ds message", rsp.get("message"),
             "未知数据源: bad, 合法取值: snapshot / fee / trail")
    check_eq("list 非法 ds 不调用服务", len(query_service.calls), 0)

    rsp = controller.list(None, "S", "E", None, 1, 20)
    check_eq("list ds=None code", rsp.get("code"), 400)
    check_eq("list ds=None message", rsp.get("message"), "数据源 {ds} 不能为空")

    # ---- list：服务异常 → 400 / 500 ----
    query_service.error = ValueError("bad window")
    rsp = controller.list("trail", "S", "E", None, 1, 20)
    check_eq("list ValueError → 400", rsp.get("code"), 400)
    check_eq("list ValueError message", rsp.get("message"), "bad window")

    query_service.error = RuntimeError("es down")
    rsp = controller.list("trail", "S", "E", None, 1, 20)
    check_eq("list RuntimeError → 500", rsp.get("code"), 500)
    check_eq("list RuntimeError message", rsp.get("message"), "es down")
    query_service.error = None

    # ---- submitExport：原样透传未过滤的 fuzzyFields（原工程行为） ----
    raw = {"fuzzyFields.platenumber": "赣A"}
    rsp = controller.submitExport("trail", "S", "E", raw)
    check_eq("submitExport.code", rsp.get("code"), 200)
    check_eq("submitExport.taskId", rsp.get("taskId"), "TASK-1")
    check_eq("submitExport.message", rsp.get("message"), "导出任务已提交, 请用 taskId 轮询状态")
    check("submitExport 透传原对象（未过滤）", export_service.calls[-1][4] is raw)
    check("submitExport 路由 TRAIL", export_service.calls[-1][1] is DataSource.TRAIL)

    rsp = controller.submitExport("bad", "S", "E", raw)
    check_eq("submitExport 非法 ds → 400", rsp.get("code"), 400)

    # ---- getExportStatus ----
    export_service.status = None
    rsp = controller.getExportStatus("NOPE")
    check_eq("status 不存在 → 404", rsp.get("code"), 404)
    check_eq("status 不存在 message", rsp.get("message"), "task not found")

    status = _UnifiedExportStatus()
    status.status = "COMPLETED"
    status.submitTime = 1000
    status.finishTime = 6500
    status.totalExported = 123
    status.filePartCount = 2
    status.filePaths = ["part-0.csv", "part-1.csv"]
    export_service.status = status
    rsp = controller.getExportStatus("TASK-1")
    check_eq("status COMPLETED.code", rsp.get("code"), 200)
    check_eq("status COMPLETED.endTime=finishTime", rsp.get("endTime"), 6500)
    check("status COMPLETED.filePaths", rsp.get("filePaths") is status.filePaths)
    check_eq("status COMPLETED.costSeconds 向零截断", rsp.get("costSeconds"), 5)

    status.status = "FAILED"
    status.errorMessage = "磁盘已满"
    rsp = controller.getExportStatus("TASK-1")
    check_eq("status FAILED.errorMessage", rsp.get("errorMessage"), "磁盘已满")
    check("status FAILED 无 endTime", "endTime" not in rsp)

    status.status = "RUNNING"
    rsp = controller.getExportStatus("TASK-1")
    check("status RUNNING 无 endTime/errorMessage",
          "endTime" not in rsp and "errorMessage" not in rsp)


def test_large_scale_query() -> None:
    print("[LargeScaleQueryController]")
    cls = _controller("LargeScaleQueryController")
    unified = UnifiedQueryService()
    large = LargeScaleQueryService()
    sync = LargeScaleDataSyncService()
    controller = cls(unified, large, sync)

    check_eq("LargeScaleQueryController.BASE_PATH", cls.BASE_PATH, "/api/v1/large")

    # ---- 三表模糊查询 ----
    for method_name, ds in (("querySnapshotFlow", DataSource.SNAPSHOT),
                            ("queryFeeRecords", DataSource.FEE),
                            ("queryTrail", DataSource.TRAIL)):
        unified.rows = [{"id": method_name}]
        rsp = getattr(controller, method_name)(
            "S", "E", {"fuzzyFields.platenumber": "赣A", "junk": "1"}, 3, 30)
        check_eq(f"{method_name}.code", rsp.get("code"), 200)
        check_eq(f"{method_name}.dataSource=ds.name()", rsp.get("dataSource"), ds.name)
        check_eq(f"{method_name}.pageNum", rsp.get("pageNum"), 3)
        check("数据源路由正确", unified.calls[-1][1] is ds)
        check_eq(f"{method_name} 过滤 fuzzyFields",
                 unified.calls[-1][4], {"platenumber": "赣A"})

    # ---- 按车牌查轨迹：carNo → platenumber ----
    # 【原工程缺陷】carNo 被放进 key="platenumber"，而 queryByDs 内的 extractFuzzyFields
    # 只保留 "fuzzyFields." 前缀的 key，因此该条件被丢弃 —— 与 Java 行为完全一致，不加修正。
    rsp = controller.queryCarTrackByCarNo("赣A12345", "S", "E", 1, 20)
    check_eq("carTrackQueryByCarNo.dataSource", rsp.get("dataSource"), "TRAIL")
    check_eq("carTrackQueryByCarNo 车牌条件被 extractFuzzyFields 丢弃（原工程缺陷）",
             unified.calls[-1][4], {})

    controller.queryCarTrackByCarNo("", "S", "E", 1, 20)
    check_eq("carTrackQueryByCarNo 空车牌不过滤", unified.calls[-1][4], {})

    # ---- 服务异常 → 500（本类无 400 分支） ----
    unified.error = RuntimeError("es down")
    rsp = controller.queryTrail("S", "E", None, 1, 20)
    check_eq("queryTrail 异常 → 500", rsp.get("code"), 500)
    check_eq("queryTrail 异常 message", rsp.get("message"), "es down")
    unified.error = None

    # ---- 统计 ----
    large.stats = {"赣A": 7}
    rsp = controller.groupByStats(
        "fee", "S", "E", "platenumber", "bigId", {"fuzzyFields.orgname": "南昌"}, 50)
    check_eq("groupByStats.code", rsp.get("code"), 200)
    check_eq("groupByStats.type", rsp.get("type"), "fee")
    check_eq("groupByStats.groupBy", rsp.get("groupBy"), "platenumber")
    check_eq("groupByStats.topN", rsp.get("topN"), 50)
    check("groupByStats.data 即服务返回值", rsp.get("data") is large.stats)
    args = large.calls[-1]
    check_eq("groupByStats 过滤 fuzzyFields", args[6], {"orgname": "南昌"})
    check_eq("groupByStats 透传 countField", args[5], "bigId")

    # ---- 提交导出：**会**过滤 fuzzyFields ----
    raw = {"fuzzyFields.platenumber": "赣A", "junk": "x"}
    rsp = controller.submitExport("trail", "S", "E", raw)
    check_eq("submitExport.code", rsp.get("code"), 200)
    check_eq("submitExport.taskId", rsp.get("taskId"), "TASK-2")
    check_eq("submitExport 过滤后传给服务", large.calls[-1][4], {"platenumber": "赣A"})

    # ---- 导出状态：endTime（不是 finishTime） ----
    large.status = None
    rsp = controller.getExportStatus("NOPE")
    check_eq("status 不存在 → 404", rsp.get("code"), 404)

    status = _LargeExportStatus()
    status.status = "COMPLETED"
    status.endTime = 888
    status.totalExported = 9
    status.filePartCount = 1
    large.status = status
    rsp = controller.getExportStatus("TASK-2")
    check_eq("status.code", rsp.get("code"), 200)
    check_eq("status.endTime 透传", rsp.get("endTime"), 888)
    check_eq("status.totalExported", rsp.get("totalExported"), 9)

    # ---- 同步接口 ----
    rsp = controller.triggerIncrementalSync()
    check_eq("triggerIncrementalSync.code", rsp.get("code"), 200)
    check_eq("triggerIncrementalSync 同步调用", sync.calls[-1], ("incrementalSync",))

    sync.calls.clear()
    rsp = controller.triggerRepairSync("fee", "S", "E")
    check_eq("triggerRepairSync.code", rsp.get("code"), 200)
    check_eq("triggerRepairSync.message", rsp.get("message"),
             "补同步任务已在后台启动 type=fee")
    check("triggerRepairSync 起了后台线程",
          _wait(lambda: any(c[0] == "repairSync" for c in sync.calls)))
    repair = [c for c in sync.calls if c[0] == "repairSync"][-1]
    check("triggerRepairSync type=fee → FEE", repair[1] is DataSource.FEE)
    check_eq("triggerRepairSync 透传时间窗", (repair[2], repair[3]), ("S", "E"))

    sync.calls.clear()
    controller.triggerRepairSync("unknown", "S", "E")
    _wait(lambda: any(c[0] == "repairSync" for c in sync.calls))
    check("triggerRepairSync 未知 type → SNAPSHOT",
          sync.calls[-1][1] is DataSource.SNAPSHOT)

    rsp = controller.triggerFullSync()
    check_eq("triggerFullSync.code", rsp.get("code"), 200)
    check("triggerFullSync 起了后台线程",
          _wait(lambda: any(c[0] == "fullSyncOneYear" for c in sync.calls)))


def test_thread_standin() -> None:
    print("[java.lang.Thread 替身]")
    from java.lang.Thread import Thread

    hits: list = []
    thread = Thread(target=lambda: hits.append("lambda"))
    check_eq("Thread 默认非守护（对齐 Java）", thread.isDaemon(), False)
    thread.start()
    thread.join(2000)
    check_eq("Thread(lambda).start() 执行", hits, ["lambda"])
    check_eq("Thread 执行完 isAlive=False", thread.isAlive(), False)
    check("Thread 自动命名", thread.getName().startswith("Thread-"))

    class _Runnable:
        def run(self):
            hits.append("runnable")

    named = Thread(_Runnable(), "named-thread")
    named.start()
    named.join(2000)
    check_eq("Thread(Runnable).start() 执行", hits[-1], "runnable")
    check_eq("Thread 自定义线程名", named.getName(), "named-thread")

    try:
        named.start()
        check("重复 start 抛 RuntimeError", False)
    except RuntimeError:
        check("重复 start 抛 RuntimeError", True)

    # 静态 API 未受影响
    check("Thread.currentThread().getName() 可用",
          isinstance(Thread.currentThread().getName(), str) and Thread.currentThread().getName() != "")
    Thread.sleep(1)


def test_sys_test() -> None:
    print("[SysTestController]")
    from com.ruoyi.base.domain.CarParaVO import CarParaVO

    cls = _controller("SysTestController")
    sys_util = _AnyStub()
    gantry = _AnyStub()
    gantry_ip = _AnyStub()
    toll_ip = _AnyStub()
    location = _AnyStub()
    fwqjcxx = _AnyStub()
    toll = _AnyStub()
    section = _AnyStub()
    controller = cls(
        redisCache=_AnyStub(),
        odsSzdnGantryIpService=gantry_ip,
        odsSzdnTollStationIpService=toll_ip,
        sysUtilService=sys_util,
        odsSzdnGantryService=gantry,
        zdataLocationDictService=location,
        dwdLcztFwqjcxxService=fwqjcxx,
        threadTaskExecutor=_AnyStub(),
        feeRecords01Service=_AnyStub(),
        odsSzdnTollService=toll,
        sectionService=section)

    check_eq("SysTestController.BASE_PATH", cls.BASE_PATH, "/base/sysutilTest")

    controller.syncCurrentTrack()
    check_eq("syncCurrentTrack 调用 syncTrack", sys_util.calls[-1][0], "syncTrack")
    check("syncCurrentTrack 传入 CarParaVO",
          isinstance(sys_util.calls[-1][1][0], CarParaVO))

    controller.syncBaseInfo()
    order = [
        ("gantry", gantry.calls[-1][0]),
        ("gantryIp", gantry_ip.calls[-1][0]),
        ("tollIp", toll_ip.calls[-1][0]),
        ("location", location.calls[-1][0]),
        ("fwqjcxx", fwqjcxx.calls[-1][0]),
        ("section", section.calls[-1][0]),
        ("toll", toll.calls[-1][0]),
    ]
    check_eq("syncBaseInfo 7 个同步调用", order, [
        ("gantry", "saveGantryRedis"),
        ("gantryIp", "updateRedis"),
        ("tollIp", "updateRedis"),
        ("location", "updateRedis"),
        ("fwqjcxx", "updateRedis"),
        ("section", "updateRedis"),
        ("toll", "updateRedis"),
    ])


def test_sys_util() -> None:
    print("[SysUtilController]")
    from com.ruoyi.base.domain.CarParaVO import CarParaVO
    from com.ruoyi.base.domain.TrailBo import TrailBo
    from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

    class _SysUtilService(_AnyStub):
        def getByTrailBo(self, trailBo):
            self.calls.append(("getByTrailBo", (trailBo,)))
            return trailBo

        def carTrackQueryNew(self, carParaVO):
            self.calls.append(("carTrackQueryNew", (carParaVO,)))
            return []

    cls = _controller("SysUtilController")
    service = _SysUtilService()
    controller = cls(sysUtilService=service, redisCache=_AnyStub())
    check_eq("SysUtilController.BASE_PATH", cls.BASE_PATH, "/base/sysutil")

    _install_request_context()
    rsp = controller.carTrackQueryByCarNo(CarParaVO())
    check("carTrackQueryByCarNo 返回 TableDataInfo", isinstance(rsp, TableDataInfo))
    check_eq("carTrackQueryByCarNo.code", rsp.getCode(), 200)
    check_eq("carTrackQueryByCarNo.msg", rsp.getMsg(), "查询成功")
    check_eq("carTrackQueryByCarNo 空车牌不发查询", rsp.getRows(), [])
    check_eq("carTrackQueryByCarNo 未调用服务", len(service.calls), 0)

    trail_bo = TrailBo()
    check("getByTrailBo 直接返回服务结果", controller.getByTrailBo(trail_bo) is trail_bo)

    # 被整段注释的两个接口不应存在（Java 中已被注释掉）
    check("syncTrack 被注释掉（无该方法）", not hasattr(controller, "syncTrack"))
    check("syncSuspiciousCar 被注释掉（无该方法）", not hasattr(controller, "syncSuspiciousCar"))


def test_fee_records() -> None:
    print("[OdsLwzxsfsjFeeRecords01Controller]")
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
    from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

    class _FeeService(_AnyStub):
        def __init__(self, rows):
            super().__init__()
            self.rows = rows

        def selectOdsLwzxsfsjFeeRecords01List(self, query):
            self.calls.append(("selectOdsLwzxsfsjFeeRecords01List", (query,)))
            return self.rows

        def selectOdsLwzxsfsjFeeRecords01ById(self, bigId):
            self.calls.append(("selectOdsLwzxsfsjFeeRecords01ById", (bigId,)))
            return self.rows[0]

    class _GantryService(_AnyStub):
        def __init__(self, rows):
            super().__init__()
            self.rows = rows

        def getGantryRedis(self):
            self.calls.append(("getGantryRedis", ()))
            return self.rows

    cls = _controller("OdsLwzxsfsjFeeRecords01Controller")
    rows = [OdsLwzxsfsjFeeRecords01()]
    rows[0].setVehicleplate("赣A12345_蓝")
    rows[0].setGantryid("G1")
    gantry = OdsSzdnGantry()
    gantry.setGantryCode("G1")
    gantry.setGantryName("长安门架")
    gantry.setSectionCode("S1")

    controller = cls(_FeeService(rows), _GantryService([gantry]), _AnyStub())
    check_eq("OdsLwzxsfsjFeeRecords01Controller.BASE_PATH",
             cls.BASE_PATH, "/base/feerecords")

    _install_request_context()
    rsp = controller.list(OdsLwzxsfsjFeeRecords01())
    check("fee list 返回 TableDataInfo", isinstance(rsp, TableDataInfo))
    check("fee list.rows 即服务返回值", rsp.getRows() is rows)
    check_eq("fee list 下划线拆分车牌", rows[0].getVehicleplate(), "赣A12345")
    check_eq("fee list 回填门架名称", rows[0].getGantryName(), "长安门架")
    check_eq("fee list 回填路段编号", rows[0].getSectionCodeStr(), "S1")

    check("fee getInfo 返回裸实体", controller.getInfo("B-1") is rows[0])


def test_snapshot_flow() -> None:
    print("[OdsRtSzdnSnapshotFlowAddcodeController]")
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
    from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

    class _SnapshotService(_AnyStub):
        def __init__(self, rows):
            super().__init__()
            self.rows = rows

        def selectOdsRtSzdnSnapshotFlowAddcodeList(self, query):
            self.calls.append(("selectOdsRtSzdnSnapshotFlowAddcodeList", (query,)))
            return self.rows

        def selectOdsRtSzdnSnapshotFlowAddcodeById(self, bigId):
            self.calls.append(("selectOdsRtSzdnSnapshotFlowAddcodeById", (bigId,)))
            return self.rows[0]

    cls = _controller("OdsRtSzdnSnapshotFlowAddcodeController")
    rows = [OdsRtSzdnSnapshotFlowAddcode()]
    rows[0].setSnappicturepath("http://jxjt.isilon.com/pic/1.jpg")
    controller = cls(_SnapshotService(rows), _AnyStub())
    check_eq("OdsRtSzdnSnapshotFlowAddcodeController.BASE_PATH",
             cls.BASE_PATH, "/base/snapshotflow")

    _install_request_context()
    rsp = controller.list(OdsRtSzdnSnapshotFlowAddcode())
    check("snapshot list 返回 TableDataInfo", isinstance(rsp, TableDataInfo))
    check("snapshot list.rows 即服务返回值", rsp.getRows() is rows)
    check_eq("snapshot list 回填 UUID（32 位无横线）", len(rows[0].getId()), 32)
    check_eq("snapshot list 图片域名替换", rows[0].getSnappicturepath(),
             "http://36.200.30.144:9080/pic/1.jpg")
    check("snapshot getInfo 返回裸实体", controller.getInfo("B-2") is rows[0])


def main() -> int:
    _install_optimization_stubs()
    test_progressive_query()
    test_unified_query()
    test_large_scale_query()
    test_thread_standin()
    test_sys_test()
    test_sys_util()
    test_fee_records()
    test_snapshot_flow()

    print()
    print(f"PASS={PASS} FAIL={FAIL}")
    if FAILURES:
        print("失败项：")
        for item in FAILURES:
            print("  - " + item)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
