# 阶段二：Java ↔ Rust 全量映射表

> 每一行：**Java 用法 → Rust 对应写法 → 关键差异 → Java 开发者最容易踩的坑**。
> 代码示例均来自本仓库的真实迁移（文件路径可直接跳转）。

## 1. 语言与类型系统

| Java | Rust（本仓库） | 关键差异 | 最容易踩的坑 |
|---|---|---|---|
| `String` / `CharSequence` | `String` / `&str` | `&str` 是借用视图，`String` 拥有数据 | 函数参数优先 `&str`，返回/存储用 `String`；`fn f(s: String)` 会移动所有权 |
| `Integer` / `int` | `Option<i32>` / `i32` | `null` 必须显式建模 | 实体可空列统一 `Option<T>`（如 `direction: Option<i32>`）；不要用 `0` 冒充 null |
| `Long` / `long` | `Option<i64>` / `i64` | 同左 | MyBatis `Long id` → `Option<i64>`；路径参数 `Long` 用 `parse_numeric_id` 转 400 |
| `BigDecimal` | `f64` / `bigdecimal::BigDecimal` | 精度语义不同 | 经纬度用 `f64`；金额若需精确计算应使用 `BigDecimal`（本仓库仅展示/查询，不做金额运算） |
| `boolean` / `Boolean` | `bool` / `Option<bool>` | 同左 | 请求参数缺失时 `Option<bool>` 才是 null；`bool` 默认 false |
| `List<T>` / `ArrayList` | `Vec<T>` | 无类型擦除 | 泛型单态化：`Vec<OdsSzdnGantry>` 不是 `Vec<Object>`，不能强转 |
| `Map<K,V>` / `HashMap` | `HashMap<K,V>` / `serde_json::Map` | 顺序语义不同 | 需要字段顺序时用 `serde_json` 的 `preserve_order`（已开启） |
| `Set<T>` / `HashSet` | `HashSet<T>` | 同左 | 不要依赖迭代顺序 |
| `class` + 继承 | `struct` + `impl` + 组合 | 无继承 | `BaseController` → `handlers::common` 的自由函数；`BaseEntity` → 字段直接展开 |
| `interface` | `trait` | 静态分派优先 | `ReadRepo<T>` 只在需要泛型 handler 时使用，不为了“像 Java”而给每个 Service 抽 trait |
| `abstract class` | `trait` + 默认方法 / `enum` | 无抽象类 | 数据源三态用 `enum DataSource`；状态机用 `enum MessageStatus` |
| 泛型擦除 | 单态化 | 运行时无 `Class<T>` | 不能 `data as T`；需要动态 JSON 时用 `serde_json::Value` |
| `Exception` / `try-catch` | `Result<T, E>` / `?` | 错误是返回值 | handler 返回 `AppResult<Response>`；`?` 自动传播，`IntoResponse` 统一出 `{code,msg}` |
| `null` | `Option<T>` | 无隐式 null | JSON 里 `null` ↔ `None`；`AjaxResult.success(null)` 要省略 `data` 键（`response.rs`） |
| 默认可变 | 默认不可变（`let mut`） | 可变性显式 | 只读变量不要加 `mut`（编译器会警告） |
| 所有权/借用 | `&T` / `&mut T` / 生命周期 | 赋值 = 移动 | E0382（use after move）：`let b = a;` 后 `a` 不能再用于拥有型类型；E0499（两个 `&mut`）、E0502（`&` 与 `&mut` 冲突）、E0597（借用活不过所有者） |

```rust
// Java: List<OdsSzdnGantry> list = ...; for (OdsSzdnGantry g : list) { ... }
// Rust: 只读遍历用 &，需要修改用 &mut（对应本仓库 Repo::list 的返回值）
let rows: Vec<OdsSzdnGantry> = repo.list_all().await?;
for g in &rows {
    println!("{}", g.gantry_name);
}
```

## 2. 并发与异步

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `Thread` / `ExecutorService` | `tokio::spawn` | task 比线程轻 | spawn 的 Future 必须 `Send + 'static`；闭包捕获的引用要 `to_string()` 克隆 |
| `CompletableFuture` 回调链 | `async fn` + `.await` | 显式挂起点 | `.await` 点之间不要持有 `std::sync::MutexGuard`（不是 Send） |
| `synchronized` / `ConcurrentHashMap` | `Arc<Mutex<T>>` / `Arc<RwLock<T>>` / `DashMap` | 所有权保证无数据竞争 | 本仓库 `pending: Arc<DashMap<...>>` 对应 `ConcurrentHashMap` |
| 虚拟线程（Loom） | tokio task | 调度模型不同 | 不要在 async 里做阻塞 IO；CSV 写盘是短小同步操作，见 `export.rs` 注释 |
| `Thread.sleep` | `tokio::time::sleep` | 异步睡眠 | 不要用 `std::thread::sleep` 阻塞 runtime |
| `@Async` | `tokio::spawn` | 无代理 | 后台任务必须自己处理错误与 panic（`CatchPanicLayer` 只覆盖 HTTP） |

