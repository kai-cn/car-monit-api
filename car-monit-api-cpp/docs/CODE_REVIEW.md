# car-monit-api（C++）独立技术审阅报告

> 审阅对象：`d:\work\IdeaProjects\car-monit-api\car-monit-api-cpp`
> 参照基线：`../pro-business-api`（Spring Boot / RuoYi）+ `../pro-base-common` 的 Java 源码
> 审阅方式：静态阅读全部核心源码 + 运行已构建的单元测试 + Java 源码逐项交叉比对
> 审阅立场：外部评审、生产上线标准；未修改任何业务代码
> 未执行数据库冒烟：避免再次产生失败登录触发 openGauss 账号锁定（与上一轮结论一致）

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| 能否上生产 | **不能**。存在 1 个可直接利用的 SQL 注入、1 个跨文件系统级的封包契约偏差、DB 访问层在 Linux 上不可用，以及可靠性/调度任务的实际失效 |
| 迁移功能等价度（按代码证据加权） | **约 60%**（详见 §3.4；文档自评接近 100%） |
| 生产就绪度 | **约 30%** |
| 六个维度评分 | 正确性 2/5、安全性 1/5、并发安全 2/5、可维护性 2/5、可移植性 1/5、生产健壮性 2/5 |
| 最关键三个风险 | ① 未鉴权的 SQL 注入面（`/api/v1/large/*`）② 自研 PG 客户端/连接池（无 TLS、无预处理、Linux 不可用、建连持锁）③ 接口契约与调度语义漂移（16 个端点信封错误、`0/3` cron 解析错误、丢失检测周期差 60 倍） |

---

## 1. 技术栈与架构现状（实测）

### 1.1 实测技术栈

