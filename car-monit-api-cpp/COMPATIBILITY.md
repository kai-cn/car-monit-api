# 兼容性说明：Java ↔ C++ 已知行为差异

> 标记含义：✅ 完全一致 ｜ ⚠️ 有差异（已补偿/可接受）｜ ❌ 无法迁移（已给出替代方案）
> 判定基准：`pro-business-api` / `pro-base-common` 的 Java 源码与**实际运行响应**（本机 9902 的 Java 实例）。

## 1. 对外契约（HTTP）

| 项 | Java 行为 | C++ 行为 | 结论 |
|---|---|---|---|
| 端口 / context-path | `9901`，`/` | `configs/config.yaml` 的 `server.port`，路由不含前缀 | ✅ |
| 路由总数 | 85 | 85 + `/health`（本工程新增的健康检查） | ✅（新增项已标注） |
| `AjaxResult` | `{msg,code,data}`；`data == null` 时**键消失** | 同键序、同省略规则 | ✅ |
| `/{id}` 详情（getInfo） | 19 个实体控制器中 16 个返回 `AjaxResult.success(entity)`；查不到返回 `{"msg":"操作成功","code":200}`（data 键省略）。仅 feeGantry/feerecords/snapshotflow 3 个直接返回实体，查不到时空 body（HTTP 200） | 同（`info_returns_raw_entity` 为唯一权威映射，`base_handlers.cpp`；16/3 逐端点核对过 Java 控制器返回类型） | ✅ |
| `TableDataInfo` | `{total,rows,code,msg}` | 同键序（`total` 为数字，非字符串） | ✅ |
| void 控制器方法 | HTTP 200 + 空 body（`application/json;charset=UTF-8`） | `Response::raw(200,"")` | ✅ |
| 业务异常 | HTTP 200 + `{"msg":"...","code":500}` | 同 | ✅ |
| 参数绑定失败 | HTTP 400 + Spring `ErrorAttributes` 信封 | 同（`BindError(400)`） | ✅ |
| 未知路径 | HTTP 404 + `{"timestamp","status":404,"error":"Not Found","message":"","path"}` | 逐字节一致（时间戳同样 `+00:00`） | ✅ |
| 分页 | `pageNum/pageSize/orderByColumn/isAsc`，`reasonable` 越界回夹末页 | 同（`dao::resolve_page`） | ✅ |
| `orderByColumn` 白名单 | `SqlUtil.escapeOrderBySql` + 仅允许字母数字下划线点 | 同（`valid_order_column`） | ✅ |
| `fuzzyFields`/`groupBy`/`countField` 白名单 | Java 只用 ES DSL（字段名进 mapping，不进 SQL）；未知字段在 ES 上为 0 命中，不报错 | C++ 的 ES 降级路径会把字段名拼进 PG SQL，因此新增**实体已知列白名单**（`service::guard_query_field`，`optimization.h`）：未命中直接 `BindError(400)`（Spring 默认错误信封），值参数仍走字面量转义。行为差异：Java 对未知字段返回空结果，C++ 返回 400（安全加固，见 `tests/test_main.cpp::test_query_field_whitelist`） | ⚠️ 有意的安全加固 |
| 未分页时 | `TableDataInfo.total` 仍返回总行数 | 同（先 `count_rows`） | ✅ |
| CORS 响应头 | Java **源码无全局 CORS 配置**；运行实例存在 CORS 处理器：跨域预检被拒返回 `403 Invalid CORS request`，实际跨域请求继续且不带 ACAO，响应带 `Vary` | 按 Spring `CorsConfiguration`/`DefaultCorsProcessor` 语义实现（见 §6.2），默认等价 `applyPermitDefaultValues()`；预检通过 200、白名单不匹配 403、`*`+credentials 返回 500 | ✅ 语义一致（配置可覆盖） |
| `Content-Type` | `application/json`（错误信封）/`application/json;charset=UTF-8`（控制器） | 同 | ✅ |

