# car-monit-api-rust — Java / Spring Boot 的 1:1 Rust 迁移

本目录是 `pro-business-api`（Java 17 / Spring Boot）的 Rust 生产级等价实现。
目标不是“重新设计一个 Rust 服务”，而是**用 Rust 逐文件重写同一个服务**：
API 路径、请求/响应结构、状态码、错误码、数据库查询语义、缓存 key、消息格式与消费语义保持一致。

- 迁移基线：[`docs/MIGRATION-BASELINE.md`](docs/MIGRATION-BASELINE.md)（阶段一：结构/接口/数据层/中间件/配置/阻塞点）
- 全量映射：[`docs/JAVA-RUST-MAPPING.md`](docs/JAVA-RUST-MAPPING.md)（阶段二：11 个维度的 Java ↔ Rust 对照）
- 本文件：阶段四（可启动产物、配置对照、依赖映射、10 个阅读难点、自检清单）

**规模**：85 个有效 HTTP 端点、30 个实体/DTO（901 字段）、22 个数据访问仓库、21 个定时任务登记
（9 个默认运行 + 1 个开关控制 + 11 个按 Java 现状禁用）、16 个自动化测试。

---

## 1. 从零启动

### 1.1 前置条件

| 组件 | 版本 | 用途 | 是否必需 |
|---|---|---|---|
| Rust | **1.90.0**（`rust-toolchain.toml` 已锁定） | 编译 | 必需 |
| GaussDB / PostgreSQL | 兼容 PostgreSQL 协议 | 业务库（schema `jl_data01`） | 必需（启动即 Ping） |
| Redis | 6+ | 字典/轨迹/幂等/可靠性 | 建议（不可用时只告警） |
| Kafka | 2.x+ | 消息生产/消费 | 可选（为空则降级 Noop） |
| Elasticsearch | 7/8 | 大表查询/导出/同步 | 可选（接口返回错误） |

Rust 工具链：

```bash
rustup toolchain install 1.90.0
rustup show                 # 在项目目录应显示 1.90.0（rust-toolchain.toml）
cargo --version
```

### 1.2 配置

```bash
cp .env.example .env        # 按需修改，或在 config/application.yaml 中直接改
```

配置优先级：**`--config` 命令行 > `CAR_MONIT_CONFIG` > `config/application.yaml` > 代码默认值**。

### 1.3 数据库

仓库内的 Java 侧只提供了 `kafka_message_record` 的 DDL；其余 19 张业务表是既有 GaussDB 表，
不在 Java 仓库存放 DDL。`migrations/` 已收录 Java 侧全部可用 SQL：

| 文件 | 来源 | 说明 |
|---|---|---|
| `migrations/001_kafka_message_record.pg.sql` | `setup_script/sql/10_kafka_message_record.pg.sql` | Kafka 消息记录表（PG 方言） |
| `migrations/002_index_optimization.sql` | `resources/sql/index_optimization.sql` | 三张大表索引优化 |
| `migrations/003_progressive_architecture_indexes.sql` | `resources/sql/progressive_architecture_indexes.sql` | 渐进式查询索引 |
| `migrations/004_partition_scheme.sql` | `resources/sql/partition_scheme.sql` | 分区方案 |
| `resources/es/*.json` | `resources/es/index` + `resources/sql` | ES 索引 mapping / ILM |

> 注意：`002` / `003` 中的 `CREATE INDEX CONCURRENTLY` 不能在事务块内执行；
> 生产环境按文件内注释逐条执行。大表索引建议低峰期操作。

### 1.4 编译、自检、测试、启动

```bash
# 依赖与编译
cargo build

# 配置自检（不连接任何外部组件）
cargo run -- --check-config
# 实测输出：
# CONFIG_OK port=9901 context_path=/ db=jdbc:postgresql://192.168.56.10:5432/RuoYi?... redis=127.0.0.1:6379 kafka=localhost:9092 es=http://localhost:9200 cron_ok=true

# 单元测试 + HTTP 层集成测试（不需要数据库/Redis/Kafka/ES）
cargo test
# 实测：16 passed; 0 failed

# 启动（需要 GaussDB 可达）
cargo run -- --config config/application.yaml
```

启动后：

```bash
curl -s http://localhost:9901/healthz
# {"status":"UP","time":"2026-10-31T..."}

curl -s http://localhost:9901/readyz      # 依赖就绪：GaussDB / Redis / ES / MQ 消费端
curl -s "http://localhost:9901/base/snapshotflow/list?pageNum=1&pageSize=2"

curl -s http://localhost:9901/not-exist
# {"code":404,"msg":"接口不存在: GET /not-exist","data":null}
```

优雅关闭：`Ctrl+C` 后 HTTP → 调度器/消费者（`watch` 信号）→ 导出任务 → Redis → GaussDB。
关闭顺序见 `src/main.rs` 末尾。

> **已使用真实 GaussDB/Redis 完成双端实测**：Java（9902）与 Rust（9911）同时连接
> `192.168.56.10:5432/RuoYi`，对 74 个只读/错误场景逐 JSON 对比，结果 **74/74 一致**。
> 详见第 10 节。

---

## 2. Java 配置 → Rust 配置逐项对照

