# car-monit-api-go

`pro-business-api`（Java / Spring Boot）的 Go 生产级等价实现。

本目录**不是**语法直译，而是「语义等价 + 逐行对照」的重构：

- 每个 Go 文件头部都有 `// JAVA 对照: <路径>:<行号>`、`// 类/职责:`、`// 对应 Go 文件:`、`// 关键映射:`；
- Java 惯用法翻译成 Go 惯用法处标 `// DIFF:`；行为与 Java 完全一致但有坑处标 `// PARITY:`；
- `Java 独有概念 → Go 等价物` 的决策理由写在对应文件头部注释里，也在本文件第 4、9 节汇总。

**规模**：121 个 Go 文件（107 个源码 + 14 个测试）/ 21,552 行（含注释）；共 **101 条 HTTP 路由** —— 85 条业务路由与 Java 的
85 个端点**一一对应**，另有 16 条 Go 侧探针/运维端点（`/healthz` `/readyz` `/health` `/metrics`
+ 12 条 `/debug/pprof/*`，后两组按配置开关决定是否挂载）；
21 个定时任务（默认配置下 9 个在跑）；53 个单元测试函数（14 个测试文件，零外部依赖）。

---

## 1. 快速开始

```bash
# 1. 依赖（首次）
go mod download

# 2. 编译（输出到 bin/）
go build -o bin/car-monit-api.exe ./cmd/api

# 3. 静态检查
go vet ./...

# 4. 单元测试（不依赖数据库/Redis/ES）
go test ./...

# 5. 启动（需要 configs/config.yaml 里的 GaussDB + Redis 可达）
go run ./cmd/api -config configs/config.yaml
```

启动后自检：

```bash
curl http://localhost:9901/healthz     # 存活
curl http://localhost:9901/readyz      # 依赖就绪（GaussDB / Redis / ES / MQ 消费端）
```

> 没有可用的 GaussDB 时，服务会**在启动阶段**报错退出（`db.Open` 会 Ping）。
> 这是与 Spring Boot 懒连接相反的行为，理由见 `internal/db/db.go:Open` 的 DIFF 注释。
> 只想验证路由装配是否正确，直接跑 `go test ./internal/router/ -v` 即可（<2 秒，零依赖）。

---

## 2. 目录映射表

Java 是「按层分包」（controller / service / mapper / domain），Go 侧保留同样的层，
但把「同一件事必须改两个文件」的样板收敛成泛型 + 表驱动 —— 目录一一对应，文件名一一对应。

| Java 包 / 位置 | Go 包 / 文件 | 说明 |
|---|---|---|
| `com.ruoyi.ProApplication` | `cmd/api/main.go` | 进程入口：显式装配所有 Bean |
| *(application.yml)* | `configs/config.yaml` + `internal/config` | 键路径与 YAML 段落名原样保留，可 diff |
| `common.config` / `common.config.interceptor` | `internal/middleware`、`internal/router` | 拦截器链、统一异常、404 兜底 |
| `common.core.redis.RedisCache` | `internal/cache` | 键值 + `SetNXWithTTL` + `Raw()` 逃生口 |
| `common.utils.*`（DateUtils/StringUtils/CommonUtil） | `internal/utils` | 纯函数，无状态 |
| `common.core.domain.AjaxResult` / `TableDataInfo` | `internal/response` | `{code,msg,data}` / `{total,rows,code,msg}` |
| `base.controller.*`（24 个 Controller） | `internal/handler`（7 个文件） | 19 个基础表走泛型注册器，3+1+1 个特殊 Controller 手写 |
| `base.service.impl.*` | `internal/service`（17 个文件） | 查询优化、同步、可靠性三件套、轨迹拼接、消费者 |
| `base.mapper.*` + `base/mapper/xml/*.xml`（23 个 XML） | `internal/repo`（27 个文件） | 手写 GORM，SQL 与接口放在同一文件 |
| `base.domain.*`（30 个实体 + VO，字段合计 901） | `internal/model`（31 个文件） | JSON tag 与 Java 字段名一致；字段数逐类相等 |
| `mq.config` / `mq.consumer` | `internal/mq` | `MessageBus` 接口 + Kafka 实现 |
| `base.task.*` + 各 `@Scheduled` | `internal/scheduler` | 21 个全部登记：9 个在跑，11 个因 Java 侧整文件注释而禁用，1 个受开关控制 |
| `ElasticsearchConfig` + `EsQueryService` | `internal/es` | 纯 `net/http`，零第三方 SDK |
| *(logback-spring.xml)* | `internal/logging` | `log/slog`，text/json 双格式 |
| *(无，手工编写)* | `tools/*.py` | 一次性代码生成器（model/repo 骨架 + import 修复），产物已入库，改表结构时才需要重跑 |

---

## 3. 全局技术对照表（含给 Java 开发者的阅读提示）

| 关注点 | Java 侧 | Go 侧 | 给 Java 开发者的阅读提示 |
|---|---|---|---|
| Web 框架 | Spring MVC `@RestController` | Gin v1.10 `RouterGroup` | 路由注册从「注解扫描」变成「显式调用」。看 `internal/handler/crud.go:registerReadOnly` 就能明白 19 个 Controller 为什么一共只需要 30 行。 |
| 依赖注入 | `@Autowired` / `@Service` / `@Component` | 构造函数 + `cmd/api/main.go` 显式传参 | 没有容器、没有反射。**依赖缺失 = 编译失败**，而不是启动期 NPE。`main.go` 的 `run()` 就是 Bean 依赖图。 |
| ORM | MyBatis-Plus `BaseMapper<T>` + XML | GORM + 手写 Repo 方法 | `selectList(q)` 变成了 `List(ctx, q, limit)`。PageHelper 的 ThreadLocal 魔法不再存在：分页 = 显式 `limit` + 内存切片（见 `handler/crud.go:handleList`）。 |
| 分页 | PageHelper `startPage()` | 调用方传 `limit=offset+pageSize` 再切片 | 这是**最容易写错**的一处：忘记 `limit` 就会一次拉 8 亿行。所有列表入口都走同一个 `pageParams`。 |
| 配置 | `@Value` / `@ConfigurationProperties` | Viper + 结构体树 + `Validate()` | `application.yml` 的键路径原样保留（连 `spring:` 段名都留着），可以两个文件并排 diff。 |
| 动态数据源 | dynamic-datasource + Druid | 单 `*gorm.DB` + `sql.DB` 连接池 | 本项目只有 master；多数据源在 `internal/db` 内演进，业务层无感。 |
| 事务 | `@Transactional` | `db.Transaction(ctx, fn)` | 显式传 `fn`，没有 AOP 代理陷阱（自调用失效那类问题不会发生）。 |
| 缓存 | `RedisTemplate` / `@Cacheable` | `internal/cache.Client` | `@Cacheable` 没有注解等价物 → `GetOrLoad` 手写 cache-aside。空值穿透用「探测对象」负缓存，见 `service/sysutil.go`。 |
| 消息队列 | Pulsar Consumer + KafkaTemplate + RocketMQ + RabbitMQ | `mq.MessageBus` 接口 + Kafka 实现 | 收/发语义统一成 `Publish` / `Consume(ctx, handler)`。返回 `error` 就是 nack（不提交 offset）。见第 9 节架构决策。 |
| 定时任务 | `@Scheduled(cron="0 */1 * * * ?")` | `internal/scheduler` 自研 cron（80 行） | Quartz 6 段式（秒 分 时 日 月 周）在这里**降级为 5 段式**，`?`→`*`，秒位必须为 0。降级规则有单测（`scheduler_test.go`）。 |
| 线程池 | `ThreadPoolExecutor` / `new Thread().start()` | `go func()` + `recover()` + `context` | goroutine 就是线程池，但 **panic 会杀进程**，所以每个后台协程都必须自带 `recover`。搜 `defer func() { if r := recover()` 能看到所有落点。 |
| 可观测性 | logback + MDC + JFR/Arthas | `log/slog` + `X-Request-Id` + `/debug/pprof/*` | 日志里带 `requestId`（中间件注入 context），对应 MDC。性能排查用 pprof 而不是 jstack。 |
| HTTP 客户端 | `RestTemplate` / `RestHighLevelClient` | 标准库 `net/http` | ES 只用了 5 个动作（search/count/bulk/scroll/delete），自己写比引 SDK 更稳（版本不用跟集群绑死）。 |
| 测试 | JUnit + `@SpringBootTest` | `go test` + `httptest` | 没有「起容器」这一步：路由测试直接编译路由树，<10ms。 |
| 打包 | `mvn package` → fat jar | `go build` → 单文件 | 无 JVM，镜像 ~20MB；交叉编译 `GOOS=linux GOARCH=amd64 go build`。 |