## 2. 序列化（Jackson → nlohmann/json）

| 项 | 差异 | 结论 |
|---|---|---|
| `Long`/`long` | 本项目**未**启用 RuoYi 的 `ToStringSerializer`，Java 实测输出数字 | ✅ C++ 输出数字 |
| `BigDecimal` | Jackson/fastjson2 保留标度（`1.2300` 原样输出） | ✅ `dao.cpp::convert_value` 的 `Decimal`（含元数据中标为 `Double` 的列——Java 域类无 `Double` 字段）分支用 `json_raw_decimal()` 以原始字面量输出并保留尾零；`json_dump()` 在序列化时还原为未加引号的数字。见 `tests/test_main.cpp::test_decimal` |
| 日期 | `@JsonFormat("yyyy-MM-dd HH:mm:ss")` / `"yyyy-MM-dd"` | ✅ 元数据 `FType::DateTime/Day` 复刻 |
| `java.util.Date`（无注解处） | Jackson 默认 ISO-8601/时间戳（取决于 `WRITE_DATES_AS_TIMESTAMPS`） | ✅ 统一按实体注解的 pattern 输出（Java 侧实体均带注解） |
| `null` 字段 | Jackson 默认**保留**键、值为 `null` | ✅ 同 |
| 未知字段 | `FAIL_ON_UNKNOWN_PROPERTIES` 默认 true（`@RequestBody` 会 400） | ⚠️ C++ 对 JSON body 中多余字段**忽略**；本项目请求体均为 `Map`/`TrailInfo`，无 400 差异 |
| 中文 | UTF-8 原样（不转 `\uXXXX`） | ✅ 实测一致 |

## 3. 数据库访问（MyBatis + Druid + pgjdbc → 自实现 wire v3 + 元数据 DAO）

| 项 | 说明 | 结论 |
|---|---|---|
| 驱动 | 自实现 PG v3：启动包、MD5 认证、SASL 认证、简单查询协议、错误字段解析 | ✅ 协议层等价；**不支持** SSL、`COPY`、游标、预处理语句（`Parse/Bind/Execute`） |
| 认证 | MD5：`md5(md5(password+user)+salt)`；SASL 支持两种派生：**openGauss** `SHA256(SHA256(password)‖salt)` 与 PostgreSQL `PBKDF2-HMAC-SHA256` | ✅ 两种均已用独立计算的向量校验（见 `tests/test_main.cpp::test_pg_auth`）；`db.auth-mode`（`CM_PG_AUTH_MODE`）可选 `auto`/`md5`/`opengauss-sha256`/`scram-sha-256`。`auto` = 按 openGauss 派生；**认证失败不再换算法重试**（重试本身也是一次失败登录，会消耗 `failed_login_attempts`） |
| 连接池 | Druid `initial-size 5 / min-idle 5 / maxActive 20 / maxWait 60000` | ✅ `PgPool` 同参数语义（惰性建连、空闲复用、超时） |
| 凭据守卫 | Java 侧由外部注入口令；C++ 口令走 `${CM_PG_PASSWORD}` 或 `configs/config.local.yaml` | ✅ 启动阶段校验：为空/未展开占位即退出（退出码 1），**不建 socket、不发认证**（`src/db/auth_guard.cpp`、`src/main.cpp`） |
| 认证失败熔断 | Java 无此机制（Druid 会反复重建连接，连续失败会把账号锁死） | ✅ 认证类错误（`28P01`/`28000`）后进程内停止重建连接，日志「已停止重试，避免触发账号锁定」；`druid.reconnect-after-auth-failure` 默认 `0`（关闭），可显式放宽 |
| SQL 拼装 | MyBatis XML `<if test>`、`<foreach>`、`resultMap`、`select_sql/order_sql` | ✅ 固化在 `src/meta/entities_generated.h` 的 `filters/select_sql/order_sql` |
| `agent_pk` 主键 | Java XML 用 `t.agent_pk` 过滤，但物理列是 `id` | ✅ 取 `filters` 的物理列（与 Go/Python 的修正一致） |
| 查询列 | Java 用 `<include refid="selectXxxVo"/>` 列清单 | ⚠️ 部分实体（如 `odsSzdnGantry`/`odsSzdnGantryIp`）元数据用 `SELECT *`；`project_row` 只输出 `resultMap` 同名字段，**响应与 Java 等价**，但会多取无关列的带宽 |
| 事务 | Spring `@Transactional`（本项目实际未使用） | ⚠️ C++ 无声明式事务；写操作均为单条语句，天然原子 |
| 隔离级别 | 默认 `READ_COMMITTED`（服务端默认） | ✅ 未显式设置 |
| 主键类型 | 一律按字符串读取，避免精度丢失 | ✅ |
| `timestamp without time zone` | JDBC 按 JVM 时区（`Asia/Shanghai`）解释 | ✅ 按 `+08:00` 锚定后再格式化（`timeutil::from_db_text`） |

