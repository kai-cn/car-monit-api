# car-monit-api（C++）上手指南

> 面向 Java 开发者。原工程：`../pro-business-api`（Spring Boot 2.4.5 / RuoYi）+ `../pro-base-common`。
> 本工程是它的 C++20 一比一移植：**85 个 HTTP 端点 + 10 个定时任务 + 19 张业务表的 DAO**，另加 2 个本工程新增端点：`/health`（依赖连接状态汇总）与 `/metrics`（请求计数/错误/时延）。

---

## 1. 环境要求

| 项 | 要求 | 本项目实测版本 |
|---|---|---|
| 操作系统 | Windows 10/11 x64（**已实测**）；Linux（由 GitHub Actions 的 GCC/Clang job 验证，见 `.github/workflows/cpp-ci.yml`；本机未实测） | Windows 11 |
| 编译器 | **MSVC 2019+（VS2022 已实测）或 MinGW-w64 g++ ≥ 10（需支持 C++20）**；Linux 下 g++ ≥ 10 | MSVC 2022 17.13（cl 19.43）+ Ninja（本轮修复的验证工具链；更早基线曾用 MinGW g++ 14.2） |
| 构建系统 | CMake ≥ 3.20 | cmake 3.30.4 |
| 生成器 | Ninja（推荐）或 MinGW Makefiles / Visual Studio | Ninja |
| 外部服务 | PostgreSQL/GaussDB、Redis、Kafka（broker 不可达不影响启动）；ES 可选（不可达时自动降级） | GaussDB `192.168.56.10:5432/RuoYi`、Redis `127.0.0.1:6379/0`、Kafka `localhost:9092` |

> 说明：**不需要 Conan/vcpkg**。HTTP/JSON 依赖已 vendored 到 `third_party/`：
> `cpp-httplib 0.15.3`（HTTP 服务/客户端）、`nlohmann/json 3.11.3`（序列化）。
> PostgreSQL/GaussDB 客户端使用 **libpqxx 7.10.0 + libpq 17.2**（认证、TLS、协议由
> libpq 处理；本工程只保留 `PgPool`/`PgResult` 接口与连接池语义）：
>   - Linux：安装 `libpq-dev`（CI 已自动安装）；
>   - Windows：CMake `FetchContent` 下载 PostgreSQL 官方（EDB 构建）17.2 二进制包，
>     仅使用其 `include/lib/bin`，URL 与 SHA256 固定；运行时 DLL 自动复制到输出目录。
> Kafka 依赖 **librdkafka 2.6.1**，通过 CMake `FetchContent` 在首次 configure 时下载源码并静态编译（缓存在 `build/_deps`）。
> Redis 使用 **hiredis 1.5.0**（FetchContent 静态编译；TLS 由 hiredis_ssl + OpenSSL 3 提供）。
> 离线构建可预先执行
> `cmake -S . -B build -DFETCHCONTENT_SOURCE_DIR_LIBRDKAFKA=<源码目录> -DFETCHCONTENT_SOURCE_DIR_LIBPQXX=<源码目录>`；
> 或 `-DCM_WITH_KAFKA=OFF` 关闭真实 Kafka、退回 Redis 队列降级路径。

## 2. 依赖安装

- **Linux**：`sudo apt-get install -y ninja-build cmake g++ libpq-dev`（Ubuntu 22.04+）。
- **Windows**：无需手工安装 libpq。首次 configure 会自动下载 PostgreSQL 官方
  17.2 二进制包（约 311 MB）并复制运行时 DLL；请保证可访问
  `get.enterprisedb.com` 与 `codeload.github.com`。
- Kafka 的 librdkafka 与 libpqxx 同样由 FetchContent 获取。

确认工具链在 PATH：

```powershell
cmake --version        # >= 3.20
g++ --version          # >= 10，且支持 -std=c++20
ninja --version
```

若使用 MSVC，请改为 `-G "Visual Studio 17 2022"` 并确保安装了「使用 C++ 的桌面开发」工作负载。

外部服务（PostgreSQL/Redis）不随工程启动，需要你自备；连接参数见第 4 节。

## 3. 构建命令