---

## 4. 接口对照表

24 个 Java Controller → 100 条路由。**全部路径与 Java 完全一致**（含 `{bigId}` → `:bigId` 的写法），
前端不需要改 baseURL。

口径核对（去注释后统计）：Java 侧**有效**端点 85 个（`SysUtilController` 里 `/syncTrack` 与
`/syncSuspiciousCar` 整段在块注释内，不计入），Go 侧 100 条 = 85 + 3 条探针/健康
（`/healthz`、`/readyz`、`/health`）+ 12 条 `pprof`。`internal/router/router_test.go` 把其中
44 条关键路由固化成了断言，并额外校验「总数 ≥ 60」防止某个 `Register` 漏调。

| Java Controller | Go 注册位置 | 路由前缀 |
|---|---|---|
| `DwdLcztFwqjcxxController` 等 8 个 `dwd_*` / 基础字典 | `handler/base.go:98-189` | `/base/{fwqjcxx,sfsjcxx,sfzjcxx,feeGantry,...}` |
| `OdsCxztFwqcllsController` | 同上 | `/manager/fwqclls`（注意：不是 `/base`，Java 原样保留） |
| `OdsRtSzdnSnapshotFlowAddcodeController` | 同上 | `/base/snapshotflow`（含 `/listToExport`） |
| `OdsLwzxsfsjFeeRecords01Controller` | 同上 | `/base/feerecords`（含 `/listToExport`） |
| `OdsSzdnProvinceBorderVehicleWeightNewstructureController` | 同上 | `/base/vehicleweight`（含 `/map`） |
| `ZdataTrailTracksController` | 同上 | `/base/trailtracks` |
| `LargeScaleQueryController` | `handler/query.go:53-64` | `/api/v1/large/*` |
| `UnifiedQueryController` | `handler/query.go:66-69` | `/api/v1/unified/*` |
| `ProgressiveQueryController` | `handler/query.go:71-75` | `/progressive/*` |
| `SysUtilController` | `handler/sysutil.go:54-60` | `/base/sysutil/*` |
| `SysTestController` | `handler/selftest.go` | `/base/sysutilTest/*`（3 个已实现 + 12 个 501；501 的原因见 9.2） |

基础表的 4 种形态（由 `ReadOnlySpec` 的开关决定）：

```text
GET {base}/list           → TableDataInfo{total,rows}   对应 startPage() + getDataTable(list)
GET {base}/listToExport   → 裸数组                      对应 listToExport()（Java 只加了 @Excel）
GET {base}/listAll        → 裸数组                      对应不传条件的 selectList(null)
GET {base}/{id}           → 裸对象 / 200 空响应          对应 getInfo()（FlatInfo 控制是否包 AjaxResult）
```

---

## 5. 逐文件对照索引