| Java (`application.yml`) | Rust (`config/application.yaml`) | 默认值 | 备注 |
|---|---|---|---|
| `server.port` | `server.port` | 9901 | 一致 |
| `server.servlet.context-path` | `server.context-path` | `/` | 一致 |
| `spring.datasource.dynamic.datasource.master.url` | 同名 | GaussDB URL | 自动剥离 `jdbc:`，只保留 PG 参数 |
| `...master.username/password` | 同名 | gaussdb / OpenGauss@123 | 一致 |
| `...master.driver-class-name` | 同名 | org.postgresql.Driver | 仅保留，不参与连接 |
| `spring.datasource.druid.initial-size/min-idle/maxActive/maxWait` | `max-open-conns` / `max-idle-conns` / 内部 60s | 20 / 5 | Rust 侧新增键 |
| `spring.redis.host/port/database` | `redis.host/port/database` | 127.0.0.1 / 6379 / 0 | 一致 |
| `spring.redis.lettuce.pool.max-active` | `redis.pool-size` | 16 | 连接管理器 |
| `spring.kafka.bootstrap-servers` | `kafka.bootstrap-servers` | localhost:9092 | 空值 → Noop |
| `spring.kafka.topic.snapshot-flow` / `kafka.topic.snapshot-flow` | `kafka.topic.snapshot-flow` | ods-rt-szdn-snapshot-flow | 一致 |
| `spring.kafka.group-id` | `kafka.group-id` | ods-rt-szdn-snapshot-flow-sub | 一致 |
| `spring.pulsar.*`（11 项） | `pulsar.*` | 见 YAML | 全部保留 |
| `rocketmq.*` | `rocketmq.*` | 见 YAML | 保留；未接线 |
| `rabbitmq.*` | `rabbitmq.*` | 见 YAML + `enabled:false` | 保留；未接线 |
| `elasticsearch.*` | `elasticsearch.*` | localhost:9200 | 全部保留 |
| `optimization.query.{timeout-ms,max-window,es-force-days}` | 同名 | 30000 / 10000 / 30 | 一致 |
| `optimization.export.{scroll-batch,file-batch,dir,scroll-keepalive-min}` | 同名 | 2000 / 100000 / `/data/export` / 5 | 一致 |
| `sync.{batch-size,full-sync-enabled,incremental-sync-interval}` | 同名 | 1000 / true / 60000 | 一致 |
| `consistency.reconcile.*` | 同名 | false / 3 / 0.01 / `0 30 2 * * ?` | 一致 |
| `reliability.*` | 同名 | 30000 / 5 / 60 / 10000 | 一致 |
| `detection.*` | 同名 | 60 / 30 / 5 | 一致 |
| `monitoring.*` | 同名 | 5000 / 3000 / 10000 / 30000 / 10 | 一致 |
| `logging.level.*` | `logging.level` | info | 一致 |
| `isLocalhost` | `app.env` | local | 语义一致 |
| `sysbaseUrl` | `app.sysbase-url` | 同左 | 一致 |
| （无） | `app.consumer-enabled` | true | **Rust 新增** |
| （无） | `app.enable-scheduler` | true | **Rust 新增** |

环境变量示例见 `.env.example`；`--check-config` 会回显最终生效的端口/地址。

---

## 3. 依赖组件映射总表

| 关注点 | Java | Rust | 本仓库实现 |
|---|---|---|---|
| Web | Spring MVC `@RestController` | Axum 0.8 | `src/handlers/*` + `src/router.rs` |
| 运行时 | 内嵌 Tomcat | tokio + hyper | `src/main.rs` |
| 序列化 | Jackson / Fastjson2 | serde / serde_json | `src/models/*`、`src/response.rs` |
| ORM | MyBatis-Plus + XML | SQLx（运行时查询） | `src/repo/mod.rs` |
| 连接池 | Druid / HikariCP | `sqlx::PgPool` | `src/db.rs` |
| 分页 | PageHelper ThreadLocal | 显式 `LIMIT/OFFSET` | `src/handlers/common.rs` |
| 事务 | `@Transactional` AOP | `Db::begin()` | `src/db.rs` |
| 缓存 | Spring Data Redis / Lettuce | `redis` crate | `src/cache.rs` |
| Kafka | spring-kafka | **rdkafka**（librdkafka） | `src/mq.rs` |
| Pulsar | pulsar-client | Kafka 同语义 `Bus`（无官方客户端） | `src/mq.rs` |
| RocketMQ | rocketmq-spring-boot-starter | 未接线（生态不成熟） | — |
| RabbitMQ | spring-amqp | 未接线（Java 无活跃消费者） | — |
| Elasticsearch | RestHighLevelClient | reqwest 直连 REST | `src/es.rs` |
| 配置 | `@Value` / `@ConfigurationProperties` | config crate + serde | `src/config.rs` |
| DI | Spring 容器 | 组合根 + `Arc<AppState>` | `src/main.rs`、`src/state.rs` |
| 日志 | SLF4J + Logback | tracing + tracing-subscriber | `src/main.rs`、`src/middleware.rs` |
| 定时任务 | `@Scheduled` + Quartz cron | 自研 6 段 cron 解析 | `src/scheduler.rs` |
| 线程池 | `ThreadPoolTaskExecutor` | `tokio::spawn` + `Semaphore` | `src/services/export.rs`、`large.rs` |
| 测试 | JUnit 5 / Mockito / AssertJ | `#[test]` / `#[tokio::test]` | `tests/*.rs` |
| 构建 | Maven fat jar | Cargo 单二进制 | `Cargo.toml` / `Cargo.lock` |
| 健康检查 | （未接 Actuator） | `/healthz`、`/readyz` | `src/router.rs` |

---

## 4. 目录映射

| Java | Rust |
|---|---|
| `EcBusinessApiApplication` | `src/main.rs` |
| `common.config.interceptor` / `WebConfig` | `src/middleware.rs`（仅请求 ID/日志） |
| `common.core.domain.AjaxResult` / `TableDataInfo` | `src/response.rs` |
| `common.core.redis.RedisCache` | `src/cache.rs` |
| `common.utils.*` | `src/utils.rs` |
| `base.controller.*`（24 个） | `src/handlers/{crud,base,query,sysutil,selftest}.rs` |
| `base.domain.*`（30 个） | `src/models/*`（`tools/gen_models.py` 解析 Java 字段类型/@JsonFormat + 真实 DB 类型生成） |
| `base.mapper.*` + `xml/*.xml` | `src/repo/mod.rs` |
| `base.service.impl.*` | `src/services/{consumer,producer,reliability,loss_detection,delay_monitor,multisource,sysutil,trail,track_sync}.rs` |
| `base.service.optimization.*` | `src/services/{query,large,export,progressive,sync,consistency}.rs` |
| `base.task.*` + 全部 `@Scheduled` | `src/scheduler.rs` |
| `config/*`（Kafka/Pulsar/Scheduling） | `src/mq.rs`、`src/scheduler.rs` |
| `mq.*` | `src/mq.rs`、`src/es.rs` |
| `base.flink.VehicleTrackFlinkJob` | **不移植**（独立 Flink 作业） |
| `resources/application.yml` | `config/application.yaml` |
| `resources/sql/*`、`setup_script/sql/*` | `migrations/*` |
| `resources/es/index/*.json` | `resources/es/*.json` |
| （无） | `tests/router_test.rs`、`tests/parity_test.rs` |