| 维度 | 实际实现 | 证据 |
|---|---|---|
| 语言标准 | C++20（`CMAKE_CXX_STANDARD 20`，`EXTENSIONS OFF`） | [CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L4-L6) |
| 编译器 / 构建 | MinGW-w64 g++ 14.2.0 + Ninja + Release（构建缓存实测）；MSVC 分支存在但只开 `/W3` | `build/CMakeCache.txt`；[CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L12-L16) |
| 工程形态 | 静态库 `carmonit_core` + 主程序 + 测试程序；源文件按目录 `file(GLOB_RECURSE ... CONFIGURE_DEPENDS)` 收集 | [CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L50-L93) |
| HTTP | vendored `cpp-httplib 0.15.3`，编译期固定 16 线程；路由/参数绑定/CORS 自研 | [CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L73-L77)、[server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L163-L282) |
| JSON | `nlohmann::ordered_json`（键序可观测），外加“裸小数占位符”回写技巧 | [json.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/json.h#L1-L45)、[json.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/json.cpp#L44-L73) |
| DB | 自研 PG v3 wire 客户端（MD5 + SCRAM/openGauss SHA256）、自研连接池、只支持简单查询协议 | [pg.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.h#L1-L147)、[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L505-L827) |
| 缓存 | 自研 Redis RESP2 客户端，单连接 + 全局互斥锁 | [redis.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L236-L252) |
| MQ | librdkafka 2.6.1（FetchContent 下载源码、SHA256 固定、静态编译） | [CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L31-L48) |
| ES | 直接用 vendored httplib 发 REST（`_search` / `_search/scroll` / `_bulk`） | [optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L159-L227) |
| 日志 | 自研同步日志：`stdio + ofstream`、每行 flush、无轮转、线程名=线程 ID 哈希 | [logging.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/logging.cpp#L46-L73) |
| 配置 | 自研“扁平化 YAML”解析（不支持 list/锚点/块标量），`${ENV}` 展开 + `config.local.yaml` 覆盖 | [config.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/config/config.cpp#L77-L181) |
| 依赖管理 | 无 vcpkg / Conan；vendored + 首次 configure 联网 FetchContent | [README_CPP.md](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/README_CPP.md#L18-L23) |
| 线程模型 | 16 个 HTTP 工作线程；1 个调度轮询线程 + 每任务 detached 线程；Kafka 2 个后台线程；SnapshotFlowSync 2 个 detached 线程；导出/同步/统计每请求 detached | [scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L127-L205)、[snapshot_flow_sync.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/snapshot_flow_sync.cpp#L243-L261) |
| 内存管理 | 基本 RAII（`unique_ptr<PgConn>`、`shared_ptr<ExportTaskStatus>`、栈对象 Response）；但存在泄漏点与无界容器（见 §4） | [pg.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.h#L136-L145)、[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L371-L390) |
| 错误策略 | 三层异常（`BizError`/`BindError`/`DbError`）在 HTTP 边界统一转换；后台线程普遍 catch 后只记日志、不重试/不降级 | [error.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/error.h#L1-L58)、[server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L229-L257) |

**实测运行结果**：`build\carmonit_tests.exe` 退出码 0，输出 `ALL TESTS PASSED`（当前工具链下 cmake/ninja 不在 PATH，未重跑全量构建；已有 Release 产物可用）。

### 1.2 模块依赖关系

```
main.cpp
 ├─ config::Config（自研 YAML + 环境变量）
 ├─ db::AuthGuard ── db::PgConn ── db::PgPool（进程级单例）
 ├─ cache::Redis（进程级单例，单 socket + 1 mutex）
 ├─ mq::KafkaProducer（librdkafka）  ⇄  service::ops   ← 双向依赖
 ├─ router::build_routes
 │    ├─ handler::register_base          ── repo::dao ── meta::EntityMeta（74KB 生成头）
 │    ├─ handler::register_sysutil       ── service::track ── dao/dict/redis
 │    ├─ handler::register_systest       ── service::track
 │    └─ handler::register_optimization  ── service::optimization ── db/redis/es(httplib)
 ├─ handler::start_schedulers            ── service::{track, ops, optimization}
 ├─ service::snapshot_flow_sync          ── db/redis/mq
 └─ http::run_server（httplib）          ── http::cors / http::ctx / http::Router
```

分层评价：

- **存在模块级循环依赖**：`src/mq/kafka_producer.cpp` include `service/ops.h` 并调用 `ops::record_reported_message`（[kafka_producer.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/mq/kafka_producer.cpp#L628-L636)）；同时 `src/service/ops.cpp` include `mq/kafka_producer.h` 并调用 `mq::deliver`（[ops.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/ops.cpp#L63-L67)）。头文件层面侥幸未互相 include，但设计上是 `mq ⇄ service` 双向环。
- **调度器放错层**：`start_schedulers()` 声明在 `handler/handlers.h`（[handlers.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/handlers.h#L14-L15)），实现却调用 `service::ops`；路由注册函数里还有副作用（启动一致性对账线程 [optimization_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/optimization_handlers.cpp#L347-L348)）。
- **上帝文件**：`service/optimization.cpp` 1655 行、`service/track.cpp` 1571 行，各自承载 6+ 个“服务类”、ES 客户端、CSV 导出、同步器、对账器；`meta/entities_generated.h` 74KB、22 个实体元数据。可读性与可测性差。
- 好的方面：`handler` 层很薄，`dao`/`meta` 把 MyBatis 的 SQL 拼装收敛到一处；`http/ctx.h` 的 Spring 参数绑定语义集中且清晰。

---

## 2. 与主流 C++ 生产栈的优劣对比

| 维度 | 当前方案 | 主流方案 | 当前优势 | 当前劣势 | 生产风险 |
|---|---|---|---|---|---|
| HTTP 框架 | vendored cpp-httplib + 自研路由/CORS | Drogon / Boost.Beast / oatpp / Pistache；cpp-httplib 也可用于中小流量 | 零额外依赖、单头文件、Windows/MinGW 友好；路由语义已按 Spring 复刻并有测试 | 同步阻塞模型、无 TLS/HTTP2、无内建限流/超时治理、无连接数上限、无指标钩子；16 线程写死 | 高并发/慢客户端下线程池耗尽；无 TLS 无法对外暴露；无优雅停机 |
| DB 访问 | 自研 PG wire v3（简单查询协议） | libpq / libpqxx / ODB / sqlpp11 + 成熟连接池 | 零外部依赖、能直接对齐 openGauss 的两种 SASL 派生 | **无 TLS、无预处理语句、无游标/COPY、无服务端游标、Linux 不可用、连接池在建连时持全局锁** | **阻断级**：注入面无参数化兜底；Linux 部署直接失败；DB 抖动时全站串行阻塞 |
| 连接池与并发 | 自研 `PgPool`：单 mutex + 10ms 轮询借还，建连在锁内 | pqxx 连接池、HikariCP 式（借还队列/超时/健康检查/最大等待） | 语义参数与 Druid 对齐（maxActive/min-idle/maxWait） | 建连（最长 60s）持锁；轮询而非条件变量；无健康检查/保活；`min_idle` 未使用；非 DbError 异常会漏还槽位 | 高：DB 不可达时 16 个 HTTP 线程全部卡在池锁上形成级联雪崩 |
| 序列化/JSON | nlohmann `ordered_json` + 裸小数占位符 | nlohmann / RapidJSON / simdjson | 键序可控、与 Jackson 语义贴近、BigDecimal 尾零有测试 | 全量 DOM、无 schema、无流式；占位符是“字符串魔术标记”，用户数据若命中标记会被输出成数字 | 中：数据量大的列表接口 CPU/内存放大；占位符碰撞导致数据被篡改（概率低但性质严重） |
| 日志 | 自研同步日志 | spdlog（异步/轮转/结构化） | 无依赖、格式贴 logback | 每行 `fflush`、全局 mutex、无轮转（文件无限增长）、无结构化字段、线程名哈希会碰撞 | 中高：磁盘写满导致进程异常；日志不可检索 |
| 配置 | 自研扁平 YAML | yaml-cpp / CLI11 / 环境变量规范 | 与 `application.yml` 键名一一对应，密钥可走环境变量 | 不支持 YAML list/锚点/块标量；`std::stoi` 非法环境变量会抛未捕获异常；`logging.level` 配了但从不生效 | 中：配置写法稍变就静默丢失；启动期崩溃 |
| 异步/协程 | `std::thread` + detached + 固定线程池 | C++20 coroutine / asio / 线程池 + 有界队列 | 实现简单、与 Java 单线程调度器语义接近 | detached 线程不可 join、不可限流、无背压；进程退出时不等待；每请求可无限 spawn | 高：导出/同步接口被反复调用会线程爆炸；停机丢数据 |
| 依赖管理与构建 | CMake + FetchContent | vcpkg / Conan / 预编译二进制 | 版本与 SHA256 固定、可离线覆盖 | 首次 configure 必须联网；无 lockfile；librdkafka 全量源码编译 1–3 分钟；无交叉编译脚本 | 中：CI/离线环境不可重现；“构建通过”依赖本机工具链 |
| 可观测性 | 只有 `/health`（恒定 `{"status":"UP"}`）+ 日志 | Prometheus/OpenTelemetry + 依赖健康检查 + 结构化日志 | 简单 | 不检查 DB/Redis/Kafka/ES；无 QPS/延迟/池占用/错误率指标；无 traceId；无告警通道（`send_alert` 只打日志） | 高：线上故障只能靠 grep 日志，无法定位 |
| 测试 | 1 个测试二进制：crypto/分页/日期/序列化/路由/CORS/Kafka 失败路径/AuthGuard | 单元 + 契约 + 集成 + 故障注入 + 压测 | 关键算法（MD5/SCRAM/PBKDF2）有独立向量，CORS 有 10 组用例 | **无端点级断言、无 DAO 测试、无并发/故障注入/压测；路由数只断言 `>=40`**（实际 86） | 高：这次审阅发现的契约偏差，现有测试一个都拦不住 |

---

## 3. 迁移进度核验（文档声称 vs 代码实际）

### 3.1 数量核对（已逐项确认）

| 指标 | 文档声称 | 代码实际 | 判定 |
|---|---|---|---|
| Java 生效端点 | 85 | 逐个统计：19 个实体控制器 48 + SysUtil 5 + SysTest 15 + unified/large/progressive 17 = **85** | ✅ 一致 |
| C++ 路由 | 86（含 `/health`） | 48 + 5 + 15 + 17 + 1 = **86** | ✅ 一致 |
| 定时任务 | 10 | 调度器注册 10 个 | ✅ 数量一致，语义不一致（见 §3.3） |
| 实体 | 19 | 19 个业务实体 + `zdataTrailFitting`/`zdataLocationDict`/`kafkaMessageRecord` = 22 个 `EntityMeta` | ✅ 业务实体数一致（文档未提后 3 个） |
| 测试 | “分页/路由/序列化/CORS/Kafka 等” | 全部集中在 `tests/test_main.cpp`，路由只断言 `>=40` | ⚠️ 声称范围大于实际强度 |

### 3.2 “文档声称 / 代码实际”对照

| 模块 | 文档声称 | 代码实际 | 判定 |
|---|---|---|---|
| 入口/配置 | ✅ 已迁移；`logging.level` 级别/文件可配 | `logging.level` 从未被读取，级别只受 `CM_LOG_LEVEL` 控制；[config.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/config/config.cpp#L173-L175) 无 logging 分支 | 部分完成（文档高估） |
| HTTP/CORS | ✅ 85 + `/health`，CORS 语义一致 | 路由数一致，CORS 有测试；但所有 `Response::raw` 一律追加 `Content-Disposition: attachment`（[server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L260-L266)），Java 不会 | 部分完成（多余响应头是契约偏差） |
| 19 个基础 CRUD（48 端点） | ✅ 已迁移 | **16 个 `/{id}` 端点返回裸实体而非 `AjaxResult` 信封**（见 §3.3 R1）；11 个端点把 Java 的 `String` 主键强制成数字（见 R2） | 声称完成但代码不支持 |
| EXCEL/导出端点 | ✅ `listToExport` | 返回 JSON 数组（与 Java `List<T>` 一致）；但 `listToExport` 的分页参数与 Java `startPage()` 语义一致 | ✅ |
| SysUtil（5） | ✅ 已迁移 | `saveRedis` 直接返回 `AjaxResult.success()`，与 Java 方法体整体注释一致（[track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L1480-L1483)） | ✅ |
| SysTest（15） | ✅ 已迁移 | `/syncOdsSzdnGantry` 只重建门架缓存，**丢失 Java 的“按门架统计收费流水条数写 `gantry_list_data:*`”逻辑**（Java 见 `SysTestController.java:327-354`；C++ [track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L1405-L1418)） | 部分完成 |
| 轨迹/可疑车辆 | ✅ `track.cpp` 13 个对外函数 | 逻辑大体齐全，但写入 Redis 的轨迹结构由 Java 的 `Map<ZdataTrailTracks,List<TrailBo>>` 改成 `[{tracks,trailList}]`（[track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L1097-L1106)），**Java 前端/进程读同一键会解析失败** | 部分完成（文档只提“序列化差异”，未提结构变更） |
| 大表查询（17 端点） | ✅ 已迁移 | 端点齐全；ES 不可用时降级到 PG，但降级 SQL 直接拼接客户端字段名/`groupBy`（见 R3） | 部分完成（且引入新漏洞） |
| 可靠性/丢失/延迟/一致性 | ✅ 已迁移 | `reliability_compensation_tick` 读 `reliability:timeout:queue`，但**全工程没有任何代码向该队列 push**（Java 在 `DataReliabilityService.java:373` push）；Kafka 成功回调写 `SENT` 而非 Java 的 `CONFIRMED`（[kafka_producer.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/mq/kafka_producer.cpp#L323-L333)）；`gauss_es_consistency_tick` 是空函数（[ops.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/ops.cpp#L281-L289)），真正的对账由另一个私有线程跑（[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L1583-L1619)） | 声称完成但语义不成立 |
| 定时任务 | ✅ 10 个，与 Java 一一对应 | 数量对，但：`0 0/3 * * * ?` 解析成“每小时第 0 分”（见 R4）；丢失检测周期 30 分钟 vs Java 30 秒（见 R5）；一致性任务重复调度（调度器里空转 + 私有线程） | 声称完成但行为不等价 |
| Kafka | ✅ 真实发送、重试、死信 | 真实发送、退避重试、死信落库都有；但超时检测/补偿链路缺失，`retry_counts` 无界增长 | 部分完成 |
| DB 客户端/池 | ✅ Druid + pgjdbc 等价 | 无 SSL、无预处理/游标；**POSIX 分支连接后未恢复阻塞模式，Linux 上 DB 不可用**（见 R6）；建连持全局锁 | 部分完成（且平台受限） |
| Redis | ✅ 等价 | 单连接串行、Windows 下 bulk 读可能半包、`ensure()` 重连泄漏 socket fd（见 R7）、`KEYS` 扫描 | 部分完成 |
| ES | ✅ REST，不可达降级 DB | REST 调用真实；但**每次请求新建 `httplib::Client`（无连接复用）**，全局 30s 冷却会把所有 ES 操作一起熔断 | 部分完成 |
| 测试 | ✅ ctest 1/1、`ALL TESTS PASSED` | 实测通过；无端点/DAO/并发/故障注入测试 | ✅ 但强度不足 |
| 文档 | — | `COMPATIBILITY.md:20` 称“未分页时先 count_rows”，代码是 `rows.size()`（[dao.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/dao.cpp#L260-L263)）；`COMPATIBILITY.md:47` 称“部分实体用 SELECT *”，实际 **20/22**；`MIGRATION_GUIDE.md:196` 仍写“BigDecimal 尾零丢失”，与 `COMPATIBILITY.md:29` 和测试相反；`handlers.h:6` 写“17 个控制器 46 端点”，实际 19/48 | 文档不一致 |

### 3.3 关键偏差明细（带代码证据）

**R1（阻断，契约）— 16 个 `/{id}` 端点返回结构错误**
Java 的 `getInfo` 绝大多数返回 `AjaxResult.success(entity)`，即 `{"code":200,"msg":"操作成功","data":{...}}`（[OdsSzdnGantryController.java:40-42](../../pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryController.java#L40-L42)，`AjaxResult` 构造见 [AjaxResult.java:53-61](../../pro-base-common/src/main/java/com/ruoyi/common/core/domain/AjaxResult.java#L53-L61)）。
C++ 对所有 19 个实体都置 `flat = true`，直接把实体 JSON 当响应；查不到时返回 **空 body**（[base_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp#L96-L110)）。
只有 3 个控制器（`feeGantry`、`feerecords`、`snapshotflow`）确实直接返回实体（如 [OdsLwzxsfsjFeeGantryFusion01Controller.java:49](../../pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeGantryFusion01Controller.java#L49-L51)），其余 16 个都是信封。**这是对前端可见的破约，且为空结果时更严重（HTTP 200 + 空 body）**。

**R2（中，契约）— 主键数字校验与 Java 类型不符**
`fwqjcxx/sfsjcxx/sfzjcxx/feeGantry/feerecords/feestationexit/snapshotflow/gantry/section/toll/org` 在 Java 是 `@PathVariable String`，C++ 置 `numeric = true`（[base_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp#L186-L364)），非数字 ID 返回 400，Java 会正常查询。

**R3（阻断，安全）— SQL 注入**
三条链路都把 HTTP 参数名/值原样拼进 SQL：
- `pg_where` 把 `fuzzyFields.<key>` 的 key 当列名拼接（[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L335-L347)），入口 [optimization_handlers.cpp:26-36](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/optimization_handlers.cpp#L26-L36)；
- `aggregation_stats` 把 `groupBy`、`countField` 直接拼进 `SELECT/GROUP BY/ORDER BY`（[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L1193-L1202)），入口 `/api/v1/large/stats/group`；
- `UnifiedQueryService::query` 的 PG 降级同样走 `pg_where(..., translate=true)`，而 `translate_field` 对未知字段原样返回（[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L133-L144)）。
Java 侧这些服务只用 ES DSL，不存在该拼接；**C++ 在“降级路径”里新引入了注入面**。本工程默认 ES 不可达（README/COMPATIBILITY 明确），因此该路径是**默认可达**的，且全站无鉴权。

**R4（高，功能）— cron `0/3` 被解析成“仅 0 分”**
`match_token` 在 `head` 既非 `*`/`?` 又无 `-` 时直接 `return v == atoi(head)`，完全忽略 `/<step>`（[scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L57-L78)）。于是 `0 0/3 * * * ?`（[scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L168)）只在每小时第 0 分触发，而 Java/Quartz 是**每 3 分钟**。同类问题：Quartz 星期字段 1=Sunday，代码用 `tm_wday`（0=Sunday）；Spring 对“日/周同时指定”是 OR，代码是 AND（[scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L94-L109)）。当前配置未触发后两者，但 `syncCurrentTrack` 已实际降频 20 倍。

**R5（中，功能）— 丢失检测周期差 60 倍**
Java `@Scheduled(fixedRateString = "${detection.interval-minutes:30}000")` 展开为 `"30000"` ms = **30 秒**（[DataLossDetectionService.java:127](../../pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataLossDetectionService.java#L127)）；C++ `interval_minutes * 60000` = **30 分钟**（[scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L174-L175)）。上线后丢失率告警会明显滞后。

**R6（阻断，可移植）— Linux 上 DB 客户端不可用**
`connect_once` 在 POSIX 分支调用 `fcntl(... O_NONBLOCK)`（[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L216-L221)），但只有 `_WIN32` 分支把 socket 恢复为阻塞并设置 `SO_RCVTIMEO/SO_SNDTIMEO`（[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L249-L255)）。POSIX 下随后所有 `recv/send` 会 `EAGAIN` 直接失败；且文件未 include `<fcntl.h>/<cerrno>`（[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L15-L24)），Linux 上大概率连编译都过不去。与 README“Linux 亦可”直接冲突（[README_CPP.md](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/README_CPP.md#L13)）。

**R7（高，资源）— Redis 重连泄漏 socket**
`ensure()` 先把 `sock_` 置 -1 再调 `connect()`；`connect()` 里的 `close_unlocked()` 看到的是 -1，旧 fd 不会被关闭（[redis.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L138-L146)）。每次“读失败→重连”都会泄漏一个 socket；Redis 重启/网络抖动时会积累到句柄耗尽。

**R8（高，可用性）— 连接池在建连时持全局锁**
`PgPool::query/execute/transaction` 都在 `mu_` 保护下执行 `slot.conn->connect(...)`，而 `maxWait` 被当作 connect 超时（默认 60s）（[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L654-L711)、[pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L713-L742)）。DB 抖动时：16 个 HTTP 线程 + 所有查询全部串行等这把锁，服务整体雪崩；且没有网络故障熔断（只有认证失败熔断）。

**R9（中，功能）— 可靠性链路不闭环**
Java `sendReliableMessage` 每次都会 `scheduleTimeoutCheck(messageId)`（[DataReliabilityService.java:152-194](../../pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataReliabilityService.java#L152-L194)），超时后 push 到 `TIMEOUT_QUEUE`，补偿任务按 `PENDING/SENT/CONFIRMED/DEAD` 分派。C++ 只写了内容与 `PENDING`，**没有超时计时器、没有入队**；补偿任务永远读到空列表（[ops.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/ops.cpp#L221-L240)）。成功回调写 `SENT`，`CONFIRMED` 分支永不出现。

**R10（中，性能/资源）— 无界后台任务与无界容器**
`/api/v1/large/sync/full`、`/sync/repair` 每次请求 `std::thread(...).detach()`，无并发限制（[optimization_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/optimization_handlers.cpp#L249-L293)）；导出任务注册表只增不删（[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L371-L390)）；Kafka `retry_counts` 只增不删（[kafka_producer.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/mq/kafka_producer.cpp#L209-L211)）。长时间运行会内存增长 + 线程爆炸。

**R11（中，性能）— N+1 字典读取**
`change_data` 每行都调用 `gantry_map()/toll_map()/section_map()/location_dict_map()`（[track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L309-L315)），每个 map 都从 Redis 读整表并全量解析（[dict.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/dict.cpp#L24-L43)）；`weight_capture_map` 每个轨迹点一次 Redis GET、未命中再查 DB（[track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L335)、[dict.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/dict.cpp#L123-L160)）。轨迹接口在 10 行/页时可产生上百次串行 Redis 往返（Redis 还是单连接全局锁）。

### 3.4 可信完成度

| 维度 | 权重 | 达成度 | 依据 |
|---|---|---|---|
| 路由/端点覆盖 | 15% | 100% | 85 + `/health` = 86，静态逐一核对 |
| 端点契约正确性 | 15% | 78% | 16 个 `/{id}` 信封错误 + 11 个主键类型错误（部分重叠），/health 无依赖检查 |
| 业务逻辑等价 | 25% | 60% | 基础 CRUD 逻辑简单；track/sysutil 深度逻辑大体在，但 Redis 结构变更、`syncOdsSzdnGantry` 缺逻辑、可靠性链路不闭环、优化模块依赖 ES 降级 |
| DB/DAO | 15% | 45% | 无预处理/TLS/游标；20/22 用 `SELECT *`；连接池设计缺陷；Linux 不可用 |
| 缓存/MQ | 10% | 50% | Redis 单连接 + fd 泄漏 + KEYS；Kafka 发送/重试/死信在，但可靠性语义缺失 |
| 调度 | 10% | 55% | 10 个已注册；cron 步进错误、检测周期错、一致性任务空转 + 重复线程 |
| 测试 | 5% | 20% | 单二进制、无端点/DAO/并发/故障注入 |
| 运维可观测 | 5% | 10% | 静态 `/health`、无指标/追踪/轮转/优雅停机 |

加权结果：`15×1.00 + 15×0.78 + 25×0.60 + 15×0.45 + 10×0.50 + 10×0.55 + 5×0.20 + 5×0.10` ≈ **60.4%**。

> 口径说明：这是“**与 Java 行为等价**”的完成度，不是“代码能不能编译/接口通不通”的完成度。若按“生产就绪度”（安全、可观测、容量、故障行为）衡量，约 **30%**。

---

## 4. 代码质量评估

### 4.1 评分

| 维度 | 分数 | 主要理由 |
|---|---|---|
| 正确性 | **2/5** | 16 个端点信封错误；cron 解析错误；检测周期错；`SELECT *` 与默认排序缺失；`count_rows` 吞错返回 0 |
| 安全性 | **1/5** | 未鉴权 + 可注入 SQL；全链路无 TLS；64MB body 无速率限制；`change_password` 未校验失败登录之外的暴力面 |
| 并发安全 | **2/5** | 池锁内建连、Redis 全局锁、detached 线程不可管、无优雅停机；`g_level` 非原子 |
| 可维护性 | **2/5** | 两个 1500+ 行 god 文件、74KB 生成头、模块循环依赖、死代码、注释与实现漂移 |
| 可移植性 | **1/5** | POSIX PG 分支不可用；`/data/export` 在 Windows 变成盘符相对路径；无跨平台 CI |
| 生产健壮性 | **2/5** | 无 HTTP 超时/限流/背压；无依赖健康检查；无指标；导出/同步无上限；日志无轮转 |

### 4.2 问题清单（级别：阻断 / 高 / 中 / 低；成本：小 / 中 / 大）

| # | 级别 | 成本 | 问题 | 证据 |
|---|---|---|---|---|
| 1 | 阻断 | 小 | SQL 注入：`fuzzyFields.*` 的 key、`groupBy`、`countField` 直接拼 SQL | [optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L335-L347)、[#L1193-L1202](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L1193-L1202) |
| 2 | 阻断 | 小 | 16 个 `/{id}` 端点响应结构与 Java 不一致；空结果返回空 body | [base_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp#L96-L110) |
| 3 | 阻断 | 中 | Linux 下 PG 客户端不可用（非阻塞未恢复、缺 fcntl include） | [pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L216-L258) |
| 4 | 高 | 大 | 自研 PG 协议层无 TLS、无预处理、无游标；所有 SQL 走简单查询 | [pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L505-L566) |
| 5 | 高 | 大 | 连接池建连持全局锁、轮询等待、无健康检查、非 DbError 异常漏还槽位 | [pg.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L654-L711) |
| 6 | 高 | 小 | Redis 重连泄漏 socket；Windows bulk 读半包直接失败；`KEYS` 阻塞扫描 | [redis.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L138-L146)、[#L195-L218](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L195-L218)、[#L326-L336](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L326-L336) |
| 7 | 高 | 中 | 可靠性超时/补偿链路缺失，状态机与 Java 不一致 | [kafka_producer.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/mq/kafka_producer.cpp#L323-L339)、[ops.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/ops.cpp#L221-L240) |
| 8 | 高 | 小 | cron `a/b` 步进被忽略；Quartz 星期基线错误；日/周 AND 语义 | [scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L57-L109) |
| 9 | 高 | 中 | 无优雅停机：调度器/导出/同步全 detached，`main` 直接 return；Kafka 之外的资源不关闭 | [scheduler.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L185-L205)、[main.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/main.cpp#L88-L92) |
| 10 | 高 | 中 | 可观测性缺失：`/health` 恒定 UP，无指标/追踪/依赖探活/日志轮转 | [routes.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/router/routes.cpp#L7-L19)、[logging.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/logging.cpp#L50-L73) |
| 11 | 中 | 小 | `/list` 对 20/22 实体用 `SELECT *`，与 Java `<include refid=Vo>` 列清单不同；部分实体无默认排序 | [entities_generated.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/meta/entities_generated.h#L8-L1607) |
| 12 | 中 | 小 | `count_rows` 失败吞错返回 0，前端会看到 total=0 但 rows 非空 | [dao.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/dao.cpp#L215-L226) |
| 13 | 中 | 小 | 所有 `raw` 响应被加 `Content-Disposition: attachment` | [server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L260-L266) |
| 14 | 中 | 中 | 64MB 请求体 + 16 线程 + 无读/写超时治理；慢请求可占满线程 | [server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L163-L166) |
| 15 | 中 | 中 | 导出/同步每请求 spawn detached 线程，无并发上限；任务注册表不回收 | [optimization_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/optimization_handlers.cpp#L249-L293)、[optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L371-L390) |
| 16 | 中 | 中 | N+1 字典读取：每行轨迹都整表读 Redis 并解析 | [track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L309-L315)、[dict.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/dict.cpp#L24-L43) |
| 17 | 中 | 小 | ES 客户端每次请求新建连接，无 keep-alive；全局冷却把全部 ES 操作一起熔断 | [optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L167-L206) |
| 18 | 中 | 中 | 自研 YAML 不支持 list/锚点；`std::stoi` 非法环境变量未捕获 | [config.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/config/config.cpp#L77-L106)、[#L357-L401](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/config/config.cpp#L357-L401) |
| 19 | 中 | 小 | `json_raw_decimal` 占位符可被用户字符串命中，序列化时变成裸数字（数据篡改） | [json.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/json.cpp#L44-L73) |
| 20 | 中 | 中 | 业务逻辑漂移：`syncOdsSzdnGantry` 缺计数逻辑；轨迹缓存结构由 Map 变数组 | [track.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L1405-L1418)、[#L1097-L1106](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/track.cpp#L1097-L1106) |
| 21 | 低 | 小 | 主键强制数字、请求重复参数取最后一个（Spring 取第一个） | [base_handlers.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp#L31-L35)、[ctx.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/ctx.h#L32-L36) |
| 22 | 低 | 小 | 死代码：`select_list_raw`、`select_by_ids`、`execute_in_tx/transaction`、`set_context_path`、`min_idle` 均未使用；`run_server` 的 `thread_count` 形参被忽略 | [dao.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/dao.cpp#L184-L213)、[server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L163) |
| 23 | 低 | 小 | `logging.level` 配置项无效；`CM_LOG_LEVEL` 之外无法调级别 | [config.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/config/config.cpp#L173-L175) |
| 24 | 低 | 小 | 日志线程名用 `hash<thread::id>%100000`，高并发会碰撞，无法与 Java 线程名对照 | [logging.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/common/logging.cpp#L46-L48) |
| 25 | 低 | 小 | 配置中明文 `elasticsearch.password: changeme`、失效的公网 `rediscluster.clusterNodes` | [config.yaml](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/configs/config.yaml#L59-L63)、[#L102-L108](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/configs/config.yaml#L102-L108) |
| 26 | 低 | 小 | 无请求级 traceId；错误响应把 DB 原始错误文本回给客户端（信息泄露） | [server.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/server.cpp#L244-L252) |
| 27 | 低 | 中 | 无 CI、无 sanitizer、无 `-Werror`、无静态分析 | [CMakeLists.txt](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/CMakeLists.txt#L12-L16) |

### 4.3 值得肯定的部分

- PostgreSQL/openGauss 的 MD5、SCRAM-SHA-256、openGauss `SHA256(SHA256(pwd)||salt)` 三种派生都有独立测试向量（[test_main.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/tests/test_main.cpp#L114-L147)），这部分实现质量明显高于其他自研模块。
- BigDecimal 尾零通过 `json_raw_decimal` + 自定义 `json_dump` 保真，并有覆盖不同标度/负数/零的用例（[test_main.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/tests/test_main.cpp#L454-L472)）。
- CORS 按 Spring `CorsConfiguration` 语义实现，10 组用例覆盖预检/实际请求/凭据通配冲突（[cors.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/http/cors.cpp#L198-L243)）。
- 凭据守卫 + 认证失败熔断确实阻止了“空口令连接 → 账号锁定”的坏循环，且放在所有网络动作之前（[main.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/main.cpp#L30-L45)），这是本轮迁移里最务实的一处工程判断。

---

## 5. 生产化优化建议

### 5.1 上线前必须做（阻断/高危）

| # | 问题 | 影响 | 具体做法 | 工作量 |
|---|---|---|---|---|
| 1 | SQL 注入 | 数据泄露/篡改，且无鉴权即可利用 | 在 [optimization.cpp](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/service/optimization.cpp#L335-L347) 增加“允许字段白名单”——按 `DataSource` 定义 `{logical -> physical}` 映射，未命中直接 `BindError(400)`；`groupBy/countField` 同样走白名单；`sql_literal` 之外禁止任何字符串拼列名 | 2–3 人日 |
| 2 | 16 个 `/{id}` 信封错误 | 前端解析失败/空响应 | 把 `flat` 声明从“统一 true”改为按 Java 返回值类型：仅 `feeGantry/feerecords/snapshotflow` 为 true，其余走 `ajax_ok_data(row)`；空结果返回 `ajax_ok()` 而非空 body。[base_handlers.cpp:96-110](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/handler/base_handlers.cpp#L96-L110) | 0.5 人日 |
| 3 | Linux 不可用 | 无法部署到 Linux 生产 | 恢复阻塞模式 + 设置 `SO_RCVTIMEO/SO_SNDTIMEO`（POSIX 分支），补 `<fcntl.h>/<cerrno>`；并在 CI 里加 Linux 构建 job。更彻底的做法是直接换 libpq（见 §5.4） | 1–2 人日（临时修复）/ 3–5 人周（替换） |
| 4 | 连接池建连持锁、无故障熔断 | DB 抖动导致全站雪崩 | 把 `connect()` 移到锁外（先预留 slot 占位，失败回收）；改条件变量等待；加“连续 N 次连接失败进入 30s 冷却”的熔断；区分 `maxWait`（借连接等待）与 `connectTimeout`（建连超时）。[pg.cpp:654-742](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/db/pg.cpp#L654-L742) | 3–5 人日 |
| 5 | 全链路无 TLS | 凭据/业务数据明文 | PG 用 libpq 的 `sslmode=require`；Redis 加 TLS；Kafka 目前 PLAINTEXT，需在受控网络内或启用 SASL_SSL；若坚持自研，至少要给 PG 加 SSLRequest 支持 | 2–4 人日（依赖换库后） |
| 6 | 无鉴权 + 64MB body + 无线程/超时治理 | 任意人可打；DoS | 恢复 Java 被注释掉的 `SecurityInterceptor` 等价物（至少 API-Key/Bearer + IP 白名单）；`set_payload_max_length` 降到业务实际值（如 1MB）；设置 `svr.set_read_timeout/ write_timeout`；接入限流。 | 3–5 人日 |
| 7 | cron 步进/星期/OR 语义 | 任务频次错误（已发生） | 用成熟 cron 解析（如 `ccronexpr`）替换 [scheduler.cpp:57-109](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/scheduler/scheduler.cpp#L57-L109)，并写单测覆盖 `0/3`、`1-5/2`、星期 0/1/7、日/周同配 | 1–2 人日 |
| 8 | 可靠性链路不闭环 | 超时消息永不被补偿，状态机失真 | 发送后启动超时检测（可用延迟队列/定时扫描 `reliability:msg:status:*` + 创建时间），超时 push `reliability:timeout:queue`；回调写 `CONFIRMED`；补齐 Java 的 `handleKafkaAck` 延迟统计。[kafka_producer.cpp:323-339](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/mq/kafka_producer.cpp#L323-L339) | 3–5 人日 |
| 9 | Redis fd 泄漏 + 半包读 | 句柄耗尽/协议错位 | 修 `ensure()`：先 `close_unlocked()` 再置 -1；Windows 分支改循环 recv；`KEYS` 全部替换为 `SCAN`（[redis.cpp:326-336](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/cache/redis.cpp#L326-L336)） | 1–2 人日 |
| 10 | 可观测性为零 | 无法排障 | `/health` 增加 DB `SELECT 1`、Redis `PING`、Kafka metadata、ES ping（分别短超时，输出 `UP/DEGRADED/DOWN`）；`/metrics` 暴露 QPS、P95、池占用、Redis 等待、Kafka lag；日志加 traceId | 5–8 人日 |
| 11 | 无优雅停机 | 停机丢消息/丢响应 | 引入信号处理：停止接受新请求 → 等待 in-flight → 停止调度/导出/同步（用可 join 的线程池）→ `rd_kafka_flush` → 关池；把 detached 改为受管 `std::jthread`/线程池。[main.cpp:88-92](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/main.cpp#L88-L92) | 3–5 人日 |
| 12 | 测试拦不住契约偏差 | 每次改动都可能破约 | 增加“黄金响应”契约测试（用 Java 实例采集 85 个端点的样本响应，逐字段 diff）；DAO 层用容器化 PG；并发测试（16 线程混合读写）；故障注入（DB/Redis/Kafka 断电）。[test_main.cpp:159-177](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/tests/test_main.cpp#L159-L177) | 10–15 人日 |

### 5.2 上线后尽快做

1. **选列与索引**：把 20 个 `SELECT *` 换成 Java `<include refid=...Vo>` 的列清单（[entities_generated.h](file:///d:/work/IdeaProjects/car-monit-api/car-monit-api-cpp/src/meta/entities_generated.h#L8-L1607)），既省带宽又能命中覆盖索引。
2. **分页稳定性**：对无默认排序的实体补 `ORDER BY`（快照流已正确），避免无 ORDER BY 的 `LIMIT/OFFSET` 翻页重复/遗漏。
3. **计数策略**：`count_rows` 改为 `count(*)` 走估算（`EXPLAIN`/`pg_class.reltuples`）或异步，避免每次列表双查；失败不要静默 0。
4. **字典缓存**：把 `gantry_map/toll_map/section_map/location_dict_map` 改为进程内不可变快照（启动/定时刷新 + `shared_ptr` 原子替换），消除每行 Redis 读与 JSON 解析（R11）。
5. **导出/同步治理**：固定大小线程池 + 每类任务单飞（同一 dataset 只允许一个 full sync），任务记录 TTL 淘汰；导出目录改为配置的绝对路径（Windows 下 `/data/export` 会变成盘符相对路径）。
6. **ES 客户端复用**：进程级 `httplib::Client`（httplib 自带连接池），按需重试；冷却改为按失败操作类型而非全局。
7. **日志**：换 spdlog（异步 + 按天/按大小轮转 + JSON 格式），保留线程名、加 traceId；一次故障排查就能看出收益。
8. **配置**：换 yaml-cpp，保留 `${ENV}` 展开与本地覆盖；启动时对环境变量做强校验并给出可读错误。
9. **资源清理**：`KafkaProducer::Impl::retry_counts`、导出任务表、`pendingMessages` 类容器加 TTL/上限。
10. **代码结构**：拆 `optimization.cpp`（ES client / query services / export / sync / consistency 分文件）、拆 `track.cpp`（轨迹转换 / 缓存字典 / 任务 / handler 适配），消除 `mq ⇄ service` 循环（把 `record_reported_message` 上移为独立 `observability` 模块）。

### 5.3 长期演进

- 并发模型：当 QPS 上升或需要 SSE/WebSocket 时，评估迁移到 Drogon（自带异步、TLS、HTTP/2、连接池、指标）或在 httplib 外层加 asio。现阶段的同步 16 线程模型只适合低流量内部服务。
- 数据访问：DAO 元数据层保留（它是把 MyBatis 语义固化下来的资产），但底层换成 libpqxx 的 prepared statement + 事务；逐步把“拼 SQL”改为“模板 + 参数绑定”。
- 契约治理：从 Java 侧 OpenAPI/注解生成契约文件，C++ 侧做编译期/运行期校验；上线采用双跑（Java 9902 vs C++ 9901）逐端点 diff。
- 容量：为列表/轨迹/导出分别定义 SLO（P95、最大返回行数、最大时间窗），并在网关层强制。

### 5.4 战略问题：自研基础设施继续维护，还是替换？

**明确建议：停止在自研 PG/Redis 协议层上加功能，优先替换；HTTP/JSON/ES/Kafka 保留。**

| 组件 | 结论 | 理由 | 迁移路径 |
|---|---|---|---|
| HTTP（httplib + 自研路由） | **保留** | httplib 是成熟库，自研部分只有路由/参数绑定/CORS，已按 Spring 语义实现并有测试；替换成本高、收益低 | 保留；补超时/限流/TLS 终结（Nginx/Envoy 前置）即可 |
| PG wire 客户端 + 池 | **替换（最高优先级）** | 目前是全工程最大风险：无 TLS、无预处理（注入只能靠手写转义）、无游标/COPY、POSIX 不可用、池锁设计缺陷。继续维护等于自养一个数据库驱动 | 保留 `db::PgPool`/`PgResult` 接口不变，内部换 libpqxx（`pqxx::connection` + `pqxx::work` + `pqxx::nontransaction`），连接池用 `pqxx::connection_pool` 或自研条件变量池；SQL 层改 `exec_params`。预计 3–5 人周，可分批：先池与连接，再 DAO 参数化 |
| Redis RESP | **替换** | 单连接 + 全局锁 + 手写 RESP + Windows 半包 + fd 泄漏；hiredis 是事实标准，支持超时、TLS、pipeline | 保留 `cache::Redis` 门面，内部换 hiredis + 连接池；1 人周 |
| JSON（nlohmann） | **保留** | 成熟、键序可控、已解决 BigDecimal 尾零 | 去掉占位符 hack：用 `Decimal` 包装类型 + 自定义 `to_json`（仍基于 nlohmann），消除标记碰撞 |
| ES REST | **保留** | ES 客户端本来就是 REST，无需第三方库 | 只做连接复用与错误分类 |
| Kafka（librdkafka） | **保留** | 官方客户端，配置已对齐 Spring Kafka | 保留 |
| 配置（自研 YAML） | **替换** | 手写解析器无法覆盖生产 YAML，且失败是静默的 | yaml-cpp，2 人日 |
| 日志 | **替换** | 无轮转、每行 flush、无结构化 | spdlog，2 人日 |
| 调度器 | **保留骨架，替换 cron 解析** | 轮询 + 防重入的设计可用；解析器不可用 | 引入 `ccronexpr`，1–2 人日 |

一句话：**“自研 HTTP + 自研 JSON 编解码”是合理的取舍；“自研数据库驱动 + 自研 Redis 客户端”是不必要的风险堆积。**

---

## 6. 结论

这套 C++ 迁移的**端点覆盖、Spring 语义复刻意识、BigDecimal/时间/认证算法等细节**做得比一般“翻译式迁移”好，代码也能编译、测试能过；但它目前只是“**行为大致相似的可运行副本**”，不是“**可上生产的等价实现**”。最关键的三个风险是：

1. **未鉴权的 SQL 注入面**（`/api/v1/large/*` 的 `fuzzyFields.*` key、`groupBy`、`countField` 直接拼 SQL，且默认 ES 不可达时该路径必然被执行）。
2. **自研 PG 访问层**：无 TLS、无参数化、无游标；Linux 上不可用；连接池在建连时持全局锁、无网络故障熔断——DB 抖动会放大成全站不可用。
3. **契约与调度语义漂移**：16 个 `/{id}` 端点返回结构错误（空结果甚至返回空 body）、cron `0/3` 被解析成每小时一次、丢失检测周期从 30 秒变成 30 分钟、可靠性超时补偿链路不闭环。

按当前状态，**不能上生产**；按 §5.1 的 12 项阻断/高危项修复后，才谈得上灰度。建议的上线顺序：先做安全与契约修复（1–2 周量级）→ 换 PG/Redis 驱动与连接池（3–6 周量级）→ 补可观测性、优雅停机与契约测试（3–4 周量级）→ 双跑对比 → 灰度切流。文档侧需要同步把 §3.2 的偏差改成现状描述，尤其是 `README_CPP.md` 的“Linux 亦可”、`COMPATIBILITY.md` 的“未分页先 count_rows”“部分实体 SELECT *”、`MIGRATION_GUIDE.md` 的“BigDecimal 尾零丢失”这三处，避免后续维护者按错误前提改动代码。
