# Java → C++ 迁移进度清单（最终）

> 源工程：`../pro-business-api` + `../pro-base-common`（RuoYi / Spring Boot 2.4.5，24 个 Controller、85 个端点）
> 目标：C++20 + CMake + MinGW-w64 g++ 14.2 + Ninja（Windows）；HTTP/JSON 依赖 vendored，Kafka 依赖由 CMake FetchContent 构建
> 更新时间：2026-11-05

## 一、总体状态

| 指标 | 结果 |
|---|---|
| 构建 | ✅ `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release` + `cmake --build build` 通过（含 librdkafka 2.6.1 静态库），零错误 |
| 测试 | ✅ `ctest` 1/1 通过（`ALL TESTS PASSED`；新增 CORS 用例与 Kafka 无 broker 失败路径） |
| 启动 | ✅ `/health` 200 `{"status":"UP"}`；日志 `路由数 86`、`任务数=10`、`Kafka 生产者启动` |
| 端点 | ✅ 85 个 Java 端点 + 1 个 `/health` = 86 条路由 |
| 定时任务 | ✅ 10 个（与 Java 生效任务一一对应） |
| Kafka | ✅ 默认 librdkafka 真实发送；Redis `mq:pending:<topic>` 可配置降级（默认关闭） |
| CORS | ✅ Spring `CorsConfiguration` 语义；预检 200/403、实际请求头完整 |
| 数据库冒烟 | ⛔ 被 DB 侧账号锁阻塞（`28000 The account has been locked.`/`28P01`），需 DB 管理员解锁后复测；与代码无关。2026-11-06 14:45、14:51（干净重建后）两次复测仍返回 `28000`；同期 Java 9902 因连接池中**旧连接**仍能返回真实数据 |

## 二、模块清单

| 模块 | Java 对应 | 状态 | 说明 |
|---|---|---|---|
| 入口/启动 | `EcBusinessApiApplication` | ✅ 已迁移 | `src/main.cpp` |
| 配置 | `application.yml` + `application-optimization.yml` | ✅ 已迁移 | `src/config/*`、`configs/config.yaml`，键名保留 |
| 日志 | logback-spring.xml | ✅ 已迁移 | 级别/文件可配；线程名→线程 ID |
| 工具类 | StringUtils/DateUtils/Convert/PageUtils/SqlUtil/RedisUtil | ✅ 已迁移 | `src/common/*`；另含自实现 MD5/SHA1/SHA256/HMAC/PBKDF2 |
| 数据库客户端 | Druid + pgjdbc | ✅ 已迁移 | `src/db/pg.*`（wire v3，MD5+SCRAM）；⚠️ 无 SSL/游标 |
| 数据访问 | 22 个 Mapper XML + PageHelper | ✅ 已迁移 | `src/db/dao.*` + `src/meta/entities_generated.h`（19 实体） |
| 缓存 | Lettuce + RedisTemplate | ✅ 已迁移 | `src/cache/redis.*`（RESP2） |
| 字典/基础缓存 | SysDict + RedisUtil | ✅ 已迁移 | `src/service/dict.*` |
| 元数据 | domain 实体 + resultMap | ✅ 已迁移 | 19 个 EntityMeta（字段/物理列/类型/过滤/SQL） |
| 基础 CRUD | 19 个 Controller（48 端点） | ✅ 已迁移 | `src/handler/base_handlers.cpp` |
| SysUtil | SysUtilController + SysUtilServiceImpl（5 端点） | ✅ 已迁移 | `sysutil_handlers.cpp` + `service/track.cpp` |
| SysTest | SysTestController（15 端点） | ✅ 已迁移 | `systest_handlers.cpp` |
| 轨迹/可疑车辆 | TrackTask + SysUtilServiceImpl | ✅ 已迁移 | `service/track.cpp`（13 个对外函数） |
| 大表查询优化 | optimization 包 12 服务（17 端点） | ✅ 已迁移 | `service/optimization.*` + `optimization_handlers.cpp` |
| ES 客户端 | RestHighLevelClient | ✅ 已迁移 | httplib REST（search/scroll/bulk）；不可达降级 DB |
| 定时任务 | `@Scheduled` + Quartz cron | ✅ 已迁移 | `src/scheduler/scheduler.cpp`（10 任务） |
| 可靠性/丢失/延迟/一致性 | DataReliability / DataLossDetection / DelayMonitoring / GaussEsConsistency | ✅ 已迁移 | `service/ops.*` |
| 路由装配 | Spring MVC | ✅ 已迁移 | `src/router/routes.cpp` |
| 测试 | JUnit | ✅ 已迁移 | `tests/test_main.cpp` + CTest |
| 交付文档 | 提示词要求 | ✅ 已迁移 | `README_CPP.md`、`MIGRATION_GUIDE.md`、`COMPATIBILITY.md`、本清单 |
| 启动脚本 | — | ✅ 已迁移 | `scripts/run.ps1` |
| Kafka 生产 | KafkaProducerConfig + KafkaProducerService + DataReliabilityService | ✅ 已迁移 | `src/mq/kafka_producer.*`（librdkafka：key=dataId、value=JSON、`__TypeId__`、异步回调、重试/死信、`kafka_message_record`） |
| CORS | Spring CorsConfiguration / DefaultCorsProcessor | ✅ 已迁移 | `src/http/cors.*`；预检前置、`Vary`、ACAO/ACAM/ACAH/ACEH/ACAC/ACMA |
| SnapshotFlowSyncService | `@PostConstruct` 全量/增量推送 | ✅ 已迁移 | `src/service/snapshot_flow_sync.*`（2 线程、batch=1000、批间 100ms、增量 interval=60000ms、游标键与 Java 一致） |
| Pulsar 消费者 | SnapshotFlow / DebeziumReadonly | ⛔ 不适用 | Java 中 `@Service` 被注释，运行时未注册 |
| RocketMQ 消费 | RocketMqConsumer | ⛔ 不适用 | Java 注解被注释 |
| CarTask | 全部方法体注释 | ⛔ 不适用 | 不注册调度 |
| SecurityInterceptor / WebConfig | 整体被注释 | ⛔ 不适用 | 无鉴权（与 Java 运行一致） |
| Spring AOP / 反射 / 事务 | 无实际切面；`@Transactional` 未使用 | ⛔ 不适用 | 见 COMPATIBILITY.md |
| Flink Job | `VehicleTrackFlinkJob`（独立作业） | ⛔ 不适用 | 不在 `pro-business-api` 的 HTTP 服务内运行 |

## 三、验证记录

| 验证项 | 结果 |
|---|---|
| 全量编译 | ✅ 通过（零 error；`-Wall -Wextra`） |
| 单元/契约测试 | ✅ `ALL TESTS PASSED`（crypto 向量、分页夹末页、AjaxResult 键序、Spring 404 信封、路由计数、CORS 10 组用例、Kafka 无 broker 失败路径） |
| `/health` | ✅ 200 `{"status":"UP"}` |
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