---

## 5. Java 开发者阅读 Rust 代码最容易困惑的 10 个点

### 5.1 `let b = a;` 之后 `a` 为什么不能用了？

```java
// Java：两个变量指向同一个对象
User a = new User("张三");
User b = a;
a.setName("李四");   // b.name 也是李四
```

```rust
// Rust：默认是“移动”
let a = User { name: "张三".into() };
let b = a;           // 所有权移动到 b
// println!("{}", a.name); // E0382: borrow of moved value
println!("{}", b.name);
```

> 这不是语法怪癖，而是防止双重释放：Rust 没有 GC，靠“同一时刻只有一个所有者”保证析构安全。
> 需要共享时用 `clone()`（复制数据）或 `&`/`Arc`（借用/共享所有权）。

### 5.2 为什么没有 `null`？

```java
String name = user.getName();          // 可能 null
if (name != null && name.length() > 0) { ... }
```

```rust
let name: Option<String> = user.name;  // 必须显式表达“可能没有”
if let Some(n) = name {
    if !n.is_empty() { /* ... */ }
}
```

### 5.3 异常去哪了？为什么到处是 `?`

```java
// Java：抛异常，由 @ControllerAdvice 兜底
User u = repo.findById(id).orElseThrow(() -> new NotFoundException());
return AjaxResult.success(u);
```

```rust
// Rust：错误是返回值，? 等价于“失败就 return Err(e)”
let user = repo.get_by_id(&id).await?
    .ok_or_else(|| AppError::NotFound(id.clone()))?;
Ok(json_ok(AjaxResult::success(Some(serde_json::to_value(user)?))))
```

`AppError::into_response` 就是 `@ControllerAdvice`。

### 5.4 `@Autowired` 在哪？

```java
@Service
public class SysUtilService {
    @Autowired private ZdataTrailTracksMapper trailMapper;
}
```

```rust
// main.rs：显式构造，依赖缺失 = 编译失败
let sysutil = Arc::new(SysUtilService::new(
    trail_tracks.clone(),
    vehicle_weight.clone(),
    // ...
));
```

### 5.5 为什么路由要手写？注解扫描呢？

```java
@RestController
@RequestMapping("/base/gantry")
public class OdsSzdnGantryController {
    @GetMapping("/list") public TableDataInfo list(OdsSzdnGantry q) { ... }
}
```

```rust
// router.rs：显式注册；漏挂由 tests/router_test.rs 的 85 条清单兜底
.route("/base/gantry/list", get(crud::gantry_list))
```

### 5.6 PageHelper 的隐式分页呢？

```java
startPage();                          // ThreadLocal 里塞 pageNum/pageSize
List<X> list = service.selectList(q); // MyBatis 自动加 LIMIT
return getDataTable(list);
```

```rust
// 显式：page_params → LIMIT/OFFSET
let p = page_params(&page);
let rows = repo.list(&q, p.page_size, p.offset()).await?;
let total = repo.count(&q).await?;
Ok(json_ok(TableDataInfo::new(serde_json::to_value(rows)?, total)))
```

### 5.7 `@JsonFormat` / `@JsonProperty` 怎么办？

```java
@JsonProperty("bigId")
@JsonFormat(pattern = "yyyy-MM-dd")
private Date receivedtime;
```

```rust
#[serde(rename = "bigId")]
pub big_id: String,

pub receivedtime: Option<Day>, // Day 的 Serialize 固定输出 "yyyy-MM-dd"
```

### 5.8 `String` 和 `&str` 怎么选？

- 函数参数：`&str`（不夺走所有权）；
- 结构体字段 / 返回值：`String`（拥有数据）；
- 字面量常量：`&'static str`（本仓库的列名白名单）。

### 5.9 `Arc<Mutex<T>>` 什么时候用？

只有在**多个 task 需要修改同一份状态**时。本仓库：
- 导出任务表：`Arc<RwLock<HashMap<..>>>`（对应 `ConcurrentHashMap`）；
- 消息元数据：`Arc<DashMap<..>>`（对应 `ConcurrentHashMap`）；
- 其它场景优先用所有权/借用，不引入共享可变状态。

### 5.10 为什么 `async fn` 里的 `MutexGuard` 会编译失败？

`std::sync::MutexGuard` 不是 `Send`，跨 `.await` 持有会让整个 Future 不能 `Send`，`tokio::spawn` 拒绝。
改用 `tokio::sync::Mutex`（本仓库 `mq.rs` 的 consumer）或缩小锁作用域。

### 5.11（附加）Spring 的“运行时魔法”在 Rust 里变成什么？

| Spring 魔法 | Rust 等价物 | 代价 |
|---|---|---|
| 注解扫描注册路由 | 显式 `Router::route` | 多写几行，但启动即确定 |
| `@Autowired` 反射注入 | `main.rs` 组合根 | 多写几行，但依赖错误编译期暴露 |
| AOP 事务/缓存 | 显式 `begin()` / `get_or_load` | 逻辑可见，无自调用失效 |
| `@Scheduled` 扫描 | `scheduler::build` 登记表 | 清单可 enum/测试 |
| `@ControllerAdvice` | `IntoResponse` | 错误路径统一 |

---

