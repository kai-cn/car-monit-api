# car-monit-api-cpp 合并审阅与测试记录（2026-11-22）

## 1. 合并结论

- 在 master 工作树 `D:/work/IdeaProjects/car-monit-api` 将本地分支 `car-monit-api-cpp` 合并到 `master`，曾生成合并提交 `ce9a0f31 Merge branch 'refs/heads/car-monit-api-cpp'`。
- 合并前两分支存在大量交叉合并：cpp 功能提交早已被 master 包含；cpp 分支剩余提交多为 CI 注释/性能调整的重复实现。合并实际冲突仅在 `.github/workflows/_java.yml`，已按 master 版本保留（openEuler 24.03 + JDK8 构建路径），最终合并树相对 master 净变化为空。
- **最终处置**：因 `ce9a0f31` 为空合并（tree 与基点 `2a8f6ce5` 相同），且同期用户已手动提交并 push 了 `crosslang-full-parity-cloud.yml` 的 CI 修复，为避免重复提交，已丢弃该空合并，将 master 对齐到最新远程 `81efbffe`，随后完成提交时间修复并强推。最终远程 master = `1eb9dd4d`（详见 §6）。
- 未触碰工作区既有未提交修改 `.github/workflows/crosslang-full-parity-cloud.yml`（其内容与用户已 push 的提交一致，重复 stash 已丢弃）。

## 2. 代码审阅结论

审阅对象：master 中 `car-monit-api-cpp/` 目录。结论：迁移工程基本完成，路由覆盖完整，但**行为等价性与端到端验证仍未闭环**，不建议直接标注生产就绪。

### 已完成/证据

- 路由覆盖 87/87（85 业务 + `/health`、`/metrics`）：`car-monit-api-cpp/contracts/README.md:7-14`，`car-monit-api-cpp/contracts/endpoints.golden.json:3-440`。
- C++20/CMake 工程，三目标 `carmonit_core`、`car-monit-api`、`carmonit_tests`，严格告警与 sanitizer 开关：`car-monit-api-cpp/CMakeLists.txt:1-6,12-59,178-244`。
- 依赖替换完成：libpqxx/libpq 参数绑定（`src/db/pg.cpp:48-53,181-187`）、hiredis 超时/TLS（`src/cache/redis.cpp:79-135`）、librdkafka 真实发送/重试/死信（`src/mq/kafka_producer.cpp:36-39,163-185,396-419`）、ES REST 与失败降级 PG（`src/service/optimization.cpp:159-236`）。
- 安全与可靠性：可选 API-Key/IP 限流（`src/http/server.cpp:335-489`）、有界后台池与优雅停机（`src/common/worker_pool.cpp:15-101`，`src/main.cpp:119-128`）、cron 语义与丢失检测周期对齐（`src/scheduler/cron.cpp:55-144`，`src/scheduler/scheduler.cpp:141-187`）。
- 旧阻断项已修复（SQL 注入白名单、响应信封、cron、连接池、可靠性队列、超时/指标）：`car-monit-api-cpp/docs/MIGRATION_PROGRESS.md:7-35`。

### 阻断/高风险项

1. **契约验证闭环缺失**：黄金基线只固化 method/path/响应形态，无 Java 真实响应体 diff；`contracts/README.md:16-18,47-51` 明确标注精确响应体待采集。`test_contract_routes_golden` 的 `kind` 由被测实现自身生成（`tests/test_main.cpp:895-899`），若实现与基线同步漂移无法发现。
2. **端到端未验证**：Kafka 仅验证无 broker 失败路径（`docs/MIGRATION_PROGRESS.md:104`）；ES 依赖外部已建索引（`MIGRATION_PROGRESS.md:108`）；部署文档承认仓库无完整生产 DDL（`deploy/README.md:75-82`）。
3. **无事务**：多语句写依赖人工补偿（`docs/MIGRATION_PROGRESS.md:109`；`src/db/pg.cpp:464-474` 的事务接口未形成业务使用面）。
4. **安全默认宽松**：HTTP 明文监听，鉴权/限流默认关闭（`configs/config.yaml:7-21`），限流为进程内固定窗口，多实例不共享。
5. **实现风险**：ES 每次请求新建 `httplib::Client` 且 30s 冷却全局生效（`src/service/optimization.cpp:166-168,184-186`）；两处 detached 线程不参与 join（`src/service/optimization.cpp:1660-1703`，`src/http/server.cpp:570-572`）；BigDecimal 占位符回写裸数字存在用户字符串误命中风险（`src/common/json.cpp:8-10,44-73`）；`logging.level` 配置项未生效（`src/config/config.cpp:202-203,450-452`）。
6. **文档/CI 注释陈旧**：`docs/CODE_REVIEW.md:15-19` 的“等价度 60%/生产就绪 30%”为修复前历史结论；`.github/workflows/master.yml:27-28` 与 `_cpp.yml:18-19` 仍称 master C++ 源码不完整，但当前 master 已有完整源码；`CMakeLists.txt:184-186` 仍 glob 空的 `src/es/`、`src/repo/`。

