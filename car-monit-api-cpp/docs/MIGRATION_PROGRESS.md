# Java → C++ 迁移进度清单（最终）

> 源工程：`../pro-business-api` + `../pro-base-common`（RuoYi / Spring Boot 2.4.5，24 个 Controller、85 个端点）
> 目标：C++20 + CMake + MSVC 2022/Ninja（Windows，已实测）；Linux 由 GitHub Actions 矩阵验证
> 更新时间：2026-11-08（P0-P7 工程化推进完成）

## 〇〇、2026-11-08 工程化推进（P0-P7，分支 `car-monit-api-cpp`）

| 阶段 | 内容 | 提交 | 验证 |
|---|---|---|---|
| P0 | 清理可再生构建目录；MSVC `/W4` + `-Wall -Wextra -Wpedantic` + 默认 `-Werror`；第三方头 SYSTEM 隔离；ASan/UBSan 选项；`getenv` 收敛 | `977534d` | 全量重编译零告警；ctest 1/1 |
| P1 | GitHub Actions：Windows(MSVC)/Linux(GCC)/Linux(Clang) 矩阵 + ASan/UBSan + cppcheck + 增量 clang-format | `4717a4e` | Linux 结果以 CI 首次运行为准（本机无 WSL/Docker） |
| P2 | PG 客户端换 libpqxx 7.10 + libpq 17：参数绑定、TLS、语句超时、28P01/28000 映射、事务；查询层 SqlFragment 全量参数化；删除自研认证与 `auth-mode` | `9cfb768` | MSVC 构建零告警；ctest 1/1（含回环失败路径，未连真实库） |
| P3 | Redis 客户端换 hiredis 1.5：连接/命令超时、可选 TLS；保留接口与重连语义 | `c33a74d` | 同上；fd 泄漏/自锁测试扩展 |
| P4 | 20 个 `SELECT *` 运行期展开显式列；字典进程内缓存（TTL 300s）+ 称重字典批量回源；count 去 ORDER BY；深翻页标注 | `4d261fc` | 新增 `test_entity_select_columns`；ctest 1/1 |
| P5 | 契约骨架：87 条路由黄金基线；只读采集脚本 + JSON diff 脚本 | `d045300` | 黄金基线严格比较通过；Java 9902 不可达 → 真实响应待采集 |
| P6 | 指标 P50/P95/P99 + 错误率 + 依赖状态/延迟 + 线程池队列；Prometheus 文本；JSON 日志 + requestId；停机硬超时 | `9b54c55` | 新增指标/JSON 日志断言；ctest 1/1 |
| P7 | 文档收尾 + 清空重建 + 启动冒烟 | 本次提交 | 见下节“最终自检” |

## 〇、2026-11-07 审阅修复轮（依据 docs/CODE_REVIEW.md，分支 car-monit-api-cpp）

按问题严重性逐项修复，每项独立提交、构建 + ctest 全绿后推进：

| # | 修复 | 提交 | 验证 |
|---|---|---|---|
| 基线 | 迁移基线入库（worktree `d:\work\IdeaProjects\car-monit-api-cpp-wt`，基于 master@21cc4ea） | `c21271f` | MSVC+Ninja 构建 + ctest 1/1 |
| 1 | SQL 注入（fuzzyFields key / groupBy / countField 白名单 + large 路由对齐 Java queryByDs） | `b094ed8` | test_query_field_whitelist（含注入载荷拒绝） |
| 2 | 16 个 `/{id}` 端点 AjaxResult 信封 + 空结果非空 body | `dd3f54d` | test_info_envelope_contract（16/3 全路径核对） |
| 3 | cron `0/3` 步进 / 周 0-7=周日 / 日周 AND（spring-context 5.3.6 探针实证）+ 丢失检测 30s | `f20dcae` | test_cron_spring_semantics（40+ 断言） |
| 4 | 可靠性超时检测闭环（scheduleTimeoutCheck + timeout 队列写入；澄清 Java 回调写 SENT） | `22b2fe6` | test_reliability_timeout（判定 + 线程生命周期） |
| 5 | POSIX 分支恢复阻塞/超时/include + scripts/ci-linux.sh + README 平台声明如实 + .gitattributes | `bc29c46`+`2f71b86` | Windows 回归全绿；Linux 提供脚本待实机验证 |
| 6 | 连接池锁外建连+CV+30s 熔断+maxWait 分离；Redis fd 泄漏+自锁死锁+半包读+SCAN；受控后台线程池 | `9bde423` | test_worker_pool / test_pg_pool_connect_breaker / test_redis_reconnect_no_deadlock |
| 7 | 可选 API-Key 鉴权 + IP 限流（默认关闭对齐 Java）+ 1MB 请求体 + 30s 读写超时 | `f7a5448` | test_server_security |
| 8 | /health 四组件状态（不主动建连）、/metrics、SIGINT/SIGTERM 优雅停机（全线程可 join）、日志按大小轮转 | `ccf97ca` | test_health_and_metrics / test_log_rotation |
| 9 | 文档纠偏（未分页 total、SELECT * 20/22、BigDecimal 尾零、端点数 87、线程模型描述） | 本次提交 | 文档与代码逐项核对 |