## 6. 自检清单

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 所有 API 路径、method 一致 | ✅ | `tests/router_test.rs::java_api_inventory_is_85_endpoints`（85 条）；`src/router.rs` 的 `JAVA_API_INVENTORY` |
| 2 | 请求/响应结构一致 | ✅ | `tests/parity_test.rs`：`AjaxResult` 省略 null data、`TableDataInfo{total,rows,code,msg}`、实体 camelCase 字段 |
| 3 | 状态码/错误码一致 | ✅ | 404/405/400/500 均复刻 Spring `{timestamp,status,error,message,path}`；真实双端对比覆盖必填参数、非法数据源、Java 侧异常端点；`tests/router_test.rs::unknown_path_returns_spring_error` |
| 4 | 数据库查询语义一致 | ✅（静态审查） | `src/repo/mod.rs` 逐表 `<if>` 条件、半开游标区间、`countBetween` 闭区间；缺 XML 的表已标注 |
| 5 | 事务边界一致 | ✅ | Java 全仓 0 个 `@Transactional`；Rust 保持单语句/两语句语义，提供 `Db::begin()` 备用 |
| 6 | 缓存 key / TTL / 失效逻辑一致 | ✅ | `src/services/*` 常量与 `Constants.java` 同字符串；`dev_post/gantry_ip/station_ip/section_road_map/station_info/gantry_list`、`pulsar:msg:processed:*`、`reliability:*`、`detection:*`、`monitoring:*` |
| 7 | 消息格式 / 消费组 / 偏移提交一致 | ✅（静态审查） | `{operationType,data}`、`pulsar:msg:processed:{dataId}`、`group.id=ods-rt-szdn-snapshot-flow-sub`、成功才 commit、DLQ `{topic}.DLQ` |
| 8 | 配置项均有对应、默认值一致 | ✅ | `docs/MIGRATION-BASELINE.md` 第 5 节；`cargo run -- --check-config` 实测输出 |
| 9 | 应用可启动并监听相同端口 | ✅（实测） | Rust 以 9911 启动并连接真实 GaussDB/Redis；Java 9902 同库运行；74 个接口逐 JSON 一致（见第 10 节） |
| 10 | 关键路径至少一个集成测试 | ✅ | `tests/router_test.rs::{healthz_over_http_returns_up, unknown_path_returns_ajax_result}`（真实 HTTP 层）；`router_assembly_does_not_conflict` 挂载全部路由 |

复现命令：

```bash
cargo build
cargo run -- --check-config
cargo test
```

---

## 7. 已知差异 / 风险（务必在灰度前确认）

| # | 差异 | 原因 | 影响 | 处理建议 |
|---|---|---|---|---|
| 1 | **Pulsar / RocketMQ / RabbitMQ 未接真实客户端** | Rust 生态无生产级 Pulsar/RocketMQ 客户端；RabbitMQ Java 侧无消费者 | 消息收发当前走 Kafka 同语义实现 | 业务只依赖 `Bus`；接真 Pulsar 时新增 `PulsarBus` 实现，幂等 key/信封不变 |
| 2 | **Flink `VehicleTrackFlinkJob` 未移植** | 独立流处理作业，不在 Spring Web 进程内 | 若该作业仍在独立部署，不受影响 | 单独立项迁移；不要塞进本服务 |
| 3 | **鉴权未实现** | Java `SecurityInterceptor` + `WebConfig` 整文件块注释 | 与 Java 当前行为一致（无鉴权） | 恢复鉴权时在 `middleware.rs` 增加 tower layer |
| 4 | **Java 侧缺失 SQL 的端点按 Java 实际 HTTP 行为复刻** | 实测 `feerecords/list|listToExport`、`progressive/feerecords|trailfitting`、`vehicleweight/{id}`、`trailtracks/{id}` 返回 Spring 500；`sysutilTest` 部分端点返回 200/500 | Rust 不再返回 501 或“推断结果”，而是返回与 Java 相同的 200/500 错误体 | 若后续补齐 Java XML，再同步恢复 Rust 的真实查询实现 |
| 5 | **日期 JSON 格式** | Java 的 `Date` 在 Spring Boot 下默认 ISO-8601，`@JsonFormat` 则按注解输出 | `Day` → `yyyy-MM-dd`；`JDateTime`（对应 Go 的 `Timestamp`/`DateTime`）→ `yyyy-MM-dd HH:mm:ss`；两者均有测试（`parity_test`） | 若前端严格依赖毫秒时间戳，需为对应字段改用自定义 Serialize |
| 6 | **Redis 序列化不兼容** | Java FastJson/JDK vs Rust JSON | 切换期共用 key 会解析失败 | 上线前 `DEL` 字典/轨迹/消息类 key；或双写过渡 |
| 7 | **PageHelper total vs 本页行数** | 轨迹查询没有 COUNT（避免打穿 8 亿级表） | `/base/sysutil/*`、`/progressive/*` 的 `total` 是本页行数（与 Go 版一致） | 前端分页控件行为需确认 |
| 8 | **`pageSize` 上限 1000** | Go 版为保护大表加入 | 超过 1000 会被截断 | 与 Go 版保持一致；如需完全对齐 Java 可移除 `page_params` 的上限 |
| 9 | **数据权限过滤（`sys_config:data_query`）** | Java 控制器读 Redis `sys_config:data_query`：不等于 `queryall` 且 `platenumber` 为空时设 `flag='JiAnDong'`，Mapper 追加 `orgcode='030000011'`（OGNL 的多字符单引号按字符串比较，是生效的） | 该 key 缺失时 Java 只返回吉安东辖区数据；Rust 现在同样按开关追加过滤 | 切流前确认两端读同一个 Redis key；key 值不同会造成「数据量差异」而非代码差异 |
| 10 | **启动与业务请求已实测** | 使用 yml 中的 GaussDB/Redis | Java/Rust 双端 74 + 93 个场景一致，另有 200+ 组过滤条件逐字段对照 | 见第 10、11 节；Kafka/ES 的真实生产链路仍需独立联调 |
| 11 | **Rust 工具链 1.90** | 2026 年的最新稳定版可能更高；本机已装 1.90 | 部分 2026 crate 可能要求更新 | 升级时改 `rust-toolchain.toml` 与 `Cargo.toml` 的 `rust-version`，再跑 `cargo test` |
| 12 | **ES / Kafka 未做完整数据集成** | 本机 ES 磁盘 97%、触发 flood-stage 只读；Kafka 未启动 | 已按 Java mapping 建索引，但仅验证了空索引路径；消息总线为 Noop | 清理磁盘后执行全量/增量同步，并用 Kafka 联调消费链路 |
| 13 | ~~日期型查询参数白名单~~（已修） | Java `BaseController.initBinder` 用 `DateUtils.parseDate`（12 种模式，全串匹配）绑定 `Date` 字段，解析失败即静默置 null，条件不生效 | 客户端把响应里的 ISO 值（如 `1969-12-31T16:00:00.000+00:00`）原样回填时，Java 忽略该过滤条件 | Rust 用 `JavaQuery` 提取器 + `JavaDateFields` 清单复刻：解析失败的日期参数在进入实体前被丢弃（见 11.2 第 7 条） |
| 14 | **`/api/v1/large/fee|trail` 的降级查询在本环境无结果** | Java 实体 `@TableName` 未写 schema，MyBatis-Plus 生成非限定表名；当前库 `search_path` 不含 `jl_data01`，降级 SQL 报错后 `query()` 吞异常返回空列表 | Rust 同样使用非限定表名并吞异常，两端均返回 `code=200, data=[]` | 若生产库把 `jl_data01` 放进 `search_path`，两端会同时恢复为真实降级结果 |

