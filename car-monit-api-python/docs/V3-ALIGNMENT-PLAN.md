# Python 镜像对齐 Java V3 —— 实施计划与端点差距矩阵

> 创建时间：2026-11-20
> 目标分支：backend `py-v3-align`（源自 `car-monit-py-V2`，对齐 `car-monit-backend-java-V3`）；api `car-monit-api-python`（对齐 `car-monit-api-java-V3`）
> 原则：**行为等价 > 结构镜像 > 可追溯**。Java 的缺陷（错别字、注释掉的端点、反直觉的默认值）一律保留，只在注释里说明，不"顺手修复"。

---

## 1. 基线确认（已实测）

| 端 | Python 迁移基线 | Java V3 相对基线的变化 |
|---|---|---|
| backend | master（Java 1.8 / Spring Boot 2.4.5），498 个 `@router.*` 端点 | 新增 2 个 Controller / 16 个端点；`topTen` 增加 2 个查询参数；大屏 GET 增加 ETag/304 与 `X-Cache`/`X-Degrade` 响应头 |
| api | master，24 Controller / 85 handler（其中 4 条 Python 专有 health/metrics） | 新增 5 个 Controller / 24 个端点；`LargeScaleQueryController` 新增 1 个下载端点；`mode=display|full` 分流；内部端点守卫；`traffic.*` 配置段 |

Java V3 diff 规模：backend `108 files, +11201/-943`；api `71 files, +9959/-430`（含测试与运维模板）。

## 2. 端点差距矩阵

### 2.1 backend（`/manager/bigScreen/export/**`，10 个新增）

| # | HTTP + 路径 | Java 方法 | 权限 | Python 状态 |
|---|---|---|---|---|
| 1 | POST `/manager/bigScreen/export/display` | `display` | `manager:bigscreen:export` | 待补 |
| 2 | POST `/manager/bigScreen/export/full` | `full` | `export` + `exportFull` | 待补 |
| 3 | GET `/manager/bigScreen/export/status/{taskId}` | `status` | 登录 | 待补 |
| 4 | POST `/manager/bigScreen/export/{taskId}/retry` | `retry` | `export` | 待补 |
| 5 | POST `/manager/bigScreen/export/{taskId}/resume` | `resume` | `export` | 待补 |
| 6 | POST `/manager/bigScreen/export/{taskId}/download-url` | `downloadUrl` | 登录 | 待补 |
| 7 | GET `/manager/bigScreen/export/download/{taskId}` | `download` | 登录 + 令牌头 | 待补 |
| 8 | GET `/manager/bigScreen/export/approvals` | `approvals` | `exportApprove` | 待补 |
| 9 | POST `/manager/bigScreen/export/approvals/{requestId}/approve` | `approve` | `exportApprove` | 待补 |
| 10 | POST `/manager/bigScreen/export/approvals/{requestId}/reject` | `reject` | `exportApprove` | 待补 |

### 2.2 backend（`/monitor/bigscreen/**`，6 个新增）

| # | HTTP + 路径 | Java 方法 | 关键行为 |
|---|---|---|---|
| 1 | GET `/monitor/bigscreen/metrics` | `metrics` | counters/gauges + 4 个比率，`round(x*10000)/10000` |
| 2 | GET `/monitor/bigscreen/switches` | `switches` | effective/defaults/gray 三份快照 |
| 3 | POST `/monitor/bigscreen/gray/{name}` | `overrideGray` | percent 默认 100；tenants 逗号分隔 |
| 4 | DELETE `/monitor/bigscreen/gray/{name}` | `clearGray` | 同上安全开关校验 |
| 5 | POST `/monitor/bigscreen/switches/{name}` | `override` | `enabled` 必填 |
| 6 | DELETE `/monitor/bigscreen/switches/{name}` | `clear` | 同上安全开关校验 |

安全约束：`export-approval` 开关的改/删额外要求 `manager:bigscreen:exportApprove`（Java `AccessDeniedException`）。

### 2.3 backend（既有端点修改）