## 一、总体状态

| 指标 | 结果 |
|---|---|
| 构建 | ✅ MSVC 2022（cl 19.43）+ Ninja + Release 通过；依赖 librdkafka 2.6.1 / libpqxx 7.10.0 / libpq 17.2 / hiredis 1.5.0，零告警（`/W4` + `/WX`） |
| 测试 | ✅ `ctest` 1/1 通过（`ALL TESTS PASSED`；含白名单/信封契约/cron/池熔断/参数绑定/列清单/契约基线/指标/JSON 日志等用例） |
| 启动 | ✅ `/health` 200（依赖状态汇总，不主动建连）；`/metrics` JSON + `?format=prometheus` |
| 端点 | ✅ 85 个 Java 端点 + `/health` + `/metrics` = 87 条路由 |
| 定时任务 | ✅ 10 个（触发频率与 Java 一致：0/3 分钟步进、30s 丢失检测、02:30 对账等） |
| Kafka | ✅ 默认 librdkafka 真实发送；Redis `mq:pending:<topic>` 可配置降级（默认关闭）；可靠性超时队列已闭环 |
| CORS | ✅ Spring `CorsConfiguration` 语义；预检 200/403、实际请求头完整 |
| 数据库冒烟 | ⛔ 被 DB 侧账号锁阻塞（`28000 The account has been locked.`/`28P01`），需 DB 管理员解锁后复测；与代码无关。2026-11-06 14:45、14:51（干净重建后）两次复测仍返回 `28000`；同期 Java 9902 因连接池中**旧连接**仍能返回真实数据 |

## 二、模块清单