---

## 8. 架构决策记录（无 1:1 替代时必须显式标注）

| 组件 | Java | 决策 | 状态 |
|---|---|---|---|
| Pulsar | `pulsar-client` + `@PulsarConsumer` | 用 `Bus` 抽象 + Kafka 实现同语义（手动 ack、DLQ、幂等 key 相同） | **需架构确认** |
| RocketMQ | `rocketmq-spring-boot-starter` | 不接线（Rust 客户端生态不成熟） | **需架构确认** |
| RabbitMQ | `spring-boot-starter-amqp` | 不接线（Java 无活跃消费者） | 可用 |
| Flink | `VehicleTrackFlinkJob` | 不移植（独立运行时） | **需架构确认** |
| ES 客户端 | `RestHighLevelClient` | reqwest 直连 6 个 REST 动作 | 可用；版本不绑定 |
| 定时任务 | Quartz 6 段 cron | 自研 6 段解析器（`?`=`*`，支持 `*/n`、`a/b`、列表） | 可用；已有单测 |
| 线程池 | `ThreadPoolTaskExecutor` | tokio task + `Semaphore`（导出 2、大查询 4） | 可用 |
| 鉴权 | Spring Security 未启用 | 保持无鉴权 | 与 Java 一致 |

---

## 9. 关键文件索引

| 文件 | 职责 |
|---|---|
| `src/main.rs` | 组合根、启动/优雅关闭、`--check-config` |
| `src/config.rs` | 全部配置项（与 application.yml 同键路径） |
| `src/state.rs` | `AppState` 依赖容器 |
| `src/router.rs` | 85 条路由 + 健康检查 + 404/405 + Java 端点清单 |
| `src/handlers/` | 24 个 Controller 的等价实现 |
| `src/models/` | 30 个实体/DTO（Java 注解 + 真实 DB 类型驱动生成） |
| `src/repo/mod.rs` | 22 个数据访问仓库 + SQL/游标/对账 |
| `src/services/` | 查询、导出、同步、消费、可靠性、轨迹、字典 |
| `src/scheduler.rs` | 21 个 `@Scheduled` 登记 + 6 段 cron |
| `tests/router_test.rs` | 路由装配 / 85 端点 / HTTP 健康检查 / 404 |
| `tests/parity_test.rs` | 工具函数、响应壳、JSON 字段、分页、校验和 |
| `tools/gen_models.py` | 解析 Java 字段类型/@JsonFormat 与 DB schema，生成 NULL 感知的 Rust 模型（改表/改实体时重跑） |
| `tools/compare_api.py` | Java(9902) ↔ Rust(9911) 74 个场景逐 JSON 对比脚本 |
| `docs/MIGRATION-BASELINE.md` | 阶段一交付物 |
| `docs/JAVA-RUST-MAPPING.md` | 阶段二交付物 |

---

## 10. 真实环境双端实测记录（2026-10-31）

### 10.1 环境与方式

| 项 | 值 |
|---|---|
| Java | `pro-business-api-1.0.jar`，`-Dserver.port=9902`，今日构建 |
| Rust | `target/debug/car-monit-api-rust.exe`，`APP_SERVER_PORT=9911` |
| 数据库 | yml 中的 GaussDB：`192.168.56.10:5432/RuoYi`（schema `jl_data01`） |
| Redis | Java 用 DB0；Rust 用 `APP_REDIS_DATABASE=15` 隔离，避免序列化格式互相污染 |
| 调度/消费者 | Rust 侧 `APP_CONSUMER_ENABLED=false`、`APP_ENABLE_SCHEDULER=false`，避免双端任务互相干扰 |
| 对比脚本 | `tools/compare_api.py`：逐接口请求 Java/Rust，解析 JSON 后深度比较（数值允许 1e-9 相对误差；忽略随机行 key 与错误时间戳） |
| 缓存前置 | Redis DB0 的 `car_list_jc` / `DATE_BorderWeighingCapture:*` 曾被 Python/Go 迁移写成 JSON，Java FastJSON 反序列化后强转会 500。对比前临时清空（`car_list_jc` 原值已备份并恢复） |
| 覆盖 | 74 个场景：19 张表 list/listAll/详情、listToExport、导出状态、large/unified/progressive、sysutil、sysutilTest、必填参数/非法数据源/404 |

