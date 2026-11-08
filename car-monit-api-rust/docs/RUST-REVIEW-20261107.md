# car-monit-api-rust 迁移实现审阅报告

> 审阅日期：2026-11-07（第二轮补充：迁移进度盘点、生产适配性评估、生产化路线图、真实编译验证）
> 对象：`d:\work\IdeaProjects\car-monit-api\car-monit-api-rust`（下文简称 "Rust 侧"）
> 基线：`pro-business-api` + `pro-base-common`（Java 17 / Spring Boot，下文简称 "Java 侧"）
> 方式：**只读静态审阅** + 编译验证（第二轮已真实执行 `cargo check` / `clippy` / `test`，结果见 §1.1）：Cargo/源码/配置/测试逐文件阅读，并与 Java 源码逐点对照。
> 约束遵守情况：未修改业务代码、未提交、未触碰 `../car-monit-api-cpp`。
>
> **报告结构**：§1–§6 与附录 A 为第一轮审阅结论（技术栈评估、迁移质量、P0/P1/P2 建议）；
> §7 迁移进度盘点、§8 生产适配性评估、§9 生产化路线图为第二轮补充，与第一轮结论互补（§9 是对 §4 的可排期重排，不是推翻）。

---

## 0. 执行摘要

| 维度 | 结论 |
|---|---|
| 迁移完成度 | **高**。85/85 路由、19 张业务表、21 个定时任务登记、572 条 `<if>` 条件、响应壳/键序/PageHelper 边界/Spring 错误体均逐字复刻；文档记录 548 项双端用例 0 应用层不一致。 |
| 技术栈选型 | **主流且合理**。axum + tokio + sqlx + redis + rdkafka + reqwest + config + serde + tracing，没有引入实验性库；自研集中在 3 处：Jackson 兼容标量层、`Cond` 查询 DSL、6 段 cron。 |
| 语义保真 | HTTP 契约层质量高；但**同步/对账/丢包检测/消费端**等"非 HTTP 主链路"存在明显缺口，恰好是 548 项双端用例未覆盖或跳过的部分。 |
| 风险等级 | **中高**：发现 4 个 P0（SQL 注入、时间戳绑定、消费端默认启用、幂等键导致丢消息），不建议未修复前直接替代生产 Java。 |
| 测试覆盖 | **偏薄**：20 个单测/装配测试；无 DB/服务级测试；548 项对比依赖外部 Python 脚本，不在 CI 中。 |
| 编译验证 | **已完成（第二轮）**：`cargo check --all-targets` 通过（0 error）；`cargo clippy --all-targets -- -D warnings` **不通过**（505 条 warning，其中 466 条来自生成代码 `filters_gen.rs`）；`cargo test` **20/20 通过**。详见 §1.1。 |
| 生产就绪度 | **未达（第二轮结论）**：功能迁移完成度高，但限流/指标/密钥管理/SIGTERM 停机/多实例一致性等 11 项生产基建缺失或不足，详见 §8。 |

**总体建议**：作为"1:1 迁移"的完成度值得肯定，可作为灰度候选，但上线前必须完成：① 关闭消费端或修复幂等先写后处理；② 修复时间戳绑定；③ 修复 `fuzzyFields` 注入面；④ 对 `sync/reconcile/loss` 做真实环境验证。

**第二轮补充结论**（详见 §7–§9）：功能迁移层面 85 条端点中 61 条真实现、47 个 Service 中 30 个已迁移、54 条 Mapper 语句中 49 条有等价实现；但生产基建仍缺 **SIGTERM 优雅停机、限流/背压、指标暴露、密钥外置、多副本一致性** 五类能力，需按 §9 的 B1–B10 完成后再进入灰度。

---

## 1. 审阅方法与限制

### 1.1 编译/Clippy/测试验证结果（第二轮已真实执行）

第一轮审阅时 D 盘可用空间为 0，`cargo check` 因 `os error 112（磁盘空间不足）` 失败。第二轮复查时磁盘已恢复（约 13.6 GB 可用），三项验证已真实执行：

| 命令 | 结果 | 说明 |
|---|---|---|
| `cargo check --all-targets` | **通过**（exit 0，0 error） | 首次全量 3m52s（含 librdkafka 的 CMake 编译）。注意：首次运行因 PATH 中无 CMake 失败（`is cmake not installed?`），把 `C:\Program Files\CMake\bin` 加入 PATH 后成功——印证了 §2.1 对 `cmake-build` 构建环境风险的判断。 |
| `cargo clippy --all-targets` | **505 warning / 0 error**（exit 0，未加 `-D`） | 按 warning 分布：`filters_gen.rs` **466 条**（生成代码的冗余 `.into()` / `as i64` 转换）、`repo/mod.rs` 23 条、`tests/parity_test.rs` 4 条、其余手写代码约 12 条。 |
| `cargo clippy --all-targets -- -D warnings` | **不通过**（exit 101） | 上述 505 条 warning 全部升级为 error。手写代码的典型 lint：`result_large_err`（[handlers/query.rs:36](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L36)）、`large_enum_variant`（[mq.rs:44](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L44) 的 `Bus` 枚举）、`too_many_arguments`×3、`field_reassign_with_default`×2、`derivable_impls`（config.rs）、`redundant_reference`（db.rs）等。 |
| `cargo test` | **20 通过 / 0 失败**（exit 0） | 14 个单元测试 + 6 个集成测试（[router_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/router_test.rs)、[parity_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/parity_test.rs)），与 README 声称的 20 条一致。 |

**结论**：代码可编译、测试全绿；但 clippy 基线未清零——若要把 `-D warnings` 纳入 CI，需先修复手写代码约 39 条 lint，并对生成文件 `filters_gen.rs` 加 `#![allow(...)]` 或在生成器（`tools/gen_filters.py`）里消除冗余转换。

### 1.2 抽样范围

| 层 | 已读并对照的文件 | 对照的 Java 源 |
|---|---|---|
| 入口/装配 | [main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs)、[state.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/state.rs)、[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs) | `EcBusinessApiApplication.java`、24 个 Controller、`WebConfig.java` |
| Handler | [common.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/common.rs)、[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs)、[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs)、[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs)、[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs)、[selftest.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/selftest.rs) | `BaseController.java`、`SysUtilController.java`、`LargeScaleQueryController.java`、`UnifiedQueryController.java`、`ProgressiveQueryController.java`、`OdsRtSzdnSnapshotFlowAddcodeController.java`、`OdsLwzxsfsjFeeRecords01Controller.java`、`ZdataTrailTracksController.java` |
| Repo | [mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs)、[filters_gen.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/filters_gen.rs) | 23 个 Mapper 接口 + 19 份 XML |
| Service | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs)、[sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sync.rs)、[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs)、[trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs)、[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs)、[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs)、[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs)、[progressive.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/progressive.rs)、[reliability.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/reliability.rs)、[loss_detection.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/loss_detection.rs)、[delay_monitor.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/delay_monitor.rs)、[consistency.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consistency.rs)、[dict.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/dict.rs)、[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs) | `UnifiedQueryService.java`、`LargeScaleDataSyncService.java`、`SysUtilServiceImpl.java`、`TrailAggregationService.java`、`SnapshotFlowPulsarConsumer.java`、`UnifiedExportService.java`、`LargeScaleQueryService.java`、`ProgressiveQueryArchitectureService.java`、`DataReliabilityService.java`、`DataLossDetectionService.java`、`DelayMonitoringService.java`、`GaussEsConsistencyService.java`、`TrackTask.java` |
| 基础设施 | [config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs)、[db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs)、[cache.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/cache.rs)、[es.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/es.rs)、[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs)、[scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs)、[middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs)、[error.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/error.rs)、[response.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/response.rs) | `application.yml`、`RedisCache.java`、`Constants.java`、`KafkaProducerConfig.java`、`PulsarConsumerConfig.java`、`SchedulingConfig.java` |
| 模型/测试 | [models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs)（`J*` 标量）、[router_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/router_test.rs)、[parity_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/parity_test.rs) | 30 个 domain 类、JUnit 基线 |

---

## 2. 技术栈评估

### 2.1 对照总表（Cargo.lock 实际解析版本）

