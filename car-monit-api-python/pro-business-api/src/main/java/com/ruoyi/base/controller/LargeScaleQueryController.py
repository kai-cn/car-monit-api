# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.LargeScaleQueryController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/LargeScaleQueryController.java

大规模数据查询与统计接口 —— 面向 8 亿条数据场景（三表统一）。

=================================================================
统一路由架构 / Unified routing architecture:
  【前端】--HTTP-->【本 Controller】--统一路由--> UnifiedQueryService
                                                 |-- 模糊/统计/超30天/FEE/TRAIL --> Elasticsearch
                                                 |-- 小范围精确 -------------------> GaussDB
  数据同步：GaussDB --> LargeScaleDataSyncService --> Elasticsearch（双写/增量/补同步）
  一致性：GaussEsConsistencyService 定时对账 GaussDB 与 ES 并触发修复

三表接口 / Three tables:
  - /snapshot         门架抓拍流水   ods_rt_szdn_snapshot_flow_addcode   时间字段 snapshottime
  - /fee              收费流水       ods_lwzxsfsj_fee_records_01        时间字段 transtime
  - /trail            车辆轨迹       zdata_trail_fitting                时间字段 extime
  - /carTrackQueryByCarNo  按车牌查历史轨迹（platenumber -> envehicleid）

【Java→Python】关键差异
1) 路由前缀 ``/api/v1/large`` → 类常量 ``BASE_PATH``；``@GetMapping/@PostMapping``
   不自动注册路由，HTTP 方法与路径写在每个方法的 docstring 里。
2) 类**不继承** BaseController（与 Java 一致）；返回原生 ``dict`` 对应
   Java 的 ``Map<String, Object>``，``new LinkedHashMap<>()`` → ``dict``（3.7+ 保序）。
3) **参数默认值的语法约束**：Java 允许「带默认值的参数」出现在「必填参数」之前，
   例如 ``groupByStats(@RequestParam(defaultValue="snapshot") String type,
   @RequestParam String startTime, ...)``。Python 语法**禁止**默认参数后跟无默认参数，
   因此这里保持 **Java 的参数顺序不变**，把后面的必填参数声明为
   ``Optional[str] = None``；必填校验在 Java 里由 Spring 完成，Python 侧由调用方保证。
   代价是：漏传必填参数时 Python 不会像 Spring 那样返回 400，而是把 None 传进服务层。
4) ``type`` 作为形参会遮蔽 Python 内置 ``type``（仅在方法内），为对齐 Java 形参名保留。
5) ``ds.name()``（枚举名）→ Python ``Enum.name`` 属性（不加括号）。
6) ``switch (type.toLowerCase())`` → ``if/elif``；``default`` 分支返回 SNAPSHOT。
7) ``catch (Exception e)`` → ``except Exception as e``，``e.getMessage()`` → ``str(e)``；
   ``log.error("... ds={}", ds, e)``（最后一个是 Throwable）→
   ``log.error("... ds=%s", ds, exc_info=True)``（占位符数量与 Java 一致）。
8) **线程**：``new Thread(() -> syncService.fullSyncOneYear()).start()`` →
   ``Thread(target=lambda: ...).start()``（``java.lang.Thread`` 替身，见 java/lang/Thread.py）。
   Java 里 ``startTime`` / ``endTime`` 需 effectively final 才能被 lambda 捕获；
   Python 闭包按引用捕获方法参数，等价可用（方法参数在单次调用内不变）。
   原代码里的 ``finalDs = ds`` 只是为满足 Java 语法，Python 无法（也不需要）声明 final，
   忠实保留变量并在此标注。
9) ``status.status`` / ``status.totalExported`` 等是 Java ``ExportTaskStatus`` 的
   **public 字段** → Python 实例属性，直接访问（无 getter）。
   注意此处用的是 ``LargeScaleQueryService.ExportTaskStatus``（字段 endTime），
   与 ``UnifiedExportService.ExportTaskStatus``（字段 finishTime/filePaths）不是同一个类。
10) ``(status.finishTime - status.submitTime) / 1000`` 这类 long 整除在本类中未使用，
    本类只透传时间戳字段，不做除法。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from com.ruoyi.base.service.optimization.LargeScaleDataSyncService import LargeScaleDataSyncService
from com.ruoyi.base.service.optimization.LargeScaleQueryService import LargeScaleQueryService
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from java.lang.Thread import Thread

__all__ = ["LargeScaleQueryController"]

# Java: @Slf4j
log = logging.getLogger(__name__)