Debug（开发/排错，默认）：

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j
```

Release（交付）：

```powershell
cmake -S . -B build-rel -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-rel -j
```

产物：

| 文件 | 说明 |
|---|---|
| `build/car-monit-api.exe` | 服务主程序 |
| `build/carmonit_tests.exe` | 单元/契约测试（crypto、分页、路由、序列化、CORS、Kafka 失败路径等） |

> 首次 configure 会下载并编译 **librdkafka 2.6.1**（静态库，约 1–3 分钟；源码缓存在 `build/_deps`）。
> 离线环境：`-DFETCHCONTENT_SOURCE_DIR_LIBRDKAFKA=<源码目录>`；或 `-DCM_WITH_KAFKA=OFF`（MQ 退回 Redis 队列）。

Linux 构建与单测（PG/Redis 协议栈已改用 libpqxx/hiredis，平台差异由依赖库处理）：

```bash
./scripts/ci-linux.sh            # cmake + ninja + ctest 一条龙；可透传额外 CMake 参数
# 等价于：cmake -S . -B build-linux -G Ninja -DCMAKE_BUILD_TYPE=Release
#         cmake --build build-linux --parallel && ctest --test-dir build-linux --output-on-failure
```

> 状态说明：Windows/MSVC+Ninja 与 openEuler 24.03 WSL（GCC 12.3.1 + libpq 15）
> 均已验证构建与 ctest 全绿；CI 工作流 `.github/workflows/cpp-ci.yml`
> 覆盖 Windows MSVC、Linux GCC/Clang、ASan/UBSan、cppcheck 与增量格式检查。

运行测试：

```powershell
ctest --test-dir build --output-on-failure
# 或直接： .\build\carmonit_tests.exe
```

测试用例清单（ctest 只有一个 `carmonit_tests` 可执行文件，内部按函数分组）：

| 分组 | 用例 | 外部依赖 |
|---|---|---|
| 纯离线单测 | `test_utils`、`test_datetime`、`test_crypto`、`test_result`、`test_decimal`、`test_router`、`test_cors`、`test_auth_guard`、`test_query_field_whitelist`、`test_info_envelope_contract`、`test_cron_spring_semantics`、`test_worker_pool`、`test_background_pool_batch`、`test_dao_param_binding`、`test_entity_select_columns`、`test_pagination_bounds`、`test_dict_cache_boundaries`、`test_contract_routes_golden`、`test_local_config_override`、`test_log_json_and_request_id`、`test_log_rotation`、`test_leader_election_failure_paths` | 无 |
| 本地端口/失败路径（不依赖真实服务） | `test_kafka_no_broker`、`test_reliability_timeout`、`test_redis_reconnect_no_deadlock`、`test_pg_pool_connect_breaker`、`test_pg_pool_config_bounds`、`test_pg_conninfo_and_error_mapping`、`test_server_security`、`test_negative_inputs`、`test_health_and_metrics` | 仅 localhost 回环 |
| 条件执行 | `test_db_optional`（需 `CM_TEST_DB=1` + 可用 GaussDB/PostgreSQL）；`test_leader_election_optional_redis`（需 `CM_TEST_REDIS=1` + 可用 Redis） | 真实 DB / Redis |

> CI 无 DB/Redis/Kafka 时，条件用例自动跳过，其余全部执行。

> 源码通过 `file(GLOB_RECURSE ... CONFIGURE_DEPENDS)` 收集 `src/{common,config,db,cache,cluster,es,meta,repo,service,handler,scheduler,mq,router,http}/*.cpp`。
> **新增 .cpp 后无需改 CMakeLists**，重新构建会自动重新 glob（若 IDE 未触发，重跑一次 `cmake -S . -B build`）。

## 4. 配置准备

配置文件：`configs/config.yaml`（可用 `-c` 指定其它路径），结构与 `application.yml` 同名同层级，便于逐键对照。

配置文件支持 `${ENV}` / `${ENV:-默认值}` 环境变量占位，敏感值（如数据库口令）请使用占位而不是明文；`configs/*.local.yaml`、`logs/`、`build/` 已在 `.gitignore` 中排除。

### 4.1 必填项

| YAML 键 | 含义 | 示例 |
|---|---|---|
| `server.port` | 监听端口（Java `server.port`） | `9901` |
| `spring.datasource.dynamic.datasource.master.url` | JDBC 风格 URL，内部解析 host/port/database | `jdbc:postgresql://192.168.56.10:5432/RuoYi?...` |
| `...master.username` / `...master.password` | 数据库账号 | 用户名 `gaussdb`；口令**不写进仓库**：配置文件里放 `${CM_PG_PASSWORD}` 占位，运行时从环境变量展开（见 4.2） |
| `spring.redis.host` / `port` / `database` | Redis | `127.0.0.1` / `6379` / `0` |
| `spring.redis.ssl` / `ssl-cacert` / `ssl-cert` / `ssl-key` | Redis TLS（默认关闭） | 可选 |
| `server.auth.enabled` / `api-key` | API-Key 鉴权（新增，默认关闭） | 可选 |
| `server.rate-limit.enabled` / `requests-per-minute` | IP 限流（新增，默认关闭） | 可选 |
| `server.shutdown-timeout-ms` | 优雅停机等待在途请求的上限（默认 30000） | 超时强制退出 |
| `logging.json` | 结构化日志开关（每行 JSON，含 requestId） | `false` |
| `elasticsearch.host` / `port` | ES（不可达时查询自动降级到 DB） | `localhost` / `9200` |

### 4.2 环境变量覆盖（优先级高于配置文件）

| 变量 | 覆盖项 |
|---|---|
| `CM_SERVER_PORT` | `server.port` |
| `CM_PG_HOST` / `CM_PG_PORT` / `CM_PG_USER` / `CM_PG_PASSWORD` / `CM_PG_DATABASE` | 数据源 |
| `CM_PG_SSLMODE` / `CM_PG_SSLROOTCERT` | PostgreSQL TLS（`disable/allow/prefer/require/verify-ca/verify-full`，默认 `prefer`） |
| `CM_PG_STATEMENT_TIMEOUT_MS` | 语句超时（默认 30000，0=不设置） |
| `CM_REDIS_HOST` / `CM_REDIS_PORT` / `CM_REDIS_PASSWORD` | Redis |
| `CM_REDIS_TLS` / `CM_REDIS_TLS_CACERT` / `CM_REDIS_TLS_CERT` / `CM_REDIS_TLS_KEY` | Redis TLS |
| `CM_ES_HOST` / `CM_ES_PORT` | Elasticsearch |
| `CM_LOG_JSON` | 结构化日志（JSON）开关 |
| `CM_SHUTDOWN_TIMEOUT_MS` | 优雅停机超时 |
| `CM_KAFKA_ENABLED` | `kafka.enabled`（`false` 时退回 Redis 降级队列） |
| `CM_KAFKA_BOOTSTRAP` | `kafka.bootstrap-servers` |
| `CM_KAFKA_FALLBACK_REDIS` | `kafka.fallback-redis`（写入 `mq:pending:<topic>`） |
| `CM_CORS_ENABLED` | `cors.enabled` |
| `CM_CORS_ALLOWED_ORIGINS` | `cors.allowed-origins`（逗号分隔） |
| `CM_CORS_ALLOW_CREDENTIALS` | `cors.allow-credentials` |
| `CM_LOG_LEVEL` | `debug` / `info` / `warn` / `error` |

### 4.2.1 数据库口令与本地覆盖文件

口令有两条注入路径，优先推荐环境变量：

```powershell
$env:CM_PG_PASSWORD = "<真实口令>"      # 当前会话有效
.\build\car-monit-api.exe
```

也可以写入与 `configs/config.yaml` 同目录的 `configs/config.local.yaml`（启动时自动加载并覆盖同名键，文件已在 `.gitignore` 中忽略，不会入库）：

```yaml
spring:
  datasource:
    dynamic:
      datasource:
        master:
          password: <真实口令>
```

**凭据守卫**：启动阶段会校验 `...master.password`，出现以下任一情况时**直接报错退出（退出码 1），不创建任何 socket、不发送认证消息**，因此不会产生失败登录：

- 口令为空或全空白（环境变量未设置）；
- 口令仍是未展开的 `${...}` 占位（`${ENV}` 展开失败时保留原文，便于识别）。

提示信息会明确告知设置 `CM_PG_PASSWORD` 或写入 `configs/config.local.yaml`。

**认证失败熔断**：任何一次认证类错误（`28P01` / `28000`）后，进程进入熔断（`src/db/auth_guard.cpp`），此后连接池不再自动重建连接，日志打印「已停止重试，避免触发账号锁定」；`auto` 模式也不再做“换算法重试”，一次失败只对应一次失败登录。可通过
`spring.datasource.dynamic.druid.reconnect-after-auth-failure`（默认 `0`，即关闭）显式放宽重连次数。修正口令或在 DB 侧解锁后**重启进程**即可恢复。

### 4.3 Kafka（与 Java `KafkaProducerConfig` 一一对应）

| YAML 键 | 默认值 | Java 对应 |
|---|---|---|
| `kafka.enabled` | `true` | —（C++ 开关，默认走真实 Kafka） |
| `kafka.fallback-redis` | `false` | —（降级开关：写 `mq:pending:<topic>`） |
| `kafka.bootstrap-servers` | `localhost:9092` | `spring.kafka.bootstrap-servers` |
| `kafka.topic.snapshot-flow` | `ods-rt-szdn-snapshot-flow` | `${kafka.topic.snapshot-flow}` |
| `kafka.acks` | `all` | `ACKS_CONFIG` |
| `kafka.retries` | `2147483647` | `RETRIES_CONFIG=Integer.MAX_VALUE` |
| `kafka.enable-idempotence` | `true` | `ENABLE_IDEMPOTENCE_CONFIG` |
| `kafka.max-in-flight` | `5` | `MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION` |
| `kafka.batch-size` | `16384` | `BATCH_SIZE_CONFIG` |
| `kafka.linger-ms` | `10` | `LINGER_MS_CONFIG` |
| `kafka.buffer-memory` | `33554432` | `BUFFER_MEMORY_CONFIG`（映射为 `queue.buffering.max.kbytes`） |
| `kafka.compression-type` | `lz4` | `COMPRESSION_TYPE_CONFIG` |
| `kafka.delivery-timeout-ms` | `120000` | Kafka 默认 `delivery.timeout.ms` |
| `kafka.request-timeout-ms` | `30000` | Kafka 默认 `request.timeout.ms` |
| `kafka.max-retry-count` | `10` | `kafka.max-retry-count`（DB 待发记录重试上限） |
| `kafka.retry-interval-ms` | `30000` | `KafkaProducerService` 重试任务间隔 |
| `kafka.retry-error-interval-ms` | `60000` | 重试任务异常后的休眠 |

线协议：`key = dataId`（StringSerializer），`value = JSON`（JsonSerializer），并带
`__TypeId__` 头（`...$ReliableMessageWrapper`），与 Spring Kafka 默认行为一致。

### 4.4 CORS（Spring `CorsConfiguration` 语义）

Java 源码没有全局 CORS 配置（`WebConfig`/`SecurityInterceptor` 整体被注释）。C++ 侧提供
可配置的 Spring 等价实现，默认值等价 `CorsConfiguration.applyPermitDefaultValues()`：

| YAML 键 | 默认值 | 说明 |
|---|---|---|
| `cors.enabled` | `true` | 关闭后完全不处理 CORS |
| `cors.path` | `/**` | 生效路径（支持 `/prefix/**`） |
| `cors.allowed-origins` | `*` | 逗号分隔；`*` + credentials 会按 Spring 规则返回 500 |
| `cors.allowed-origin-patterns` | 空 | 通配符 origin（如 `http://*.example.com`） |
| `cors.allowed-methods` | `GET,HEAD,POST` | 预检与实际请求都校验 |
| `cors.allowed-headers` | `*` | `*` 回显请求头；否则做大小写不敏感白名单匹配 |
| `cors.exposed-headers` | 空 | 回显为 `Access-Control-Expose-Headers` |
| `cors.allow-credentials` | `false` | 为 `true` 时回显 `Access-Control-Allow-Credentials: true` |
| `cors.max-age` | `1800` | `Access-Control-Max-Age` |

预检请求在业务路由/拦截器之前处理：通过返回 200（空 body + `Allow`），origin 不在白名单
返回 403 `Invalid CORS request`；实际跨域请求在 origin 不被允许时仍继续业务，但不带
`Access-Control-Allow-Origin`（与 Spring `DefaultCorsProcessor` 一致）。

Java 的 `application-optimization.yml` 中的 `optimization.*`、`sync.*`、`consistency.*`、`reliability.*`、`detection.*`、`monitoring.*` 已合并进同一个 `config.yaml`，键名保持原样（如 `optimization.query.max-window`）。

## 5. 启动命令

```powershell
# 前台启动，默认配置
.\build\car-monit-api.exe

# 指定配置文件
.\build\car-monit-api.exe --config configs\config.yaml

# 指定端口 + 调试日志（PowerShell）
$env:CM_SERVER_PORT="9910"; $env:CM_LOG_LEVEL="debug"; .\build\car-monit-api.exe
```

也可用脚本：`.\scripts\run.ps1 -Port 9910 -LogLevel debug`

- 日志：控制台 + `logs/car-monit-api.log`（相对**工作目录**，请在工程根目录启动，否则请自行创建 `logs/`）。
- 启动日志会打印实际端口、路由数（86）、调度任务数（10）。

## 6. 验证启动成功

```powershell
curl.exe -s http://127.0.0.1:9901/health
# 指标（JSON）：请求量/错误率/延迟分位/依赖状态/后台池队列深度
curl.exe -s http://127.0.0.1:9901/metrics
# Prometheus 文本格式（可直接被 scrape）
curl.exe -s "http://127.0.0.1:9901/metrics?format=prometheus"
# {"status":"UP"}

curl.exe -s "http://127.0.0.1:9901/base/fwqjcxx/list?pageNum=1&pageSize=1"
# {"total":218,"rows":[{"agentPk":"1",...,"fwqmc":"三清山西服务区"}],"code":200,"msg":"查询成功"}
```

分页/排序/白名单校验：

```powershell
curl.exe -s "http://127.0.0.1:9901/base/gantry/list?pageNum=1&pageSize=5&orderByColumn=gantryCode&isAsc=asc"
```

错误语义（与 Spring 一致）：

```powershell
# 未知路径 -> HTTP 404 + Spring error 信封
curl.exe -s -i http://127.0.0.1:9901/no-such-path
# 参数类型不匹配 -> HTTP 400 + Spring error 信封
curl.exe -s -i "http://127.0.0.1:9901/base/fwqjcxx/list?pageNum=abc"
```

CORS（默认 `allowed-origins=*`，预检通过 200、白名单不匹配 403）：

```powershell
# 普通跨域 GET
curl.exe -s -i http://127.0.0.1:9901/health -H "Origin: http://example.com"
#   Access-Control-Allow-Origin: *

# 预检通过
curl.exe -s -i -X OPTIONS http://127.0.0.1:9901/health `
  -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET"
#   200 + Access-Control-Allow-Methods/Max-Age + Vary

# 预检被拒（先启动时设置 $env:CM_CORS_ALLOWED_ORIGINS="http://localhost:3000"）
curl.exe -s -i -X OPTIONS http://127.0.0.1:9901/health -H "Origin: http://example.com" `
  -H "Access-Control-Request-Method: GET"
#   403 Invalid CORS request（text/plain;charset=ISO-8859-1）
```

Kafka（无 broker 时发送失败进入重试/死信，不影响启动）：

```powershell
# 启动日志出现：Kafka 生产者启动: bootstrap=localhost:9092
# 强制走 Redis 降级队列：
$env:CM_KAFKA_FALLBACK_REDIS="true"; .\build\car-monit-api.exe
# 完全关闭 Kafka（写入 mq:pending:<topic>）：
$env:CM_KAFKA_ENABLED="false"; .\build\car-monit-api.exe
```

> **依赖数据库**：上述列表接口需要 `master` 数据源可用。若数据库不可用，启动仍会成功（Druid 同样懒加载），列表接口返回
> `HTTP 500 {"timestamp":...,"status":500,"error":"Internal Server Error","message":"无法连接数据库 ...","path":"..."}`。
> 无可用 DB 时，可用 `/health` 与 Redis 类端点做最小冒烟。

## 7. 常见启动失败排查

| 现象 | 原因 | 排查/处理 |
|---|---|---|
| 链接错误 `undefined reference to cm::service::...` | 新增 `.cpp` 未被 glob 进 `carmonit_core` | `cmake -S . -B build` 重新配置；确认文件在 `src/**` 下 |
| `端口监听失败: 9901` / `/health` 404 | 端口已被其它实例占用（本机同时跑 Java(9902)/Python(9901) 时常见） | `Get-NetTCPConnection -LocalPort 9901`；换 `CM_SERVER_PORT=9910` 再试 |
| `[28P01] Invalid username/password` 或 `28000 The account has been locked` | DB 账号口令错误；或连续失败登录触发 openGauss 账号锁定 | 核对 `CM_PG_USER/CM_PG_PASSWORD`；锁定需在 DB 侧 `ALTER USER <user> ACCOUNT UNLOCK;`（见 COMPATIBILITY.md）。注意：认证失败后进程已熔断，重启前请先修正口令 |
| `Redis 连接失败`（仅 WARN） | Redis 未启动/地址错误 | `redis-cli -h 127.0.0.1 ping`；缓存类端点会按降级语义返回 |
| `Kafka 生产者启动失败` / 发送一直重试 | broker 不可达、`bootstrap-servers` 错误、topic 未创建 | 启动不会失败；用 `kafka-topics.sh --list` 确认 broker/topic；临时可 `CM_KAFKA_FALLBACK_REDIS=true` 降级到 Redis 队列 |
| `Kafka 配置项无效: ...`（WARN） | 配置键与 librdkafka 名称不一致 | 检查 `kafka.*`，例如 `buffer-memory` 会映射为 `queue.buffering.max.kbytes` |
| 中文乱码/编译告警 `-Werror` 类问题 | 源文件编码或警告升级 | 源文件为 UTF-8；GCC 无需 `/utf-8`，MSVC 已加 |
| 数据库列名找不到（`column "xxx" does not exist`） | 实体元数据的物理列名与库表不一致 | 修改 `src/meta/entities_generated.h` 中的 `column` |

## 8. 目录结构

```
src/
  main.cpp              # 对应 EcBusinessApiApplication + SpringApplication.run
  common/               # StringUtils/DateUtils/Convert/PageUtils/SqlUtil/RedisUtil 的等价工具
  config/               # application.yml -> config.yaml 解析 + @Value 语义
  db/                   # pg.cpp（libpqxx 客户端/池）、dao.cpp（MyBatis XML + PageHelper 等价）
  cache/                # RedisTemplate / RedisCache 等价（hiredis）
  meta/                 # 19 个实体的 @TableField / resultMap / SQL 片段（entities_generated.h）
  mq/                   # KafkaTemplate 等价物（librdkafka 生产者 + 重试/死信）
  service/              # ServiceImpl：dict(字典)、track(轨迹)、ops(可靠性/检测)、optimization(大表查询)
  handler/              # 24 个 Controller -> base/sysutil/systest/optimization 四组注册函数
  scheduler/            # @Scheduled / Quartz cron 等价实现
  http/                 # cpp-httplib 封装 + Spring MVC 参数绑定语义（ctx.h）+ CORS（cors.cpp）
  router/               # 路由装配（build_routes / start_schedulers）
tests/test_main.cpp     # 等价于 JUnit：crypto/分页/序列化/路由/错误码/CORS/Kafka 失败路径
configs/config.yaml     # application.yml（含 optimization profile）的等价配置
third_party/            # httplib、nlohmann（librdkafka 由 CMake FetchContent 获取）
```

## 9. Java 开发者常见坑

1. **没有 Spring 容器**：Bean 由 `Config::instance()`、`PgPool::instance()`、`Redis::instance()` 单例提供；没有 `@Autowired`。
2. **没有 MyBatis**：SQL 由 `src/db/dao.cpp` 按 `src/meta/entities_generated.h` 的元数据拼装；改表结构 = 改元数据。
3. **没有 GC**：连接/线程必须有明确生命周期；HTTP 线程池固定 16（`CPPHTTPLIB_THREAD_POOL_COUNT`），调度线程 detached 且带 `running` 原子量防重入。
4. **异常不再"自动回滚"**：DAO 每条 SQL 独立执行，无 Spring 事务；需要事务的写操作请看 COMPATIBILITY.md。
5. **`Long` 仍然是 JSON 数字**（本项目未启用 RuoYi 的 Long→String 序列化，和 Java 实测响应一致）。
6. **null 与缺键**：`AjaxResult` 的 `data` 为 null 时**整个键消失**（与 Java 一致），不要用 C++ 的 `nullptr` 直觉去判断。
7. **时间**：DB 的 `timestamp without time zone` 按 `+08:00` 锚定，输出统一 `yyyy-MM-dd HH:mm:ss`；不要用本地时区的 `localtime`。