## 4. 缓存（Spring Data Redis → RESP2）

| 项 | 差异 | 结论 |
|---|---|---|
| 连接 | Lettuce 连接池 → 单连接 + 互斥 | ⚠️ 并发吞吐低于 Lettuce 池；语义一致（RESP2、`SELECT db`、`AUTH`） |
| 值编码 | Java 侧 `RedisTemplate` 默认 JDK 序列化，部分键用 FastJson | ⚠️ C++ 统一按 **JSON 文本**读写；与 Java 进程**共用同一 Redis 时**，JDK 序列化的键无法互相解析（本项目自建的 `car_*`/`sys_config:*` 键均为 JSON，一致） |
| 键名 | `Constants.java` 常量 | ✅ 全部按原常量（`car_list_jc`、`js_car_snapshot`、`DATE_BorderWeighingCapture:` 等） |
| 过期 | `setex`/`expire` 语义 | ✅ |
| 降级 | Redis 不可用时 Java 抛异常/返回空 | ✅ 连接失败仅 WARN，读缓存走 DB 兜底 |

## 5. 定时任务（Spring `@Scheduled` / Quartz cron → `src/scheduler`）

| 项 | 差异 | 结论 |
|---|---|---|
| cron | Spring 6 段（秒 分 时 日 月 周），支持 `* ? a/b a-b a-b/s 逗号`；周字段 0/7=周日、1=周一；日/周同时受限为 AND；第 7 段（年）非法 | ✅ 独立模块 `src/scheduler/cron.{h,cpp}`，语义以 spring-context 5.3.6 实证为准（`0/3`=0,3,…,57；`5/15`=5,20,35,50），按 `+08:00` 墙钟计算；注册时 `cron_validate` 预检并告警 |
| 触发模型 | 单线程 `ThreadPoolTaskScheduler`（默认池大小 1）→ **不会重入** | ✅ 每任务 `std::atomic<bool> running` 防重入，行为一致 |
| fixedRate | `initialDelay=0`，启动即执行一次 | ✅ 同（启动日志可见首轮执行） |
| 丢失检测周期 | `@Scheduled(fixedRateString="${detection.interval-minutes:30}000")` —— 占位符与字面量 `"000"` 拼接，默认 **30 秒**（键名叫 minutes，实际按秒） | ✅ 同（`interval_minutes * 1000`，修复原 `*60000` 把周期放大 60 倍的问题） |
| 任务清单 | 5 个 cron + 5 个固定间隔（检测/补偿/离线/延迟/一致性） | ✅ 共 10 个 |
| `CarTask` | Java 中全部方法体被注释 | ❌ 不注册（与 Java 等价） |
| 一致性任务 | `consistency.reconcile.enabled=false` 时直接返回 | ✅ 同 |

