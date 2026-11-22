# 部署与运维基线

面向生产的部署约束与观测口径。改动范围对应 `docs/review-2026-11-07/02_技术栈对比与生产优化.md` 的 P0 清单。

## 1. 部署形态：默认单副本，多副本需开锁

**默认单副本**，`deploy/k8s.yaml` 用 `replicas: 1` + `strategy: Recreate` 固化这一约束。

原因：定时任务与 GaussDB→ES 同步会写共享状态，无锁的多副本会：

- 每个副本各跑一遍 `syncCurrentTrack` / `syncHistroyTrack` / `processPendingQueue`；
- 增量同步的水位线（`es:sync:watermark:*`）互相覆盖，造成重复推 ES；
- 导出任务状态在进程内存里，多副本轮询会打到没有该任务的实例。

### 1.1 多副本：开启分布式租约锁

```yaml
scheduler:
  distributed-lock:
    enabled: true          # 默认 false；多副本必须 true
    key-prefix: "scheduler:lock:"
    ttl: 5m                # 需大于最慢 job 的常规耗时
```

语义：每次触发前 `SET NX PX` 抢 `<prefix><jobName>`，抢到才执行；执行期间每 ttl/3
用 Lua 校验 token 续约，结束后 compare-and-delete。抢不到说明别的副本在跑，本次触发跳过。

失效场景（务必知晓）：

| 场景 | 后果 | 应对 |
|---|---|---|
| 续约失败（Redis 抖断/主从切换） | 租约到期后别的副本可再执行，出现短暂并发 | 告警「租约续期失败」；保证 Redis 稳定 |
| Redis 完全不可用 | 所有 job 抢不到锁 → **全部跳过**（宁可漏跑不重复跑） | 保证 Redis 可用，或用单副本形态 |
| 进程 SIGKILL | 租约等 ttl 自然过期，最多空转一个 ttl 周期的触发 | ttl 不要设过大（建议 3–10 分钟） |

验证方法：

1. 单副本开启后，行为应与关闭时一致（每个 job 照常执行，日志出现 `分布式租约锁已启用`）；
2. 双副本：同一时刻只有一台出现 `[定时任务] 开始执行 job=syncCurrentTrack`，另一台是调试级 `其他副本持有租约`；
3. Redis 侧 `GET scheduler:lock:syncCurrentTrack`：执行期间有值，结束后消失。

> 仍建议把**写共享状态**的 job 拆成独立 Deployment（`replicas: 1`）后再扩 API 副本；
> 锁只是兜底，不是替代部署形态设计的手段。分布式锁不覆盖导出任务状态（仍在进程内存）。

## 2. 探针语义

| 探针 | 路径 | 说明 |
|---|---|---|
| liveness | `/healthz` | 只回进程存活，不检查依赖 |
| readiness | `/readyz` | 检查 GaussDB / Redis / Elasticsearch；任一不可用返回 503 |
| 兼容 | `/health` | 同 `/readyz`（给不区分两种探针的运维脚本用） |

`/readyz` 响应里的 `mqConsumer` 是**消费循环心跳**（`internal/mq/health.go`）：

- 未配置 `kafka.bootstrap-servers` → `DOWN`（本地降级模式，正常现象）；
- 消费循环卡在 handler 里超过 45s 无心跳，或连续 3 次拉取失败 → `DOWN`；
- 默认 `server.consumer-required-for-ready: false`：`mqConsumer=DOWN` 只体现在响应体，
  不改变 HTTP 状态码（保持 Java 侧「MQ 非强依赖」语义）。
  若 MQ 是关键链路，置 `true`，让 K8s readiness 直接摘流量。

## 3. 优雅关闭时序（回滚/发布前必看）

收到 SIGTERM 后的固定顺序与时间预算：

