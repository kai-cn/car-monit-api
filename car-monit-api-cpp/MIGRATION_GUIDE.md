# Java → C++ 迁移指南

> 源工程：`pro-business-api`（RuoYi / Spring Boot 2.4.5 / MyBatis / Druid / Redis / Kafka / Pulsar / ES）+ `pro-base-common`
> 目标工程：`car-monit-api-cpp`（C++20 / CMake / cpp-httplib / nlohmann-json / 自实现 PG & Redis 协议）
> 验收口径：类/接口/枚举、方法语义、业务分支、常量、错误码、日志、配置项、SQL、HTTP 契约、序列化、定时任务、缓存与并发行为逐项对齐；无法对齐者给出替代方案并单列差异。

## 0. 结论概览

| 维度 | Java | C++ | 状态 |
|---|---|---|---|
| Controller / 端点 | 24 个 / 85 个 | 4 组注册函数 / 85 个（+`/health`） | ✅ |
| Service | 22 个 ServiceImpl + optimization 12 个 | `service/{dict,track,ops,optimization}.cpp` | ✅ |
| Mapper / SQL | 22 个 Mapper XML | `db/dao.cpp` + `meta/entities_generated.h`（19 实体） | ✅ |
| 定时任务 | 10 个生效（CarTask 全部注释） | 10 个 | ✅ |
| 中间件 | Druid/Redis/Kafka/Pulsar/ES | 自实现 PG/Redis + httplib ES + librdkafka | ✅ Kafka 已接真实客户端 |

---

## 1. 技术栈扫描与映射矩阵

| Java 组件 | 实际用法 | C++ 选型 | 取舍依据 | 差异 |
|---|---|---|---|---|
| Spring Boot 2.4.5 | IoC、MVC、自动配置 | 手写启动 `src/main.cpp` + 显式单例 | 无反射，显式优于隐式 | ❌ 无自动装配 |
| `@RestController` / `@RequestMapping` | 185 条映射注解 | `http::Router::add(method, pattern, handler)` | 路由表可读、可测 | ✅ 路径/方法一致 |
| `@RequestParam` / `@PathVariable` / `@RequestBody` | 参数绑定 | `http::Request`（同名 query/form、path_params、`json()`） | 复刻 Spring 绑定规则 | ⚠️ 未知字段不报错 |
| Jackson | JSON + `@JsonFormat` | nlohmann/json 3.11.3 | 与 Java 键序/省略语义最接近 | ⚠️ `BigDecimal` 尾零 |
| MyBatis + XML | 22 个 Mapper | `meta::EntityMeta` 元数据 + `dao` 拼装 | 无运行期反射/XML 解析 | ✅ SQL 与 resultMap 等价 |
| PageHelper | `startPage()` + `reasonable` | `dao::resolve_page` | 保留越界回夹末页 | ✅ |
| Druid + pgjdbc | 连接池 + JDBC | `db::PgPool` + `db::PgConn`（libpqxx 7.10 + libpq 17） | 认证/TLS/协议交给 libpq；参数绑定 `$1..$n` | ⚠️ stock libpq 不支持 openGauss sha256（需服务端 md5 或 openGauss 定制 libpq）；不支持游标/COPY（本工程未使用） |
| Spring Data Redis (Lettuce) | `RedisTemplate` | `cache::Redis`（hiredis 1.5） | 单连接 + 互斥；TLS 可选 | ⚠️ 无连接池/pipeline；值统一 JSON |
| Spring `@Scheduled` / Quartz cron | 10 个任务 | `scheduler::Scheduler`（6 段 cron） | 等价触发语义 | ✅ |
| Kafka (`KafkaTemplate`) | 发送快照流 | `src/mq/kafka_producer.*`（librdkafka 2.6.1） | FetchContent 静态编译 | ✅ key/value/头/重试对齐 |
| Pulsar | 消费者类 `@Service` 被注释 | 不实现 | 与 Java 运行时一致 | ✅ 不适用 |
| RestHighLevelClient | 查询/滚动/bulk | httplib + REST DSL | 无 Java 客户端 | ✅ 降级语义保留 |
| Logback | 控制台 + 文件 | `common/logging.h`（异步无关，按级别过滤） | 格式复刻 | ⚠️ 线程名为线程 ID |
| JUnit | 单测 | `tests/test_main.cpp` + CTest | 等价 | ✅ |