复现：

```bash
# 终端 1：Java（已有构建产物）
java -Dserver.port=9902 -jar pro-business-api/target/pro-business-api-1.0.jar
# 终端 2：Rust
cd car-monit-api-rust
APP_SERVER_PORT=9911 APP_REDIS_DATABASE=15 APP_CONSUMER_ENABLED=false \
  APP_ENABLE_SCHEDULER=false APP_KAFKA_BOOTSTRAP_SERVERS= \
  cargo run -- --config config/application.yaml
# 终端 3：对比
python tools/compare_api.py
# SUMMARY ok=74 bad=0
```

### 10.2 实测中发现并修正的差异

1. **可空列解码**：467 个 DB 可空列被当作非空 `String`/`i32`，真实数据一遇到 NULL 就 500。
   改为 NULL 感知标量：`JString / JInt / JLong / JFloat / JBool / Day / JDateTime / JIsoDateTime / JList`，
   JSON 为 null 时与 Jackson 一致。
2. **跨类型兼容**：GaussDB 实际列类型与 Java 实体类型不一致（VARCHAR↔TEXT、INT2↔INT4↔INT8、
   FLOAT8↔INT4、TIMESTAMP↔TIMESTAMPTZ、`TEXT[]`、`tinyint`），SQLx 默认 `Option<T>` 会拒绝。
   为标量类型实现 `compatible()` 与按实际 SQL 类型解码。
3. **时区**：JDBC `serverTimezone=Asia/Shanghai` + Jackson UTC 输出；`Date` 字段需要 -8h，
   而 Java String 字段走 `getString` 返回墙钟时间、不能偏移。两类分别处理。
4. **快照列表 SQL**：按 `OdsRtSzdnSnapshotFlowAddcodeMapper.xml` 只选 17 列并 `ORDER BY snapshottime DESC`。
   当时的 `flag == 'JiAnDong'` 之所以看起来「未生效」，是因为 Redis 里恰好有 `sys_config:data_query=queryall`；
   该开关的完整语义见第 12 节第 1 条。
5. **渐进式查询不分页**：Java phase1 直接 `selectList`（无 PageHelper），pageSize 被忽略；
   Rust 改为无 LIMIT 的 `list_unbounded`。
6. **feeGantry 列表 id**：Java 每行临时生成 UUID，Rust 同步。
7. **Spring 错误体**：404/405/400/500 统一输出 `{timestamp,status,error,message,path}`；
   Java 侧因缺失 Mapper SQL 的 12 个端点，Rust 返回相同的 200/500，而不是 501。
8. **缓存污染**：Redis DB0 中 `car_list_jc` / `DATE_BorderWeighingCapture:*` 被 Python/Go 迁移写入
   JSON（Java 用 FastJSON2/JDK 序列化），会让 `/base/vehicleweight/map`、
   `/base/sysutilTest/syncCurrentTrack|syncHistroyTrack` 在 Java 侧 500。
   对比前临时清空后两端一致（`car_list_jc` 已备份并在测试后恢复）。切换版本前必须清缓存或双写过渡。

### 10.3 结论

- 74 / 74 场景 JSON 一致（状态码 + 响应体）。
- 复现时若 Java 报 500，先确认 Redis 缓存是否被非 Java 服务写过（见 10.2 第 8 条）。
- 未纳入自动对比的是会产生副作用的 POST（导出提交、全量/增量同步）与消息消费链路；
  这些接口的启动参数/校验分支已在代码层对齐，但仍需在独立测试环境验证。
- ES 索引曾按 Java mapping 临时创建（ES8 需额外设置 `index.max_ngram_diff`），用于验证空索引路径；
  测试后已删除，恢复“无业务索引”的原始状态（本机磁盘 97%，会触发 flood-stage 只读）。
  Kafka 未启动，消息总线为 Noop。

---

## 11. 第三轮全量复核：以 Mapper XML 为准重建过滤层（2026-10-31）

第二轮后仍有一类差异没有被覆盖：**列表接口的 WHERE 条件**。前 167 个场景只验证了
“无过滤 / 少量过滤”的响应，而手写仓库过滤函数漏掉了大量 `<if>` 分支，且部分操作符写错。
本轮改成从 XML 机器推导，逐条件对齐。

### 11.1 做法

`tools/gen_filters.py` 解析 19 个 `select*List` 语句的 `<if>` 分支，生成
`src/repo/filters_gen.rs`（571 条条件，`src/repo/mod.rs` 通过 `pub use filters_gen::*` 使用）：

| XML 写法 | 生成的 Rust 条件 |
|---|---|
| `and t.col = #{f}` | `Cond::Eq` / `Cond::EqI64` / `Cond::EqF64`（按实体字段类型选择） |
| `and t.col like concat('%',#{f},'%')` | `Cond::Like` |
| `and t.col >= / <= to_timestamp(#{f},…)` | `Cond::Gte` / `Cond::Lte` |
| `and <foreach> t.col = #{item} </foreach>` / `… in (…)` | `Cond::In` |
| `flag == 'JiAnDong'`、`LIMIT #{startNum}` | 不生成（与实测一致） |

列名严格照抄 XML，不做 snake_case 归一化。这一点很重要：
Java 的部分 XML 引用的是 SELECT 别名（服务区的 `t.agent_pk`、省界称重的 `t.dataSource`），
这些名字在库里并不存在，Java 带该条件时会 500。Rust 用同一列名后得到同样的数据库错误，
行为自然对齐；若把它“修好”，反而会与 Java 不一致。

### 11.2 本轮修正的差异