| 阶段 | 动作 | 预算 |
|---|---|---|
| 1 | HTTP Server 停止接收新请求并等待在途请求 | 20s |
| 2 | 定时任务调度器 Stop（等待在途 job） | 共享 60s |
| 3 | MQ 消费者 Close（当前消息处理完才退出） | 共享 60s |
| 4 | 快照同步 Close（stopCh 打断 sleep） | 共享 60s |
| 5 | 统一导出 / 大表导出 Close（先 cancel 进程级 ctx，再等待） | 共享 60s |
| 6 | GaussDB→ES 同步 Close | 共享 60s |
| 7 | Kafka 生产者 Close → Kafka 总线 Close | 共享 60s |
| 8 | Redis Close → GaussDB Close | 共享 60s |

- 后台组件共享 **60s 总预算**，逐项扣减；任一项超时记 `WARN` 并继续关闭后续组件，
  避免一个卡死的大任务拖住整个进程；
- 因此 `terminationGracePeriodSeconds` 必须 ≥ 90（manifest 已设 90），`preStop` sleep 5s；
- 导出任务被取消时 CSV 落到当前批次为止，任务状态记为 `FAILED` 且 `errorMessage` 含
  「任务被取消」，不会留在 `RUNNING` 造成前端无限轮询。

**回滚方式**：本服务不持有迁移脚本与表结构变更，回滚只需把 Deployment 镜像 tag 指回上一个版本
（`kubectl set image` 或 `kubectl rollout undo`）。回滚前确认两件事：

1. 若曾开启分布式锁，回滚到不支持该配置的镜像前应先把 `scheduler.distributed-lock.enabled`
   从 ConfigMap 移除（旧版本不认识该键，但 Viper 会忽略未知键，风险仅为配置冗余）；
2. 若本次运行改写过 `es:sync:watermark:*` 或 `snapshot_flow:last_sync_*`，旧版本会继续沿用，
   不需要清理；但要清 `trail:realtime:*` 等序列化不兼容的键（见 §6）。

## 4. 可观测性

### 4.1 指标（`/metrics`，Prometheus 文本格式）

默认开启（`server.metrics-enabled: true`）。最小指标集：

| 指标 | 类型 | 说明 |
|---|---|---|
| `car_monit_http_requests_total{method,route,status}` | counter | HTTP RED 的 rate/errors |
| `car_monit_http_request_duration_seconds{method,route}` | histogram | 路由模板级耗时（不含具体 id） |
| `car_monit_dependency_up{dependency}` | gauge | gaussdb / redis / elasticsearch，15s 后台采样 |
| `car_monit_consumer_healthy` | gauge | 消费端心跳是否健康 |
| `car_monit_consumer_heartbeat_age_seconds` | gauge | 距最后一次心跳的秒数（持续增大=卡死） |
| `car_monit_consumer_messages_total{result}` | counter | 消费成功/失败条数 |
| `car_monit_consumer_handle_duration_seconds{result}` | histogram | 单条消息处理耗时（DB+ES 双写） |
| `car_monit_gauss_es_sync_rows_{read,written,failed}_total` | gauge | 同步进度（进程累计） |
| `car_monit_db_pool_*` / `car_monit_redis_pool_*` | gauge | 连接池水位 |

指标口径说明：

- `http_requests_total` 的 `route` 是**路由模板**（`/base/gantry/:id`），不是真实 URL，
  因此时间序列数量受路由数约束（101 条），不会因 id 展开而爆炸；
- `/metrics` 自身不计入指标，抓取流量不会污染业务 RED；
- `dependency_up` 由 15s 后台采样更新，抓取时刻恰好抖动不会误报，但也意味着最长 15s 延迟；
- 同步计数是**进程累计值**，重启归零；需要跨重启的进度请看 Redis 水位线
  （`es:sync:watermark:{snapshot,fee,trail}`）。

建议告警值：