| Go 文件 | Java 对照 | 迁移中的关键点 |
|---|---|---|
| `internal/config/config.go` | `application.yml:1-297` | YAML 键原样保留；`Validate()` 替代 JSR-303 |
| `internal/db/db.go` | Druid + `@Transactional` | 启动即 Ping（fail fast）；`schema` 固定为实体上的 schema |
| `internal/cache/redis.go` | `RedisCache.java` | `SetNXWithTTL` = `setIfAbsent`（幂等基石） |
| `internal/es/client.go` | `EsQueryService` + `RestHighLevelClient` | 纯 `net/http`；`Bulk` 的 `_id` 即 upsert |
| `internal/response/response.go` | `AjaxResult` / `TableDataInfo` | 字段顺序与 Java 一致，前端零改动 |
| `internal/middleware/middleware.go` | `WebConfig` / `@ControllerAdvice` | `c.Error(err)` + `ErrorHandler` 复刻集中异常 |
| `internal/mq/kafka.go` | `KafkaProducerConfig` + `PulsarConsumerConfig` | 重试/退避/死信/优雅退出全部显式（约 60 行） |
| `internal/handler/crud.go` | 19 个基础 Controller | 泛型注册器；静态段与 `:id` 同级共存已实测通过 |
| `internal/handler/base.go` | `OdsLwzxsfsjFeeRecords01Controller:31-205` 等 | `Decorate` / `DecorateExport` 复刻 list 与 listToExport 的细微差异 |
| `internal/handler/query.go` | 3 个优化查询 Controller | 保留「large 回显枚举名 / unified 回显路径原串」的不一致 |
| `internal/handler/sysutil.go` | `SysUtilController:33-202` | `clearTrailPoints` 在 ByCarNo 为 true、ByTime 为 false |
| `internal/service/large.go` | `LargeScaleQueryService` | ES 优先 + GaussDB 降级；`enumName` 拼装 |
| `internal/service/progressive.go` | `ProgressiveQueryArchitectureService` | 三级策略（10M/100M/1B）逐级降维 |
| `internal/service/sync.go` | `LargeScaleSyncService` | 时间分片 + bulk writer + 水位线 |
| `internal/service/export.go` | `UnifiedExportService` | scroll 分批 → 多文件 → 任务状态机 |
| `internal/service/reliability.go` | `DataReliabilityService:48-723` | 三重确认 + 超时补偿 + 死信入库 |
| `internal/service/loss_detection.go` | `DataLossDetectionService` | 报数 vs 落库条数比对 + 补偿 |
| `internal/service/delay_monitor.go` | `DelayMonitoringService` | 4 段耗时采样（设备→接收→生产→消费→落库） |
| `internal/service/multisource.go` | `MultiSourceDataFlowService` | 6 类源 → TrailBo → Redis 实时拼接 + 乱序队列 |
| `internal/service/trail.go` | `TrailAggregationService` | 缺失点插值 + 字典富集 + 质量评分 |
| `internal/service/sysutil.go` | `SysUtilServiceImpl` | 轨迹查询/富集；8 类流水回源带负缓存 |
| `internal/service/snapshot_consumer.go` | `SnapshotFlowPulsarConsumer:60-448` | `{operationType,data}` → 幂等 → DB + ES |
| `internal/service/producer.go` | `KafkaProducerService` | 本地记录 + 失败重试扫描 |
| `internal/scheduler/scheduler.go` | `@EnableScheduling` / `CronExpression` | 自研 5 段式 cron + ticker |
| `internal/scheduler/jobs.go` | 21 处 `@Scheduled` 的登记表 | `CarTask` 11 个以 `Disabled: true` 登记（Java 侧整文件注释） |
| `internal/service/track_sync.go` | `SysUtilServiceImpl:284-387,1962-1987` + `TrackTask.java:84-160` | `syncTrack` / `carTrackQuery` / `syncHistroyTrack` 三段轨迹缓存链路 |
| `internal/repo/sync_cursor.go` | `OdsLwzxsfsjFeeRecords01Mapper.xml:19-39` + `ZdataTrailFittingMapper.xml:19-39` | keyset 游标；区间是**半开** `[start, end)`，与 XML 的 `<` 逐字对齐 |
| `internal/repo/snapshot_flow_cursor.go` | `OdsRtSzdnSnapshotFlowAddcodeMapper.xml:195-221` + `:71` | 同上；`getMaxSnapshotTime` 的 `COALESCE(MAX(...), now())` 原样保留 |
| `internal/repo/kafka_message_record_ops.go` | `KafkaMessageRecordMapper.xml:32-64` | 重试扫描是 `status IN (0, 2)`：0=待发送也必须重试，只取 2 会漏掉「入库后进程崩溃」的消息 |
| `internal/handler/selftest.go` | `SysTestController.java:22-368` | 3 个已实现 + 12 个 501（响应体带 `javaRef` / `reason` / `porting: blocked`） |
| `internal/router/router.go` | `WebConfig` + 全部 `@RequestMapping` | 中间件链、健康检查、pprof、404 兜底 |
| `cmd/api/main.go` | `ProApplication` | 装配顺序 + 优雅关闭（逆序释放） |

---

## 6. 启动与验证章节（按序执行）

### 6.1 编译与静态检查

```bash
go build ./... && echo BUILD_OK
go vet ./... && echo VET_OK
gofmt -l cmd internal          # 期望：无输出
```

预期输出：

```text
BUILD_OK
VET_OK
```

`golangci-lint`（提示词要求 errcheck / govet / staticcheck）：

```bash
golangci-lint run ./... --disable-all -E errcheck -E govet -E staticcheck
# 预期输出：无 issue（若本机未安装，用 go vet 兜底 —— 二者对 govet 的结论一致）
```

### 6.2 单元测试（零外部依赖）

```bash
go test ./... -count=1
```

预期输出（当前仅 2 个包有测试）：

```text
?    github.com/ruoyi/car-monit-api-go/internal/cache     [no test files]
...
ok   github.com/ruoyi/car-monit-api-go/internal/router    1.3s
ok   github.com/ruoyi/car-monit-api-go/internal/scheduler 0.0s
```

路由清单细看：

```bash
go test ./internal/router/ -run TestRoutesRegistered -v
# 若任一 Java 侧 URL 缺失，会打印 "缺少路由: GET /base/xxx"
```

### 6.3 启动服务

前置：`configs/config.yaml` 中的 GaussDB（`192.168.56.10:5432/RuoYi`）与 Redis（`127.0.0.1:6379`）可达。

```bash
go run ./cmd/api -config configs/config.yaml
```

预期启动日志（关键行，顺序固定）：

```text
INFO 开始装配应用 version=1.0.0 config=configs/config.yaml env=local
INFO GaussDB 连接已建立 maxOpen=20
INFO Redis 连接已建立 addr=127.0.0.1:6379 db=0
INFO Elasticsearch 客户端已创建 baseURL=http://localhost:9200 indexes=[snapshot_flow fee_records trail_fitting]
INFO 定时任务 @Scheduled 登记完成 registered=21 disabled=11
INFO 定时任务 调度器已启动 jobs=21
INFO 定时任务 已按配置禁用 job=syncSuspiciousCar1 spec=0 1 * * *
...（CarTask 的 11 个逐条列出）
INFO [快照消费者] 消费循环已启动
INFO HTTP 服务已启动 addr=:9901 mode=release contextPath=/
```

> 若 `kafka.bootstrap-servers` 为空，会看到 `WARN 未配置 kafka.bootstrap-servers，消息总线降级为本地模式`，
> 此时消费端不启动，`/readyz` 里 `mqConsumer=DOWN` —— 这是预期行为，不是故障。
> 消费端启动后 `mqConsumer` 读的是**消费循环心跳**（45s 无心跳或连续 3 次拉取失败即 DOWN），
> 不是"启动过一次"的常量；默认不改变 HTTP 状态码，`server.consumer-required-for-ready=true`
> 时才升级为 503。

### 6.4 冒烟验证

```bash
# 存活探针（不需要任何依赖）
curl -s http://localhost:9901/healthz
# {"status":"UP","time":"2026-10-31T15:00:00+08:00"}

# 依赖就绪（数据库/缓存/ES 全通时才返回 200）
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9901/readyz
# 200

# 404 兜底：返回的仍是 AjaxResult，而不是 gin 的纯文本
curl -s http://localhost:9901/not-exist
# {"code":404,"msg":"接口不存在: GET /not-exist","data":null}

# 真实业务接口（示例：抓拍流水第一页）
curl -s "http://localhost:9901/base/snapshotflow/list?pageNum=1&pageSize=2" | head -c 400

# 版本
go run ./cmd/api -version
# car-monit-api-go 1.0.0
```

### 6.5 优雅关闭

```bash
# 前台运行时按 Ctrl+C，预期日志：
INFO 收到退出信号，开始优雅关闭
INFO 定时任务 调度器已停止
INFO 应用已退出
```