| 关注点 | Java 基线 | Rust 现行（locked） | 主流替代 | 判断 |
|---|---|---|---|---|
| Web 框架 | Spring MVC + 内嵌 Tomcat | **axum 0.8.9** + tower 0.5 + tower-http 0.6 + hyper 1.12 | actix-web 4、poem、warp | **合理**。axum 与 tower/tower-http 生态兼容最好，中间件可组合；actix-web 吞吐略高但生态割裂；poem 更轻但中间件与社区规模小。短板：只用了 `catch-panic`，`trace`/`cors` feature 引入却未使用，也**没有** body 上限、超时、压缩层。 |
| 异步运行时 | Tomcat 线程池 | **tokio 1.54.1（full）** | async-std（维护弱）、smol | **合理**。tokio 是事实标准。短板：在 async task 里做同步文件 IO（见 §3.4）。 |
| 数据库访问 | MyBatis-Plus + XML | **sqlx 0.8.6**（postgres / runtime-tokio-rustls / chrono / uuid / json / bigdecimal） | sea-orm、diesel、rbatis | **选型正确但收益未兑现**。对 1:1 复刻动态 SQL，sqlx 最合适；sea-orm 会引入实体关系与查询抽象，反而难以复刻"列名照抄 XML"的语义；diesel 异步弱；rbatis 最像 MyBatis 但社区小。问题：**没有使用 `query!`/`query_as!` 编译期校验**（`macros` feature 开着但只用了运行时 `query_as`），所谓"编译期 SQL 校验"这一最大卖点没有落地；`migrations/` 也没有接入 `sqlx::migrate!`。 |
| 连接池/事务 | Druid | `sqlx::PgPool`（max 20 / min 5 / acquire 60s） | deadpool-postgres、bb8 | **合理**。`Db::begin()` 已提供但全仓无调用（Java 也无 `@Transactional`，语义一致）；`log-sql` 配置项声明后**从未被读取**（[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L105-L106)、[db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs#L58-L79)）。 |
| 缓存 | spring-data-redis / Lettuce（生产另用 JedisCluster） | **redis 0.27.6** + `ConnectionManager` | deadpool-redis / bb8 + redis、redis-cluster | **可接受，但配置未落地**。`redis.pool-size=16` 与 `redis.password` 都只是声明：连接串只拼 `host/port/db`（[cache.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/cache.rs#L30-L42)），`ConnectionManager` 是单条多路复用连接，**不是连接池**；**无 Cluster 支持**，而 Java 生产实时轨迹走 JedisCluster（README 已承认此处降级）。 |
| 消息队列 | spring-kafka / pulsar-client / rocketmq / spring-amqp | **rdkafka 0.37.0（cmake-build）**；Pulsar/RocketMQ/RabbitMQ 未接线 | rdkafka(dynamic-libs)、kafka(pure-rust)、lapin、pulsar crate | **Kafka 选型合理**（librdkafka 是事实标准，支持手动提交、exactly-once 语义可控）。短板：`cmake-build` 会在构建期编译 librdkafka，构建机必须装 CMake/C 工具链，构建时间与产物体积都上去；`dead_letter_topic` 永远为空、DLQ 只能落到 `{topic}.DLQ`；`pulsar.max_retry_times` 被拿来当 Kafka 重试上限，配置语义串味（[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L161-L163)）。Pulsar 无生产级 Rust 客户端，用 Kafka 同语义替代是务实决策，但**必须架构确认**。 |
| Elasticsearch | RestHighLevelClient | **reqwest 0.12.28 直连 REST**（search/count/scroll/bulk/delete） | elasticsearch 官方 crate、opensearch | **权衡合理**。只用 6 个动作，手写 REST 换来"集群版本不绑定、依赖少"；代价是没有 typed query DSL、批量没有逐条失败检查、`count()` 不检查 HTTP 状态（失败静默返回 0，[es.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/es.rs#L88-L99)）。上官方 crate 收益（类型安全、重试）小于改造成本，不建议换。 |
| 配置 | application.yml + `@Value` | **config 0.15.27** + serde + 手写 `APP_*` 覆盖 | figment、envy、clap | **可用但重复**。同时存在 `config::Environment(prefix="APP", separator="__")` 和 `apply_env_overrides()` 单下划线两套机制（[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L728-L753)、[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L603-L709)），前者实际形同虚设；且大量配置项解析后无人消费（见 §3.7）。 |
| 错误处理 | Exception + @ControllerAdvice | **thiserror 2.0.21 + anyhow 1.0.104 + `AppError: IntoResponse`** | snafu、miette | **合理**。`AppError` 覆盖 Db/Redis/Reqwest/Json/Io，`IntoResponse` 复刻 Spring `/error` 体（[error.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/error.rs#L94-L119)）。短板：所有非 Http 变体输出 `message=""`（与 Spring 默认一致，但业务排障只能看日志）；panic 兜底返回 `AjaxResult` 形状，与其它 500 的 Spring 错误体不一致（[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L315-L332)）。 |
| 序列化 | Jackson / Fastjson2 | **serde 1.0.229 + serde_json 1.0.154（preserve_order）+ 自研 `JString/JInt/JLong/JFloat/JBool/Day/JDateTime/JIsoDateTime/JList`** | 纯 serde + `Option<T>` | **必要但最重**。`J*` 层约 500 行（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L53-L814)），同时解决三件事：Jackson 的 null 语义、GaussDB 实际列类型与 Java 实体类型不一致（INT2/INT4/INT8、FLOAT8↔INT4、TEXT[]）、`@JsonFormat` 输出格式。替代方案（每表手写 `FromRow`）代码量更大且更易漏。**保留**，但要补边界测试（数字时间戳、精度、INT8→i32 截断）。 |
| 日志/可观测 | SLF4J + Logback（滚动文件） | **tracing 0.1.44 + tracing-subscriber 0.3（text/json）** | opentelemetry-otlp、metrics + prometheus | **合理**。request_id/span 已接（[middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs#L32-L78)）。缺口：无 metrics/OTLP、无慢请求阈值告警、日志只到 stdout（原 Java 有 logback 滚动文件，部署侧需自行接管）、`logging.level` 只给默认 filter。另新增 `/healthz`、`/readyz`（Java 未接 Actuator，属合理新增）。 |
| 定时任务 | `@Scheduled` + Quartz 6 段 cron | **自研 6 段解析器**（[scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L44-L225)） | tokio-cron-scheduler、cron crate、job_scheduler | **可接受**。代码约 180 行、有单测、支持 `*/n`、`a/b`、列表、`?`=`*`，精度到秒；换成第三方库仍需处理 Quartz 的 6 段语义，收益有限。短板：**没有同一任务防重入**（慢任务会叠加执行，Java 默认单线程调度器不会）。 |
| DI/装配 | Spring 容器 | 组合根 + `Arc<AppState>`（[state.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/state.rs#L28-L72)） | — | **合理**，但 `AppState` 是 40 字段"上帝对象"（见 §3.6）。 |
| 测试 | JUnit 5 + Mockito | `#[test]` / `#[tokio::test]` + tower `oneshot` | testcontainers、mockall | 选型合理，覆盖不足（见 §3.8）。 |
| 构建/部署 | Maven fat jar | Cargo 单二进制（`lto=thin`、`strip=true`） | — | 合理，产物更小、启动更快。 |

### 2.2 逐项判断摘要

- **Web / 运行时**：没有选错。真正欠缺的是生产级中间件（body 限制、超时、压缩、可选的 `TraceLayer`），成本很低（每项 1-5 行 tower layer）。
- **数据库**：sqlx 是正确选择，但"运行时 SQL + 手写 panic-free 动态条件"意味着**没有任何编译期 SQL 校验**；错列名只能等到运行期。若要提升，建议对核心表用 `query_as!` + `sqlx prepare`（离线缓存 `.sqlx/`），成本中等、收益是编译期发现列/类型漂移。
- **缓存**：最大的短板不是库，而是**配置承诺与实现不符**（pool-size/password/Cluster）。生产若沿用 JedisCluster，这里必须补。
- **消息队列**：rdkafka 是唯一成熟解；Pulsar 缺失是生态问题，不是选型问题。建议把 `cmake-build` 改成 `dynamic-libs` 或提供构建镜像，降低 CI 风险。
- **ES**：手写 REST 属"够用就好"，不建议替换；建议补 HTTP 状态检查（`count`）与 bulk item 级失败统计。
- **配置**：`config` crate 没问题，但"两套环境变量机制 + 大量死配置"是维护债，建议收敛。
- **错误/序列化**：错误层薄而正确；序列化层的自研是本次迁移最大的"非框架代码"，必须有针对性测试兜底。
- **日志/调度**：均属"够用"；缺 metrics 与任务防重入可在 P2 处理。

---

## 3. 迁移质量评价与证据

### 3.1 做得好的部分（有证据）

| # | 能力 | 证据 |
|---|---|---|
| 1 | 85 条端点清单固化，防漏挂 | `JAVA_API_INVENTORY` 85 条 + 测试断言（[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L397-L763)、[router_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/router_test.rs#L211-L220)） |
| 2 | `AjaxResult` 的 `msg → code → data` 键序、省略 null `data` | 手工 `envelope` + 测试锁定（[response.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/response.rs#L18-L49)、[parity_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/parity_test.rs#L40-L58)） |
| 3 | PageHelper 的 `reasonable` 钳位与 `pageSize<=0` 语义 | `count` 先行的 `offset_for` + `empty` 分支（[common.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/common.rs#L28-L83)、[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L27-L60)） |
| 4 | Java `initBinder` 的日期白名单（解析失败即丢弃条件） | `JavaDateFields` + `JavaQuery` 提取器（[common.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/common.rs#L158-L316)），并有专门测试（[parity_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/parity_test.rs#L156-L236)） |
| 5 | 重复查询参数按 Spring 的逗号拼接语义合并 | `JavaQuery::from_request_parts` 的 `kept` 归并（[common.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/common.rs#L274-L305)） |
| 6 | Spring 默认错误体 `{timestamp,status,error,message,path}` | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L282-L313)、[error.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/error.rs#L94-L119) |
| 7 | 572 条 `<if>` 条件从 XML 机器生成，且保留"列名照抄 XML"的错误一致性 | `filters_gen.rs` + 生成说明；`JiAnDong` 字面量条件已落地（[filters_gen.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/filters_gen.rs#L53-L56)） |
| 8 | 缓存 key 与 Java `Constants` 逐字一致 | `trail:`、`car_list_jc`、`DATE_*`、`dev_post`、`gantry_ip`、`station_ip`、`section_road_map`、`station_info`、`gantry_list`、`pulsar:msg:processed:`（[services/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/mod.rs#L23-L58)） |
| 9 | `trailtracks/{uuid}` 的三分支（0 行 200 / 1 行 200+data / 多行 500） | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L267-L288)，对应 Java `selectOne` 的 `TooManyResultsException` |
| 10 | 已识别并保留 Java 侧缺陷（lat=lon、indexType 沿用、captureTime 仅含 T 才赋值、4 分钟阈值注释写 3 分钟） | [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L14-L18)、[trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs#L374-L381)、[trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs#L401-L440) |

### 3.2 语义保真度缺口（按严重度，含具体证据）

#### P0-1 `fuzzyFields` 未白名单，DB 降级路径存在 SQL 注入

- Rust `query_from_es` 对未知逻辑字段返回 400，但 `query()` 捕获后**降级到 DB**；DB 路径把未知 key 直接当物理列名拼进 SQL：

```rust
// src/services/query.rs:353-367
let physical = meta.logical_to_physical.get(k.as_str()).cloned().unwrap_or(k.as_str());
args.push(format!("%{}%", v));
where_clauses.push(format!("{} LIKE ${}", physical, args.len())); // physical 来自请求 key
```

见 [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L353-L367)。`large_query` / `unified_list` 都走这条路径（[handlers/query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L71-L108)、[handlers/query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L276-L306)）。
Java 侧 `UnifiedQueryService.queryFromMysql` 用同样的 `translation.getOrDefault(key, key)`（[UnifiedQueryService.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedQueryService.java#L327-L333)），**同样可注入**；但 Rust 文件头注释声称"只接受白名单里的逻辑字段（与 Go 版一致），未知字段返回 400"（[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L9-L10)），**与实现不符**。
- 影响：请求方可构造 `fuzzyFields.<构造列名>=x`，把任意 SQL 片段拼进 `WHERE`；参数值本身是绑定参数，但列名不是。
- 定性：P0（安全）。修复会导致与 Java 行为差异，需要与架构确认"安全优先还是行为一致优先"。

#### P0-2 游标/对账/丢包检测的时间条件把字符串直接绑到 timestamp 列

- `cursor_query`（三表同步共用）生成 `AND {time_col} >= $n`、`> ($n,$n+1)`，绑定值是 `String`（[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1201)）。
- `count_between` 生成 `WHERE {col} BETWEEN $1 AND $2`，同样绑 `String`（[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1203-L1220)）。
- `SnapshotFlowRepo::list_big_ids_between` 同样 `BETWEEN $1 AND $2`（[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L702-L716)）。
- 对照 Java：XML 明确使用 `to_timestamp(#{startTime},'yyyy-mm-dd HH24:MI:SS')` 与 `<` / `BETWEEN`（[OdsLwzxsfsjFeeRecords01Mapper.xml](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/OdsLwzxsfsjFeeRecords01Mapper.xml#L19-L31)、[OdsRtSzdnSnapshotFlowAddcodeMapper.xml](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/OdsRtSzdnSnapshotFlowAddcodeMapper.xml#L195-L208)）。
- 项目自己已经踩过这个坑：README §11.2 第 8 条明确记录"之前 Rust 直接绑定文本，SQLx 报类型错误 → 500"，并把 `Cond::Gte/Lte` 改成 `to_timestamp($n,...)`（[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L72-L85)）。**但 `cursor_query`/`count_between`/`list_big_ids_between` 三处漏改。**
- 影响：
  - `POST /api/v1/large/sync/full|incremental|repair` 首次分片读取即报错（错误只进日志，HTTP 仍 200，**静默失败**）；
  - `consistency.reconcile`（默认关闭）与 `loss detection`（默认 30 分钟运行）持续报错/降级；
  - 这些路径正是 548 项验证中"跳过/未测"的部分（[VERIFICATION-FULL-20261102.md](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/docs/VERIFICATION-FULL-20261102.md#L91-L99)）。

#### P0-3 消费端默认启用，而 Java 侧消费者是禁用状态

- Rust 默认 `app.consumer-enabled: true`（[application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml#L140-L144)），`main` 在 bus 活跃时启动 `SnapshotFlowConsumer`（[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L287-L301)），消费成功后写 GaussDB + ES（[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L135-L163)、[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L174-L208)）。
- Java 侧 `SnapshotFlowPulsarConsumer` 与 `DebeziumReadonlyPulsarConsumer` 都是 `//@Service` 注释（[SnapshotFlowPulsarConsumer.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java#L55-L57)、[DebeziumReadonlyPulsarConsumer.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/DebeziumReadonlyPulsarConsumer.java#L63-L65)），`PulsarProducerService` 同样禁用（[PulsarProducerService.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/PulsarProducerService.java#L45)）。
- 结论：Rust 在灰度期会**主动写共享库/共享 ES**，Java 不会。README §7 未记录这一点，`consumer-enabled` 注释"默认与 Java 一致"是**错误陈述**。这会直接造成双端数据/ES 文档差异，甚至与 Java 定时同步互相覆盖。

#### P0-4 幂等键先写后处理，失败后重试被当成"已处理"→ 静默丢消息

- 处理顺序：先 `set_nx`，再解析 `data`，再落库（[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L105-L133)）。
- 首次处理失败时返回 `Err`，`handle_with_retry` 在进程内重试（[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L279-L296)）；重试再次进入 `handle`，`set_nx` 返回 `false` → 直接 `Ok(())` 视为成功 → 提交 offset。**消息从未落库，也没有进 DLQ。**
- Java 的 `processMessage` 也是同样顺序（[SnapshotFlowPulsarConsumer.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java#L274-L287)），但 Java 消费者从未启用；Rust 启用后该缺陷变成**现网数据丢失**。
- 修复方向（任一）：成功后再 `SETNX`/成功标志；或失败时 `DEL` 幂等键；或 `set_nx` 的值带状态并在重试时允许接管。注意最后一种要防并发重复处理。

#### P1-1 `changeData` 未重置瞬态字段 → 轨迹接口 JSON 与 Java 不一致

- Java 在 `changeData` 末尾显式清零：`firtStationCode/Name/Time`、`plateColor`、`carType`、`carVehicle`、`carNum`、`passType`（[SysUtilServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java#L746-L753)）。
- Rust 的 `change_data` 完全没有这段（[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L131-L135)、返回处 [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L405-L409)）。
- 这些字段在 `ZdataTrailTracks` 上是 `#[sqlx(skip)]`（DB 不填充），默认 `None`（[zdata_trail_tracks.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/zdata_trail_tracks.rs#L88-L114)），因此 `JString(None)` 序列化为 `null`；Java 是 `""`。
- 影响：`/base/sysutil/carTrackQueryByCarNo`、`/carTrackQueryByTime`、`/changeTrailInfo` 只要**有数据行**，响应里 `"plateColor"` 等字段就是 `null` 而非 `""`。548 项验证中这些接口 `total=0`（无数据行），所以没被发现。

#### P1-2 `syncHistroyTrack` 写出的 `car_history_trail:*` 形状与 Java 不同

- Rust 写 `Vec<ZdataTrailTracks>`，直接来自 `get_history_trail`，**未做 `getTrailBoList`/`changeData` 富集**，也未过滤空 `trail_points`，且按 `uuid` 倒序（[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L131-L177)）。
- Java 写 `List<TrailInfo>`：每条包含 `tracks + trailList`，只收录 `trailPoints` 非空且 `changeData` 成功的条目，顺序为"新数据在前 + 旧数据补充"，无排序（[TrackTask.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/task/TrackTask.java#L94-L157)）。
- 影响：任何读取 `car_history_trail:{carNo}` 的消费者（前端/其它服务）在切换后会拿到不兼容 JSON。README 只提到"与旧数据按 uuid 合并"，未标注形状差异。
- 同一文件里 `sync_track` 写 `car_curent_trail:{carNo}` 时也漏了 Java 的 `trailInfo.setTrailUuid(carNo)`（[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L117-L126) vs [SysUtilServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java#L375-L380)）。

#### P1-3 `snapshot` 同步写入 ES 的 `_id` 取 `big_id`，Java 取 `datauuid`

- Rust：`entity_doc(&r, &r.big_id, ...)`（[sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sync.rs#L131-L141)），而游标 id 用的是 `datauuid`（同文件 L132-137）。
- Java：`SyncTask(..., r -> ((OdsRtSzdnSnapshotFlowAddcode) r).getDatauuid())`（[LargeScaleDataSyncService.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleDataSyncService.java#L252-L257)）。
- 影响：同一行数据在 ES 中的 `_id` 不同 → 双端并行写会产生重复文档；只由 Rust 全量重建时，`_id` 与 Java 侧既有文档不一致，做灰度/回滚或按 id 删除会错。消费端 `save_to_es` 也用 `big_id`（[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L201-L206)），与 Rust 同步路径一致，但同样与 Java 的 `datauuid` 不一致，需统一到 Java 语义。

#### P1-4 `/base/feerecords/{bigId}` 状态码不一致

- Java `getInfo` 调 `selectOdsLwzxsfsjFeeRecords01ById`（[OdsLwzxsfsjFeeRecords01ServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeRecords01ServiceImpl.java#L37-L40)），而该 Mapper **只有 `selectByCursorShard` 一条语句**（[OdsLwzxsfsjFeeRecords01Mapper.xml](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/OdsLwzxsfsjFeeRecords01Mapper.xml#L19)）→ `Invalid bound statement` → Spring 500。
- Rust 路由把 `/{id}` 挂到通用 `fee_records_flat`（[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L70)、[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L286-L294)）→ 会真实查库，命中返回 200 + 实体，未命中返回 200 空体。
- 548 项验证**未覆盖** `/base/feerecords/*`（全文无该路径），README §7 只列了 `list|listToExport`。属于未被发现的状态码差异。

#### P1-5 日期反序列化只接受字符串，数字时间戳会失败

- `JIsoDateTime`/`JDateTime`/`Day` 的 `Deserialize` 都是 `Option::<String>::deserialize`（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L227-L236)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L306-L315)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L767-L777)）。
- 后果 1：消息 `data` 里若出现数字 epoch（Debezium 默认 `io.debezium.time.Timestamp` 就是 INT64 毫秒），`serde_json::from_value::<OdsRtSzdnSnapshotFlowAddcode>` 整体失败 → 消费者按"格式错误"**确认丢弃**（[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L123-L129)）；Java FastJSON 会数值转 Date。
- 后果 2：ES 里若已有 Java 写出的数字时间戳文档，`convert_docs` 的 `from_value` 失败后会**回退返回原始 doc**（[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L394-L418)），导致 `/api/v1/large|unified` 输出字段类型与 Java 不同（数字 vs ISO 字符串）。
- 建议：为 `J*` 时间类型增加"数字毫秒/秒"分支，或显式在消费入口做 `Value` 归一化；并在切换前用 Rust 重建索引。

#### P1-6 轨迹去重的时间阈值按"分钟截断"比较，4m01s~4m59s 区间行为不同

- Rust：`(t2 - t1).num_minutes().abs() > 4`（[trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs#L401-L440)，判断在 L416）。
- Java：毫秒差 `diff > 4 * 60 * 1000`（[SysUtilServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java#L2101-L2143)）。
- 影响：差 4 分 30 秒时 Java 认为是新点、Rust 认为是重复点并合并图片 → 轨迹点数与图片归属都可能不同。该差异不易被随机样本发现。

#### P1-7 `/base/sysutil/*` 的 `total` 与越界页行为

- Rust `total = list.len()`（本页行数），且 `offset()` 不做 reasonable 钳位（[handlers/sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs#L33-L92)）。
- Java `new PageInfo(list).getTotal()` 是**匹配总数**（PageHelper 会先 COUNT），且 `pageNum=9999` 会钳位到最后一页（[SysUtilController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/SysUtilController.java#L102-L107)、[PageUtils.java](file:///d:/work/IdeaProjects/car-monit-api/pro-base-common/src/main/java/com/ruoyi/common/utils/PageUtils.java#L18-L26)）。
- README §7 #7 已声明"total 为本页行数（与 Go 版一致）"，属已知取舍；但 `pageNum` 越界时 Java 返回末页、Rust 返回空数组，这一点文档未说明。

#### P1-8 `/base/vehicleweight/{id}` 无条件 500 依赖"环境观测"，非代码路径

- Rust 直接固定返回 500（[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L259-L265)、路由 [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L92-L95)）。
- Java 该接口**是有 SQL 的**（[OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml#L117-L122)），只是 WHERE 用 `t.dataSource`（该列在库中不存在）才报错；若表结构调整/换库，Java 会变成 200，Rust 仍是 500。
- 同理 `vehicleweight/list` 的部分过滤条件 500 是"列名不存在"导致的，Rust 生成器照抄列名才一致（这是正确的 1:1 策略），但把"200/500"硬编码在 handler 里则不可持续。

### 3.3 错误处理

- 正向：`AppError` + `?` + `IntoResponse` 覆盖统一出口；`CatchPanicLayer` 兜住 handler panic；`SpringQueryRejection` 把 Axum 的纯文本 400 转成 Spring JSON（[common.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/common.rs#L236-L252)）。
- 问题 1：`AppError::IntoResponse` 恒写 `message: ""`，与 Spring 默认一致，但所有 400 业务错误/DB 错误在响应里没有任何可读信息，排障只能翻日志；Java 侧同样是空 message，所以这属"一致但难用"。
- 问题 2：`handle_panic` 返回 `AjaxResult{code,msg}`（[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L315-L332)），与其它 500 的 `{timestamp,status,...}` 不一致；若前端按统一错误体解析会踩坑。
- 问题 3：多处"吞异常"是刻意复刻 Java（`QueryService::query` 失败返回空列表、导出任务失败写状态），但**同步/对账链路**的失败只写日志且 HTTP 仍 200（P0-2），运维无法从接口感知失败。

### 3.4 并发与资源管理

- `tokio::spawn` 生命周期：调度器/消费者/导出/可靠性重试都可无限 spawn；`main` 的优雅关闭只等 `export.close()`/`large.close()`（信号量），**不等待**调度器/消费者任务真正结束（[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L362-L369)）。在途写库/写文件可能被进程退出打断。
- **同步阻塞 IO 跑在 async worker 上**：导出用 `std::fs::create_dir_all` + `csv::Writer<std::fs::File>`（[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L174-L229)、[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs#L255-L330)）。大文件 flush 会阻塞 tokio worker；Java 是独立线程池。建议 `tokio::fs` 或 `spawn_blocking`。
- `KafkaBus` 用 `Arc<tokio::sync::Mutex<StreamConsumer>>` 并在 `recv()` 期间持锁（[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L210-L250)），单消费循环下无碍，但把"1 秒超时 + mutex + commit 再锁"叠在一起，后续加并发消费者会立刻打结；`commit_lock` 与外层 mutex 也重复。
- 调度器无防重入（[scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L176-L224)）：`Every` 任务若执行超过间隔会叠加；`syncHistroyTrack` 这类"遍历上百车"的任务尤其危险。
- `ReliabilityService` 每条消息 spawn 一个 30 秒定时 task（[reliability.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/reliability.rs#L359-L374)），且超时后**不从 `pending` 移除**（`handle_message_timeout` 只记录/入队），长期运行会内存增长。当前 `send_snapshot_flow_data` 无调用方，风险暂未暴露。
- 乐观面：共享状态用 `Arc<RwLock<HashMap>>` / `DashMap` 替代 `ConcurrentHashMap`，锁粒度合理；`std::sync::Mutex` 只在 `MessageMeta` 内且不跨 await 持有。

### 3.5 类型建模（null 三态 / 时间 / 金额精度）

- **null 三态**做得好：`JString/JInt/...` 都是 `Option` 包装，且 `JList` 用 `present` 区分 `null` 与 `[]`（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L625-L686)），与 Jackson 行为一致；`AjaxResult.success(None)` 省略 `data` 键也有测试。
- **时间**：`Day`/`JDateTime`/`JIsoDateTime` 的 `Decode` 对非 `TIMESTAMPTZ` 统一 `-8h`（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L249-L269)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L328-L347)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L789-L805)）。这在 `Asia/Shanghai` 固定偏移下成立，但**硬编码而不是读取配置**；一旦部署时区或 JDBC 参数变化，全部时间字段偏移 8 小时。
- **精度**：Java `BigDecimal` 的经纬度/金额在 Rust 端统一 `f64`（`JFloat`）。展示场景可接受；若后续做金额汇总会引入二进制浮点误差（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L542-L623)）。
- **跨类型截断**：`JInt` 从 `INT8/FLOAT8/NUMERIC` 用 `as i32` / `to_i32()`，`JLong` 从 `FLOAT8` 用 `as i64`，溢出静默截断（[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L416-L437)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L508-L531)）；Java 会抛 `DataIntegrityViolation`/精度异常。只在异常列上才会触发，但属"静默改数据"。

### 3.6 分层与耦合

- 组合根清晰：`main.rs` 显式装配 22 个 repo + 12 个 service，`AppState` 注入（[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L135-L282)），依赖缺失编译期报错，符合迁移规则。
- 但 `AppState` 有 **40 个字段**（[state.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/state.rs#L28-L72)），handler 可绕过 service 直接拿 repo（如 [crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L27-L44) 直接对 `ReadRepo` 做 list/count；[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L116-L124) 直接回退 `state.gantry.list_all()`）。这提高了横向修改成本，也让"服务层"边界名存实亡。
- `SysUtilService` 依赖 9 个 repo + dict + cache + env（[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L41-L87)），单文件 800 行，是耦合最重的点；但对应 Java `SysUtilServiceImpl` 本身也是 2600 行"上帝类"，属忠实迁移而非新债。
- 模型层同时耦合 serde + sqlx + Java 语义（`J*` 的 `Type/Decode/Encode/Serialize/Deserialize` 五套 impl），修改成本高；这是可接受的集中化代价。

### 3.7 重复代码与死代码

| 类别 | 具体 |
|---|---|
| 重复实现 | `export.rs` 与 `large.rs` 各有一套 scroll→CSV 导出（约 130 行/处，[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L134-L266) 与 [large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs#L230-L356)），任务状态更新、分片、flush 逻辑几乎同构；可抽公共 `ScrollCsvWriter`。 |
| 重复定义 | `handlers/base.rs` 自己实现了 `split_csv`（[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L46-L52)），与 `utils::split_csv` 重复且语义不同（前者保留空段语义差异见 §3.2）。 |
| 死代码 | `Base::prepare_fee_records` / `decorate_fee_records` 标 `#[allow(dead_code)]`（[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L90-L142)）；`large.fuzzy_query`（[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs#L76-L125)）；`progressive.query_fee_records/query_trail_fitting`（[progressive.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/progressive.rs#L229-L314)）；`trail_tracks_detail_500`（[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L263-L265)）；`selftest::blocked_endpoints/not_ported`（[selftest.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/selftest.rs#L60-L109)）；`consumer::consumer_started_flag/DeliveryReport`（[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L211-L220)）；`Db::{begin,scalar_i64,fetch_rows}`、`repo::db_err/ping`（[db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs#L52-L79)、[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1226-L1237)）。 |
| 死配置 | `rocketmq`/`rabbitmq`/`mq` 整棵配置树无人读取（[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L222-L270)、[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L407-L429)）；`app.sysbase_url`、`server.mode`、`redis.pool_size`、`master.log_sql`、`pulsar.max_retry_count`（[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L314) 仅 `let _ =` 读后丢弃）。注：`kafka.max_retry_count` 实际被 [producer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/producer.rs#L56-L60) 用于 DB 记录级重试，属活配置（第一轮表述有误，此轮更正）；消费重试上限用的是 `pulsar.max_retry_times`。 |
| 未用依赖 | `hyper`（直接依赖未使用）、`once_cell`；`tower-http` 的 `trace`/`cors` feature 引入但未使用（[Cargo.toml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/Cargo.toml#L10-L14)、[Cargo.toml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/Cargo.toml#L55-L63)）。 |

### 3.8 测试覆盖

- 现有：20 个测试（[router_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/router_test.rs)、[parity_test.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/tests/parity_test.rs)），覆盖路由装配、85 端点清单、cron 可解析、健康检查、404、纯函数、响应壳、日期白名单。
- 缺口：**没有任何 DB 查询/过滤条件/状态码分支的服务级测试**；`Cond` 生成、`cursor_query`、`dedupe_points`、`sync_history_track`、消费者状态机都没有测试。548 项一致性验证写在 `tools/verify_full.py`，需要 Java + Rust + 真实 GaussDB/Redis 同时运行，不在 `cargo test`/CI 中。
- 风险：后续任何改动（尤其是重跑 `tools/gen_filters.py`）只能靠人工双端脚本回归。

---

## 4. 分级优化建议

> 每条包含：涉及模块 / 预期收益 / 改动范围 / 风险。所有建议均**未落地**，仅作评审结论。

### P0（上线前必须解决）

| ID | 建议 | 模块 / 范围 | 预期收益 | 风险 |
|---|---|---|---|---|
| P0-1 | 未知 `fuzzyFields` 一律拒绝（400 或忽略），DB 降级路径只允许 `logical_to_physical` 白名单 | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L353-L367) / 约 10 行 + 2 个测试 | 关闭 SQL 注入面；同时修正文件头"已白名单"的错误描述 | 与 Java 现有行为不一致（Java 同样可注入）。建议：Rust 先修，Java 侧同步修或灰度期只在 Rust 收紧；需架构确认 |
| P0-2 | `cursor_query`/`count_between`/`list_big_ids_between` 全部改成 `to_timestamp($n,'yyyy-mm-dd HH24:MI:SS')`（或绑定 `NaiveDateTime`） | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L702-L716)、[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1220) / 3 处约 30 行 | 让全量/增量/补同步、对账、丢包检测真正可用；与 Java XML 完全对齐 | 时间入参格式必须与 `to_timestamp` 兼容（统一 `format_datetime`）；游标二元组 `(time,uuid)` 的 SQL 需保持 `>` 语义。修复后必须真库验证 |
| P0-3 | 消费端默认关闭（`consumer-enabled: false`），部署时显式开启；或在 README/部署清单中标注"Rust 会写库/写 ES，Java 不会" | [application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml#L140-L144)、[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L287-L301) | 避免迁移期双写/互相覆盖；修正"与 Java 一致"的错误陈述 | 若生产确实需要消费能力，则不能关闭；需确认"谁负责消费"（Java 当前无人消费） |
| P0-4 | 幂等键改为"处理成功后写入"或失败回删；重试时允许接管未完成状态 | [consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L105-L121)、[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L279-L296) / 约 20 行 | 消除 DB/ES 瞬时失败导致的静默丢消息；让重试与 DLQ 真正生效 | 并发重复消费：需保证"状态=SENT/CONFIRMED 才跳过，PENDING 可接管"；改动后要补消费状态机测试 |

### P1（灰度前应完成）

| ID | 建议 | 模块 / 范围 | 预期收益 | 风险 |
|---|---|---|---|---|
| P1-1 | `change_data` 补上 Java 的瞬态字段清零（`plateColor/carType/carVehicle/carNum/passType/firtStation*`） | [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L131-L135)、返回前 | 轨迹接口 JSON 与 Java 字节级一致 | 低；注意这些字段在 `ZdataTrailTracks` 上确实是 `#[sqlx(skip)]`，清零即 `""`/`null` 需与 Jackson 对齐（`JString::from("")`） |
| P1-2 | `sync_history_track` 改为写 `Vec<TrailInfo>`（`getTrailBoList` + `changeData` + 空轨迹过滤），`sync_track` 补 `trailUuid` | [track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L117-L177) | 恢复 `car_history_trail:*` / `car_curent_trail:*` 的缓存契约 | 中；缓存形状变更必须清 key 或双写；需确认下游消费者 |
| P1-3 | 同步/消费写 ES 的 `_id` 统一为 Java 的 `datauuid`（snapshot） | [sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sync.rs#L126-L141)、[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L201-L206) | 与 Java 文档 id 对齐，避免重复文档/回滚错乱 | 中；切换前需清空/重建相应索引 |
| P1-4 | `/base/feerecords/{bigId}` 按 Java 返回 500，或补 Java XML 后两端一起放开 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L70)、[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L286-L294) | 状态码一致；补齐 548 项未覆盖用例 | 低；若未来 Java 补 XML，需要同步恢复真实查询 |
| P1-5 | `J*` 时间类型支持数字毫秒/秒；消费入口做日期归一化 | [models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L227-L236)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L306-L315)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L767-L777) | 兼容 Debezium/FastJSON 的数字时间戳；ES 文档双向可读 | 中；放宽解析会改变"非法输入"边界，需要测试锁定 |
| P1-6 | 去重阈值改为毫秒比较 `> 4*60*1000` | [trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs#L416) | 4 分钟边界与 Java 一致 | 低；但会影响已缓存轨迹的合并结果（灰度期需清 `car_curent_trail`/`trail:*`） |
| P1-7 | `/base/sysutil/*` 的 `total` 与 `pageNum` 钳位：要么实现 COUNT（成本高、大表风险），要么在 README/前端契约中明确"total=本页行数、越界页返回空" | [handlers/sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs#L38-L57) | 消除与 Java 的分页契约差异或明确接受 | 做 COUNT 会打穿 8 亿级表；建议维持现状但**补齐文档与前端确认** |
| P1-8 | `vehicleweight/{id}` 的 500 改为按条件复刻（保留列名错误，而不是硬编码状态） | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L259-L265) | 换库/改表后行为仍可推导 | 低；需接受"当前库仍 500"的实测结果不变 |

### P2（可持续性/性能）

| ID | 建议 | 模块 / 范围 | 预期收益 | 风险 |
|---|---|---|---|---|
| P2-1 | 导出/大导出改 `tokio::fs` 或 `spawn_blocking`，抽公共 CSV scroll writer | [export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L134-L266)、[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs#L230-L356) | 不阻塞 tokio worker；消除约 130 行重复 | 低-中；注意排序/分片命名保持不变 |
| P2-2 | 调度器增加 per-job `AtomicBool`/`Mutex` 防重入 | [scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L176-L224) | 避免慢任务叠加（尤其历史轨迹同步） | 低；与 Spring 单线程调度语义更接近 |
| P2-3 | Redis：使用连接池（deadpool/bb8）或在配置中删除 `pool-size`；支持 password；如需 Cluster 增加 `redis::cluster` 分支 | [cache.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/cache.rs#L30-L42)、[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L124-L145) | 配置承诺兑现；生产 JedisCluster 场景可接 | 中；Cluster 会改变所有 key 路由，需独立验证 |
| P2-4 | 清理死配置/死依赖/死代码；`.env.example` 补 `APP_ENABLE_SCHEDULER`、删除 `LOG_SQL` 或实现 SQL 日志 | [config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs)、[Cargo.toml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/Cargo.toml)、[.env.example](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/.env.example) | 降低误解与维护成本 | 低；删除配置会影响现有 YAML 兼容性，建议只删"零引用"项 |
| P2-5 | `ConsistencyService` 索引名改用 `config.elasticsearch.index.*`（与 `QueryService::meta` 同源） | [consistency.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consistency.rs#L83-L90) | 改索引名后对账不再错表 | 低 |
| P2-6 | 统一"业务时间用本地时区、监控 key/窗口用本地日期"；`loss/delay/consistency/track_sync` 现用 UTC | [loss_detection.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/loss_detection.rs#L106-L108)、[delay_monitor.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/delay_monitor.rs#L259-L261)、[consistency.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consistency.rs#L70-L71)、[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L173) | 与 Java `DateUtils.formatDate/formatHour` 一致；丢包检测窗口不再偏 8 小时 | 低-中；需同步设计 `TIMEZONE` 配置项，避免再硬编码 +8 |
| P2-7 | `ReliabilityService` 超时后移除 `pending`；改为单一定时器扫描而非每消息 spawn | [reliability.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/reliability.rs#L359-L393) | 防内存增长与 task 爆炸 | 低；当前链路无调用方，优先级可后置 |
| P2-8 | 补测试：`cursor_query` 生成的 SQL、`dedupe_points` 4 分钟边界、`sync_history_track` 形状、`change_data` 字段清零、`fuzzyFields` 白名单 | `tests/` | 把本次发现的差异固化为回归用例 | 低；需要 `sqlx` 离线/测试库或纯 SQL 快照断言 |
| P2-9 | 为 `PgPool` 加 `after_connect` 设置 `search_path=jl_data01,jl_data01...`？**不建议**：会改变非限定表名行为（见 README §7 #14），保持现状 | — | 保持与 Java 的"search_path 不含 jl_data01"一致 | — |

---

## 5. 剩余风险与待确认决策

### 5.1 技术性剩余风险

| # | 风险 | 依据 / 影响 |
|---|---|---|
| R1 | **前端分页契约**：`/base/sysutil/*` 的 `total` 是本页行数、越界页返回空；Java 是匹配总数、越界钳位末页 | §3.2 P1-7；需前端确认分页控件是否依赖 total |
| R2 | **Redis 序列化不兼容**：Rust 存 JSON，Java FastJSON/JDK；共用 key 会互相解析失败 | README §7 #6；切换前必须清字典/轨迹/消息类 key 或双写 |
| R3 | **ES 文档时间格式**：Rust 写 ISO 字符串、Java FastJSON 可能写数字；Rust 反序列化只认字符串 | §3.2 P1-5；切换前应以 Rust 重建索引，或放宽解析 |
| R4 | **Pulsar/RocketMQ 无真实客户端**：当前用 Kafka 同语义替代；若生产消息源是 Pulsar，Rust 无法直连 | README §7 #1；需架构确认消息中间件归属 |
| R5 | **Flink 作业未迁移**：若该作业仍在独立部署则不受影响 | README §7 #2；需确认部署拓扑 |
| R6 | **生产 Redis 集群**：Rust 只连单节点主 Redis，生产实时轨迹读 `trail:{carNo}` 的集群分支缺失 | README §8、[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L12-L16) |
| R7 | **搜索/导出链路未真实验证**：ES 磁盘曾 97%、Kafka 未启动；`sync`/`export`/`consume` 均靠代码审查 | [VERIFICATION-FULL-20261102.md](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/docs/VERIFICATION-FULL-20261102.md#L91-L99) |
| R8 | **时区硬编码 `-8h`/`+8h`**：`Asia/Shanghai` 固定偏移，跨时区部署或 JDBC `serverTimezone` 变化会整体偏移 | [models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L259-L269) |
| R9 | **金额精度**：Java `BigDecimal` → Rust `f64`，展示场景 OK，汇总/计费不可用 | §3.5 |
| R10 | ~~编译/Clippy 未验证~~ **已验证（第二轮）**：`cargo check` 通过、`cargo test` 20/20 通过、clippy 有 505 条 warning（466 条来自生成代码） | §1.1 |
| R11 | **两套环境变量机制**：`config::Environment(prefix APP, separator "__")` 与手写 `APP_*` 单下划线并存，容易误配 | [config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L728-L753) vs [config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L603-L709) |
| R12 | **`gen_filters.py` 与 XML 漂移**：`filters_gen.rs` 是生成物，Java XML 变更后若忘记重跑会静默不一致 | [filters_gen.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/filters_gen.rs#L1-L20) |

### 5.2 待确认决策（需要业务/架构回答）

1. **消费端归属**：迁移期由谁消费 `ods-rt-szdn-snapshot-flow`？Java 当前无人消费。若由 Rust 消费，必须先修 P0-4 再开启；若不由 Rust 消费，默认值应改为 `false`。
2. **Pulsar / RocketMQ / RabbitMQ**：是否必须支持真实 Pulsar？Rust 生态确无生产级客户端，需接受"Kafka 同语义"或单独立项。
3. **安全优先 vs 行为一致**：`fuzzyFields` 注入面是 Java 既有缺陷。Rust 是否可以先修（产生行为差异），还是必须复刻到与 Java 完全一致？
4. **`/base/feerecords/{bigId}`**：按 Java 返回 500，还是补齐 Mapper XML 后两端一起放开？
5. **`total` 语义**：`/base/sysutil/*`、`/progressive/*` 是否接受"本页行数"？若前端依赖匹配总数，需要额外 COUNT 或缓存计数。
6. **时间语义**：全站时间字段是否确定只在 `Asia/Shanghai` 部署？若是，把 `-8h/+8h` 收敛为一个常量/配置项；若否，需要重做时区策略。
7. **ES 重建**：切换前是否允许清空/重建 `snapshot_flow`、`fee_records`、`trail_fitting` 索引（用于统一 `_id` 与时间格式）？

---

## 6. 复现与后续验证清单

```bash
# 0) 编译前置：rdkafka 使用 cmake-build，构建机必须有 CMake 且在 PATH 中
#    Windows: set PATH=C:\Program Files\CMake\bin;%PATH%
#    （第二轮实测：PATH 缺 CMake 时 rdkafka-sys 构建直接失败）
# 1) 静态检查（第二轮实测：check 通过；clippy 505 warning）
cargo check --all-targets
cargo clippy --all-targets            # 当前 505 warning / 0 error
cargo clippy --all-targets -- -D warnings   # 当前不通过，需先清基线
# 2) 单元/装配测试（第二轮实测：20 passed / 0 failed）
cargo test
# 3) 双端对比（需要 Java 9902 / Rust 9911 / 真实 GaussDB+Redis）
python tools/compare_api.py         # 74 场景
python tools/compare_round2.py      # 93 场景
python tools/compare_round3.py      # 186 场景
python tools/verify_full.py --stage all   # 548 场景
# 4) 本次新增建议的针对性验证
#   - /api/v1/large|unified 传 fuzzyFields.<非法列名>
#   - POST /api/v1/large/sync/full（观察是否写 ES；确认 P0-2）
#   - 消费端：数据库暂时不可用时投递一条消息，确认是否进 DLQ 而非静默成功
#   - /base/sysutil/carTrackQueryByCarNo 在有数据行的库上逐 JSON 对比
#   - /base/feerecords/{bigId} 双端状态码
```

---

## 7. 迁移进度盘点（以 Java 原始实现为基线）

### 7.1 判定口径

| 判定 | 含义 |
|---|---|
| **已迁移** | Java 行为在 Rust 有对应实现，主路径可工作（允许存在已记录的 P1/P2 偏差） |
| **部分迁移** | 结构/入口已迁移，但关键分支缺失，或行为依赖环境且不可推导 |
| **未迁移** | Java 有活跃实现，Rust 完全没有对应逻辑 |
| **明确不适用** | Java 侧本身是死代码（无调用方）、被注释的 Bean、示例类，或属于独立运行时（Flink） |

> 统计口径：只统计"当前真正会被执行"的 Java 代码；`//@Service`、无调用方的 @Service/@Component 单独标注。

### 7.2 总量对照

| 维度 | Java 基线（实测计数） | Rust 现状（实测计数） | 完成度 |
|---|---|---|---|
| 源文件 | 166（business）+ 53（common）= **219** | **72** 个 `.rs` | — |
| HTTP 端点 | **85**（24 Controller，已排除块注释端点） | **85** 条（84 个 `route` 调用 + `{ds}`/`{table}` 动态段覆盖） | 100% 注册，**72% 真实现**（见 7.3） |
| Controller | **24** | 5 个 handler 文件 + 宏生成 19 组 CRUD | 24/24 有对应 |
| 实体/DTO | **30**（901 字段） | **31** 个 model 模块（30 实体 + `java_date_fields`） | 30/30 |
| 业务表 | **21** 张 + `kafka_message_record` | **22** 个 Repo | 22/22 |
| Mapper 接口/XML | **23** 接口 / **22** XML / **54** 条语句 | 22 Repo + `filters_gen`（19 个过滤函数、572 条件） | 语句级 49/54（见 7.7） |
| Service 类 | **47**（34 impl + 13 optimization） | **17** 个 service 模块 | 30 已迁移 / 6 部分 / 2 未迁移 / 9 不适用（见 7.6） |
| 定时任务 | **21** 个 `@Scheduled` + **3** 个后台常驻/启动钩子 | **21** 个登记（10 运行 + 11 禁用）+ 1 个重试循环 | 21/21 登记；启动钩子缺 2 类（见 7.8） |
| 配置键 | **174**（含框架专属项） | **119** 个 YAML 键 / **126** 个结构体字段 | 业务相关约 70 项全映射；框架专属 N/A（见 7.9） |
| 测试 | JUnit（Java 侧无有效单测） | **20** 个（14 单测 + 6 集成），`cargo test` 20/20 通过 | 见 §3.8 |

> 注：README-MIGRATION 中的"19 张业务表"指"19 个通用 CRUD 表"；实际库表清单为 21 张业务表 + `kafka_message_record`，与 22 个 Repo 一一对应。

### 7.3 HTTP 端点逐类盘点

| 分类 | 数量 | 端点 | 依据 |
|---|---|---|---|
| **真实现** | **61** | 19 组通用 CRUD 中除 4 条外的 44 条；`sysutil` 2 条（`changeTrailInfo`、`getByTrailBo`）；`large` 7 条（除 3 条 sync）；`unified` 3 条；`progressive` 2 条（snapshotflow、scale-level）；`sysutilTest` 3 条（syncBaseInfo/syncCurrentTrack/syncHistroyTrack） | 路由 + handler 走真实 DB/ES 查询（[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs)、[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs)、[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs)、[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs)） |
| **部分实现** | **5** | `POST /api/v1/large/sync/full`、`/sync/incremental`、`/sync/repair`；`GET /base/sysutil/carTrackQueryByCarNo`、`/carTrackQueryByTime` | 3 个 sync 响应壳正确，但后台游标 SQL 因 P0-2 在真实库上会失败（[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L229-L270)、[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1200)）；2 个轨迹接口 `total`/瞬态字段偏差（P1-1/P1-7） |
| **空壳（复刻 Java 失败行为）** | **18** | `feerecords/list`、`listToExport`；`vehicleweight/{id}`；`progressive/feerecords`、`trailfitting`；`sysutilTest` 的 `syncSuspiciousCar1..10`、`syncOdsSzdnGantry`、`separateSnapshotFlowTimeList`；`sysutil/saveRedis` | Rust 端固定返回 500 或 200 空体，**不执行真实逻辑**： [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L58-L88)、[base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L259-L265)、[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L337-L358)、[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L407-L417)、[sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L89-L93) |
| **行为不一致的空壳** | **1** | `GET /base/feerecords/{bigId}` | Rust 走通用 Repo 返回 200/空体；Java 因 Mapper 缺语句返回 500（详见 §3.2 P1-4） |

**关键结论**：85 条端点中，**61 条是真实现、5 条部分、18 条是"照实复刻 Java 失败"的壳、1 条是行为错的壳**。也就是说：
- 对外可用面 = 61 + 5 = 66 条（77.6%）；
- 剩下 19 条（22.4%）在 Java 侧本身就不可用或 Rust 复刻了失败；
- 24 个 Controller 中，**唯一没有任何"与 Java 行为一致且可用"端点的是 `OdsLwzxsfsjFeeRecords01Controller`**（list/listToExport 双端 500，getInfo 在 Rust 返回 200 但 Java 是 500）；`SysTestController` 15 条里只有 3 条真实现。

### 7.4 Controller 层盘点

| 分组 | Controller 数 | 端点数 | 真实现 | 部分 | 壳/偏差 | 备注 |
|---|---|---|---|---|---|---|
| 19 组通用 CRUD（fwqjcxx/sfsjcxx/sfzjcxx/fwqclls/feeGantry/feerecords/feeStationEnter/feestationexit/snapshotflow/provcapture/stationcapture/gantry/gantryIp/vehicleweight/section/toll/tollStationIp/org/trailtracks） | 19 | 48 | 44 | 0 | 4（2 个 feerecords list + vehicleweight 详情 + feerecords 详情） | 由 `crud_handlers!` 宏 + `list_impl/export_impl/all_impl/info_*_impl` 生成（[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L27-L131)） |
| LargeScaleQueryController | 1 | 10 | 7 | 3（sync） | 0 | [handlers/query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L71-L270) |
| UnifiedQueryController | 1 | 3 | 3 | 0 | 0 | 导出状态结构逐字段对齐 |
| ProgressiveQueryController | 1 | 4 | 2 | 0 | 2（feerecords/trailfitting） | snapshotflow + scale-level 真实现 |
| SysUtilController | 1 | 5 | 2 | 2（两个轨迹查询） | 1（saveRedis，Java 也是空实现） | [handlers/sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs) |
| SysTestController | 1 | 15 | 3 | 0 | 12 | 12 个壳有 Java 出处与原因注释（[selftest.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/selftest.rs#L60-L89)） |
| **合计** | **24** | **85** | **61** | **5** | **19** | |

### 7.5 实体 / 表 / Repo 盘点

| 项 | 结论 | 证据 |
|---|---|---|
| 30 个 Java domain | **30/30 有 Rust 模型**，字段名 camelCase、`@JsonFormat` 用 `Day/JDateTime/JIsoDateTime` 复刻 | [models/](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models)、[models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L825-L838) |
| 21 张业务表 + `kafka_message_record` | **22/22 Repo**（16 个 `entity_repo!` + 6 个 `entity_repo_numeric!`） | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L340-L539) |
| 列名/表名映射 | 服务区表 `ods_szdn_service` 的 25 列别名逐列复刻；其余表列名照抄 XML（含不存在的 `t.dataSource`，以复刻 500） | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L331-L339) |
| 空表 / 无 SQL 的表 | `fee_records` 的 List/ById 在 Java 无 XML（Java 500）；Rust 保留了 Repo，但 handler 复刻 500/错壳 | §3.2 P1-4 |
| `pulsar_message_record` | Rust 模型存在但无 Repo/无使用（Java `PulsarProducerService` 被注释） | 明确不适用 |

### 7.6 Service 层盘点（47 个类）

| 判定 | 数量 | 类清单 |
|---|---|---|
| **已迁移** | **30** | 数据层 21 个 `*ServiceImpl` 中的 **18 个**（除下文 3 个部分迁移）+ 非数据层 6 个（DataLossDetection、DataReliability、DelayMonitoring、KafkaProducer、MultiSourceDataFlow、TrailAggregation）+ optimization 6 个（LargeScaleDataSync、LargeScaleQuery、ProgressiveQuery、UnifiedExport、UnifiedQuery、GaussEsConsistency） |
| **部分迁移** | **6** | 数据层 3 个：`DwdLcztFwqjcxxServiceImpl`（`fwq_name` 缓存未刷新）、`OdsLwzxsfsjFeeRecords01ServiceImpl`（List/ById Java 缺 XML）、`OdsSzdnGantryIpServiceImpl`（`selectIPSet` 未迁移）；非数据层 1 个：`SysUtilServiceImpl`（changeData 清字段、syncTrack trailUuid、分页 total 等）；optimization 2 个：`EsIndexManageService`（只有未调用的 `create_index_if_absent`，无 ILM/mapping/启动建索引）、`ElasticsearchQueryService`（Progressive phase3 直接返回空而不查 ES） |
| **未迁移 / 行为越界** | **2** | ① `SnapshotFlowSyncService`：Java `@Service` + `@PostConstruct` 启动 **2 个常驻循环**（全量 DB→Kafka 回灌 + 增量永久轮询），`sync.full-sync-enabled` 默认 true，Rust 完全没有对应逻辑（`full_sync_enabled` 仅解析未使用）；② `SnapshotFlowPulsarConsumer`：Java `//@Service` 禁用，而 Rust **新增了默认启用的等价消费者**——这不是"少做"，而是"多做"，同样需要处理（见 P0-3） |
| **明确不适用** | **9** | `DebeziumReadonlyPulsarConsumer`（`//@Service`）、`PulsarProducerService`（`//@Service`）、`HighPerformanceSyncService`（@Service 但零调用方）、`TimeRangeParallelQueryExample`（@Component 示例）、`BillionLevelQueryService`、`HundredMillionLevelQueryService`、`CompositeQueryOptimizationService`、`LargeTableQueryOptimizationService`、`QueryValidationService`（均零外部引用，只互相引用） |

> 说明：9 个"不适用"里有 **5 个是 Java 侧死代码**（无调用方）；如果未来 Java 启用它们，Rust 需重新评估。`EsIndexManageService` 虽在 Java 是活跃 Bean（@PostConstruct 建 ILM/索引），Rust 只搬了底层原语，属真实缺口。

### 7.7 Mapper 查询盘点（54 条 XML 语句）

| 语句类型 | 条数 | Rust 等价实现 | 状态 |
|---|---|---|---|
| `selectXxxList`（各表过滤列表） | 19 | `filters_gen::*_filters` + `Repo::list` | **已迁移**（572 条条件全量生成） |
| `selectXxxById` | 19 | `Repo::get_by_id` / `get_by_id_i64` | **已迁移**（`fee_records` 的 Java 缺 XML，Rust 端为错壳） |
| `select...ByUuidList` / `ByQueryUuids` | 4（snapshot/prov/station/vehicleweight） | 逐 uuid `list_eq` 循环 + Redis 负缓存（N+1 查询） | **已迁移（实现不同）**：单条 `IN` 变成每 uuid 一次查询，见 [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L693-L728) |
| `selectByCursorShard` | 3（snapshot/fee/trail） | `cursor_query` / 各 Repo | **已迁移但有 P0-2**（时间文本绑定） |
| KafkaMessageRecord 3 条 | 3 | `select_failed_records/update_status_by_id/increment_retry_count` | **已迁移**（注意 NULL retry_count 语义差，§3.2） |
| `getHistoryTrail` | 1 | `TrailTracksRepo::get_history_trail` | **已迁移** |
| `selectIPSet` | 1 | — | **未迁移**（调用链 `OdsSzdnGantryIpServiceImpl.selectIPSet` 本身无调用方） |
| `getLatestTrail` / `getUnFitting` / `getLatestTrailByCursor` | 3 | — | **未迁移**（仅服务 `syncSuspiciousCarQutaz(New)` 与 `HighPerformanceSyncService`/`TimeRangeParallelQueryExample`，前者最终因缺 SQL 断链） |
| `selectOdsRtSzdnSnapshotFlowAddcodeListNew` | 1 | — | **未迁移**（同上，可疑车链路） |
| **合计** | **54** | **49** | **5 条未迁移** |

补充：Java Mapper 接口中还有 **4 个"有声明、无 XML"** 的方法（`selectOdsLwzxsfsjFeeRecords01ById/List/ListNew`、`selectGantryNum`），Java 调用即 500；Rust 对其中 3 个用 500/错壳复刻，`selectGantryNum` 对应端点 `syncOdsSzdnGantry` 也固定 500——属**忠实复刻 Java 断链**，不是 Rust 缺口。

### 7.8 定时任务与后台常驻任务盘点

| 类别 | Java | Rust | 状态 |
|---|---|---|---|
| `@Scheduled` 21 个 | TrackTask 3 + DataFlowTask 2 + Detection 1 + Delay 1 + Reliability 2 + Consistency 1 + CarTask 11 | 21 个登记：10 运行、1 开关（reconcile）、11 禁用（CarTask） | **21/21 登记**（[scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L235-L423)） |
| KafkaProducer 重试循环 | `@PostConstruct` + 单线程池 | `producer.start()` 常驻循环 | **已迁移**（[producer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/producer.rs#L64-L87)） |
| `SnapshotFlowSyncService` 全量/增量回灌 | `@PostConstruct` 启动 2 个循环 | 无 | **未迁移（活跃缺口）** |
| `EsIndexManageService` 启动建索引/ILM | `@PostConstruct` | 仅 `create_index_if_absent` 原语，**无调用方**，无 ILM | **部分迁移** |
| Pulsar/Kafka 消费者 | `//@Service` 禁用 | 默认启用（Kafka 语义） | **行为越界**（P0-3） |

### 7.9 配置项盘点

| 分组 | Java 键（示例） | Rust | 状态 |
|---|---|---|---|
| server / context-path | `server.port`、`servlet.context-path` | `server.port/context-path/mode` | 已迁移（`mode` 为 Rust 新增） |
| 数据源/连接池 | Druid 12 项 + p6spy + dynamic | `max-open/max-idle/conn-max-lifetime/log-sql` | 部分：Druid 检测/PS cache/filters/slowSql 未迁移；`log-sql` 未消费 |
| Redis | host/port/database/lettuce pool 4 项/shutdown-timeout | host/port/password/database/pool-size | 部分：`password` 未生效、`pool-size` 未消费 |
| Kafka | bootstrap/topic/max-retry-count | bootstrap/topic/max-retry-count/group-id | 已迁移（`group-id` 为 Rust 显式项） |
| Pulsar | 14 项 | 13 项 | 部分：`max-pending-messages-across-partitions` 缺失；`max-retry-count` 仅 `let _` |
| Elasticsearch | host/port/scheme/timeout 2 项/index 8 项 | 同名 13 项 | 已映射；`auto-create/shards/replicas/ilm-policy/attach-ilm` **未消费** |
| optimization / sync / consistency / reliability / detection / monitoring | 全部 | 全部 | 已迁移（`sync.es` 旧索引项除外） |
| mybatis-plus | 6 项 | — | 明确不适用（无 ORM） |
| forest / rediscluster | `forest.*` 8 项、`rediscluster.clusterNodes/refresh-interval-ms` | — | **未迁移**（HTTP 外呼与生产 Redis 集群分支） |
| rocketmq / rabbitmq / mq | 12 项 | 同名树 | 解析但**未接线**（与 README 声明一致） |
| logging | `level.root/web` | `logging.level/format` | 部分（`web` 级别无对应） |
| isLocalhost / sysbaseUrl | 2 项 | `app.env` / `app.sysbase_url` | 已映射（`sysbase_url` 未消费） |

> 结论：**业务语义相关的配置基本齐全**；缺口集中在 ① Druid 级连接治理、② Redis 密码/池/集群、③ ES 索引生命周期、④ Forest 外呼、⑤ 4 类消息中间件未接线——其中 ④⑤ 与 Java 现状一致（Java 也无活跃调用/消费者），①–③ 属生产适配缺口。

### 7.10 剩余缺口清单（按影响排序）

| # | 缺口 | 类型 | 影响 | 对应 Java | 对应 Rust |
|---|---|---|---|---|---|
| G1 | 消费端默认启用 + 幂等先写后处理 | 行为/数据 | 丢消息、与 Java 双写冲突 | `SnapshotFlowPulsarConsumer`（禁用） | [consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L105-L121) |
| G2 | `SnapshotFlowSyncService` 启动回灌未迁移 | 功能 | 依赖该 Bean 的 DB→Kafka 回灌链路缺失 | `SnapshotFlowSyncService` | 无 |
| G3 | 游标/对账/丢包时间绑定错误 | 功能 | sync/reconcile/loss 实际不可用 | XML `to_timestamp` | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1220) |
| G4 | `fuzzyFields` 注入面 | 安全 | SQL 注入 | `UnifiedQueryService`（同样存在） | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L353-L367) |
| G5 | ES 索引管理（建索引/ILM/mapping） | 运维 | 新环境需人工建索引；`auto-create` 配置失效 | `EsIndexManageService` @PostConstruct | `es.rs` 原语未调用 |
| G6 | `car_history_trail` / `car_curent_trail` 缓存形状 | 契约 | 下游读缓存不兼容 | `TrackTask` / `SysUtilServiceImpl` | [track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L117-L177) |
| G7 | snapshot ES `_id` 用 `big_id` | 数据 | ES 文档 id 与 Java 不一致 | `LargeScaleDataSyncService` 用 `datauuid` | [sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sync.rs#L131-L141) |
| G8 | `/base/feerecords/{bigId}` 200 vs 500 | 契约 | 状态码不一致 | Mapper 缺 XML | [crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L286-L294) |
| G9 | `selectIPSet`、`getLatestTrail`、`getUnFitting`、`getLatestTrailByCursor`、`ListNew` 共 5 条 SQL | 代码完整性 | 若 Java 复活这些功能需补 | `GantryIpServiceImpl` / 可疑车链路 | 无 |
| G10 | Forest 外呼 + `sysbaseUrl` | 功能 | 可疑车外推链路缺失（Java 也无调用方） | `HttpSysUtilApiService` | 无 |
| G11 | 生产 Redis 集群分支 | 功能 | 生产实时轨迹读不到 | `redisSourceFactory` | [track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L12-L16) |
| G12 | `fwq_name` 字典缓存刷新 | 副作用 | `syncBaseInfo` 少刷一个 key（当前无消费方） | `DwdLcztFwqjcxxServiceImpl.updateRedis` | [dict.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/dict.rs#L62-L71) |

---

## 8. 技术栈与框架的生产适配性评估

> 标准：不是"能否跑"，而是"能否在多人运维、多副本、可观测、可回滚的生产环境长期运行"。逐项给出现状、差距与风险。

### 8.1 逐项评估

| # | 维度 | 当前实现 | 差距 / 风险 | 等级 |
|---|---|---|---|---|
| 1 | **连接池与超时** | PgPool：max20/min5/acquire 60s；`conn_max_lifetime_seconds` 被当作 `idle_timeout`（语义错位，[db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs#L27-L38)）；Redis 单 `ConnectionManager`；ES/reqwest 有 connect/socket 超时；**HTTP 层无超时、无 body 上限**；DB 查询无 `statement_timeout` | 一条慢 SQL 会长期占用连接并挂住请求；大 body 可打爆内存；`idle_timeout` 误用会提前回收空闲连接、抬高建连频率 | **高** |
| 2 | **优雅停机** | `axum::serve(...).with_graceful_shutdown(ctrl_c)`（[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L347-L360)） | **只监听 Ctrl+C，不监听 SIGTERM**；容器/K8s 停止发 SIGTERM 时进程直接被杀，HTTP 排空、offset 提交、导出落盘全部跳过。且关闭顺序不等待 scheduler/consumer 任务 | **高** |
| 3 | **健康检查/就绪探针** | `/healthz` 恒 UP；`/readyz` 检查 DB/Redis/ES/mqConsumer（[router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L220-L278)） | ES 失败只写字段不翻转整体 DOWN；启动时 Redis 连接失败 → `cache=None`，readyz 不再报 Redis；无启动期就绪门控（端口已监听但依赖未就绪） | 中 |
| 4 | **限流与背压** | 导出有 `Semaphore(2/4)`；其余无 | 无 IP/租户限流、无 HTTP 并发上限、无 body 上限；`/api/v1/large/*` 可被刷；导出任务 map 无上限且 `clean_expired_tasks` 从未调用（[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L120-L127)） | **高** |
| 5 | **日志与 trace 关联** | tracing + request_id span + 响应头（[middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs#L32-L78)） | 在 async 中间件里用 `span.enter()` 进入 span 并在作用域内 `.await`，属于 tracing 不推荐的模式（应用 `.instrument()`）；跨 await/任务迁移时 span 上下文可能错配。不解析 inbound `traceparent`；出站（ES/Kafka/DB）不传播 trace；无采样、无慢请求阈值 | 中 |
| 6 | **指标暴露** | 无 `/metrics`，无任何计数器/直方图 | 无法观测 QPS/延迟/错误率、DB 池占用、Redis 故障、Kafka lag、导出队列深度、定时任务成败。Java 亦无 Actuator，但生产必须有 | **高** |
| 7 | **配置与密钥** | YAML 内直接写库密码 `OpenGauss@123`、ES `changeme`（[application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml#L13-L15)、[application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml#L68-L73)）；支持 `APP_*` 覆盖 | 明文密钥入库；Redis password 覆盖键存在但**不生效**；两套 env 机制（`config::Environment` 的 `__` 与手写 `_`）；无 secret manager/无加密 | **高** |
| 8 | **数据库迁移管理** | `migrations/` 4 个 SQL，无 `sqlx::migrate!`、无版本表、无启动校验 | 表结构演进靠人工执行；多环境无法保证一致；`tools/gen_models.py` 是代码生成不是 DB 迁移 | 中 |
| 9 | **多实例部署** | 无状态 HTTP 部分可横向扩展（Kafka 同 group 分片消费、Redis 幂等跨实例） | ① 每个副本都会跑全部定时任务（无 leader 选举/无 `enable-scheduler=false` 约束）；② 导出任务状态在**进程内 HashMap**，轮询打到别的副本即 404；③ 导出文件写本地 `/data/export`；④ `MultiSourceService` 对 Redis 轨迹做无锁 read-modify-write，跨实例丢更新 | **高** |
| 10 | **文件与磁盘依赖** | 导出落 `/data/export`，同步 `std::fs` 写在 async worker | 无磁盘水位检查、无保留期/清理、失败残留分片、无共享存储约定；阻塞 tokio worker | 中 |
| 11 | **异常兜底** | `CatchPanicLayer` + `AppError: IntoResponse`；调度任务用 `catch_unwind` | 后台 `tokio::spawn`（sync/full、repair、导出）panic 只终止该 task，无告警；多处 `unwrap()`（锁中毒、writer）；无全局请求超时；ES `count` 失败静默返回 0 | 中 |
| 12 | **传输安全** | 服务明文 HTTP；DB `sslmode` 默认 `disable`（[db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs#L110-L124)）；ES 可 basic auth | 与 Java 现状一致（`useSSL=false`），但生产需 TLS/入口收敛；无鉴权（与 Java 一致） | 中 |
| 13 | **构建环境** | `rdkafka` 使用 `cmake-build`（[Cargo.toml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/Cargo.toml#L38)） | 构建机必须装 CMake + C 工具链；第二轮实测 PATH 缺 CMake 直接构建失败（`is cmake not installed?`）；首构建 3m52s，镜像体积大 | 中 |
| 14 | **依赖与 lint 基线** | `cargo check` 通过；clippy 505 warning（466 来自生成文件） | `-D warnings` 无法进 CI；生成代码噪音掩盖手写代码告警 | 低-中 |

### 8.2 "离生产还差什么"——一句话清单

1. **进程生命周期**：补 SIGTERM 监听 + 关闭排空/超时（当前 Ctrl+C 之外不会优雅退出）。
2. **流量治理**：补 body 上限、请求超时、并发/限流（当前公网可打爆大查询与内存）。
3. **可观测**：补 `/metrics`、慢请求/错误率/队列/Kafka lag 指标与 trace 传播（当前只有日志）。
4. **密钥**：密码外置到 Secret/环境变量，Redis password 生效，移除仓库明文。
5. **多副本契约**：定时任务 leader 化或副本禁用、导出任务状态外置（Redis/DB）、导出文件共享存储。
6. **数据链路**：修 P0-2/P0-3/P0-4 后再谈消费/同步；补 `SnapshotFlowSyncService` 或明确不需要。
7. **ES 运维**：索引/ILM/mapping 启动初始化或脚本化，`auto-create` 配置落地。
8. **CI 基线**：check/test 必绿，clippy 清零手写代码并隔离生成文件。

---

## 9. 生产化路线图（可排期）

> 与 §4 的关系：§4 按代码风险分级（P0/P1/P2），本章按**上线时间窗**重排，并补充生产基建项。每条给出模块、改动范围、验收方式、风险。
> 命名：B=上线前必做，S=上线后短期（1–2 迭代），M=中期演进。

### 9.1 上线前必做（Blockers）

| ID | 事项 | 涉及模块 / 改动范围 | 验收方式 | 风险 |
|---|---|---|---|---|
| B1 | 消费端默认关闭；如确需消费，先修幂等顺序（成功后再标记/失败回删） | [config/application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml#L140-L144)、[consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L105-L121)、[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs#L279-L296)；约 20 行 + 1 个状态机测试 | ① 默认启动日志无"消费者已启动"；② 模拟 DB 失败：消息 3 次重投后进 `.DLQ`，Redis 无残留幂等键；③ 成功路径只落库一次 | 若业务确需 Rust 消费，需与 Java 侧确认唯一消费方，避免双写 |
| B2 | 三处时间条件改 `to_timestamp($n,'yyyy-mm-dd HH24:MI:SS')` 或绑定 `NaiveDateTime` | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L702-L716)、[repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1220)；约 30 行 | 真库执行 `POST /sync/full` 与 `POST /sync/incremental`：日志出现"分片完成/同步完成"，`/readyz` 正常；`loss_detection` 不再报 SQL 类型错误 | 时间入参格式需统一；游标二元组 `>` 语义不能破坏；需回归 `compare_*` |
| B3 | `fuzzyFields` 未知字段拒绝/忽略，DB 降级只用白名单 | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs#L353-L367)；约 10 行 + 2 测试 | 传 `fuzzyFields.<列名注入串>` 返回 400 或空结果，不再拼接；正常模糊字段结果与旧版一致 | 与 Java 行为产生差异（Java 同样可注入），需架构确认是否同步修 Java |
| B4 | 补 SIGTERM 优雅停机 + 关闭顺序（HTTP 排空 → 调度/消费 → 导出 → DB/Redis） | [main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L347-L369)；约 30 行 | Linux 下 `kill -TERM`：日志出现"收到退出信号…应用已退出"，无 `Killed`；在途导出状态为 COMPLETED/FAILED 而非悬挂 | Windows 开发环境用 Ctrl+C 验证；需区分 cfg(unix) |
| B5 | 探针语义修正：ES/Redis 故障纳入 readiness；启动期依赖未就绪不接流量 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L228-L278) | 停 ES → `/readyz` 503 且 `elasticsearch=DOWN`；停 Redis → 503（而非静默 UP）；恢复后转 200 | 若 K8s 用 readiness 摘流，需确认 ES 短抖动不会导致全量摘流（可分级：DB 必需、ES 降级） |
| B6 | 密钥外置：移除 YAML 明文；`APP_*_PASSWORD` 全链路生效（尤其 Redis） | [application.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/config/application.yaml)、[cache.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/cache.rs#L30-L42)、[config.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/config.rs#L649-L656) | 仓库无明文密码；设置 `APP_REDIS_PASSWORD` 后能连有密码 Redis；错误密码时启动降级日志明确 | Redis 密码生效后，未配密码环境需保持空串兼容 |
| B7 | HTTP 请求体上限 + 全局超时 + 并发上限 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L38-L42)：加 `RequestBodyLimitLayer` / `TimeoutLayer` / `ConcurrencyLimitLayer`；约 10 行 | 20MB body 返回 413；`/base/sysutil/changeTrailInfo` 超大 JSON 不再 OOM；慢请求在阈值被中断并返回 408/503 | 超时值需大于最慢导出/查询接口；导出是后台任务不受 HTTP 超时影响 |
| B8 | 契约补齐：`change_data` 清瞬态字段、`car_history_trail` 形状、snapshot ES `_id`、`feerecords/{bigId}`、去重毫秒阈值 | [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L131-L135)、[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L117-L177)、[sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sync.rs#L131-L141)、[crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L286-L294)、[trail.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/trail.rs#L416) | 有数据行的库上 `carTrackQueryByCarNo` 逐 JSON 对比通过；`feerecords/{bigId}` 双端 500；ES 文档 `_id` 抽查等于 `datauuid`；4m30s 轨迹点不再被误合并 | 缓存形状变更需清 `car_history_trail:*` / `car_curent_trail:*`；ES `_id` 变更需重建索引 |
| B9 | 多副本前置约束：`enable-scheduler=false` 于只读副本；导出任务状态外置（Redis/DB）或固定会话路由 | [main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs#L313-L334)、[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L52-L127) | 2 副本同时启动：定时任务只在 1 个副本执行；导出提交后任意副本轮询状态均能命中；文件路径可被所有副本访问 | 外置状态需引入 Redis key 设计；导出文件共享存储依赖基础设施 |
| B10 | CI 基线：`cargo check`/`cargo test` 必绿；clippy 清零手写代码（约 39 条），生成文件 `filters_gen.rs` 加 `#![allow(...)]` 或修生成器 | [filters_gen.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/filters_gen.rs)、`tools/gen_filters.py`、CI 配置 | CI 上 `cargo clippy --all-targets -- -D warnings` 退出码 0；`cargo test` 20/20 | 修生成器需重跑并复核 572 条条件与 Java XML 一致 |

### 9.2 上线后短期（1–2 迭代）

| ID | 事项 | 涉及模块 / 改动范围 | 验收方式 | 风险 |
|---|---|---|---|---|
| S1 | 指标暴露：`/metrics`（请求量/延迟分位/错误率、DB 池、Redis 可用性、Kafka lag、导出队列、定时任务成功/耗时） | 新增 `metrics` + `metrics-exporter-prometheus`；[middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs) 采集；约 150 行 | Prometheus 抓取成功；压测时 QPS/延迟面板有数据；停机后指标仍可查 | 指标基数控制（不要按 url 全量 label）；与日志重复无妨 |
| S2 | 日志/trace 规范化：`.instrument()` 替代 `span.enter()`；解析 `traceparent`；出站注入；采样 | [middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs#L61-L67)、[es.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/es.rs)、[mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs)；约 80 行 | 同一请求的日志/ES/Kafka 日志可串成一条 trace；跨服务 trace_id 一致 | 需要日志采集侧约定字段；采样率过高会丢排障信息 |
| S3 | 限流/并发保护：按路由组限流（大查询、导出、管理端点）+ 全局并发上限 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs)：`GovernorConfig`/`ConcurrencyLimitLayer`；约 40 行 | 压测超过阈值返回 429/503；正常业务无影响 | 阈值需与容量测试匹配；误伤批量调用方 |
| S4 | 导出目录治理：保留期、GB 水位告警、失败残留清理、任务 TTL | [export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L120-L132)、[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs)、新增清理任务 | 连续导出 100 次后目录受控；失败任务无残留分片；状态 map 不无限增长 | 清理误删在途文件；需按 task 状态保护 |
| S5 | ES 索引生命周期落地：启动建 ILM/mapping 或独立运维 Job；`auto-create` 生效；`consistency` 用配置索引名 | [es.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/es.rs#L235-L260)、[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs)、[consistency.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consistency.rs#L83-L90) | 新环境空 ES 启动后 3 个索引 + ILM 自动存在；改 `elasticsearch.index.*` 后查询/对账一致 | 索引创建需要权限；ILM 名称变更影响已有索引 |
| S6 | 调度治理：per-job 防重入、执行超时、失败告警、执行记录 | [scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L176-L224)；约 60 行 | 人为让任务睡 2 个周期，验证不叠加；超时任务被取消并告警 | 取消长任务可能留下半成品；需与业务定义可中断点 |
| S7 | 时区统一：存储/传输用 UTC 或统一 `Asia/Shanghai` 常量，移除硬编码 ±8h；监控 key 用本地日期 | [models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs#L259-L269)、[loss_detection.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/loss_detection.rs#L106-L108)、[delay_monitor.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/delay_monitor.rs#L259-L261) | 同一时刻 DB/接口/监控窗口时间一致；换个时区跑测试仍一致 | 会改变现有缓存 key 与展示值，需要灰度/清缓存 |
| S8 | DB 迁移管理：`sqlx::migrate!` 或独立 migration Job + 版本表 + 发布校验 | `migrations/` + [main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs) | 空库可一条命令建全表；重复执行幂等；版本落后时启动拒绝 | 生产 DDL 权限与锁表风险；需与 DBA 流程合并 |
| S9 | 链路验证补全：sync/export/consume 在独立环境跑通并纳入回归 | `tools/verify_full.py` 扩展 + 本报告 §7 清单 | 全量/增量/补同步、导出落盘、消费 ACK/DLQ 均有自动化用例 | 需要独立 Kafka/ES 环境与数据隔离 |

### 9.3 中期演进

| ID | 事项 | 涉及模块 / 改动范围 | 验收方式 | 风险 |
|---|---|---|---|---|
| M1 | Redis 生产化：连接池（deadpool/bb8）、Cluster 分支、`trail:{carNo}` 集群读取 | [cache.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/cache.rs)、[track_sync.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/track_sync.rs#L60-L71) | 压测连接复用；Cluster 模式下读写全部 key 正确 | Cluster 改造面大，key 设计与跨 slot 操作需重审 |
| M2 | 消息中间件收敛：Pulsar 真客户端或书面确认长期 Kafka；补齐 `SnapshotFlowSyncService` 等价能力 | [mq.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/mq.rs)、新增 backfill 服务 | 消息源切换演练通过；回灌断点续传有水位 | Pulsar Rust 生态不成熟；回灌可能压垮 DB/Kafka |
| M3 | ES 客户端增强（可选）：typed query DSL、bulk item 级失败统计、重试与熔断 | [es.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/es.rs) | bulk 部分失败可被计数并告警；ES 抖动不放大 | 引入官方 crate 会绑定版本；手写增强成本低但需维护 |
| M4 | 结构重构：拆分 `AppState`（40 字段）、收敛 service 边界、导出公共 `ScrollCsvWriter` | [state.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/state.rs)、[export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs)、[large.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/large.rs) | 编译期依赖图更清晰；导出逻辑单点维护；回归 548 项不变 | 大范围重构风险高，需在功能冻结期做 |
| M5 | 类型建模收敛：`J*` 增加数字时间戳/精度测试；金额改 `BigDecimal`；`JInt` 溢出改为报错 | [models/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/models/mod.rs) | 单测覆盖各 SQL 类型与 JSON 边界；金额汇总无误差 | 改动会影响所有实体解码，需全量回归 |
| M6 | 可观测进阶：OTLP trace、慢 SQL 日志（`log-sql` 落地）、队列积压/延迟面板 | [db.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/db.rs)、[main.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/main.rs) | 慢 SQL 可在日志按阈值检索；trace 串通 DB/ES/Kafka | 采样与性能开销；SQL 日志需脱敏 |
| M7 | 安全收口：恢复鉴权（如 Java 后续启用）、SQL 列名白名单、TLS、审计日志 | [middleware.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/middleware.rs)、[query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/query.rs) | 未授权请求 401/403；注入用例全部拒绝；DB/ES 走 TLS | 鉴权会改变前端调用方式；TLS 需证书管理 |
| M8 | 容量与压测：8 亿级表查询/导出/分页基线，连接池与线程数定型 | `tools/` 压测脚本 + 生产同构环境 | 给出 QPS/P99/资源水位报告；确定 `max_connections`、导出并发 | 需要大数据量与独立环境；压测可能影响共享库 |

---

## 附录 A：抽样核对结果速览

| 抽样点 | Rust 位置 | Java 位置 | 结论 |
|---|---|---|---|
| 85 路由清单 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L397-L763) | 24 个 Controller 注解 | 一致 |
| `/base/fwqjcxx/list` 等 19 表通用 CRUD | [crud.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/crud.rs#L27-L60) | 各 Controller `list/getInfo/listAll` | 一致 |
| `/base/snapshotflow/list` 富集 | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L176-L246) | [OdsRtSzdnSnapshotFlowAddcodeController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java#L40-L90) | 一致 |
| `/base/feerecords/list|listToExport` | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L58-L88) | [OdsLwzxsfsjFeeRecords01Controller.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java#L46-L120) | 一致（均 500） |
| `/base/feerecords/{bigId}` | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L70) | [OdsLwzxsfsjFeeRecords01ServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsLwzxsfsjFeeRecords01ServiceImpl.java#L37-L40) | **不一致**（Rust 200，Java 500） |
| `/base/trailtracks/{uuid}` | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L267-L288) | [ZdataTrailTracksController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/ZdataTrailTracksController.java#L43-L46) | 一致 |
| `/base/vehicleweight/{id}` | [base.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/base.rs#L259-L265) | [OdsSzdnProvinceBorderVehicleWeightNewstructureController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnProvinceBorderVehicleWeightNewstructureController.java#L45-L48) | 当前一致（500），实现方式脆弱 |
| `/base/sysutil/carTrackQueryByCarNo` | [handlers/sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/sysutil.rs#L33-L58) + [services/sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L110-L129) | [SysUtilController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/SysUtilController.java#L77-L109) | 分页/瞬态字段不一致（P1-1/P1-7） |
| `/base/sysutil/getByTrailBo` | [sysutil.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/sysutil.rs#L412-L485) | [SysUtilServiceImpl.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java#L969-L1223) | 基本一致；FeeStationEnter/Exit 的 clear 条件略有差异 |
| `/api/v1/large/{snapshot,fee,tail}` | [handlers/query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L71-L146) | [LargeScaleQueryController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/LargeScaleQueryController.java#L54-L154) | 一致（存在 P0-1 注入面） |
| `/api/v1/large/stats/group` | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L148-L182) | [LargeScaleQueryController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/LargeScaleQueryController.java#L164-L191) | 一致 |
| `/api/v1/unified/{ds}/list` | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L276-L306) | [UnifiedQueryController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/UnifiedQueryController.java#L64-L95) | 一致 |
| `/progressive/{table}/list` | [query.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/handlers/query.rs#L380-L433) | [ProgressiveQueryController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/ProgressiveQueryController.java#L53-L174) | 一致（total=本页行数） |
| `/base/sysutilTest/*` 12 个"跑不通"端点 | [router.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/router.rs#L337-L358) | [SysTestController.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/controller/SysTestController.java) | 一致（200 空体/500） |
| 三表 `<if>` 过滤 | [filters_gen.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/filters_gen.rs) | 19 份 XML | 一致（机器生成，列名照抄） |
| 游标同步 SQL | [repo/mod.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/repo/mod.rs#L1155-L1201) | XML `selectByCursorShard` | **不一致**（文本绑定 vs `to_timestamp`） |
| 快照消费 | [consumer.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/consumer.rs#L89-L208) | [SnapshotFlowPulsarConsumer.java](file:///d:/work/IdeaProjects/car-monit-api/pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java#L253-L320) | 逻辑一致，但 Java 类被禁用；Rust 默认启用 |
| 导出 CSV 列 | [export.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/services/export.rs#L314-L365) | `UnifiedExportService` 静态列 | 需人工核对列名，未逐字段比对 |
| 调度登记 21 个 | [scheduler.rs](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-rust/src/scheduler.rs#L235-L423) | `CarTask/TrackTask/DataFlowTask` + 服务内 `@Scheduled` | 一致（CarTask 11 个禁用） |