1. **过滤条件缺失**：`fwqjcxx / sfsjcxx / sfzjcxx / fwqclls / feeGantry / feeStationEnter /
   feeStationExit / snapshotflow / provcapture / stationcapture / gantry / gantryIp /
   vehicleweight / section / toll / tollStationIp / org / location_dict / trailtracks`
   共 571 条 `<if>` 全部落地。典型例子：`gantryIp?ip=…`（Java 1 行 / 旧 Rust 1033 行）、
   `section?startPileNo=…`（Java 0 / 旧 Rust 85）、`toll?idCard=…`、`org?orgIsVirtual=…`、
   `stationcapture?deviceip=…`、`feeStationEnter?bigId=…`，现已两端一致。
2. **`LIKE` 大小写**：MyBatis 的 `like` 是大小写敏感的，Rust 之前用 `ILIKE`。
   改为 `LIKE`（`Cond::Like` 与 large 降级查询同步修正）。
3. **`sfsjcxx?agentPk=…`**：XML 写成 `and t.agent_pk = #{id}`，`id` 不是实体属性，
   MyBatis 运行期抛 BindingException → 500。生成器识别“测试字段与绑定名不一致”，
   产出 `Cond::Eq("__mybatis_missing_property_id__", …)` 复现同一 500。
4. **`/api/v1/large/fee|trail`**：Java 的 `UnifiedQueryService.query()` 捕获所有异常，
   ES 失败→降级 MySQL→仍失败则返回**空列表**（HTTP 仍是 200 + `code=200`）。
   Rust 之前把降级错误抛出，变成 `code=500`。现按 Java 吞异常；同时表名改为与
   `@TableName` 一致的非限定名（见第 7 节第 14 条）。
5. **`PageHelper` 的 `pageSize<=0`**：`PageParams.empty` + `list_impl` / `export_impl` /
   `sysutil` / `base` 各入口：`rows=[]` 但 `total` 仍是真实匹配数。
6. **非法数字主键**：`/manager/fwqclls/abc`、`/base/gantryIp/abc`、`/base/tollStationIp/abc`
   走 `entity_repo_numeric!` → Spring `@PathVariable Long` 的 400，而不是数据库 500。
7. **日期型查询参数按 Java 白名单绑定**：Java 的 `BaseController.initBinder` 对所有
   `java.util.Date` 属性用 `DateUtils.parseDate`（12 种模式、要求整串匹配）解析，失败返回 null，
   于是 `<if test="x != null">` 条件根本不拼进 SQL（HTTP 仍 200、返回全量）。
   Rust 新增 `JavaDateFields`（`tools/gen_date_fields.py` 从实体扫描生成）与 `JavaQuery` 提取器，
   在进入实体反序列化之前丢弃白名单之外的日期参数；`utils::parse_time` 同时补齐白名单里的
   `yyyy-MM`、`yyyy/MM/dd HH:mm`、`yyyy.MM.dd` 等形式，保证「被保留的参数一定能解析」，
   否则会从 Java 的 200 变成 Rust 的 400。
   典型用例：`provcapture?tailcapturetime=1969-12-31T16:00:00.000+00:00`（Java 忽略 → 356 行）、
   `=1969-12-31 16:00:00`（Java 生效 → 0 行），两端现在都一致。
8. **时间范围条件必须走 `to_timestamp`**：XML 写的是
   `and t.entime >= to_timestamp(#{inApplyTime1},'yyyy-mm-dd HH24:MI:SS')`。
   之前 Rust 直接绑定文本，`inApplyTime1=2025-09` 这类「Java/SimpleDateFormat 能解析、
   数据库隐式转换不能」的值会让 SQLx 报类型错误 → 500（Java 是 200/0）。
   `Cond::Gte/Lte` 改为渲染 `to_timestamp($n,'yyyy-mm-dd HH24:MI:SS')`，与 XML 字面一致。

### 11.3 复核矩阵与结果

对比前先把 Redis DB0 的 `car_list_jc` 备份到 `.run/car_list_jc.current.bak`、清空、跑完再恢复
（该 key 现由非 Java 服务写成 JSON，Java FastJSON 反序列化后强转 `CarVO` 会 500）。

| 检查 | 命令 | 结果 |
|---|---|---|
| 第 1 轮（4 段式基线） | `python tools/compare_api.py` | `ok=74 bad=0` |
| 第 2 轮（分页/过滤/非法 ID/POST/405） | `python tools/compare_round2.py` | `ok=93 bad=0` |
| 第 3 轮（18 张表 × 每表 ≤12 个真实值过滤，含 ISO 时间值） | `python tools/compare_round3.py` | `checked=186 bad=0` |
| 日期/时间范围边界（白名单内、白名单外、非法串） | 临时脚本 | `bad=0`（修 `to_timestamp` 前 1 处 500） |
| 详情端点 | `/base/{fwqjcxx,sfsjcxx,sfzjcxx}/{id}` | 状态码与响应体一致 |
| 轨迹查询 | `/base/sysutil/carTrackQueryByCarNo?carNo=…` | 一致（`total=0`）；`carTrackQueryByTime` 依赖 `car_list_jc`，需清缓存后两端一致 |
| 单元/集成测试 | `cargo test` | 19 passed, 0 failed |

未做双端实测的：`POST /api/v1/large/sync/{full,incremental}`（会向 ES 回灌数据，本机 ES 磁盘 97%）
与消息消费链路；`sync/full`、`sync/repair` 的响应结构已与 Java 控制器逐字段核对（后台线程 + 固定文案）。

### 11.4 复现

```bash
# Rust 侧过滤条件重生成（改 XML 后必须执行）
cd car-monit-api-rust
python tools/gen_filters.py         # -> src/repo/filters_gen.rs
cargo build && cargo test

# 三轮对比（需 Java 在 9902、Rust 在 9911，并临时清空 car_list_jc）
python tools/compare_api.py         # ok=74 bad=0
python tools/compare_round2.py      # ok=93 bad=0
python tools/compare_round3.py      # checked=186 bad=0
```

`tools/compare_round3.py` 的做法：先用 Java 无过滤列表取一行样本，再把该行每个非空标量字段
作为查询参数分别打 Java/Rust，比较状态码与 `total`。ISO 时间串不再跳过——
`JavaQuery` 已按 Java 的白名单把它丢弃（见 11.2 第 7 条）。