---

## 2. 逐层对照

### 2.1 应用入口与配置

**Java**

```java
@SpringBootApplication
public class EcBusinessApiApplication {
    public static void main(String[] args) { SpringApplication.run(EcBusinessApiApplication.class, args); }
}
```

**C++**（[main.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/main.cpp)）

```cpp
auto& cfg = cm::config::Config::instance();
cfg.load(config_path);          // configs/config.yaml（application.yml 的等价物）
cfg.apply_env_overrides();      // CM_* 环境变量优先
cm::db::PgPool::instance().init(...);   // Druid 等价；失败不阻断启动
cm::cache::Redis::instance().connect(...);
auto router = cm::router::build_routes();
cm::router::start_schedulers();
return cm::http::run_server(cfg.server_port(), router, 16);
```

- 配置文件名/层级与 `application.yml` 一致（`spring.datasource.dynamic.datasource.master.*` 等），`application-optimization.yml` 的键并入同一文件。
- `@Value` → `Config` 的强类型 getter；`@ConfigurationProperties` 的松散绑定 → 显式键路径。

### 2.2 HTTP 层

**Java**

```java
@RestController
@RequestMapping("/base/fwqjcxx")
public class DwdLcztFwqjcxxController extends BaseController {
    @GetMapping("/list")
    public TableDataInfo list(DwdLcztFwqjcxx entity) { startPage(); return getDataTable(service.selectList(entity)); }
    @GetMapping("/{agentPk}")
    public AjaxResult getInfo(@PathVariable Long agentPk) { return AjaxResult.success(service.selectById(agentPk)); }
}
```

**C++**（[base_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp)）——19 个实体共用一个 `Spec` 注册器，每个 `Spec` 对应一个 Controller：

```cpp
Spec s;
s.meta = &meta::dwdLcztFwqjcxx;
s.base = "/base/fwqjcxx";
s.id_param = "agentPk";
s.numeric = true;   // @PathVariable Long
s.flat = true;      // getInfo 直接返回实体
register_spec(router, s);   // 自动注册 /list、/{agentPk}（按需 /listToExport、/listAll）
```

路由总数由 `Router` 统计并在启动日志打印：`http - HTTP 服务启动于 0.0.0.0:9901，路由数 86`。

### 2.3 序列化层

**Java**：`AjaxResult` 是 `HashMap`，`put("msg")...put("code")...put("data")`，`data==null` 时不 put。

**C++**（[result.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/result.h)）：`ajax_result()` 用 `nlohmann::ordered_json` 复刻键序与省略规则；`table_data()` 输出 `{total,rows,code,msg}`。
元数据 `FType{Str,Int,JavaLong,Double,Decimal,Timestamp,DateTime,Day,Json}` → `dao::convert_value` 完成类型与日期格式化。

### 2.4 数据访问层

**Java**：`Mapper XML` 的 `select_sql`/`where`/`order by` + `PageHelper`。

**C++**：`EntityMeta{fields(JSON名/物理列/类型/pk), filters, select_sql, order_sql}`；`repo::select_list(meta, req, extra_where, columns_override)` 产出 `{rows,total}`，再由 handler 包装成 `TableDataInfo`。

分区 SQL 差异：Java 的 `t.agent_pk` 在视图/表上不存在（实际列是 `id`），C++ 用 `physical_pk_column()` 取 `filters` 里的真实列（与 Go/Python 修正一致）。

### 2.5 横切关注点

| 关注点 | Java 机制 | C++ 实现 | 陷阱 |
|---|---|---|---|
| 日志 | SLF4J + logback，MDC | `CM_LOG_INFO("logger") << ...`，级别/文件可配 | 无线程名，只有线程 ID |
| 异常 | 业务异常 → HTTP 200 `code:500`；绑定异常 → 400 | `BizError`/`BindError` + `http/server.cpp` 统一转换 | 勿在析构里抛异常 |
| 鉴权 | `SecurityInterceptor`/`WebConfig` **整体被注释** | 不实现 | ✅ 与 Java 一致（无鉴权） |
| 限流/熔断 | 无 | 无 | — |
| 指标 | 无 Micrometer | 日志统计（延迟/丢失率） | — |
| 配置刷新 | 无 `@RefreshScope` | 重启生效 | ⚠️ |

### 2.6 定时任务