## 6. 消息中间件（Kafka / Pulsar）

### 6.1 Kafka（librdkafka 2.6.1 → `KafkaProducerConfig` / `KafkaProducerService`）

| 项 | Java 行为 | C++ 行为 | 结论 |
|---|---|---|---|
| 客户端 | Spring Kafka `KafkaTemplate` + `DefaultKafkaProducerFactory` | librdkafka C API（`src/mq/kafka_producer.cpp`），异步发送 + delivery 回调 | ✅ |
| topic | `kafka.topic.snapshot-flow`，默认 `ods-rt-szdn-snapshot-flow` | 同（`kafka.topic.snapshot-flow`） | ✅ |
| key | `StringSerializer`，值为 `dataId` | 同（UTF-8 原文，空时从 payload 的 `dataId` 取） | ✅ |
| value | `JsonSerializer`；可靠性消息为 `ReliableMessageWrapper`，字段顺序 `messageId,dataId,checksum,operationType,data,timestamp,version` | 同（`ordered_json` 保持声明顺序）；`checksum = md5(data JSON)` | ✅ |
| 消息头 | JsonSerializer 默认写 `__TypeId__` | 同（`...$ReliableMessageWrapper`；DB 重试为 `com.alibaba.fastjson2.JSONObject`） | ✅ |
| 生产者配置 | `acks=all`、`retries=MAX`、幂等、`max.in.flight=5`、`batch=16384`、`linger=10`、`buffer=33554432`、`lz4` | 同名配置逐项映射（`buffer.memory` → `queue.buffering.max.kbytes`） | ✅ |
| 发送语义 | 异步，不阻塞请求；成功回调 `updateStatusById(1)` + `handleKafkaAck` | 同（delivery 回调更新 `kafka_message_record` + Redis 状态 `SENT`） | ✅ |
| 失败处理 | 失败回调 `incrementRetryCount` + 指数退避（`2^retry * 1000ms`，默认 5 次），超限进死信 | 同（`reliability.max-retry-count=5`；死信写 Redis `DEAD` + `kafka_message_record` `status=3`） | ✅ |
| DB 重试任务 | 每 30s 查 `status IN (0,2) AND retry_count < 10`，异常休眠 60s | 同（`kafka.retry-interval-ms` / `retry-error-interval-ms`） | ✅ |
| Redis 可靠性键 | `reliability:msg:content:<id>` / `reliability:msg:status:<id>`（24h） | 同 | ✅ |
| 超时检测 | `scheduleTimeoutCheck`：发出后 `message-timeout-ms`（默认 30s）读状态，非 `CONFIRMED` 即 RPUSH `reliability:timeout:queue` + 告警 | 同（`kafka_producer.cpp` 的 `schedule_timeout_check`/`process_due_timeouts`，独立线程、降级模式亦生效；判定逻辑 `reliability_timed_out` 有单测） | ✅ |
| 无 broker | 应用可启动，发送在后台重试 | 同（`rd_kafka_new` 不建连；失败走回调） | ✅ |
| 降级路径 | 无 | `kafka.fallback-redis=true` 或 `kafka.enabled=false` 时写 `mq:pending:<topic>`（默认关闭） | ✅ 新增可选项 |
| SnapshotFlowSyncService | `@PostConstruct` 全量+增量把表数据推 Kafka | ✅ 已迁移（`src/service/snapshot_flow_sync.cpp`）：2 线程、`sync.batch-size=1000`、批间 `sleep(100ms)`、增量 `sleep(interval)` 且异常按同间隔重试、游标键 `snapshot_flow:last_sync_id` / `snapshot_flow:last_sync_time`、`sync.full-sync-enabled` 默认 true | ✅ |
| 重试补偿 | `DataReliabilityService.retrySend` 从待发队列取回重投 | ✅ 同（经 `mq::deliver` 走 Kafka；开关打开时仍走 Redis 队列） | ✅ |
| Pulsar 消费者 | `SnapshotFlowPulsarConsumer` / `DebeziumReadonlyPulsarConsumer` 的 `@Service` **在源码中被注释**，未注册为 Bean | ✅ 不启动（与 Java 运行时一致） | ✅ |
| RocketMQ | `RocketMqConsumer` 注解被注释 | ❌ 不适用 | — |