关闭顺序（在 `cmd/api/main.go:shutdown` 中固定）：
HTTP Server → 调度器 → 同步任务 → 生产者 → Redis → GaussDB。

---

## 7. Java 开发者快速上手

### 7.1 心智模型转换（先记住这 6 条）

1. **没有容器**。`main.go` 里的 `new XxxService(newXxxRepo(db))` 就是 `@Autowired`。
   找不到「这个 Service 被谁注入了」？`grep -r "NewXxxService" cmd/` 即可，没有第二处。
2. **错误是返回值，不是异常**。`err != nil` 必须处理；`handler` 里 `_ = c.Error(err)` 后
   **立刻 return**，由 `ErrorHandler` 中间件统一出 `{code,msg}`。
3. **`nil` 接口陷阱**。`var p *Foo = nil` 装进 `interface{}` 后 `i != nil` 为真。
   所以 `mq.Publisher` 的实现里都有 `if b == nil || b.writer == nil` 的显式判空。
4. **并发不是免费的**。起 `go func()` 前先问：ctx 取消时它会退出吗？panic 会杀进程吗？
   本仓库的答案统一是：`select { case <-ctx.Done(): ... }` + `defer recover()`。
5. **循环变量**。Go 1.22 之前 `for _, v := range` 的 `v` 是同一个变量（本仓库锁 1.24，已修复），
   但**闭包里捕获 `v` 仍然要谨慎**，尤其往 goroutine 里传。
6. **`defer` 在函数返回时执行，不是块结束**。`for` 里 `defer f.Close()` 会攒到最后一次性关闭
   （大量文件句柄爆炸的经典事故）。

### 7.2 Top-5 坑（本迁移中真实踩到的）

| # | 坑 | 现象 | 规避 |
|---|---|---|---|
| 1 | **gin 路由冲突**：`/list` 与 `/:id` 同级 | 老版本 gin 直接 panic；本仓库已实测 gin 1.10 支持静态段与参数段互为兄弟 | `router_test.go` 把这条固化为断言，升级 gin 时先跑它 |
| 2 | **PageHelper 的隐式分页** | `selectList(q)` 在 Java 里被 ThreadLocal 悄悄加了 `LIMIT`；Go 忘了传 `limit` 就全表扫 | 所有列表走 `handler/crud.go:handleList`，`limit = Offset()+PageSize` 只有一处 |
| 3 | **类型断言失败** | Java 的 `(Foo) data` 抛 `ClassCastException` 被外层 catch 吞掉；Go 的 `data.(*Foo)` 失败返回 `ok=false` | `multisource.go:convertToStandardEvent` 全部用 `x, ok :=` 并返回明确 error |
| 4 | **响应头重复写** | 先 `c.Status(400)` 再 `c.JSON(200,...)` → `superfluous WriteHeader` 且 body 丢失 | 只保留一次写出；`requireTimeRange` 只判断不写，由调用方 `c.JSON(status, body)` |
| 5 | **Quartz 6 段式 ≠ 标准 cron** | `"0 30 2 * * ?"` 直接丢给 5 段解析器 → 任务永不触发 | `scheduler.normalizeSpec` 统一降级 + 单测覆盖仓库里全部 21 个表达式 |

### 7.3 调试三件套

```bash
# CPU 火焰图：访问 30 秒采样（对应 Java 的 JFR / async-profiler）
go tool pprof http://localhost:9901/debug/pprof/profile?seconds=30

# 堆内存 / goroutine 泄漏（对应 jmap + jstack）
go tool pprof http://localhost:9901/debug/pprof/heap
curl -s http://localhost:9901/debug/pprof/goroutine?debug=2 | head -50

# 数据竞争检测（对应 JVM 没有的 -race；必须跑）
go test -race ./...
go run -race ./cmd/api

# 断点调试（对应 IDEA Remote Debug，端口 2345）
go install github.com/go-delve/delve/cmd/dlv@latest
dlv debug ./cmd/api -- -config configs/config.yaml
#   (dlv) break internal/handler/crud.go:167
#   (dlv) continue
```

---

## 8. 架构决策（提示词要求「无 1:1 替代时必须显式标注」）

| 组件 | Java 侧 | Go 侧结论 | 状态 |
|---|---|---|---|
| **Pulsar** | `apache/pulsar-client` + `@PulsarConsumer` | `apache/pulsar-client-go` 依赖 CGO（破坏交叉编译与静态单文件镜像） | **需架构决策**。当前用 Kafka 实现同语义（`mq.KafkaBus`），业务层只依赖 `Publisher`/`Consumer` 接口，接真 Pulsar 只需新增一个实现文件 |
| **RocketMQ** | `rocketmq-spring-boot-starter` | `rocketmq-client-go` 维护活跃度低、API 不稳定 | **需架构决策**。同上升级为 `mq` 接口的另一个实现 |
| **RabbitMQ** | `spring-boot-starter-amqp` | `rabbitmq/amqp091-go` 成熟可用 | 可用；当前配置 `rabbitmq.enabled=false`，未接（Java 侧也没有活跃的消费者） |
| **Seata 分布式事务** | 未在本项目使用 | — | 不涉及 |
| **Drools 规则引擎** | 未在本项目使用 | — | 不涉及 |
| **Elasticsearch 客户端** | `elasticsearch-java`（RestHighLevelClient） | 官方 Go SDK 版本必须与集群大版本严格绑定 | 自研 `net/http`（5 个动作），零依赖、可单测 |
| **Quartz / `@Scheduled`** | `spring-context` 的 `TaskScheduler` | `robfig/cron/v3` 可用，但 Quartz 6 段式需隐式适配 | 自研 80 行解析器，降级规则显式可测（`scheduler.go`） |

---

## 9. 未 1:1 移植的部分（含一处**重要发现**）

### 9.1 CarTask 的 11 个任务：Java 侧根本没在跑

`CarTask.java` 的**全部内容**都在块注释里：第 1 行 `/*`、第 231 行 `*/`，
23 个 `/*` 与 23 个 `*/` 成对，剥掉注释后 **0 行代码**（`package` / `import` / `class` 全被注掉）。

所以这 11 个 `@Scheduled` 从未被 Spring 扫描到，一天一次也不会执行。Go 侧的处理方式：

- **登记但不执行**（`Disabled: true`）：任务名与 cron 表达式与 Java 逐行对应，`Scheduler.Start` 会逐条打
  `已按配置禁用`，WARN 里带 `javaRef` / `range` / `wouldCall`（第 11 个任务的 `wouldCall` 是
  `separateSnapshotFlowTimeList`，不是前 10 个的 `syncSuspiciousCarQutaz`）；