`@Scheduled(cron = "0 0/3 * * * ?")` → `scheduler.add_cron("0 0/3 * * * ?", fn)`；`fixedRate` → `add_fixed(ms, fn)`。
每任务 `std::atomic<bool> running` 防重入（等价 Spring 单线程调度器），200ms 轮询、`+08:00` 墙钟。

### 2.7 MQ / ES

- Kafka 发送：`mq::deliver()` → librdkafka（key=dataId、value=JSON、`__TypeId__`、异步回调 + 重试/死信）；`kafka.fallback-redis=true` 时退回 `RPUSH mq:pending:<topic>`（默认关闭）。
- CORS：`src/http/cors.cpp` 按 Spring `CorsConfiguration`/`DefaultCorsProcessor` 实现，预检前置、`Vary`、ACAO/ACAM/ACAH/ACEH/ACAC/ACMA。
- ES：`httplib::Client` 直连 `_search`/`_search/scroll`/`_bulk`；失败 30s 冷却后降级 GaussDB（⚠️）。

---

## 3. 逐模块对照表

| 模块 | Java 源 | C++ 源 | 状态 |
|---|---|---|---|
| 入口/启动 | `EcBusinessApiApplication` | `src/main.cpp` | 已迁移 |
| 配置 | `application.yml`、`application-optimization.yml`、`@Value` | `src/config/{config.h,config.cpp}`、`configs/config.yaml` | 已迁移 |
| 工具类 | `StringUtils`/`DateUtils`/`Convert`/`PageUtils`/`SqlUtil`/`RedisUtil` | `src/common/{utils,datetime,json,result,error,logging,crypto}` | 已迁移 |
| DB 客户端/池 | Druid + pgjdbc | `src/db/pg.{h,cpp}` | 已迁移（受限：无 SSL/游标） |
| DAO/分页 | MyBatis XML + PageHelper | `src/db/dao.{h,cpp}` + `src/meta/entities_generated.h` | 已迁移 |
| Redis | Lettuce + RedisTemplate | `src/cache/redis.{h,cpp}` | 已迁移 |
| 字典缓存 | `SysDictData`/`RedisUtil` | `src/service/dict.{h,cpp}` | 已迁移 |
| 基础 CRUD | 19 个 Controller | `src/handler/base_handlers.cpp` | 已迁移（48 端点） |
| SysUtil | `SysUtilController` + `SysUtilServiceImpl` | `src/handler/sysutil_handlers.cpp` + `service/track.cpp` | 已迁移（5 端点） |
| SysTest | `SysTestController` | `src/handler/systest_handlers.cpp` | 已迁移（15 端点） |
| 大表查询优化 | `optimization` 包（12 服务） | `src/service/optimization.{h,cpp}` + `handler/optimization_handlers.cpp` | 已迁移（17 端点） |
| 定时任务 | `TrackTask`/`DataFlowTask`/`@Scheduled` | `src/scheduler/scheduler.cpp` | 已迁移（10 任务） |
| 可靠性/丢失/延迟/一致性 | `DataReliabilityService`/`DataLossDetectionService`/`DelayMonitoringService`/`GaussEsConsistencyService` | `src/service/ops.{h,cpp}` | 已迁移 |
| MQ | Kafka/Pulsar | `src/mq/kafka_producer.{h,cpp}` + `service/ops.cpp::mq_deliver` | 已迁移（librdkafka；Redis 兜底可选） |
| CORS | Spring CorsConfiguration | `src/http/cors.{h,cpp}` | 已迁移（预检 200/403） |
| ES | RestHighLevelClient | `service/optimization.cpp`（REST） | 已迁移 |
| 测试 | JUnit | `tests/test_main.cpp` | 已迁移 |
| CarTask | 全部注释 | 不注册 | 不适用 |

---

## 4. 一页纸速查表