| 模块 | Java 对应 | 状态 | 说明 |
|---|---|---|---|
| 入口/启动 | `EcBusinessApiApplication` | ✅ 已迁移 | `src/main.cpp` |
| 配置 | `application.yml` + `application-optimization.yml` | ✅ 已迁移 | `src/config/*`、`configs/config.yaml`，键名保留 |
| 日志 | logback-spring.xml | ✅ 已迁移 | 级别/文件可配；线程名→线程 ID；按大小轮转（logging.max-file-mb/max-files） |
| 工具类 | StringUtils/DateUtils/Convert/PageUtils/SqlUtil/RedisUtil | ✅ 已迁移 | `src/common/*`；另含自实现 MD5/SHA1/SHA256/HMAC/PBKDF2 |
| 数据库客户端 | Druid + pgjdbc | ✅ 已迁移 | `src/db/pg.*`（libpqxx 7.10 + libpq 17；参数绑定/TLS/语句超时）；⚠️ stock libpq 不支持 openGauss sha256 |
| 数据访问 | 22 个 Mapper XML + PageHelper | ✅ 已迁移 | `src/db/dao.*` + `src/meta/entities_generated.h`（19 实体） |
| 缓存 | Lettuce + RedisTemplate | ✅ 已迁移 | `src/cache/redis.*`（hiredis 1.5；连接/命令超时、可选 TLS） |
| 字典/基础缓存 | SysDict + RedisUtil | ✅ 已迁移 | `src/service/dict.*` |
| 元数据 | domain 实体 + resultMap | ✅ 已迁移 | 19 个 EntityMeta（字段/物理列/类型/过滤/SQL） |
| 基础 CRUD | 19 个 Controller（48 端点） | ✅ 已迁移 | `src/handler/base_handlers.cpp` |
| SysUtil | SysUtilController + SysUtilServiceImpl（5 端点） | ✅ 已迁移 | `sysutil_handlers.cpp` + `service/track.cpp` |
| SysTest | SysTestController（15 端点） | ✅ 已迁移 | `systest_handlers.cpp` |
| 轨迹/可疑车辆 | TrackTask + SysUtilServiceImpl | ✅ 已迁移 | `service/track.cpp`（13 个对外函数） |
| 大表查询优化 | optimization 包 12 服务（17 端点） | ✅ 已迁移 | `service/optimization.*` + `optimization_handlers.cpp` |
| ES 客户端 | RestHighLevelClient | ✅ 已迁移 | httplib REST（search/scroll/bulk）；不可达降级 DB |
| 定时任务 | `@Scheduled` + Quartz cron | ✅ 已迁移 | `src/scheduler/`（10 任务；`cron.{h,cpp}` 独立解析器，Spring 5.3.6 语义） |
| 可靠性/丢失/延迟/一致性 | DataReliability / DataLossDetection / DelayMonitoring / GaussEsConsistency | ✅ 已迁移 | `service/ops.*` |
| 路由装配 | Spring MVC | ✅ 已迁移 | `src/router/routes.cpp` |
| 测试 | JUnit | ✅ 已迁移 | `tests/test_main.cpp` + CTest |
| 交付文档 | 提示词要求 | ✅ 已迁移 | `README_CPP.md`、`MIGRATION_GUIDE.md`、`COMPATIBILITY.md`、本清单 |
| 启动脚本 | — | ✅ 已迁移 | `scripts/run.ps1`；另有 `scripts/ci-linux.sh`（Linux 验证） |
| Kafka 生产 | KafkaProducerConfig + KafkaProducerService + DataReliabilityService | ✅ 已迁移 | `src/mq/kafka_producer.*`（librdkafka：key=dataId、value=JSON、`__TypeId__`、异步回调、重试/死信、`kafka_message_record`、超时检测） |
| CORS | Spring CorsConfiguration / DefaultCorsProcessor | ✅ 已迁移 | `src/http/cors.*`；预检前置、`Vary`、ACAO/ACAM/ACAH/ACEH/ACAC/ACMA |
| SnapshotFlowSyncService | `@PostConstruct` 全量/增量推送 | ✅ 已迁移 | `src/service/snapshot_flow_sync.*`（2 线程、batch=1000、批间 100ms、增量 interval=60000ms、游标键与 Java 一致、可停机 join） |
| Pulsar 消费者 | SnapshotFlow / DebeziumReadonly | ⛔ 不适用 | Java 中 `@Service` 被注释，运行时未注册 |
| RocketMQ 消费 | RocketMqConsumer | ⛔ 不适用 | Java 注解被注释 |
| CarTask | 全部方法体注释 | ⛔ 不适用 | 不注册调度 |
| SecurityInterceptor / WebConfig | 整体被注释 | ⛔ 不适用 | 无鉴权（与 Java 运行一致；C++ 另提供可选 API-Key/限流，默认关闭） |
| Spring AOP / 反射 / 事务 | 无实际切面；`@Transactional` 未使用 | ⛔ 不适用 | 见 COMPATIBILITY.md |
| Flink Job | `VehicleTrackFlinkJob`（独立作业） | ⛔ 不适用 | 不在 `pro-business-api` 的 HTTP 服务内运行 |

## 三、验证记录

| 验证项 | 结果 |
|---|---|
| 全量编译 | ✅ 通过（零 error；MSVC /W3，POSIX 分支 -Wall -Wextra 等价检查随 ci-linux.sh） |
| 单元/契约测试 | ✅ `ALL TESTS PASSED`（crypto 向量、分页夹末页、AjaxResult 键序、Spring 404 信封、路由计数、CORS 10 组用例、Kafka 无 broker 失败路径、查询字段白名单、信封契约、cron 语义、池熔断、线程池、安全判定、健康检查结构、日志轮转） |
| `/health` | ✅ 200 `{status: UP|DEGRADED, components:{database,redis,kafka,elasticsearch}}` |
| `/metrics` | ✅ 200 `{requestsTotal,errorsTotal,inFlight,avgLatencyMs,uptimeSeconds}` |
| CORS 预检通过 | ✅ `OPTIONS` + 白名单 origin → 200 + `Access-Control-Allow-Origin/Methods/Max-Age` + `Vary` |
| CORS 预检被拒 | ✅ 非白名单 origin → 403 `Invalid CORS request`（`text/plain;charset=ISO-8859-1`） |
| CORS 实际请求 | ✅ 跨域 GET 带 ACAO；origin 不在白名单时继续业务且不带 ACAO |
| Kafka 无 broker | ✅ 启动不失败；`send_sync` 返回失败并带错误信息（`test_kafka_no_broker`） |
| 未知路径 | ✅ 与 Java 逐字段一致：`{"timestamp","status":404,"error":"Not Found","message":"","path"}` |
| 列表接口（需要 DB） | ⛔ 当前被 DB 账号锁阻塞，返回与 Spring 同形的 500 信封；解锁后需复测 |
| 参数类型错误 | ✅ 400 + Spring error 信封 |