---

## 12. 第四轮：全量双端接口校验（2026-11-02）

框架：`tools/verify_full.py`（7 个阶段，548 项用例）；逐条结果写入
`docs/VERIFICATION-FULL-20261102.md`，原始数据在 `.run/verify/*.json`。
判定口径升级为「状态码 + 响应体深度比较 + 键顺序 + 原始字节」，
Java 每行随机生成的 `id`/`taskId` 只比存在性与类型。

本轮新发现并修复的差异（都是双端实测才暴露、静态读代码看不到的）：

1. **数据权限过滤没落地**。`OdsRtSzdnSnapshotFlowAddcodeController.list/listToExport` 读 Redis
   `sys_config:data_query`；只要它不是 `queryall` 且 `platenumber` 为空，就设 `flag='JiAnDong'`，
   Mapper 追加 `orgcode = '030000011'`（OGNL 的多字符单引号按字符串比较，是生效的）。
   上一轮误判为「OGNL 未生效」→ Rust 忽略 flag → 无车牌过滤时 Rust 300 行、Java 0 行。
   现在 `tools/gen_filters.py` 会把 `<if test="flag != null and flag == 'X'"> and t.col = 'Y'`
   这类字面量条件也生成出来（共 572 条 `<if>`）。
2. **`@PathVariable Long` 的类型转换契约**。`provcapture / stationcapture / feeStationEnter`
   详情主键在 Java 是 `Long`，非数字 ID（含 `listAll`、`abc`、`__no_such_id__`）走
   `MethodArgumentTypeMismatchException` → Spring 400；Rust 之前按字符串查库 → 500。
   这三张表改用 `entity_repo_numeric!`。
3. **绑定失败要输出 Spring 的 400 JSON**。数值字段传非数字（`axlecount=abc`）时 Java 返回
   `{timestamp,status,error,message,path}`，Axum 默认返回纯文本
   `Failed to deserialize query string: …`。新增 `SpringQueryRejection`。
4. **`zdata_trail_tracks.uuid` 不唯一**。Java `selectOne()` 命中多行抛 `TooManyResultsException`
   （实测同一 uuid 17 行）→ 500；0 行 → `{"msg":"操作成功","code":200}`；恰好 1 行才返回数据。
   Rust 之前对所有 id 一律 500，现在按行数三分支。
5. **`AjaxResult` 的键顺序**。Java 是 `HashMap`，实测稳定输出 `msg → code → data`；
   Rust 之前是 `code,msg,data`。`response::envelope()` 改为同序并有测试锁定。
   （`TableDataInfo` 与 large 系列用 POJO/`LinkedHashMap`，顺序本来就一致。）
6. **PageHelper 的 `reasonable` 越界钳位**。`pageNum` 超过总页数时 Java 返回**最后一页**
   （`gantry` total=1526、`pageSize=3`、`pageNum=9999` → 末尾 2 行），不是空列表。
   新增 `PageParams::offset_for(total)`，各 list/listToExport 先 `count` 再取数
   （PageHelper 本来就是先 count 后取数）。
7. **容器级请求行长度上限**。Tomcat `maxHttpHeaderSize=8192` 把请求行也算进去，
   实测 `path?query` 上限 8075 字节（8075→200，8076→400）。`middleware.rs` 加同长度闸门；
   Java 此时是容器 HTML 错误页，Rust 继续返回应用的 Spring JSON —— 状态码一致，body 属容器差异。
8. **降级查询的日期字段变 null**。`/api/v1/large/snapshot`、`/api/v1/unified/snapshot/list`
   原先 `SELECT *` → `row_to_json` → `from_value::<实体>`，而 `row_to_json` 对
   `timestamp without time zone` 按 `DateTime<Utc>` 取列会解码失败并静默变 null，
   导致 `snapshottime/receivedtime/loadtime` 与 Java 不一致。
   改为 `query_as::<_, 实体>`（等价于 Java 用 Mapper 取实体），与 `/base/.../list` 同源编码。
9. **`type` 参数不该校验**。Java 的 `resolve(type)`/`resolveDs(type)` 对未知值一律 `default → SNAPSHOT`；
   Rust 之前回「type 只能是 snapshot / fee / trail」。`parse_type_lenient` 改为默认 Snapshot。
10. **`carNo` 必填语义**。Java 的 `@RequestParam String carNo` 只有**缺失**才 400，
    传空串正常执行（只是不放模糊条件）；Rust 之前空串也 400。改为按存在性判断。
11. **重复查询参数的绑定规则**。Spring 对同名参数会把多个值用逗号拼成一个再绑定
    （实测 `platenumber=%&platenumber=%` 在 Java 变成 `%,%` → LIKE 不命中 → 0 行；
    `pageNum=1&pageNum=2` 会让数值字段变成 `1,2`），
    而 `serde_urlencoded` 把重复字段直接判成 400。`JavaQuery` 改为按 Java 的逗号拼接语义合并。

环境变化也值得一提：本轮期间 Java 的定时同步任务把 ES 索引 `snapshot_flow`（300 docs）建好，
所以 large/unified 的路由与 10-31 那轮不同（`fee_records`、`trail_fitting` 仍不存在 →
两端都走降级 → 结果仍一致）。

最终结果：`inventory 2/2`、`base 140/140`、`filters 343`（一致 342 + 容器级 1）、
`query 34/34`、`sysutil 10`（一致 7 + 跳过 3）、`contract 19/19` —— 合计 548 项，0 项应用层不一致。
同时 `compare_api.py ok=74 bad=0`、`compare_round2.py ok=93 bad=0`、`compare_round3.py checked=186 bad=0`，
`cargo test` 20 passed（新增时间格式解析、AjaxResult 键序、`JavaQuery` 丢弃日期参数三组用例）。

跳过项与残留风险记录在 `docs/VERIFICATION-FULL-20261102.md` 第 6 节。