| 你在 Java 里想找的东西 | 到 C++ 项目里看 |
|---|---|
| `EcBusinessApiApplication` / `SpringApplication.run` | `src/main.cpp` |
| `application.yml` / `application-*.yml` | `configs/config.yaml` |
| `@Value("${xxx}")` | `src/config/config.h` 的 `Config` getter |
| `@RestController` / `@RequestMapping` | `src/handler/*_handlers.cpp` 的 `r.add(...)` |
| `@RequestParam` / `@PathVariable` / `@RequestBody` | `src/http/ctx.h` 的 `Request` |
| `BaseController.getDataTable` / `startPage` | `src/handler/base_handlers.cpp::list_response` + `src/db/dao.cpp::resolve_page` |
| `AjaxResult` / `TableDataInfo` / `Result<T>` | `src/common/result.h` |
| `@JsonFormat` / Jackson | `src/meta/entities_generated.h` 的 `FType` + `dao::convert_value` |
| Mapper XML / `resultMap` / `<if>` | `src/meta/entities_generated.h`（`filters`/`select_sql`） |
| `PageHelper.startPage` | `src/db/dao.cpp::resolve_page` |
| `SqlUtil.escapeOrderBySql` | `src/db/dao.cpp::valid_order_column` |
| Druid 数据源 | `src/db/pg.cpp::PgPool` |
| `RedisTemplate` / `RedisUtil` | `src/cache/redis.h` |
| `Constants.java` 键名 | `src/service/dict.h`、`src/service/track.h` 的 `k*` 常量 |
| `@Scheduled` / cron | `src/scheduler/scheduler.cpp` |
| `KafkaTemplate.send` | `src/mq/kafka_producer.h::KafkaProducer::send` / `mq::deliver` |
| `RestHighLevelClient` | `src/service/optimization.cpp`（`httplib` REST） |
| `logback-spring.xml` | `src/common/logging.{h,cpp}` |
| `StringUtils` / `DateUtils` | `src/common/utils.{h,cpp}` / `src/common/datetime.{h,cpp}` |
| JUnit 测试 | `tests/test_main.cpp` |

---

## 5. Java 开发人员必须警惕的 10 个非对称差异（按风险降序）

1. **MQ 已接真实 Kafka**（✅ 高）：`mq::deliver` 默认经 librdkafka 发送（key=dataId、value=JSON、`__TypeId__` 头）；`kafka.fallback-redis=true` 才退回 Redis 列表。无 broker 时应用仍可启动，发送失败进入重试/死信；端到端验证需要可用 broker + topic（见 COMPATIBILITY §9.4）。
2. **无 Spring 事务**（⚠️ 高）：`@Transactional` 的回滚语义不存在；当前 85 个端点以查询为主，写操作是单条语句。新增多语句写入时必须自己实现"失败补偿"，不能假设自动回滚。
3. **无反射/DI/AOP**（❌ 高）：新增一个 Controller 需要手写 `Spec` 并调用 `register_spec`；Bean 是单例，AOP 切面（日志/权限/事务）一律没有。
4. **内存所有权**（❌ 高）：`PgConn` 由 `PgPool` 持有，`shared_ptr` 出池；`Response` 按值返回。切勿把局部 `Json&` 或裸连接指针带出作用域。
5. **线程模型**（⚠️ 中高）：HTTP 16 线程固定；调度/导出/同步任务运行在受控线程池（调度 2 worker、后台任务 4 worker/队列 128，满载快速失败）。SIGINT/SIGTERM 触发优雅停机：停止接受新请求 → 回收调度器/同步线程 → 排空后台任务 → `rd_kafka_flush` → 关连接池。
6. **`BigDecimal` 尾零已保真**（✅ 已修复）：`convert_value` 的 `Decimal` 分支用 `json_raw_decimal()` 以原始字面量输出（`1.2300` 原样保留），`json_dump()` 序列化时还原为未加引号的数字；`tests/test_main.cpp::test_decimal` 覆盖不同标度/负数/零/非数字字面量。（历史版本曾丢失尾零，勿再按旧文档排查。）
7. **Redis 值编码**（⚠️ 中）：统一 JSON 文本。若与 Java 进程共用一个 Redis 且 Java 用 JDK 序列化，双方**无法互读**。
8. **`null` 与缺键**（⚠️ 中）：`AjaxResult.data` 为 null 时键消失；`Json::is_null()` 与"键不存在"要分开判断。
9. **时间语义**（⚠️ 中）：DB `timestamp without time zone` 一律按 `+08:00` 锚定，输出 `yyyy-MM-dd HH:mm:ss`；用 `timeutil::format_naive_plus8`，不要 `localtime`。
10. **编译期约束**（⚠️ 低中）：模板报错冗长、`-Wall -Wextra` 下警告即代码异味（当前构建零错误）；新增源文件依赖 glob，必要时重跑 `cmake -S . -B build`。