### 6.2 CORS（Spring `CorsConfiguration` → `src/http/cors.cpp`）

| 项 | Java 行为 | C++ 行为 | 结论 |
|---|---|---|---|
| 源码配置 | **无**（`WebConfig`/`SecurityInterceptor` 整体注释；Python 迁移指南亦确认） | 提供配置化实现，默认 `cors.enabled=true`、`allowed-origins=*`、`allowed-methods=GET,HEAD,POST`、`allowed-headers=*`、`max-age=1800`、`allow-credentials=false`（等价 `applyPermitDefaultValues()`） | ✅ 可覆盖 |
| 预检位置 | CORS 处理器在业务路由之前 | 同（`OPTIONS` 路由统一先调用 `apply_cors`） | ✅ |
| 预检通过 | 200 + `Allow` + `Access-Control-Allow-*` + `Vary` | 同（空 body；`Allow` 取实际路由方法 + HEAD/OPTIONS） | ✅ |
| 预检被拒 | `403`，`text/plain;charset=ISO-8859-1`，body `Invalid CORS request` | 逐字节一致 | ✅ |
| 实际跨域请求 origin 不被允许 | 继续业务，不写 ACAO，带 `Vary` | 同 | ✅ |
| `allowedOrigins=*` + `allowCredentials=true` | Spring 抛 `IllegalArgumentException` → 500 | 同（Spring 错误信封 + 相同提示文案） | ✅ |
| `allowedOriginPatterns` | 通配模式匹配后回显实际 origin | 同（`*` 转正则，大小写不敏感） | ✅ |
| 同源请求（Origin == Host） | 不属于 CORS，不处理 | 同（`CorsUtils.isCorsRequest` 等价） | ✅ |
| 非 CORS 请求 | 不受影响 | 同（仅 OPTIONS 兼容 Spring `HttpOptionsHandler` 的 200 + Allow） | ✅ |

## 7. Elasticsearch（RestHighLevelClient → httplib REST）

| 项 | 差异 | 结论 |
|---|---|---|
| 调用方式 | 官方 Java 客户端 DSL/bulk/scroll | ✅ 直接 REST：`_search`、`_search/scroll`、`_bulk`、Basic Auth |
| 索引创建 / ILM | 配置 `auto-create:false`、`attach-ilm:false` | ✅ 不主动建索引；缺失时 `_search` 失败 → 降级 |
| 降级 | 项目文档要求 ES 不可用时回落 GaussDB | ✅ 30 秒冷却 + `WARN` 日志后走 PG |
| 超时 | `connection-timeout/socket-timeout=30000` | ✅ |

## 8. 运行时 / 并发 / 内存

| 项 | 说明 | 结论 |
|---|---|---|
| 反射、注解、动态代理 | Spring 的 DI/AOP/`@Autowired`/`@Transactional` 依赖反射与代理 | ❌ C++ 无对应物。替代：显式单例 + 显式函数注册 + 元数据表；**无 AOP 切面** |
| GC | JVM 自动回收 | ❌ C++ 显式所有权：`std::shared_ptr`/栈对象/`unique_ptr`；连接与线程均 RAII |
| 线程池 | Tomcat `max-threads`、`@Async` 线程池 | ⚠️ httplib 固定 16 线程；SysTest 的 `syncSuspiciousCar1..10` 用 detached 线程（与 Java `CompletableFuture.runAsync` 等价） |
| Kafka 后台线程 | Kafka 客户端网络线程 + 重试调度线程 | ✅ 1 个 poll 线程（delivery 回调/到期重试）+ 1 个 DB 重试线程（30s/60s） |
| 类加载 / 热部署 | DevTools 热重启 | ❌ 需重新编译链接 |
| 日志 | logback：`时间 [线程名] 级别 logger - msg` | ⚠️ 格式复刻，`[线程名]` 改为**线程 ID**（`[96471]`） |
| 配置刷新 | `@RefreshScope`/Nacos | ❌ 不支持热刷新，改配置需重启 |

