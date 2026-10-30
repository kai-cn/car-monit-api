# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.UnifiedQueryController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/UnifiedQueryController.java

统一大表查询/导出 Controller。

=================================================================
设计目标：
  为 3 张 8 亿级大表（门架抓拍 / 收费流水 / 车辆轨迹）提供
  一致的“全字段模糊 + 时间范围 + 分页 / 异步导出”HTTP 入口。

路由异常时由 UnifiedQueryService 自动降级到 MySQL，
调用方无需关注底层是 ES 还是 DB。

接口规范：
  GET  /api/v1/unified/{ds}/list                 分页列表查询
  POST /api/v1/unified/{ds}/export/submit        提交异步导出任务
  GET  /api/v1/unified/export/status/{taskId}    查询导出状态

{ds} 取值：
  snapshot  -> 门架抓拍流水 (ods_rt_szdn_snapshot_flow_addcode)
  fee       -> 收费流水 (ods_lwzxsfsj_fee_records_01)
  trail     -> 车辆历史轨迹 (zdata_trail_fitting)

模糊查询参数格式：
  GET  /api/v1/unified/snapshot/list?startTime=2026-05-01 00:00:00
                                     &endTime=2026-05-31 23:59:59
                                     &fuzzyFields.platenumber=赣A1
                                     &fuzzyFields.gantryname=长安
                                     &pageNum=1&pageSize=20

【Java→Python】关键差异
1) 路由前缀 ``/api/v1/unified`` → 类常量 ``BASE_PATH``；``@GetMapping/@PostMapping``
   不自动注册路由，HTTP 方法与路径写在每个方法的 docstring 里。
2) 类**不继承** BaseController（与 Java 一致，Java 里只是普通 ``@RestController``）；
   返回原生 ``dict`` 对应 Java 的 ``Map<String, Object>``。
3) ``new LinkedHashMap<>()`` → ``dict``（Python 3.7+ 字典保持插入顺序，
   与 LinkedHashMap 的迭代顺序语义一致）。
4) ``@RequestParam(required = false) Map<String, String> fuzzyFields``：
   Spring 对“Map 类型 + 无 name”的参数语义是**收集全部请求参数**，
   所以原代码才需要用 ``extractFuzzyFields`` 过滤 ``fuzzyFields.`` 前缀。
   Python 侧同样接收“未过滤的原始 dict”，方法内按前缀过滤，行为保持一致。
5) ``catch (IllegalArgumentException e)`` → ``except ValueError as e``：
   Python 没有受检异常，IllegalArgumentException 用 ``ValueError`` 表达。
   **捕获顺序必须保持**（子类型在前），否则 400 分支会被后面的 ``except Exception`` 吞掉。
6) ``e.getMessage()`` → ``str(e)``（ValueError/Exception 的 str() 即为消息）；
   若异常没有消息，Java 得到 null、Python 得到 ``""``，属可接受的细微差异。
7) ``log.error("[统一查询] 异常 ds={}", ds, e)``：SLF4J 最后一个参数若是 Throwable
   会打印堆栈；logging 对应写法是 ``log.error("... ds=%s", ds, exc_info=True)``
   （占位符个数与 Java 一致，堆栈由 exc_info 输出）。
8) ``switch (ds.toLowerCase())`` + ``default: throw`` → ``if/elif`` + ``raise ValueError``。
9) ``long costSec = (status.finishTime - status.submitTime) / 1000;`` 是 **Java long 整除**
   （向零截断）；Python ``//`` 是向下取整，负数时结果不同，故用 ``int(... / 1000)``
   对齐 Java 的“向零截断”。
10) ``UnifiedExportService.ExportTaskStatus`` 的 **public 字段** → Python 实例属性，
    直接 ``status.status`` 访问（无 getter）。
11) 原工程注意点（忠实保留）：
    - ``list()`` 是“先 ``extractFuzzyFields`` 过滤再查询”，
    - 而 ``submitExport()`` 把**未过滤**的 ``fuzzyFields`` 原样传给
      ``exportService.submitExportTask(...)``（未调用 extractFuzzyFields）。
    两处行为不一致属原实现，Python 侧不做修正，仅在代码处标注。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from com.ruoyi.base.service.optimization.UnifiedExportService import UnifiedExportService
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService

__all__ = ["UnifiedQueryController"]

# Java: @Slf4j
log = logging.getLogger(__name__)