- 不实现 `SyncSuspiciousCarQutaz`：它**不是「没人调」**，而是「调到就抛异常」—— L1408 依赖的
  `selectOdsLwzxsfsjFeeRecords01ListNew` 在全部 23 个 Mapper XML 里都不存在，证据见 9.2 第 1 行。
  即便把注释解开，这 11 个任务也只会在线程池里反复抛 `Invalid bound statement`；
- 将来 Java 解除注释时，先补齐 9.2 里那两条缺失的 SQL，再去掉 `Disabled` 并实现方法
  （`jobs.go` 里有指引）。

### 9.2 仍未移植的接口：12 个端点，全部是「Java 侧跑不通」而非「排期未完」

这 12 个端点返回 **501 + `javaRef` + `reason`**（而不是 200），避免调用方误以为执行成功。
每一条都按「接口声明 → XML 语句 → 调用方」三段核对过，证据如下。

| 待续项 | Java 出处 | 结论与证据 |
|---|---|---|
| `syncSuspiciousCar1..10`（10 个） | `SysTestController.java:175-321` → `SysUtilServiceImpl.syncSuspiciousCarQutaz:1245-1635` | L1408 调 `syncFeeRecords`，后者依赖 `OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew` —— 该 id 在全部 23 个 Mapper XML 中**不存在**，接口上也无 `@Select`，MyBatis 必抛 `Invalid bound statement`。调用顺序是 `syncSnapshotFlow`(L1402) 先写一页、`syncFeeRecords`(L1408) 再中断，所以 L1427 之后的跨省/路段分析**永远执行不到** |
| `/syncOdsSzdnGantry` | `SysTestController.java:327-354` | 依赖 `OdsLwzxsfsjFeeRecords01Mapper.selectGantryNum`，同样只有声明没有 SQL；且入参时间串写死为 `"2025-11-01 00-00-00"`（时分秒用了短横线），即使补上 SQL 也过不了 `to_timestamp(...,'yyyy-mm-dd HH24:MI:SS')` |
| `/separateSnapshotFlowTimeList` | `SysTestController.java:359-364` | 产出 `car_uspicious:{日期}:{车牌}`，唯一消费方 `syncSuspiciousCarDB()`（L2644）**没有任何调用方**，且它会用 SHA1 签名向外部 HTTP 接口推数据；输入 `js_car_snapshot:*` 又只由上面那条中断的链路写入 |
| `DataFlowTask.syncGantryCaptureData` | `DataFlowTask.java:55-71` | Java 侧方法体**本身为空**（全被注释）；Go 侧保留同名占位任务以对齐 cron 清单 |
| `MultiSourceDataFlowService.processData` 的调用方 | `DataFlowTask.java:65`（被注释） | Java 侧从未接线；Go 侧同样不接（见 `snapshot_consumer.go` 的 PARITY） |

> 已从前一版的待续清单中**移出**：`syncCurrentTrack`、`syncHistroyTrack`（已实现，见
> `internal/service/track_sync.go`）与 CarTask 的那 11 个（改为「登记 + 禁用」，见 9.1）。
>
> 为什么不去「补」那两条缺失的 SQL：补出来的是一条 Java 从未成功执行过的语句，等于凭空定义一套
> 没人验证过的行为 —— 对 8 亿级表的全扫描尤其如此。要先补齐 SQL 并确认外部接口仍在线，才谈得上移植。

### 9.3 数据访问层：30 个实体 + 64 个 Mapper 方法逐一核对

用「接口声明 → XML 语句 → 调用方」三段法把 `base.mapper` 重扫了一遍，结论是**没有静默缺口**。

实体层：`base.domain` 的 30 个类 ↔ `internal/model` 的 30 个 struct，**字段数逐类相等**
（合计 901 ↔ 901，缺 0）。比对时要把两边的命名差异抹平（Java `agentPk` ↔ Go `AgentPk`），
并处理 Java 里 `private` 与包级私有混写的情况（`TrailBo` 有 9 个字段没写修饰符）。

数据访问层：23 个 Mapper / 64 个方法，差异分三类。

| 类别 | 例子 | 处理 |
|---|---|---|
| 命名不同但已实现 | `selectXxxById` → `GetByID`、`selectXxxList` → `List`、`selectByCursorShard` → `ListByCursorShard`、`getMaxSnapshotTime` → `MaxSnapshotTime` | Go 用 Go 的命名，映射写在文件头「关键映射」 |
| XML 有语句，但 Java 调用方是死代码 | `getLatestTrail` / `getUnFitting`（只被零调用方的 `syncSuspiciousCarQutazNew` 调）、`getLatestTrailByCursor`（只被 `HighPerformanceSyncService` 与 demo 类 `TimeRangeParallelQueryExample` 调 —— 前者是 `@Service` 但没有注入点，仅在一份 md 文档里被提到）、`selectIPSet`（零调用方）、`selectOdsRtSzdnSnapshotFlowAddcodeListNew`（只被中断链路上的 `syncSnapshotFlow` 调） | 不移植；证据写在 `handler/selftest.go` 的 PARITY |
| Java 侧自己就缺 SQL | `selectGantryNum`、`selectOdsLwzxsfsjFeeRecords01ListNew` | 见 9.2 |

`PulsarMessageRecordMapper` 也不移植：Java 里 `PulsarProducerService` 的注解是 `//@Service`
（被注释掉），不是 Bean，Mapper 也就没有消费方；Go 侧统一走 `mq.MessageBus`（Kafka 实现）。

> 顺带记一笔：`pro-business-api/src/main/resources/mapper/xml/PulsarMessageRecordMapper.xml` 只有
> 一行未闭合的 `<?xml version="1.0"`，本身也是坏的 —— 进一步说明这条链路没被使用。

---

## 10. 已知差异与风险（灰度前必须确认）

1. **收费流水的 `JiAnDong` 数据权限无法翻译**
   Java 在 `OdsLwzxsfsjFeeRecords01Controller` 里 `setFlag("JiAnDong")` 收窄数据范围，
   但该表**没有 org 列**，对应 XML（`mapper/xml/OdsLwzxsfsjFeeRecords01Mapper.xml`）也没有该条件。
   Go 侧只能记 WARN 后不过滤 —— **返回集比 Java 更大**。
2. **`selectList` 条件覆盖度已机械核对完**：23 个 Mapper XML 实际都在
   `pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/`（不是常规的 `resources/mapper/xml/`，
   所以第一版迁移误判为「XML 缺失」）。`getHistoryTrail` 已按 `ZdataTrailTracksMapper.xml:116-158`
   逐条对齐（含 `flag` 的 `now() - 180` / `now() - 3` 两个时间窗与 `jl_data01.zdata_trail_fitting` 表名）。
   19 张基础表的 `<if>` 过滤列 与 Go 的 `tx.Where` 列，由
   `docs/parity-2026-11-02/tools/predicates.py` 做了机械对照，结果：**17/19 张零缺项**。
   剩两张是 Java 自己坏，不是 Go 漏实现：
   `feerecords`（XML 里根本没有 list 语句，Java 上该端点恒 500）、
   `fwqjcxx`（33 个过滤条件里 28 个引用的是 SELECT 别名，如 `t.id agent_pk` 却被写成
   `and t.agent_pk = #{agentPk}`，Java 侧带任一这类过滤即 `column does not exist` → 500）。
   本轮另外补齐了 `trailtracks` 缺的 6 个条件（此前 `?type=0` 在 Java 过滤生效、Go 全量返回）。