```rust
// Java: new Thread(() -> syncService.fullSyncOneYear()).start();
let svc = state.sync.clone();
tokio::spawn(async move {
    if let Err(e) = svc.full_sync_one_year().await {
        tracing::error!(err = %e, "[同步-全量] 异常");
    }
});
```

## 3. Web 框架（Spring MVC → Axum）

| Spring | Axum（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `@RestController` | `Router::route` + handler | 显式注册 | 漏注册不会编译失败 → `router_test` 固化 85 条 |
| `@GetMapping("/x")` | `get(handler)` | 同左 | Axum 0.8 路径参数语法是 `{id}`，不是 `:id` |
| `@PathVariable` | `Path<T>` | 提取器顺序：`State`/`Path`/`Query` 在 `Json` 之前 | 多个 `Query<T>` 可共存（各自解析 URI） |
| `@RequestParam` | `Query<T>` / `Query<HashMap<..>>` | 无隐式默认值 | `PageQuery` 手动给默认值；字段名靠 `#[serde(rename)]` 对齐 camelCase |
| `@RequestBody` | `Json<T>` / `Option<Json<T>>` | 必须显式声明可选体 | `Option<Json<T>>` 用于 `@RequestBody(required=false)` |
| `@ControllerAdvice` | `AppError: IntoResponse` + `fallback` | 无全局异常处理器 | 404/405 也要返回 `AjaxResult`，否则前端 `JSON.parse` 失败 |
| `SecurityInterceptor` | 不实现（Java 整文件注释） | — | 若恢复鉴权，加 tower layer，不要在 handler 里散落判断 |
| 内嵌 Tomcat | tokio + hyper | — | 端口/上下文路径见 `config.rs` |

## 4. ORM / 数据访问

| MyBatis / JPA | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `BaseMapper<T>.selectList(q)` | `Repo<T>::list(Cond, limit, offset)` | 动态 SQL 改为 `Cond` 枚举 | 列名必须是 `&'static str` 白名单（防注入） |
| `@TableName` | `Model::TABLE` / `Repo` 构造参数 | 同左 | 服务区 Mapper 的表名/列名与类名不一致（见 baseline 3.2） |
| `@TableId` | `Model::PK` | 同左 | `gantry_ip`/`toll_station_ip` 主键是 bigint，需 `get_by_id_i64` |
| `#{}` 占位符 | `$1..$n`（sqlx） | 驱动差异 | 手写游标 SQL 用 `pg_placeholders` 把 `?` 转 `$n` |
| `@Transactional` | `Db::begin()` | 无 AOP | 现有链路无事务注解；不要为了“看起来安全”擅自扩大事务边界 |
| PageHelper | `PageParams` → `LIMIT/OFFSET` | 无 ThreadLocal | 忘记传 limit 会全表扫描；本仓库所有列表入口统一走 `page_params` |
| `PageInfo(list).getTotal()` | `Repo::count(q)` | 需显式 COUNT | 轨迹查询为了不打穿大表，保留“本页行数”口径（与 Go 版一致） |
| MyBatis `<foreach>` | `Cond::In` | 同左 | 空集合不要生成 `IN ()`（`QueryBuilder` 只在非空时拼接） |

## 5. 中间件

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| Spring Data Redis / Lettuce | `redis` crate + `ConnectionManager` | 连接池由 manager 管理 | `lrange/lrem/ltrim` 的索引类型是 `isize` |
| `RedisTemplate` FastJson 序列化 | JSON 字符串 | 序列化格式不同 | 与 Java 共用 Redis 时必须先清 key（见 README） |
| `spring-kafka` | `rdkafka`（librdkafka） | 无容器托管 | 消费者循环、手动提交、退避、DLQ 全部显式（`mq.rs`） |
| `@KafkaListener` | `Bus::consume` | 同左 | 处理成功才提交 offset；失败重投，超限进 `{topic}.DLQ` |
| `pulsar-client` | `Bus` + Kafka 实现 | 无官方 Rust 客户端 | 幂等 key/消息信封保持与 Java 相同，便于灰度互认 |
| `spring-amqp` | 未接线 | — | Java 侧也没有活跃消费者 |
| HikariCP | `sqlx::PgPool` | 连接池参数手动映射 | `max-open-conns=20` 等参数在 `config.rs` |

