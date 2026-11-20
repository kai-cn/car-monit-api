# api Python ↔ Java V3 对齐：交接记录

> 记录时间：2026-11-20（会话内实时记录，非事后追认）
> 分支：`car-monit-api-python`（工作树 `d:/work/IdeaProjects/car-monit-api-java-V3`）
> 对齐目标：`car-monit-api-java-V3`

## 1. 已完成（P0 端点全量对齐）

| 项 | 结果 | 证据 |
|---|---|---|
| Java V3 Controller 镜像同步 | 5 个新 Controller + `LargeScaleQueryController.java` 更新 | `pro-business-api/src/main/java/com/ruoyi/base/controller/v3/` |
| 路由生成器支持 `v3` 子包 | `gen_routes.py` 补递归扫描 | `tools/gen_routes.py:358` |
| 生成表 | **29 Controller / 110 handler**（master 基线 24 / 85） | `app/routes/generated.py:8` |
| Python Controller 实现 | 5 个新类 + `LargeScaleQueryController` 的 `downloadExport`/`mode` | `.../controller/v3/*.py` |
| V3 服务层 | 22 个 Java 类集中在一个 `v3_services.py`，类名/方法名保持一致 | `.../service/v3/v3_services.py` |
| 内部端点守卫 | `/api/v3/**` + `/api/v1/large/export/**`，令牌头 + 回环白名单 | `app/middleware/internal_guard.py` |
| 方法级 parity | **Tier B = 0**（190 fully matched） | `python tools/check_parity.py` |
| 路由注册 | 29/29 controller ok，110/110 route registered | `python tools/check_routes.py` |
| 专用测试 | 7/7 通过 | `tests/test_v3_alignment.py` |
| 全量测试 | 213 passed / 9 failed / 19 skipped | 见 §3 |

## 2. 未完成 / 已知差异（下个会话优先级）

1. **P1 真实中间件接入**：`v3_services.py` 的 ES/GaussDB/Kafka 操作是契约骨架（空结果 + 任务状态机），
   未接 `app.middleware.real_es` / `app.db.engine`。Java V3 的 ES 查询语义（PIT/search_after、
   ILM、reconcile 分钟桶、bulk 回灌）尚未在 Python 侧落地真实数据路径。
2. **P1 `ResponseEntity` 状态码**：api Python 的 registry 统一返回 HTTP 200（body 带 `code`），
   Java 的 `BigScreenStatsV3Controller` / `BigScreenWarningV3Controller` 返回真实 4xx/5xx 状态。
   当前 backend Python 按 `body.code` 判断，端到端行为等价；若要求逐字节状态一致，需改 registry。
3. **P2 `downloadExport` 文件流**：返回 `_download` 契约 dict，未实现真实 `FileResponse` 写出。
   Java 返回 `application/gzip` + `Content-Disposition: <taskId>.csv.gz`。
4. **P2 `traffic.*` 配置项**：Java V3 新增的 7 组配置尚未写进 Python `app/settings.py`
   （当前用 `TRAFFIC_QUERY_ENGINE` / `TRAFFIC_SECURITY_INTERNAL_TOKEN` 两个环境变量兜底）。
5. **P2 Kafka `SearchSyncConsumer`**：Java V3 新增 `@KafkaListener`（`search-sync` topic），
   Python 侧未注册对应消费者；Python-only 的 health/metrics 路由已存在。

## 3. 测试环境说明（重要，避免误判为回归）

* 使用 `D:\work\IdeaProjects\car-monit-api\car-monit-api-python\.venv\Scripts\python.exe`（Python 3.12.9，
  含 `confluent_kafka`）。其它 sibling worktree 的 venv 缺该包，会产生 22 个假失败。
* 全量 `pytest -q` 的 9 个失败**全部为 Windows 控制台 GBK 编码导致的子进程 stdout 解码失败**
  （`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xcb`，随后 `TypeError: argument of type 'NoneType'`）：
  `_smoke_t08_delay/timerange`、`_smoke_t09b~f`、`test_check_secrets`、`test_v2_p0::test_app_boots...`。
  这些脚本单独运行均输出 `SMOKE OK`；与 V3 改动无关。
* 推荐门禁命令（本次全部通过）：
  ```powershell
  python tools\gen_routes.py
  python tools\check_routes.py
  python tools\check_parity.py
  python -m pytest tests/test_v3_alignment.py tests/test_phase2c.py -q
  ```

## 4. 云 runner 实测（2026-11-20 增补）

复用现有 Python workflow 完成云实测，`python / python 3.12 (gates)`、`integration`、
`image build` 全部 success（run `44712677650`）。云上暴露并已修复 3 个本地被掩盖的真实回归：
t09c `submitExport` 签名（`32c52c94`）、smoke Controller 数断言（`53eae39f`）、
内部守卫 TestClient host（`b3537c0b`）。跨语言对拍 `crosslang-parity-cloud.yml`
（run `44713232995`）整条 success，Python vs Java8 `fails=0`。详见 `V3-CLOUD-VERIFICATION.md`。

## 5. 文档索引

* `V3-ALIGNMENT-PLAN.md` —— 端点差距矩阵与实施顺序（基线）
* `V3-ALIGNMENT-INDEX.md` —— 文件级索引
* `V3-ALIGNMENT-HANDOVER.md` —— 本文件（交接）
* `V3-CLOUD-VERIFICATION.md` —— 云 runner 实测与对拍验收记录
* `Java-to-Python-对照手册.md` —— 迁移期 master 基线对照手册（仍有效，V3 增量看本目录）
* `迁移审阅报告.md` —— master 基线审阅记录

## 5. 下一条命令

```powershell
Set-Location d:\work\IdeaProjects\car-monit-api-java-V3
git add -A
git commit -m "feat(python): 对齐 Java V3 24+1 端点与内部守卫"
```
