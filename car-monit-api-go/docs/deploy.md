# 部署与运维基线

面向生产的部署约束与观测口径。改动范围对应 `docs/review-2026-11-07/02_技术栈对比与生产优化.md` 的 P0 清单。

## 1. 部署形态：单副本（硬约束）

**必须单副本**，`deploy/k8s.yaml` 用 `replicas: 1` + `strategy: Recreate` 固化这一约束。

原因：调度器（`internal/scheduler`）与 GaussDB→ES 同步**没有分布式锁**。多副本会：

- 每个副本各跑一遍 `syncCurrentTrack` / `syncHistroyTrack` / `processPendingQueue`；
- 增量同步的水位线（`es:sync:watermark:*`）互相覆盖，造成重复推 ES；
- 导出任务状态在进程内存里，多副本轮询会打到没有该任务的实例。

需要水平扩容时，先给会写共享状态的 5 个 job 加分布式锁（redsync 或类似的 Redis 锁），
或把这些 job 拆成独立 Deployment（`replicas: 1`）后再扩 API 副本。

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

## 3. 优雅关闭

`shutdown` 顺序：HTTP Server → 调度器 → MQ 消费者 → 快照同步 → 导出服务 ×2 →
GaussDB→ES 同步 → Kafka 生产者 → Kafka 总线 → Redis → GaussDB。

- HTTP 关闭等待 20s；
- 后台组件共享 **60s 总预算**，逐项扣减，单项超时记 WARN 并继续关闭下一个；
- 因此 `terminationGracePeriodSeconds` 必须 ≥ 90（manifest 已设 90）；
- `preStop` 固定 sleep 5s，给 Service 摘除 endpoint 留时间。

导出任务在收到关闭信号时会先 cancel 进程级 ctx，让 CSV 写完当前批次后落 `FAILED`（任务状态含
「任务被取消」），不会留下半截文件还在被轮询为 `RUNNING`。

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

建议告警：

- `car_monit_consumer_heartbeat_age_seconds > 60` 持续 2 分钟；
- `car_monit_consumer_healthy == 0` 持续 2 分钟（注意本地未配 Kafka 时恒为 0，需按环境排除）；
- `car_monit_dependency_up == 0` 持续 1 分钟；
- `rate(car_monit_http_requests_total{status=~"5.."}[5m]) / rate(car_monit_http_requests_total[5m]) > 0.01`。

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

- 仓库只保留 `configs/config.example.yaml` 模板，密码字段为空；
- 真实密码通过 `APP_` 环境变量注入（键路径 `.`/`-` 转 `_`，大写）：

```
APP_SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD=xxx
APP_ELASTICSEARCH_PASSWORD=xxx
```

- **注意**：Viper 的 `AutomaticEnv` 只对「已出现在 yaml 或代码 defaults 中的键」生效。
  新增配置项必须同时写进 `configs/config.example.yaml` 与 `internal/config/config.go` 的 `Load` defaults。

## 6. 其它必查项

| 项 | 要求 |
|---|---|
| 时区 | `app.timezone: Asia/Shanghai`（默认）。启动时赋值给 `time.Local`；精简镜像缺 tzdata 时固定 +08:00 兜底 |
| 导出目录 | `optimization.export.dir` 在非 local 环境必须是**绝对路径**（Validate 会拒绝相对路径），并挂持久卷 |
| 磁盘 | 导出与 ES 同机时注意磁盘水位；ES 进入 flood stage 会给索引加只读锁（历史事件见 `docs/parity-2026-11-02/11`） |
| 灰度切换 | `trail:realtime:*` / `trail:pending:*` / `car_history_trail:*` / `car_sync_time:*` / `car_curent_trail:*` / `snapshot_flow:last_sync_*` 六族 key 与 Java 的序列化格式不兼容，切换前必须清空 |
| 端口/库号 | 默认 `configs/config.yaml` 是 9901 + Redis db0（与 Java 共用），仅供本地；差分/灰度用 `config.verify.yaml`（9903 + db1） |