## 9. 运维注意事项

1. **openGauss 账号锁定**：连续失败登录会触发 `28000 The account has been locked.`，此时**新连接**（含 Java/Python/C++）全部被拒，但**已建立**的连接仍可工作。解锁需在 DB 侧执行 `ALTER USER <user> ACCOUNT UNLOCK;`（或等待 `password_lock_time`）。这是数据库侧策略，与本次移植无关，但会影响冒烟验证。2026-11-06 14:45、14:51 两次复测（含干净重建后）仍为 `28000`；同期 Java 9902 依赖连接池中已建立的旧连接，仍能返回真实数据，因此可同一请求对比基线，但 C++ 侧无法新建连接。
   **已加固**：口令为空/未展开时启动即退出（不产生任何失败登录）；认证失败后进程内熔断，不再自动重连。因此**当前版本在缺口令/错口令场景下不会再产生失败登录**，重启前请先修正 `CM_PG_PASSWORD` 或 `configs/config.local.yaml`。
2. **端口冲突**：本机常见 9901(Python)/9902(Java)/9903(Go) 被占用。用 `CM_SERVER_PORT` 换端口，避免误判为 `/health` 404。
3. **日志目录**：日志写在**工作目录**下的 `logs/`，请从工程根目录启动。
4. **Kafka 端到端验证条件**：**已具备条件，但当前环境不可达** —— `Test-NetConnection 127.0.0.1 9092` = False，且配置的 `kafka.bootstrap-servers=localhost:9092` 无监听。真实投递验证需要：① broker 监听 `bootstrap-servers`；② 提前创建 topic（或允许自动创建）；③ DB 的 `jl_data01.kafka_message_record` 表可写。可复制命令：

```powershell
# 1) 生产者侧（C++，真实发送）
$env:CM_KAFKA_ENABLED="1"; .\build\car-monit-api.exe -c configs/config.yaml
# 2) 消费端核对 key/value（value 应为 ReliableMessageWrapper JSON，key=dataId）
kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic ods-rt-szdn-snapshot-flow --property print.key=true --from-beginning
# 3) 落库状态（1=成功 / 3=死信）
#    SELECT message_id,status,retry_count,offset FROM jl_data01.kafka_message_record ORDER BY id DESC LIMIT 10;
# 4) 日志核对：搜索 "消息发送成功" 与 offset
Select-String -Path .\logs\car-monit-api.log -Pattern '消息发送成功|offset'
```
5. **SnapshotFlowSyncService**：✅ 已按 Java 源码迁移（`src/service/snapshot_flow_sync.cpp`）。取值：`sync.batch-size=1000`、全量批间 `sleep(100ms)`、增量 `sync.incremental-sync-interval=60000ms`、`sync.full-sync-enabled=true`（默认）、首次增量从 1 天前开始、游标键 `snapshot_flow:last_sync_id` / `snapshot_flow:last_sync_time`。全量会在启动后扫全表（Java 同样如此），如不需要可设 `sync.full-sync-enabled=false`。
6. **CORS 默认值来源**：Java 源码没有 CORS 配置，运行实例的 CORS 处理器配置来源无法从源码确定（疑似空 `CorsConfigurationSource` 或外部配置）。C++ 默认采用 Spring `applyPermitDefaultValues()`；若要与线上 Java 完全一致，可以用 `cors.allowed-origins` 配成相同白名单（或临时配置为空白名单以复现“全部预检 403”）。