3. **`total` 已按 Java 语义对齐（P-PAGE-8）**：轨迹查询（`/base/sysutil/carTrackQuery*`）的 total
   走与取数**同谓词**的 COUNT（`CountHistoryTrail`），越界页按 PageHelper 的 reasonable 回夹末页。
   早期版本曾用「本页行数」代替 total，已修复（`docs/parity-2026-11-02/09`）。
4. **`trail:realtime:*` / `trail:pending:*` 不能跨版本共用**：Java 用 JDK 序列化，Go 用 JSON。
   灰度切换前需清空这两类 key（`multisource.go` 头部的 PARITY）。
5. **`KEYS` 命令**：`ProcessPendingQueue` 与 `CheckOfflineDevices` 沿用了 Java 的 `KEYS pattern`，
   生产环境 Redis 数据量大时会阻塞 —— 与 Java 行为一致；V2 已改为 `SCAN` 游标遍历（见 14 节）。
6. **定时任务并发模型**：Java 侧 `SchedulingConfig.java:44` 显式 `setPoolSize(10)`（任务并行，
   同一任务不重入）；Go 每个任务一个 goroutine，语义接近，差异仅在「同一时刻就绪任务 >10」时
   Java 排队、Go 全并行（当前 9 个任务在跑，不触发）。见 `scheduler.go:Start` 的 DIFF。
7. **`saveOrUpdate` 是两次 SQL**（先查后写），与 MyBatis-Plus 一致；高并发下可能出现
   「查到不存在 → 双 insert」的竞态，Java 侧同样存在，未在此修复。
8. **实时轨迹的第二个 Redis 集群未接入**：`syncTrack` 在生产模式下用
   `redisSourceFactory.createSource(redisConfig)` 读 `rediscluster.clusterNodes`（application.yml:138），
   Go 侧还没有这套集群客户端，统一读主 Redis 并在非 local 环境打 WARN。
   **本地（`app.env: local`）不受影响**；生产切换前必须补这个客户端，否则 `car_curent_trail:*` 会一直是空的。
9. **`car_history_trail:*` / `car_sync_time:*` / `car_curent_trail:*` 不能跨版本共用**：
   同 `trail:realtime:*` 的理由，Java 存 JDK 序列化对象，Go 存 JSON。

---

## 11. Go 版本锁定策略

提示词要求 `go 1.26.x`。本机 / 当前 CI 工具链为 **go1.24.1**，`go` 指令高于本地版本会直接拒绝构建
（`requires go >= 1.26`），因此 `go.mod` 暂定为：

```go
go 1.24.1
```

生产镜像升级到 go1.26 后，只需改 `go.mod` 两行（无需改任何代码）：

```go
go 1.26.0
toolchain go1.26.0
```

`go.mod` 里有同样的注释，避免下一个人以为是笔误。

---

## 12. 本次迁移的验证结论

| 检查项 | 命令 | 结果 |
|---|---|---|
| 编译 | `go build ./...` | 通过 |
| 静态检查 | `go vet ./...` | 通过 |
| 格式 | `gofmt -l cmd internal` | 无输出 |
| 单元测试 | `go test ./...` | config / db / handler / mq / repo / router / scheduler / service / utils **9 个包全绿**（53 个测试函数，零外部依赖） |
| 路由完整性 | `go test ./internal/router/ -run TestRoutesRegistered` | 100 条路由，50 条关键路径逐条断言 + 总数下限 60 |
| 自测端点行为 | `go test ./internal/router/ -run TestSelfTestEndpoints` | 3 个已实现返回 200；4 个抽样 501 带 `javaRef` / `reason` |
| cron 降级 | `go test ./internal/scheduler/` | 21 个 Quartz 表达式全部可算下次触发时间 |
| 定时任务登记 | `go test ./internal/scheduler/ -run TestRegisterAllTrackJobs` | 15 条（全依赖为 nil 时）：TrackTask 2 条在跑、CarTask 11 条 Disabled |
| 404 兜底 | `go test ./internal/router/ -run TestRouterMiddlewareChain` | 返回 `{code:404,msg,data}` + `X-Request-Id` |
| 实体字段完整性 | 一次性审计脚本（未入库） | 30 类 / 901 字段 ↔ 901 字段，缺 0 |
| Mapper 方法覆盖 | 同上 | 23 个 Mapper / 64 个方法，0 静默缺口（分类见 9.3） |
| 锚点完整性 | 同上 | 104 个业务迁移 `.go` 文件全部带 `// JAVA 对照:`，且每个文件至少含一处 `DIFF`/`PARITY`/架构决策标记；V2 新增的 3 个基础设施文件（`metrics.go`/`health.go`/`wait.go`）标为「Go 侧新增」 |
| **双端 HTTP 差分回归** | `docs/parity-2026-11-02/tools/parity.py` | 364 条用例 **OK 329 / DIFF 13 / STATUS 22 / NONDET 0**（r12 定稿）；自 r5 起到 r12 零回归（明细见第 13 节） |
| **谓词覆盖度机械对照** | `docs/parity-2026-11-02/tools/predicates.py` | 19 张表 × Java `<if>` 列 vs Go `tx.Where` 列：**17/19 零缺项**，剩 2 张是 Java 侧自身缺语句 |

本轮复核另外修掉三个「注释写对了、代码没做到」的问题（均已带上 PARITY 注释）：

1. `KafkaMessageRecordRepo.SelectFailedRecords` 过滤条件写成 `status = 2`，而 XML 是
   `status IN (0, 2)` —— 会把 status=0（入库后未及发送）的消息永远排除在重试之外。
2. 三个 `ListByCursorShard` 的上界写成 `<=`，而 XML 是 `<`。时间分片是连续的
   `[start, start+n)`，用闭区间会让分片边界那一行被两个 goroutine 各读一次。
3. `kafka_message_record_ops.go` 头部原称「这几个方法没有对应 XML」，实际
   `KafkaMessageRecordMapper.xml` 三条语句都在，已改为逐条标注行号。

> 注意：`internal/repo` 目前**没有任何单测**（无 DB 依赖无法直接跑）。上述三点靠的是人工比对
> XML 与 GORM 调用，不是自动化回归 —— 改这三处 SQL 时请重新对一遍 XML。

---

## 13. 双端 HTTP 差分回归（2026-11-03）