## 6. 配置

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `application.yml` | `config/application.yaml` | 键路径原样保留 | YAML 里 `password:`（null）反序列化到 `String` 会失败 → 必须写 `""` |
| `@Value("${x}")` | `Config` 结构体字段 | 一次性反序列化 | 少写一层嵌套不会报错，只会得到零值 → `validate()` 显式校验 |
| `@ConfigurationProperties` | `#[derive(Deserialize)]` | 同左 | 新增配置项要同时改默认值、YAML、`.env.example` |
| `spring.profiles.active` | `CAR_MONIT_CONFIG` / `--config` | 无 profile 机制 | 多环境用不同 YAML 文件，不要复制多份代码 |
| 环境变量 | `APP_*`（config crate） | 前缀映射 | 带连字符的键（如 `server.context-path`）建议直接改 YAML，避免环境变量歧义 |
| JSR-303 `@Validated` | `Config::validate()` | 显式调用 | 校验必须在加载末尾执行，否则错误推迟到第一次查询 |

## 7. 日志与可观测性

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| SLF4J + Logback | `tracing` + `tracing-subscriber` | 结构化日志 | `RUST_LOG=info` 或 `logging.level` 控制级别 |
| `Logger` | `tracing::info!/warn!/error!` | 宏形式 | 字段用 `key = %value`，不要字符串拼接 |
| MDC | `tracing::span!`（`middleware.rs` 的 request_id span） | 无 ThreadLocal | 每个请求的 `request_id` 写入日志与 `X-Request-Id` 响应头 |
| logback-spring.xml | text/json 双格式 | — | `logging.format: json` 切换 |

## 8. 序列化

| Jackson / Fastjson | serde（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `@JsonProperty` | `#[serde(rename = "...")]` | 编译期生成 | 字段名与 Java 不一致时必须写 rename（模型已全量生成） |
| `@JsonIgnore` | `#[serde(skip)]` | 同左 | 数据库瞬态字段用 `#[sqlx(skip)]`，JSON 仍输出（Jackson 默认包含） |
| `@JsonFormat(pattern="yyyy-MM-dd")` | `Day` 类型（`models/mod.rs`） | 自定义 Serialize | 不要把 `DateTime` 直接暴露成 RFC3339 给需要 `yyyy-MM-dd` 的前端 |
| `@JsonInclude(NON_EMPTY)` | `#[serde(skip_serializing_if = "...")]` | 同左 | `AjaxResult.success(null)` 必须省略 `data` 键 |
| Jackson 多态 | `enum` + 手写 match | 无运行时类型信息 | 数据源三态用 `DataSource`，不要用字符串散落判断 |

## 9. 依赖注入

| Spring | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| `@Service` / `@Component` | `main.rs` 显式 `new` | 无容器 | 依赖缺失 = 编译失败，而不是启动后 NPE |
| `@Autowired` 字段注入 | 构造函数参数 / `AppState` 字段 | 无反射 | 看 `state.rs` 就知道有哪些依赖 |
| `@Bean` | `main.rs` 中的构造表达式 | 同左 | 单例通过 `Arc` 共享；无 prototype 概念 |
| 循环依赖 | 编译期不允许 | — | 用 `DictService` 收敛字典依赖，避免 Service 互相注入 |
| `@PostConstruct` | `main.rs` 中显式调用 `init()` / `start()` | 无生命周期回调 | 见 `loss.init()`、`delay.init()`、`consumer.start()` |

## 10. 测试

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| JUnit 5 | `#[test]` / `#[tokio::test]` | 内置 | `cargo test` |
| AssertJ | `assert_eq!` / `pretty_assertions` | 同左 | — |
| Mockito | trait hand-written fake / `mockall` | 无运行时代理 | 本仓库用 `Bus::Noop`、`Option<Cache>` 表达“未启用” |
| `@SpringBootTest` | `Router` 装配测试 + `Db::lazy` | 无需起容器 | `tests/router_test.rs` 不连接数据库 |
| 集成测试 | `#[tokio::test]` + 真实 DB | 同左 | 当前需要 GaussDB/Redis，CI 中标记为手动执行 |

## 11. 构建与部署

| Java | Rust（本仓库） | 关键差异 | 坑 |
|---|---|---|---|
| Maven / Gradle | Cargo | 唯一主流构建 | `Cargo.lock` 入库锁定版本 |
| fat jar | 单二进制 | 无 JVM | `cargo build --release` 产物在 `target/release/` |
| `java -jar` | `./car-monit-api-rust` | 同左 | `--config` / `--check-config` |
| `-Xmx` / JVM 调优 | 无 GC | 所有权 + 析构 | 不需要 GC 参数；关注 `tokio` worker 数与连接池 |
| Actuator | `/healthz`、`/readyz` | 新增 | Java 未接 Actuator；探针只读、无副作用 |
| JFR / jstack | `tracing` / `tokio-console`（可扩展） | 工具链不同 | 本仓库提供结构化日志与 request_id |