class UnifiedQueryController(object):
    """统一大表查询/导出Controller。"""

    # Java: @RequestMapping("/api/v1/unified")
    BASE_PATH = "/api/v1/unified"

    def __init__(self,
                 queryService: Optional[UnifiedQueryService] = None,
                 exportService: Optional[UnifiedExportService] = None) -> None:
        # Java: @Autowired private UnifiedQueryService queryService;
        self.queryService = queryService or UnifiedQueryService()
        # Java: @Autowired private UnifiedExportService exportService;
        self.exportService = exportService or UnifiedExportService()

    # ================================================================
    # 模块1：分页列表查询
    # ================================================================

    def list(self,
             ds: str,
             startTime: str,
             endTime: str,
             fuzzyFields: Optional[Dict[str, str]] = None,
             pageNum: int = 1,
             pageSize: int = 20) -> Dict[str, Any]:
        """通用大表分页查询接口（GET /api/v1/unified/{ds}/list）。

        注意：
          1. fuzzyFields.* 是 Spring 自动注入的多值参数，需手动提取过滤；
          2. 若 from + size 超过 ES max_result_window，会抛异常引导使用导出接口。

        【Java→Python】方法名 ``list`` 与内置类型同名：Java 里是重载无关的方法名，
        Python 里作为类方法没有影响（方法体内的 ``list`` 仍解析到内置类型），
        保持同名以对齐源码。
        """
        # Java: Map<String, Object> result = new LinkedHashMap<>();
        result: Dict[str, Any] = {}
        try:
            source = self.parseDataSource(ds)
            fields: Dict[str, str] = self.extractFuzzyFields(fuzzyFields)

            # Java: List<?> data = queryService.query(source, startTime, endTime, fields, pageNum, pageSize);
            data: List[Any] = self.queryService.query(
                source, startTime, endTime, fields, pageNum, pageSize)

            result["code"] = 200
            result["message"] = "ok"
            result["dataSource"] = ds
            result["pageNum"] = pageNum
            result["pageSize"] = pageSize
            result["data"] = data
        except ValueError as e:
            # Java: catch (IllegalArgumentException e) —— 参数/数据源非法 → 400
            result["code"] = 400
            result["message"] = str(e)
        except Exception as e:
            # Java: catch (Exception e) —— 其余异常 → 500（含 ES 超窗等 IllegalStateException）
            log.error("[统一查询] 异常 ds=%s", ds, exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    # ================================================================
    # 模块2：大数据量异步导出
    # ================================================================

    def submitExport(self,
                     ds: str,
                     startTime: str,
                     endTime: str,
                     fuzzyFields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """提交异步导出任务（POST /api/v1/unified/{ds}/export/submit）。

        解决单次导出 >100 万条 OOM 问题。调用方：
          1. POST 提交获取 taskId；
          2. 前端轮询 GET /api/v1/unified/export/status/{taskId}；
          3. 完成后从 status.filePaths 拿到可下载的 CSV 文件列表。

        Body 形式（JSON）：
          { "platenumber": "赣A", "gantryname": "长安" }
        """
        result: Dict[str, Any] = {}
        try:
            source = self.parseDataSource(ds)
            # 【原工程行为，忠实保留】此处**没有**调用 extractFuzzyFields，
            # 直接把 @RequestBody 收到的原始 Map 透传给导出服务；
            # 与上面的 list() 不一致，属原实现，不做修正。
            taskId: str = self.exportService.submitExportTask(
                source, startTime, endTime, fuzzyFields)

            result["code"] = 200
            result["message"] = "导出任务已提交, 请用 taskId 轮询状态"
            result["taskId"] = taskId
        except ValueError as e:
            result["code"] = 400
            result["message"] = str(e)
        except Exception as e:
            log.error("[统一导出] 提交异常 ds=%s", ds, exc_info=True)
            result["code"] = 500
            result["message"] = str(e)
        return result

    def getExportStatus(self, taskId: str) -> Dict[str, Any]:
        """查询导出任务状态（GET /api/v1/unified/export/status/{taskId}）。"""
        result: Dict[str, Any] = {}
        # Java: UnifiedExportService.ExportTaskStatus status = exportService.getExportStatus(taskId);
        # 注意：这里用的是 **UnifiedExportService** 自己的 ExportTaskStatus（内含 finishTime/filePaths），
        # 与 LargeScaleQueryService.ExportTaskStatus（内含 endTime）是两个不同的内部类。
        status = self.exportService.getExportStatus(taskId)
        if status is None:
            result["code"] = 404
            result["message"] = "task not found"
            return result
        result["code"] = 200
        # Java 的 public 字段 → Python 实例属性，直接访问
        result["status"] = status.status
        result["totalExported"] = status.totalExported
        result["filePartCount"] = status.filePartCount
        result["submitTime"] = status.submitTime
        if "COMPLETED" == status.status:
            result["endTime"] = status.finishTime
            result["filePaths"] = status.filePaths
            # Java long 整除向零截断 → int(... / 1000)
            costSec = int((status.finishTime - status.submitTime) / 1000)
            result["costSeconds"] = costSec
        elif "FAILED" == status.status:
            result["errorMessage"] = status.errorMessage
        return result

    # ================================================================
    # 私有辅助
    # ================================================================

    def parseDataSource(self, ds: str) -> "UnifiedQueryService.DataSource":
        """字符串 -> DataSource 枚举，校验非法输入。"""
        if ds is None:
            # 原工程消息里的 {ds} 是字面量（不是占位符），原样保留
            raise ValueError("数据源 {ds} 不能为空")
        # Java: switch (ds.toLowerCase())
        lowered = ds.lower()
        if lowered == "snapshot":
            return UnifiedQueryService.DataSource.SNAPSHOT
        if lowered == "fee":
            return UnifiedQueryService.DataSource.FEE
        if lowered == "trail":
            return UnifiedQueryService.DataSource.TRAIL
        raise ValueError("未知数据源: " + ds + ", 合法取值: snapshot / fee / trail")

    def extractFuzzyFields(self, raw: Optional[Dict[str, str]]) -> Dict[str, str]:
        """从 Spring 注入的 Map 中提取 fuzzyFields.* 前缀的参数。"""
        # Java: Map<String, String> result = new HashMap<>();
        result: Dict[str, str] = {}
        if raw is None:
            return result
        # Java: for (Map.Entry<String, String> e : raw.entrySet())
        for key, value in raw.items():
            if key.startswith("fuzzyFields.") and value is not None and value != "":
                # Java: key.substring("fuzzyFields.".length())
                result[key[len("fuzzyFields."):]] = value
        return result