| 告警 | 表达式 | 建议阈值 |
|---|---|---|
| 消费端卡死 | `car_monit_consumer_heartbeat_age_seconds > 60` | 持续 2 分钟 |
| 消费端不健康 | `car_monit_consumer_healthy == 0` | 持续 2 分钟（未配 Kafka 的环境需排除） |
| 依赖不可用 | `car_monit_dependency_up == 0` | 持续 1 分钟 |
| 5xx 比例 | `rate(car_monit_http_requests_total{status=~"5.."}[5m]) / rate(car_monit_http_requests_total[5m]) > 0.01` | 持续 5 分钟 |
| 查询长尾 | `histogram_quantile(0.99, rate(car_monit_http_request_duration_seconds_bucket[5m])) > 5` | 持续 5 分钟 |
| 连接池饥饿 | `rate(car_monit_db_pool_wait_total[5m]) > 0` | 持续 5 分钟（说明 max-open-conns 偏小） |
| Redis 池紧张 | `car_monit_redis_pool_total_conns >= 0.9 * pool-size` | 持续 5 分钟 |

### 4.2 日志

- GORM 的**慢 SQL** 走 `WARN`、SQL 错误走 `ERROR`（`slow-threshold` 由 `spring.datasource...slow-threshold` 控制，默认 5s）；
- 普通 SQL 只在 `logging.level=debug` 且 `log-sql: true` 时输出（`DEBUG`）；
- 日志为 stdout 单出口，由采集端负责轮转；裸机部署需自行接 logrotate 或容器化。

### 4.3 pprof

默认**关闭**（`server.pprof-enabled: false`）。排查问题时临时打开，且只在非公网环境：

```
server:
  pprof-enabled: true
```

## 5. 配置与密钥

- 入库的三份配置（`config.yaml` / `config.verify.yaml` / `config.example.yaml`）**口令字段全部为空**，
  主机名用 `*.example.internal` 占位；`internal/config` 的
  `TestBaselineConfigsContainNoSecrets` 会在 CI 里持续守住这条；
- 真实值两个入口，优先级 **主配置 < 本地覆盖 < `APP_` 环境变量**：

```
# 方式 A：环境变量（推荐部署）
APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD=xxx
APP_ELASTICSEARCH_PASSWORD=xxx

# 方式 B：本地覆盖文件（推荐本地开发）
cp configs/config.local.yaml.example configs/config.local.yaml   # 已 gitignore
```

- 启动日志会打印 `override=<实际合并的覆盖文件路径>`，便于确认用了哪份配置（不含口令）；
- 启动失败的错误文本经过 `utils.RedactString` 脱敏：配置口令、URL-encode 形态、
  `password=`/`token=` 等键值一律替换为 `***`；
- **注意**：Viper 的 `AutomaticEnv` 只对「已出现在 yaml 或代码 defaults 中的键」生效。
  新增配置项必须同时写进 `configs/config.example.yaml` 与 `internal/config/config.go` 的 `Load` defaults。

## 6. 其它必查项

| 项 | 要求 |
|---|---|
| 时区 | `app.timezone: Asia/Shanghai`（默认）。启动时赋值给 `time.Local`；精简镜像缺 tzdata 时固定 +08:00 兜底 |
| 导出目录 | `optimization.export.dir` 在非 local 环境必须是**绝对路径**（Validate 会拒绝相对路径），并挂持久卷 |
| 磁盘 | 导出与 ES 同机时注意磁盘水位；ES 进入 flood stage 会给索引加只读锁（历史事件见 `docs/parity-2026-11-02/11`） |
| 灰度切换 | `trail:realtime:*` / `trail:pending:*` / `car_history_trail:*` / `car_sync_time:*` / `car_curent_trail:*` / `snapshot_flow:last_sync_*` 六族 key 与 Java 的序列化格式不兼容，切换前必须清空 |
| 端口/库号 | 默认 `configs/config.yaml` 是 9901 + Redis db0（与 Java 共用），仅供本地；差分/灰度用 `config.verify.yaml`（9903 + db1），两者都需要各自的 `.local.yaml` 才能连通真实环境 |
| 请求超时 | `server.request-timeout: 0`（默认关闭）。开启后（如 `30s`）基础查询链路获得统一 deadline，慢依赖不再无限挂住 goroutine |