## 3. 本地实测

- 工具链：CMake + Visual Studio 2022（MSVC 19.43），生成器 `Visual Studio 17 2022 -A x64`。
- 配置：`cmake -S D:/work/IdeaProjects/car-monit-api/car-monit-api-cpp -B D:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/build -G "Visual Studio 17 2022" -A x64 -DCM_WITH_KAFKA=ON` 成功；FetchContent 成功获取 librdkafka 2.6.1、libpqxx 7.10 + libpq 17.2、hiredis 1.5。
- 编译：`cmake --build ... --config Release --parallel` 成功，产出 `car-monit-api.exe`、`carmonit_tests.exe`、`carmonit_core.lib`；依赖库仅有第三方 C4819/C5030 警告，本项目源码无编译错误。
- 测试：`ctest --test-dir ... -C Release --output-on-failure` 通过（1/1 测试目标，15.96s）；内部 `carmonit_tests` 注册 33 个测试函数（`tests/test_main.cpp:1458-1491`）。

## 4. 迁移进度判断

- **工程迁移：完成**（可配置、可编译、可测试，双平台 CI 路径存在）。
- **路由迁移：完成**（87/87 端点纳入黄金基线，19 实体 CRUD 统一生成）。
- **行为等价验证：进行中**（仅有路由/形态基线，缺 Java 真实响应体 diff 与有状态端点验证）。
- **生产就绪：未完成**（DB/Kafka/ES 端到端、事务、安全默认、TLS、openGauss SHA256 兼容性仍待处理）。

## 5. 后续建议

1. 先补 Java 与 C++ 真实响应体采样/diff，尤其 POST/PUT/DELETE、导出与异常路径；再更新黄金基线与 `MIGRATION_PROGRESS.md` 结论。
2. 在联调环境用 compose/k8s 资产跑 DB/Kafka/ES 真实冒烟，记录可复现命令与结果；明确生产 DDL 来源。
3. 上线前收口 HTTP TLS、鉴权默认策略、多实例限流、ES 连接复用、detached 线程 join、BigDecimal 占位符与 `logging.level` 配置生效。
4. 清理历史审阅/工作流注释与空 glob，避免把修复前 60%/30% 结论误当现状。

## 6. 提交时间修复与远程对齐（收尾记录）

- 对齐：丢弃空合并 `ce9a0f31`（tree 与基点 `2a8f6ce5` 相同，无独有内容），本地 master 依次对齐到 `b581d9f2` 与最新远程 `81efbffe`（用户已 push 的两个 CI 提交），避免重复提交。重复 stash 已丢弃，审阅文档保留。
- 时间修复：用 `git filter-branch --env-filter` 对 44 个 cpp 迁移提交（作者时间 11-07/11-08，提交者时间被批量改成 11-22 11:46/11:48）把提交者时间改回作者时间；筛选条件为提交者时间戳落在 `[1795319183,1795319323]` 且作者时间戳 `< 1795200000`，其余提交不动。
- 验证：提交数 578 不变；tree 前后均为 `0352a0c9...`，`git diff` 为空（内容零变化）；时间错位提交从 45 降至 1，仅剩 `ebe4712d`（作者 11-17 / 提交 11-19，本就不在目标范围，正确保留）。示例：`fix(ops): use explicit non-system UID` 新哈希 `95d6029e`，作者/提交时间均为 `2026-11-08 15:58:31 +0800`。
- 强推：经用户确认，执行 `git push --force-with-lease origin master`，远程 master 由 `81efbffe` 更新为 `1eb9dd4d`（forced update）；`ls-remote` 已复核一致。回滚点保留在 `refs/original/refs/heads/master`=`81efbffe` 与 `backup/master-before-date-fix-20261122`=`ce9a0f31`。
- 清理：filter-branch 临时目录 `.git-rewrite`（585 文件）已删除。