## 四、剩余风险 / 待确认

1. **DB 账号锁（冒烟阻塞项）**：`28000 The account has been locked.` 阻断所有**新**连接（已建立连接不受影响 —— Java 9902 仍能用连接池里的旧连接返回真实数据）。解锁需 DB 侧执行 `ALTER USER gaussdb ACCOUNT UNLOCK;`。解锁前 C++ 侧无法做数据级比对，只能做静态比对（字段名/顺序/类型已与 Java 实测响应核对一致）。
2. **Kafka 端到端未验证**：本机无可用 broker（`localhost:9092` 不可达），只覆盖了失败路径。需 broker + topic + `jl_data01.kafka_message_record` 可写，详见 COMPATIBILITY.md §9.4。
3. **`BigDecimal` 尾零**：✅ 已按 Java 语义保留标度（`json_raw_decimal` + `json_dump`，覆盖不同标度/负数/零）。
4. **CORS 默认值**：Java 源码没有 CORS 配置，默认采用 Spring `applyPermitDefaultValues()`；若线上 Java 有独立白名单，需按实际值配置 `cors.allowed-origins`。详见 COMPATIBILITY.md §9.6。
5. **SnapshotFlowSyncService**：✅ 已按 Java 源码一比一迁移（`src/service/snapshot_flow_sync.cpp`），游标/批大小/间隔/启停条件均取自源码。
6. **ES 索引管理**：不建索引、不挂 ILM（与 Java 配置 `auto-create:false`/`attach-ilm:false` 一致），但依赖外部已建好索引。
7. **无事务**：新增多语句写操作时需要人工补偿。
8. **Linux 实机验证**：POSIX 差异已由 libpqxx/hiredis 接管；CI 已配置 GCC/Clang/ASan 三个 Linux job，但本机 WSL 被禁用、无 Docker，**首次 CI 运行结果待确认**。
9. **契约响应体 diff**：路由级黄金基线（87 条）已完成；Java 9902 于 2026-11-08 探测为连接被拒绝，真实响应样本待采集；采集/diff 脚本已就绪（`scripts/contract-collect.ps1`、`contract-diff.ps1`）。
10. **openGauss 专有 SHA256**：stock libpq 不支持；若服务端 `password_encryption_type` 仅允许 sha256/sm3，需改为 md5 或使用 openGauss 定制 libpq（见 DECISIONS D-011）。
11. **HTTP TLS**：PG/Redis 已支持 TLS；HTTP 监听仍为明文，按审阅建议由前置网关终结 TLS。
12. **Kafka 端到端**：仍无可用 broker；只覆盖失败路径/死信落库。
13. **SysTest 异步任务**：`syncSuspiciousCar1..10` 仍使用 detached 线程（Java 为 `CompletableFuture.runAsync`）；后续可改为独立受控线程池。
14. **磁盘**：P7 清空重建后 D 盘仅剩约 55 MB（回收站占用需人工清空）；后续大构建前需先释放空间。

## 五、P7 最终自检（2026-11-08）

| 项 | 结果 |
|---|---|
| 清空重建 | 删除 `build/` 后全新 configure + build 成功；本工程代码零告警（第三方库仅 C4819/C5030 噪声） |
| ctest | `1/1 Test #1: carmonit_tests ... Passed`（`ALL TESTS PASSED`） |
| 启动冒烟 | 回环失败路径（DB/Redis 指向 `127.0.0.1:1`、Kafka 关闭）：`/health` 200 `DEGRADED`（database/redis/kafka/elasticsearch 四组件齐全）；`/metrics` JSON 含依赖状态/延迟分位；`/metrics?format=prometheus` 60 行；`/no-such-endpoint` 返回 Spring error 信封（`timestamp/status/error/message/path`） |
| 磁盘 | D 盘剩余约 55 MB（低于 1 GB 阈值，需人工清空回收站后才能继续大构建） |