完整过程、取证与逐项归因在 `docs/parity-2026-11-02/`（README + 00~08 + 可重跑工具 + 约 800 份原始报文）。
本节只记基线口径与缺陷统计。

### 13.1 基线状态

| 项 | 值 |
|---|---|
| Java 基准 | `pro-business-api-1.0.jar`，**:9902**（jar 构建 2026-10-31 12:47，与当前源码一致，可作为基准） |
| Go 被测 | `bin/api.exe` + `configs/config.verify.yaml`，**:9903** |
| 数据库 | **共用**同一个 GaussDB `192.168.56.10:5432/RuoYi` |
| Redis | 同实例 **不同库**：Java `db0` / Go `db1` |
| ES | 共用，索引确实存在（7.15.2：`snapshot_flow` 300 / `fee_records` 369 / `trail_fitting` 1 篇）。第五轮实测更正：**`range` 不报错**（时间列 `snapshottime`/`transtime`/`extime` 是 `text`，于是按**词项字典序**比日期 —— 静默给错数据，比报错更危险）；真正失败的是 **`sort`**（`all shards failed`，`Text fields are not optimised for sorting`）。两端都无条件附加该 sort，**路由决策与失败点逐字等价**，故这不是 Go 的差异；要修 mapping 属独立排期（会同时改变两端行为） |
| **磁盘（红线）** | 11-04 实测 **C: 98%、D: 95%**，`D:\pagefile.sys` 22.2 GB 与 ES 数据同卷 → ES 反复进 flood stage 并给索引挂 `read_only_allow_delete` 锁（**磁盘回落后不会自动清**），Java/ES 因此在 18:07 与次日先后停摆。**在释放约 14 GB 之前：不要重启 ES、不要清锁、不要在降级状态下跑差分**。详见 `docs/parity-2026-11-02/11` §1.1 |

> **端口与库号别踩**：`configs/config.yaml`（默认那份）仍是 `port: 9901` + `redis.database: 0`。
> 9901 上是另一个 Python 版迁移；而 db0 是 Java 的缓存库 —— 误用这份配置会用 Go 的 JSON 格式
> 覆写 Java 的字典缓存（Java 用 fastjson2 带 `@type`，读回强转实体失败 → 500）。
> 校验与灰度一律用 `config.verify.yaml`。

> **db0 会被共驻服务清空**：同机还跑着 `ruoyi-admin.jar`(:9988) 等，它会周期性把 `sys_config:*`
> 全量清掉再按自己的表重建。所以「往 Java 侧补缓存键」的拉平方式不可持续，只能改 Go 自己的 db1。
> 本轮即因此把 `sys_config:data_query` 从 db1 删除，让两端都走「缺省 → 受限」分支后才可比。

### 13.2 缺陷统计（364 条用例，同一请求打两端逐字段比）

| 阶段 | OK | DIFF | STATUS | NONDET |
|---|---|---|---|---|
| 初测 | 208 | 101 | 27 | 22 |
| 修分页/过滤 6 项后 | 287 | 24 | 25 | 22 |
| 修工具假差异 + 契约 + 日期绑定后 | 358 | **314** | 22 | 22 | **0** |
| 复跑确认（r6、final-r7、r8，判定逐条一致） | 358 | **314** | 22 | 22 | 0 |
| 补 sysutil 边界用例后（r9） | **361** | **315** | 24 | 22 | 0 |
| 修掉轨迹 `total` 语义后（r10） | 361 | 317 | 22 | 22 | 0 |
| **修掉 `null` vs `""` 与统一查询错误契约后（r11）** | 361 | **329** | **10** | 22 | 0 |
| **补 3 条时间格式用例后（r12，定稿）** | **364** | **329** | **13** | 22 | 0 |

r9 那步 `DIFF` 22→24 **不是回归**：新加的 `pageSize=0/-1` 边界用例把一处此前无人覆盖的差异
显性化了（轨迹查询 `total` 用本页行数，Java=112 / Go=0），原有 358 条判定与上一轮**完全一致**。
r10 是把这条差异修掉后的复跑（2 条 DIFF→OK）；r11 一次关掉两条（12 条 DIFF→OK，含 `TrailBo`
的 null 三态与统一查询的错误契约）；r12 只是**加用例**（把 `04` 里只存在于 suite2 的时间格式宽度
差异提进主表，+3 条 DIFF），共同 361 条**零迁移**。三轮均**零回归**。

**14 次跑批；自 r5 起到 r12 相邻比对零回归**（修复过程中有 3 次抖动：`final→r3` 暴露轨迹投影少 15 列、
`r3→r4` 是日期绑定接得过宽带出的 2 条，全部已收敛 —— 逐轮账见 `docs/parity-2026-11-02/08` §3.3）。
`NONDET` 那 22 条最后查明是工具假差异：`feeGantry`/`snapshotflow` 的行 `id`
由 `StringUtils.getUUID()` 每次重新生成，不能当主键 —— 改用 `datauuid` 对齐后全部转 OK。

已修（**19 项**，其中 15 项在真实服务上回归验证、3 项为可失败断言 + 走查、1 项部分闭环，追溯矩阵见 `07` §2、`09`、`10`）：

| 类别 | 条目 |
|---|---|
| 分页 | `pageSize>1000` 静默截断；`pageSize<=0` 语义相反；越界页未回夹末页（改为先 COUNT 再 LIMIT）；`orderByColumn/isAsc` 被忽略；**轨迹 `total` 用本页行数当总数（补 `CountHistoryTrail`，与取数共用谓词）** |
| 过滤 | `trailtracks` 丢 6 个条件；绑定错误被静默吞（Integer 非法→400、Date 非法→按没传，与 Java 一致）；日期参数按实测格式矩阵重写 |
| 轨迹链路 | `captureTime` 恒空（`time.Parse` 不容尾随时区，Java 的 `SimpleDateFormat` 容）→ 去重整段失效；Go 自补 `ORDER BY` 导致多记录车牌**换行**；历史轨迹**少投影 15 列**（2162 个字段恒 null）；相对时间窗缺 `extime <= now()` 上界 |
| 契约 | 非法/缺失请求体应 400；结尾斜杠不应 404；行 `id` 应为 32 位无横线；**`TrailBo`/`TrailInfo` 的 `null` / `""` / 有值三态（27 字段改 `*string`）**；**统一查询降级失败不再往上冒 500（对齐 Java `query()` 永不抛）** |

剩余 **35 条**（= r12 的 13 DIFF + 22 STATUS）**没有一条是 Go 把数据算错**，逐条归因见 `10` §6：

