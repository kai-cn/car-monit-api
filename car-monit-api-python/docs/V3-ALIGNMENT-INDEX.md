# api Python ↔ Java V3 对齐：文档与文件索引

> 更新：2026-11-20

## 1. 文档

| 文件 | 用途 | 状态 |
|---|---|---|
| `V3-ALIGNMENT-PLAN.md` | 端点差距矩阵、实施顺序、验证命令 | 已完成（含实测基线） |
| `V3-ALIGNMENT-HANDOVER.md` | 交接：已完成 / 未完成 / 阻断项 / 下一条命令 | 实时更新 |
| `V3-ALIGNMENT-INDEX.md` | 本文件：文件级索引 | 实时更新 |
| `Java-to-Python-对照手册.md` | master 基线 Java→Python 语法/结构差异 | 仍有效 |
| `迁移审阅报告.md` | master 基线审阅结论 | 仍有效 |

## 2. 新增/修改的 Python 文件

### Controller（Java V3 新增 5 个）
- `pro-business-api/src/main/java/com/ruoyi/base/controller/v3/TrafficQueryV3Controller.py` —— POST `/api/v3/traffic/list`
- `.../v3/ExportV3Controller.py` —— GET `/api/v3/export/capabilities`、POST `/display` `/full` `/cancel/{taskId}`、GET `/status/{taskId}`
- `.../v3/BigScreenStatsV3Controller.py` —— 4 条 `/api/v1/bigscreen/stats/*`
- `.../v3/BigScreenWarningV3Controller.py` —— GET `/api/v1/bigscreen/warning/list`
- `.../v3/TrafficAdminV3Controller.py` —— 13 条 ES/回灌/对账运维端点
- `.../controller/LargeScaleQueryController.py` —— 新增 `mode`、`body` 参数，`downloadExport`

### Service / 中间件
- `.../service/v3/v3_services.py` —— 22 个 Java V3 服务的 Python 镜像（类/方法名一致）
- `app/middleware/internal_guard.py` —— 内部端点守卫（Java `InternalEndpointGuardConfig`）
- `app/main.py` —— 注册守卫中间件
- `tools/gen_routes.py` —— 支持 `controller/v3/*Controller.java` 递归扫描
- `app/routes/generated.py` —— 重新生成（29 / 110）

### 测试
- `tests/test_v3_alignment.py` —— 7 个对齐用例（路由覆盖 + 核心契约）
- `tests/test_phase2c.py` —— 路由数断言 85 → 110
- `scripts/smoke_test.py` —— `EXPECTED_ROUTES` 85 → 110

### Java 镜像（供 gen_routes / check_parity 读取）
- `pro-business-api/.../controller/v3/*.java`（5 个，从 V3 分支同步）
- `pro-business-api/.../controller/LargeScaleQueryController.java`（更新到 V3）

## 3. 验证结果（2026-11-20 实测）

```
controllers : 29     handlers : 110
check_routes : 29/29 ok, 110 routes registered
check_parity : Tier B = 0 (190 fully matched)
pytest tests/test_v3_alignment.py tests/test_phase2c.py : 8 passed
pytest -q : 213 passed / 9 failed（9 个为 Windows GBK 子进程解码问题，见 HANDOVER §3）
```