- `GET /manager/bigScreen/topTen` 新增 `startTime` / `endTime` 可选参数，默认最近 7 天；Mapper 新增 `getTopTenRange`。
- `BigScreenResponseFilter`：前缀 `/manager/bigScreen`（注意驼峰），为所有 GET 加 `ETag`/304、`X-Cache`、`X-Degrade`、`X-Data-*`，下载流排除。
- `SysDictDataController` / `SysDictTypeController` 写操作后 `DictVersionService.bump(...)`。
- 14 个 base Controller 数据源从本地表切 API；`ZdataTrailFittingController` 保留本地库并回 `dataSource=LOCAL_DB`。

### 2.4 api（5 个新增 Controller / 24 个端点）

| Controller | 端点 |
|---|---|
| `TrafficQueryV3Controller` `/api/v3/traffic` | POST `/list` |
| `ExportV3Controller` `/api/v3/export` | GET `/capabilities`；POST `/display`；POST `/full`；GET `/status/{taskId}`；POST `/cancel/{taskId}` |
| `BigScreenStatsV3Controller` `/api/v1/bigscreen` | GET `/stats/escape`；`/stats/audit`；`/stats/income`；`/stats/warning-top` |
| `BigScreenWarningV3Controller` `/api/v1/bigscreen` | GET `/warning/list` |
| `TrafficAdminV3Controller` `/api/v3` | POST `/es/bootstrap`；GET `/es/status`；GET `/es/readiness`；POST `/es/activate`；POST `/es/car-warning/bootstrap`；POST `/sync/car-warning/backfill`；POST `/sync/dws/backfill`；POST `/sync/car-warning/outbox/poll`；POST `/sync/backfill`；GET `/sync/backfill/status/{taskId}`；POST `/sync/reconcile`；POST `/sync/outbox/relay`；POST `/sync/reconcile/orphans` |

注意：`BigScreenStatsV3Controller` / `BigScreenWarningV3Controller` 路径是 `/api/v1/bigscreen/**`，**不是** `/api/v3/**`；也不在内部守卫拦截范围内。

### 2.5 api（既有端点修改）

- `GET /api/v1/large/export/download/{taskId}` **新增**（Java V3 `LargeScaleQueryController.downloadExport`）；未完成 409、不存在 404、文件名 `<taskId>.csv.gz`。
- `POST /api/v1/large/export/submit` 新增 `mode=display|full`；不带 mode 仍走 legacy（向后兼容）。
- `GET /api/v1/large/export/status/{taskId}` 优先查 V3 任务，重启后按文件恢复，再回落 legacy。
- `InternalEndpointGuardConfig` 拦截 `/api/v3/**` 与 `/api/v1/large/export/**`：配置令牌时校验 `X-Internal-Token`（常量时间比较）；未配置时只允许 127.0.0.1/::1，否则 403。
- `traffic.*` 配置段：`query/engine`、`es/auto-bootstrap`、`sync/enabled`、`export/dir`、`bigscreen/*` 等。

## 3. 实施顺序

1. **P0 端点可见性**：两侧新增 Controller / 路由全部注册，`check_routes` 与自建 parity 脚本通过。
2. **P1 核心服务**：导出任务状态机、下载令牌、FeatureSwitch、ES 查询/导出、Admin 运维动作。
3. **P2 行为细节**：响应头、ETag/304、权限点、错误码映射、内部守卫。
4. **P3 验证与交付**：测试脚本、文档索引、独立复核、推送。

## 4. 验证命令

```powershell
# backend
cd d:\work\IdeaProjects\car-monit-py-V2-wt\car-monit-py
python -m pytest -q tests
python scripts/smoke_test.py

# api
cd d:\work\IdeaProjects\car-monit-api-java-V3\car-monit-api-python
python tools\gen_routes.py
python tools\check_routes.py
python tools\check_parity.py
python -m pytest -q
```

## 5. 交接

任务中断时更新同目录 `HANDOVER.md`（记录已完成项、未完成项、阻断项、下一条命令）。