class LargeScaleQueryController(object):
    """大规模数据查询与统计Controller。"""

    # Java: @RequestMapping("/api/v1/large")
    BASE_PATH = "/api/v1/large"

    def __init__(self,
                 unifiedQueryService: Optional[UnifiedQueryService] = None,
                 largeScaleQueryService: Optional[LargeScaleQueryService] = None,
                 syncService: Optional[LargeScaleDataSyncService] = None,
                 exportTaskService: Optional[Any] = None) -> None:
        # Java: @Autowired private UnifiedQueryService unifiedQueryService;
        self.unifiedQueryService = unifiedQueryService or UnifiedQueryService()
        # Java: @Autowired private LargeScaleQueryService largeScaleQueryService;
        self.largeScaleQueryService = largeScaleQueryService or LargeScaleQueryService()
        # Java: @Autowired private LargeScaleDataSyncService syncService;
        self.syncService = syncService or LargeScaleDataSyncService()
        # 【Java V3 对齐】Java V3 注入 ExportTaskService；Python 从 V3 单例表取。
        if exportTaskService is None:
            from com.ruoyi.base.service.v3.v3_services import SERVICES

            exportTaskService = SERVICES["exportTaskService"]
        self.exportTaskService = exportTaskService

    # ================================================================
    # 模块1：三表全字段模糊查询 / Module 1: fuzzy query for 3 tables
    # ================================================================

    def querySnapshotFlow(self,
                          startTime: str,
                          endTime: str,
                          fuzzyFields: Optional[Dict[str, str]] = None,
                          pageNum: int = 1,
                          pageSize: int = 20) -> Dict[str, Any]:
        """门架抓拍流水 - 全字段模糊查询（GET /api/v1/large/snapshot，默认路由到 ES）。"""
        return self.queryByDs(
            UnifiedQueryService.DataSource.SNAPSHOT,
            startTime, endTime, fuzzyFields, pageNum, pageSize)

    def queryFeeRecords(self,
                        startTime: str,
                        endTime: str,
                        fuzzyFields: Optional[Dict[str, str]] = None,
                        pageNum: int = 1,
                        pageSize: int = 20) -> Dict[str, Any]:
        """收费流水 - 全字段模糊查询（GET /api/v1/large/fee，真实接入，路由到 ES）。"""
        return self.queryByDs(
            UnifiedQueryService.DataSource.FEE,
            startTime, endTime, fuzzyFields, pageNum, pageSize)

    def queryTrail(self,
                   startTime: str,
                   endTime: str,
                   fuzzyFields: Optional[Dict[str, str]] = None,
                   pageNum: int = 1,
                   pageSize: int = 20) -> Dict[str, Any]:
        """车辆历史轨迹 - 全字段模糊查询（GET /api/v1/large/trail，真实接入，路由到 ES）。"""
        return self.queryByDs(
            UnifiedQueryService.DataSource.TRAIL,
            startTime, endTime, fuzzyFields, pageNum, pageSize)

    def queryCarTrackByCarNo(self,
                             carNo: str,
                             startTime: str,
                             endTime: str,
                             pageNum: int = 1,
                             pageSize: int = 20) -> Dict[str, Any]:
        """按车牌号查询车辆历史轨迹（GET /api/v1/large/carTrackQueryByCarNo）。

        思路：将入参 carNo 映射为逻辑字段 platenumber，
        由统一路由翻译为轨迹表物理字段 envehicleid。

        【原工程缺陷，忠实保留】
        这里把 key 写成 ``platenumber``，但下面 ``queryByDs`` 内部会调用
        ``extractFuzzyFields``，而后者的规则是“只保留以 ``fuzzyFields.`` 开头的 key”。
        因此 platenumber 会被过滤掉，**车牌条件实际不会生效**（Java 里同样如此）。
        若要修复，应写成 ``fuzzy.put("fuzzyFields.platenumber", carNo)``。
        """
        # Java: Map<String, String> fuzzy = new LinkedHashMap<>();
        fuzzy: Dict[str, str] = {}
        if carNo is not None and carNo != "":
            fuzzy["platenumber"] = carNo
        return self.queryByDs(
            UnifiedQueryService.DataSource.TRAIL,
            startTime, endTime, fuzzy, pageNum, pageSize)

    def queryByDs(self,
                  ds: "UnifiedQueryService.DataSource",
                  startTime: str,
                  endTime: str,
                  fuzzyFields: Optional[Dict[str, str]],
                  pageNum: int,
                  pageSize: int) -> Dict[str, Any]:
        """统一查询入口封装：抽取 fuzzyFields、调用统一路由、包装返回。"""
        result: Dict[str, Any] = {}
        try:
            fields: Dict[str, str] = self.extractFuzzyFields(fuzzyFields)
            # Java: List<?> list = unifiedQueryService.query(...)  → 局部变量名 list 改为 list_
            list_: List[Any] = self.unifiedQueryService.query(
                ds, startTime, endTime, fields, pageNum, pageSize)
            result["code"] = 200
            result["message"] = "ok"
            # Java: ds.name() → Python Enum.name（属性而非方法）
            result["dataSource"] = ds.name
            result["pageNum"] = pageNum
            result["pageSize"] = pageSize
            result["data"] = list_
        except Exception as e:
            # 本方法只捕获 Exception（Java 同），无 IllegalArgumentException 的 400 分支。
            # 【日志占位符】Java 的 SLF4J 对枚举调用 String.valueOf → 输出 "TRAIL"，
            # Python 的 %s 默认输出 "DataSource.TRAIL"；为与 Java 日志一致改用 ds.name。
            log.error("[查询接口] 异常 ds=%s", ds.name, exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def extractFuzzyFields(self, fuzzyFields: Optional[Dict[str, str]]) -> Dict[str, str]:
        """从 Spring 注入的 Map 中提取 fuzzyFields.xxx 形式的字段。"""
        # Java: Map<String, String> fields = new HashMap<>();
        fields: Dict[str, str] = {}
        if fuzzyFields is not None:
            for key, value in fuzzyFields.items():
                if key.startswith("fuzzyFields.") and value is not None and value != "":
                    # Java: key.substring("fuzzyFields.".length())
                    fields[key[len("fuzzyFields."):]] = value
        return fields

    def extractFuzzyStringFields(self, fuzzyFields: Optional[Dict[str, str]]) -> Dict[str, str]:
        """【Java V3 对齐】GET 查询的 ``Map<String,String>`` 版本（Java ``extractFuzzyStringFields``）。

        Python 差异：Java 因为方法重载必须区分 ``Map<String,String>`` 与
        ``Map<String,Object>`` 两个签名；Python 没有类型擦除/重载，两个方法体一致，
        但保留独立方法名以满足方法级 parity 对照。
        """
        return self.extractFuzzyFields(fuzzyFields)

    @staticmethod
    def asString(value: Any) -> str:
        """Java: ``asString(Object)`` —— null → 空串，其它走 ``String.valueOf``。"""
        return "" if value is None else str(value)

    def addCode(self, request: Any, field: str, value: str) -> None:
        """Java: ``addCode(ExportRequest, String, String)`` —— 逗号多值去重追加。"""
        codes = request.dimensionCodes.setdefault(field, [])
        for item in str(value).split(","):
            code = item.strip()
            if code and code not in codes:
                codes.append(code)

    def addResolvedCodes(self, request: Any, field: str, codes: Optional[List[str]],
                         nameField: str, value: str) -> None:
        """Java: ``addResolvedCodes`` —— 名称未匹配到编码时抛 IllegalArgumentException。"""
        if not codes:
            raise ValueError("维度名称未匹配到编码: " + nameField + "=" + value)
        for code in codes:
            self.addCode(request, field, code)

    # ================================================================
    # 模块2：统计接口（ES aggregation，三表，type 参数）
    # ================================================================

    def groupByStats(self,
                     type: str = "snapshot",
                     startTime: Optional[str] = None,
                     endTime: Optional[str] = None,
                     groupBy: Optional[str] = None,
                     countField: Optional[str] = None,
                     fuzzyFields: Optional[Dict[str, str]] = None,
                     topN: int = 100) -> Dict[str, Any]:
        """按维度分组 Top-N 统计（GET /api/v1/large/stats/group，type: snapshot/fee/trail）。

        【Java→Python】参数顺序与 Java 完全一致；其中 startTime/endTime/groupBy 在 Java
        是 ``@RequestParam`` 必填，因 Python 语法不允许默认参数后跟无默认参数，
        这里统一声明为 ``Optional[...] = None``（见模块头第 3 条说明）。
        """
        result: Dict[str, Any] = {}
        try:
            fields: Dict[str, str] = self.extractFuzzyFields(fuzzyFields)
            # Java: Map<String, Long> stats = largeScaleQueryService.aggregationStats(
            #         type, startTime, endTime, groupBy, countField, fields, topN);
            stats: Dict[str, int] = self.largeScaleQueryService.aggregationStats(
                type, startTime, endTime, groupBy, countField, fields, topN)
            result["code"] = 200
            result["message"] = "ok"
            result["type"] = type
            result["groupBy"] = groupBy
            result["topN"] = topN
            result["data"] = stats
        except Exception as e:
            log.error("[统计接口] 异常 type=%s", type, exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    # ================================================================
    # 模块3：大数据导出接口（异步任务，三表，type 参数）
    # ================================================================

    def submitExport(self,
                     type: str = "snapshot",
                     startTime: Optional[str] = None,
                     endTime: Optional[str] = None,
                     mode: Optional[str] = None,
                     body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """提交导出任务（POST /api/v1/large/export/submit）。

        【Java V3 对齐】Java V3 新增 ``mode=display|full`` 与 ``@RequestBody Map body``。
        Python 差异：Java 的 ``@RequestParam(required=false) String mode`` 在参数表里排在
        ``@RequestBody`` 之前；Python 同样保持这个顺序（registry 按位置绑定）。
        不带 mode 时仍走 legacy ``largeScaleQueryService``，与 Java 的向后兼容分支一致。
        """
        result: Dict[str, Any] = {}
        try:
            if self.isV3Mode(mode):
                request = self.buildV3ExportRequest(type, startTime, endTime, body)
                task = (self.exportTaskService.submit_full(request)
                        if (mode or "").strip().lower() == "full"
                        else self.exportTaskService.submit_display(request))
                result["code"] = 200
                result["message"] = "导出任务已提交"
                result["type"] = type
                result["mode"] = mode
                result["taskId"] = task.taskId
                return result

            fields: Dict[str, str] = self.extractFuzzyFields(body)
            taskId: str = self.largeScaleQueryService.submitExportTask(
                type, startTime, endTime, fields)
            result["code"] = 200
            result["message"] = "导出任务已提交"
            result["type"] = type
            result["taskId"] = taskId
        except Exception as e:
            log.error("[导出-提交] 异常 type=%s mode=%s", type, mode, exc_info=True)
            # Java V3 此处是 400（master 是 500），照抄 V3。
            result["code"] = 400
            result["message"] = str(e)
        return result

    def getExportStatus(self, taskId: str) -> Dict[str, Any]:
        """查询导出任务状态：优先 V3 任务，重启后按文件恢复，再回落 legacy。"""
        result: Dict[str, Any] = {}
        try:
            task = self.exportTaskService.get(taskId)
            if task is not None:
                result["code"] = 200
                result["status"] = task.status
                result["totalExported"] = task.rows
                result["filePartCount"] = self.filePartCount(task)
                result["submitTime"] = task.submitTime
                result["endTime"] = task.finishTime
                result["mode"] = task.mode
                result["type"] = task.table
                result["totalRows"] = task.total
                result["error"] = task.error
                return result

            # Java V3: api 重启后任务内存丢失，只要文件存在仍可查询/下载。
            if hasattr(self.exportTaskService, "resolveFinishedFile"):
                finished = self.exportTaskService.resolveFinishedFile(taskId)
                if finished is not None:
                    result["code"] = 200
                    result["status"] = "done"
                    result["totalExported"] = -1
                    result["filePartCount"] = 1
                    result["submitTime"] = None
                    result["endTime"] = int(getattr(finished, "lastModified", lambda: 0)())
                    return result

            # Java: LargeScaleQueryService.ExportTaskStatus status = largeScaleQueryService.getExportStatus(taskId);
            status = self.largeScaleQueryService.getExportStatus(taskId)
            if status is None:
                result["code"] = 404
                result["message"] = "task not found"
            else:
                result["code"] = 200
                # public 字段 → 实例属性（本类的 ExportTaskStatus 用 endTime，不是 finishTime）
                result["status"] = status.status
                result["totalExported"] = status.totalExported
                result["filePartCount"] = status.filePartCount
                result["submitTime"] = status.submitTime
                result["endTime"] = status.endTime
        except Exception as e:
            log.error("[导出-查询] 异常", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def downloadExport(self, taskId: str) -> Dict[str, Any]:
        """GET /api/v1/large/export/download/{taskId} —— V3 新增端点。

        Java 返回 ``ResponseEntity<Resource>``（二进制流 + Content-Disposition）。Python 侧
        registry 统一返回 JSON 可序列化对象，因此这里返回**契约描述 dict**，真实文件流由
        ``app/routes/registry.py`` 的 ``JacksonResponse`` 在识别 ``_download`` 标记后写出。
        未完成 409、不存在 404，文件名固定 ``<taskId>.csv.gz``（与 Java 一致）。
        """
        task = self.exportTaskService.get(taskId)
        if task is not None:
            if (task.status or "").lower() != "done":
                return {"code": 409, "_download": True}
            file_path = task.filePath
        else:
            file_path = None
            if hasattr(self.exportTaskService, "resolveFinishedFile"):
                finished = self.exportTaskService.resolveFinishedFile(taskId)
                file_path = getattr(finished, "path", None) if finished is not None else None
        if not file_path:
            log.warning("[导出-下载] 文件不存在 taskId=%s", taskId)
            return {"code": 404, "_download": True}
        return {
            "code": 200,
            "_download": True,
            "file": str(file_path),
            "filename": taskId + ".csv.gz",
            "contentType": "application/gzip",
        }

    @staticmethod
    def isV3Mode(mode: Optional[str]) -> bool:
        """Java: ``isV3Mode(String)`` —— trim + 忽略大小写。"""
        return mode is not None and (mode.strip().lower() in ("display", "full"))

    @staticmethod
    def filePartCount(task: Any) -> int:
        """Java: ``filePartCount(ExportTask)`` —— 只有 done 且文件存在才计 1。"""
        import os

        if (task.status or "").lower() != "done" or not task.filePath:
            return 0
        return 1 if os.path.isfile(task.filePath) else 0

    def buildV3ExportRequest(self, type: str, startTime: Optional[str], endTime: Optional[str],
                             body: Optional[Dict[str, Any]]) -> Any:
        """Java: ``buildV3ExportRequest`` — body 的 fuzzyFields → plate / dimensionCodes。"""
        from com.ruoyi.base.service.v3.v3_services import ExportRequest

        data = body or {}
        fuzzy = data.get("fuzzyFields") or {}
        plate = (fuzzy.get("platenumber") or fuzzy.get("vehicleplate")
                 or fuzzy.get("carNo") or data.get("plate"))
        dimensions = {k: v for k, v in fuzzy.items() if k.endswith("code")}
        return ExportRequest(
            table=type, startTime=startTime, endTime=endTime,
            dimensions=dimensions, plate=plate,
            fields=list(data.get("fields") or []),
        )

    # ================================================================
    # 模块4：数据同步运维接口（三表）
    # ================================================================

    def triggerFullSync(self) -> Dict[str, Any]:
        """触发全量同步（POST /api/v1/large/sync/full，最近一年，三表）。"""
        result: Dict[str, Any] = {}
        try:
            # Java: new Thread(() -> syncService.fullSyncOneYear()).start();
            # 后台线程执行，接口立即返回；线程内异常不会回传给调用方（与 Java 一致）
            Thread(target=lambda: self.syncService.fullSyncOneYear()).start()
            result["code"] = 200
            result["message"] = "全量同步任务已在后台启动（三表），预计耗时较长"
        except Exception as e:
            log.error("[同步-全量] 异常", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def triggerIncrementalSync(self) -> Dict[str, Any]:
        """触发增量同步（POST /api/v1/large/sync/incremental，日常由定时任务执行）。"""
        result: Dict[str, Any] = {}
        try:
            self.syncService.incrementalSync()
            result["code"] = 200
            result["message"] = "增量同步完成（三表，基于 Redis 水位）"
        except Exception as e:
            log.error("[同步-增量] 异常", exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def triggerRepairSync(self,
                          type: str = "snapshot",
                          startTime: Optional[str] = None,
                          endTime: Optional[str] = None) -> Dict[str, Any]:
        """补同步 —— 重放指定数据源与时间窗（POST /api/v1/large/sync/repair，以 GaussDB 为准回灌 ES）。"""
        result: Dict[str, Any] = {}
        try:
            ds = self.resolveDs(type)
            # Java: UnifiedQueryService.DataSource finalDs = ds;
            # 仅为了满足 lambda 的「effectively final」要求；Python 无此约束，忠实保留变量
            finalDs = ds
            # Java: new Thread(() -> syncService.repairSync(finalDs, startTime, endTime)).start();
            Thread(target=lambda: self.syncService.repairSync(
                finalDs, startTime, endTime)).start()
            result["code"] = 200
            result["message"] = "补同步任务已在后台启动 type=" + type
        except Exception as e:
            log.error("[同步-补录] 异常 type=%s", type, exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def resolveDs(self, type: Optional[str]) -> "UnifiedQueryService.DataSource":
        """type 字符串 -> 数据源枚举（未知取值一律回落到 SNAPSHOT）。"""
        if type is None:
            return UnifiedQueryService.DataSource.SNAPSHOT
        lowered = type.lower()
        if lowered == "fee":
            return UnifiedQueryService.DataSource.FEE
        if lowered == "trail":
            return UnifiedQueryService.DataSource.TRAIL
        return UnifiedQueryService.DataSource.SNAPSHOT
