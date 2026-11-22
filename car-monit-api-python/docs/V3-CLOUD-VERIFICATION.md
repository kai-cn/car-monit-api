# 云 runner 实测 + Java V3 全量业务对比验收记录

> 记录时间：2026-11-20（会话内实时记录）
> 触发方式：复用现有 Python workflow — api `master.yml`（内部 `workflow_call` 到 `_python.yml`）、
> backend `ci.yml`（`py` job）、backend master `crosslang-parity-cloud.yml`（跨语言对拍）
> 凭据：`D:\work\runtime-logs\gh_cred.py` 缓存 token；dispatch 经 `dispatch-redacted.py`，不回显输入值

## 1. 云 runner 实测发现的真实回归（本地被编码/环境问题掩盖）

| # | 现象（云日志） | 根因 | 修复 | 提交 |
|---|---|---|---|---|
| 1 | `_smoke_t09c` FAIL：`submitExport.code=400`，`mode` 收到 dict | Java V3 给 `LargeScaleQueryController#submitExport` 新增第 4 参 `mode`，fuzzyFields 移到第 5 参 `body`；smoke 脚本仍按 master 4 参调用 | 改为 `submitExport("trail","S","E",None,raw)` | `32c52c94` |
| 2 | `smoke_test` FAIL：`Controller 数 = 24` | V3 对齐后为 29 个 Controller，脚本硬编码 24 | 断言改为 29 | `53eae39f` |
| 3 | `smoke_all_routes` FAIL：`large export/submit → 403` | 内部守卫未把 Starlette `TestClient` 的合成 host `testclient` 当回环；Java MockMvc 不经真实 socket，等价 127.0.0.1 | 守卫增加 `IN_PROCESS_HOSTS={"testclient"}` | `b3537c0b` |
| 4 | backend `test_quartz_tasks` FAIL：`20 条 != 15 条` | 用例依赖 `datetime.now()` 落在 2026-10；云上当前日期 2026-11 使月份数变 4 | 冻结 `now=2026-10-20` | backend `ac960499` |

**关键结论**：这 4 项本地全量 pytest 都"通过"（本地 Windows 子进程 GBK 解码失败掩盖了 1/2，
时间依赖在本地同样偶发），只有云 runner（Linux、UTF-8、固定时区）暴露。云实测不可替代。

## 2. 云 runner 最终验收结果

### 2.1 api Python 门禁（`master.yml` → `_python.yml`）

- 最终 run：`44712677650`（分支 `car-monit-api-python`，提交 `b3537c0b`）
- `python / python 3.12 (gates)`：**completed success** — 含 pytest、coverage ≥65%、
  `check_routes`（29 controller / 110 route）、`check_parity`（Tier B=0）、`check_mappers`、
  `check_env`、secret scan、`smoke_test`、`smoke_all_routes`
- `python / integration`（Redis+ES+Kafka service containers）：**completed success**
- `python / python image build (no push)` / `image python`：**completed success**
- 运行级失败仅为其它语言 job（`java / java (JDK 8)`、`image java`、`Master Gate`），
  与 Python 迁移无关。

### 2.2 backend Python 门禁（`ci.yml` py job）

- 最终 run：`44712980926`（分支 `car-monit-py-V2`，提交 `ac960499`）
- `py` job：**completed success** — Python 3.12 源码编译 + compileall + pytest + coverage + wheel/sdist
- 覆盖率：34123 语句 / 9147 命中 / **73%**
- 同 run 的 `go` job failure 与本任务无关。

### 2.3 跨语言对拍（复用 `crosslang-parity-cloud.yml`）

- run：`44713232995`（backend master，`langs=python`）
- `baseline-java8`：Java 8 fat jar probe success（startup 16.5s，peak RSS 1711MB）
- `candidates (python)` / `(go)` / `(rust)`：**全部 completed success**，整条 run success
- Python vs Java8 报告（artifact `crosslang-python`，job log `crosslang-python-v3.log`）：
  ```
  endpoints=2  status_match=2  exact=1  semantic=1  nondet=1  fails=0
  /            200/200  69/69 bytes   OK
  /captchaImage 200/200 4140/3968     NONDET（验证码图，body 非确定）
  ```
- 覆盖度限制：该 workflow 的 `endpoints/backend.txt` 仅 2 个免认证端点；
  探针（即便本次扩展了 `--headers-env`）在该 workflow 中未传认证头，
  故**未覆盖 V3 新增的 16 个需权限端点**。这是现有 workflow 的固有覆盖边界，非本次改动缺陷。

### 2.4 Java V3 全量业务对齐的静态证据（云 gates 内执行）

| 检查 | 结果 | 含义 |
|---|---|---|
| `check_parity` | checked 224 / fully matched 190 / Tier B **0** | Java V3 源码与 Python 镜像逐方法对齐，无真实缺口 |
| `check_routes` | 29 controller / 110 route registered | 与 Java V3 handler 数一一对应 |
| `smoke_test` | failed 0，路由 110 / Controller 29 | 路由表与契约一致 |
| `tests/test_v3_alignment.py` | api 7 passed / backend 6 passed | V3 新端点的核心契约（状态机、令牌、守卫、指标） |

## 3. 工具与排障备注（供下个会话）

* 云 runner 日志抓取：`python save_full_joblog.py <repo> <job_id> <out.log>`（重定向会掉 auth，
  必须用仓库内的 `NR` opener）。
* Python workflow 不可单独 dispatch（`_python.yml` 只有 `workflow_call`）；
  必须 dispatch `master.yml`（api）或 `ci.yml`（backend）。
* 云上 Python 源码编译 3–5 分钟，py job 总时长 20+ 分钟属正常，不要误判卡死。
* 认证端点全量 HTTP 对拍是下一步工作：需给 `crosslang-parity-cloud.yml` 增加
  `PARITY_HEADERS_JSON` secret 注入 + 扩展 `endpoints/backend.txt` 到 V3 端点清单，
  并用登录 token 对拍。本次已完成探针侧支持（`--headers-env`）。

## 4. 文档索引

* `V3-ALIGNMENT-PLAN.md` / `V3-ALIGNMENT-HANDOVER.md` / `V3-ALIGNMENT-INDEX.md` —— 对齐基线
* `V3-CLOUD-VERIFICATION.md` —— 本文件
* backend 侧：`car-monit-py/docs/V3-CLOUD-VERIFICATION.md`