| 性质 | 条数 |
|---|---|
| Java 端点自身 500（缺 bound statement、别名当列名、`#{id}` 无 getter、`TooManyResults`） | 22 |
| 404/405 响应体形状（Spring 错误体 vs `AjaxResult`，待决策） | 6 |
| Java 的 FEE/TRAIL 降级 SQL 因表名缺 schema 恒失败 → Java 空、Go 有值（**Go 正确**，待业务确认） | 4 |
| 时间格式宽度：Java `Timestamp.valueOf` 只认 `yyyy-MM-dd HH:mm:ss`，纯日期与带 `T` 一律空集，Go 更宽能查出数据 | 3 |

（第五轮之后，`TrailBo` 空串 vs `null` 这一类**残余已归零** —— 原 r10 账上的 11 条全部转 OK，
且 Java 合法的 19 处 `""`（`imagesArry` 17 + `devName` 2）没有被翻转。）

**第六轮定论**（`docs/parity-2026-11-02/11`）：

- 上面那 3 条时间格式差异**建议不复刻**。读完 `UnifiedQueryService` 后确认 Java 的"空集"
  不是格式策略，而是两次失败的级联：`:183` 解析失败→"保守走 ES"→`:245` sort 打在 `text` 列抛错
  →`:137` 降级→`:321` 用同一个严格解析器再抛一次→`:143` 返回空。净效果是对合法输入静默返回空。
- **导出成功路径首次跑通**（新建 date-mapping 副本索引、两端临时指向；原索引未动）：
  两端都 `COMPLETED / 300 行 / 1 分片`。产物是 **CSV 不是 xlsx**。
  内容级对比发现 **Java 的 CSV 用标准解析器读不回来**（列数集合 `{4,39}`，`:406` 把 JSON 包进
  引号却没把内部的 `"` 翻倍），Go 是合法 RFC4180（列数恒 4）。
  → 切到 Go 后每个下游读到的列数会从"看起来 39 列"变成规范 4 列，**灰度前必须拿真实消费方验一次**。
  另有一处 Go 侧多余字段：`es/client.go` 的 `parseHits` 给每条文档塞了 `_id`，
  Java 的 `getSourceAsMap()` 没有（detail 键数 37 vs 36），建议去掉。

### 13.3 差分复跑方式

```bash
cd car-monit-api-go/docs/parity-2026-11-02/tools
python parity.py --gen && python parity.py --out r12 --md ../raw/r12.md        # 364 条
python suite2.py                                                              # 29 条补测
python predicates.py                                                          # 19 张表谓词覆盖度
```
写接口默认不执行（`--allow-write` 才跑）；`/large/sync/*` 始终不跑 —— 它会用同 `_id`
覆盖 Java 写进 ES 的 `_source`，之后所有读对比的基准都会失真。

---

## 14. V2 生产化改造（2026-11-08，分支 `car-monit-api-go-V2`）

依据 `docs/review-2026-11-07/` 的两份审阅报告，本轮只做「不改对外契约」的生产加固。
所有新增开关的默认值都保持 V1/Java 行为；部署形态与告警建议见 [docs/deploy.md](docs/deploy.md)。

| # | 改动 | 位置 | 默认行为 |
|---|---|---|---|
| 1 | **GORM 慢 SQL/错误分级**：慢 SQL → `WARN`、SQL 错误 → `ERROR`（原先全部 `DEBUG`） | `internal/db/db.go:gormSlogLogger` | 不变（只是日志可见性） |
| 2 | **`/readyz` 消费端心跳化**：`mq.Heartbeat` 记录 running/lastTick/连续失败；45s 无心跳或连续 3 次拉取失败 → `mqConsumer=DOWN` | `internal/mq/health.go`、`internal/service/snapshot_consumer.go` | 响应体可见；状态码不变 |
| 3 | **消费循环无限重试**：异常 → 5s 退避 → 重启（原实现只重试一次就退出） | `internal/service/snapshot_consumer.go:Start` | 与 Java `while(true)` 对齐 |
| 4 | **优雅关闭补全**：导出服务 `Close()` 接入 shutdown（先 cancel 进程级 ctx 再等）、常驻协程补 recover、后台组件共享 60s 超时预算 | `cmd/api/main.go:shutdown`、`service/export.go`、`service/large.go`、`service/snapshot_sync.go` | 关闭更慢但不再截断 CSV / 不再无限等待 |
| 5 | **Prometheus 指标**：`/metrics`（HTTP RED、依赖健康、消费心跳/耗时、同步计数、连接池） | `internal/metrics`、`internal/router/router.go` | `server.metrics-enabled: true` |
| 6 | **pprof 开关**：`/debug/pprof/*` 从"始终挂载"改为默认关闭 | `internal/router/router.go` | `server.pprof-enabled: false` |
| 7 | **时区固定**：`app.timezone`（默认 `Asia/Shanghai`）启动时赋值 `time.Local`，消除 DB 路径与绑定/JSON 路径双轨 | `cmd/api/main.go`、`internal/config/config.go:ResolveTimezone` | 与 JVM 部署基线一致 |
| 8 | **依赖安全水位**：x/net v0.25→v0.42、x/crypto v0.23→v0.40 等（受 go1.24.1 工具链上限约束） | `go.mod` | 无行为变化 |
| 9 | **CI 门禁**：gofmt(只查)/build/vet/test + govulncheck | `.github/workflows/car-monit-api-go-ci.yml`、`check.bat` | 本地脚本不再 `gofmt -w` |
| 10 | **`KEYS` → `SCAN`**：待处理队列、设备心跳、延迟统计、丢失检测四处 | `internal/cache/redis.go:ScanKeys` + 4 个调用点 | 结果集一致（内部去重） |
| 11 | **缓存击穿防护**：`GetOrLoad` 用 singleflight 合并同 key 并发回源 | `internal/cache/redis.go` | 目前无生产调用点，为后续接入准备 |
| 12 | **请求级超时兜底**：`server.request-timeout`（默认 0=关闭） | `internal/middleware/middleware.go:Timeout` | 关闭 |
| 13 | **配置与部署物料**：`configs/config.example.yaml`（密码置空 + env 注入）、`deploy/k8s.yaml`（单副本 + Recreate + 90s grace）、`docs/deploy.md` | 新增 | 不改现有配置 |

**未做（按「无事实依据不改线上契约」处理）**：

- 调度器分布式锁：当前按**单副本**部署（manifest 已固化 `replicas: 1`），扩容前必须先补锁；
- 接口鉴权：与 Java 一致（`SecurityInterceptor` 整文件被注释），依赖网络层隔离；
- CSV 列结构：Java 产物列数 `{4,39}` 且标准解析器读不回来，Go 是合法 RFC4180（恒 4 列），
  切换前需由下游消费方确认，不在本轮擅自改动；
- gorm / gin / go-redis 的功能性升级：需要独立回归窗口，本轮只升安全相关的 x/*。

**验证**：`go build ./...`、`go vet ./...`、`go test ./...`（9 个包 / 53 个测试函数）全部通过；
`gofmt -l cmd internal` 在 LF 检出下无输出。
