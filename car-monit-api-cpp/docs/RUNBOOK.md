# car-monit-api (C++) 运维手册（RUNBOOK）

适用范围：`car-monit-api-cpp` 单实例/多实例生产部署与本地联调。部署资产见
`deploy/README.md`、`deploy/k8s/README.md`。

## 1. 启动与停止

### 1.1 直接运行二进制

```bash
cd car-monit-api-cpp
export CM_PG_PASSWORD='<真实口令>'       # 不要写进配置文件/命令历史
./build/car-monit-api -c configs/config.yaml
```

Windows PowerShell：

```powershell
$env:CM_PG_PASSWORD = "<真实口令>"
.\build\car-monit-api.exe -c configs\config.yaml
```

- 默认配置路径 `configs/config.yaml`，可用 `-c` / `--config` 指定。
- 日志目录、导出目录、TLS 证书等相对路径均以**当前工作目录**为基准，建议始终在
  `car-monit-api-cpp` 根目录启动。
- 启动阶段先校验数据库口令；口令为空/仍是 `${...}` 占位时直接退出（退出码 1），
  **不会发起任何数据库连接**（避免失败登录触发 openGauss 账号锁定）。

### 1.2 Docker Compose（本地/单机）

```bash
cd car-monit-api-cpp
cp deploy/.env.example .env      # 修改占位口令
docker compose up -d --build
docker compose ps                # api 应为 healthy
docker compose logs -f api

docker compose stop api          # 优雅停止（SIGTERM）
docker compose restart api
docker compose down              # 停止并保留数据卷
docker compose down -v           # 停止并删除数据卷（会重跑 initdb）
```

### 1.3 Kubernetes

```bash
kubectl -n car-monit-api rollout status deploy/car-monit-api
kubectl -n car-monit-api rollout restart deploy/car-monit-api   # 优雅滚动重启
```

滚动策略 `maxUnavailable: 0, maxSurge: 1`；`terminationGracePeriodSeconds: 45` +
`preStop sleep 10`。进程收到 SIGTERM 后停止接受新请求，最多等待
`server.shutdown-timeout-ms`（默认 30s）排空在途请求；超时强制退出（退出码 1）。

## 2. 配置与环境变量

### 2.1 覆盖优先级（从低到高）

1. `configs/config.yaml`（或 `-c` 指定的文件）；
2. 同目录 `config.local.yaml`（启动时自动加载，按键覆盖；已在 `.gitignore` 忽略）；
3. 环境变量 `CM_*`（`Config::apply_env_overrides()`）。

YAML 值中的 `${ENV}` / `${ENV:-默认值}` 在读取时展开；展开失败会保留原文，
数据库口令守卫会因此判定未配置并退出。

### 2.2 常用配置项

| YAML 键 | 环境变量 | 默认 | 说明 |
|---|---|---|---|
| `server.port` | `CM_SERVER_PORT` | `9901` | 监听 `0.0.0.0:<port>` |
| `server.shutdown-timeout-ms` | `CM_SHUTDOWN_TIMEOUT_MS` | `30000` | 优雅停机等待上限 |
| `server.max-payload-bytes` | — | `1048576` | 请求体上限（1MB） |
| `server.read-timeout-ms` / `write-timeout-ms` | — | `30000` | HTTP 读写超时 |
| `server.auth.enabled` / `api-key` | — | `false` | API-Key/Bearer 鉴权；为空时 fail-closed |
| `server.rate-limit.*` | — | 关闭 | 按 IP 固定窗口限流 |
| `spring.datasource...master.url/username` | `CM_PG_HOST` / `CM_PG_PORT` / `CM_PG_USER` / `CM_PG_DATABASE` | 见 config.yaml | JDBC 风格 URL 解析出 host/port/db |
| `...master.password` | `CM_PG_PASSWORD` | `${CM_PG_PASSWORD}` | 必填；空/未展开直接退出 |
| `...master.sslmode` | `CM_PG_SSLMODE` | `prefer` | `disable/allow/prefer/require/verify-ca/verify-full` |
| `...master.sslrootcert` | `CM_PG_SSLROOTCERT` | 空 | CA 证书路径 |
| `...druid.maxActive/maxWait` | — | `20` / `60000` | 连接池上限与等待 |
| `...druid.reconnect-after-auth-failure` | — | `0` | 认证失败后重建连接次数（0=熔断） |
| `spring.redis.host/port/database` | `CM_REDIS_HOST` / `CM_REDIS_PORT` | `127.0.0.1` / `6379` / `0` | Redis |
| `spring.redis.ssl*` | `CM_REDIS_TLS` / `CM_REDIS_TLS_CACERT` / `CM_REDIS_TLS_CERT` / `CM_REDIS_TLS_KEY` | 关闭 | Redis TLS |
| `kafka.enabled` | `CM_KAFKA_ENABLED` | `true` | false 时走 Redis 降级队列 |
| `kafka.bootstrap-servers` | `CM_KAFKA_BOOTSTRAP` | `localhost:9092` | broker 地址 |
| `kafka.fallback-redis` | `CM_KAFKA_FALLBACK_REDIS` | `false` | 降级写 `mq:pending:<topic>` |
| `elasticsearch.host/port` | `CM_ES_HOST` / `CM_ES_PORT` | `localhost` / `9200` | ES；不可达时查询降级到 DB |
| `elasticsearch.username/password` | —（无 env 覆盖） | — | 生产用 Secret 挂载 `config.local.yaml` |
| `cluster.leader-election.enabled` | `CM_LEADER_ELECTION_ENABLED` | `true` | 多实例单活开关 |
| `cluster.leader-election.key/ttl-ms/renew-ms` | `CM_LEADER_LOCK_KEY`（key） | `car-monit:leader` / `30000` / `10000` | Redis 锁 |
| `cluster.leader-election.fail-open` | `CM_LEADER_FAIL_OPEN` | `false` | Redis 不可用时暂停后台任务 |
| `logging.max-file-mb` / `max-files` | — | `50` / `5` | 日志轮转 |
| `logging.json` | `CM_LOG_JSON` | `false` | 每行 JSON + requestId |
| `logging.level.root/web` | `CM_LOG_LEVEL` | `INFO` / `DEBUG` | 日志级别 |

完整键位与 Java 对照见 `README_CPP.md` §4。

### 2.3 凭据注入（必须遵守）

- 禁止把真实口令、密钥、内部 IP 凭据提交到仓库、镜像、日志或工单。
- 推荐方式：环境变量 `CM_PG_PASSWORD` / Kubernetes Secret / `config.local.yaml`
  （该文件已被 `.gitignore` 忽略，并由 Secret 挂载）。
- 示例值只出现在 `deploy/.env.example` 与 `deploy/k8s/examples/secret.example.yaml`，
  均为占位符。

## 3. 健康检查与指标

| 端点 | 行为 | 用途 |
|---|---|---|
| `GET /health` | 汇总 DB/Redis/Kafka/ES 状态；任一 DOWN 时 `status=DEGRADED`，**HTTP 仍为 200** | 进程存活/容器健康检查 |
| `GET /metrics` | 默认 JSON 指标快照 | 调试 |
| `GET /metrics?format=prometheus` | Prometheus 文本，供抓取 | 监控 |
| `GET /api/v1/large/scale-level` | 只读运行时信息（不查 DB） | 非 DB 冒烟 |

关键指标：

- `carmonit_requests_total` / `carmonit_errors_total` / `carmonit_requests_in_flight`
- `carmonit_request_duration_ms_avg/p50/p95/p99`
- `carmonit_dependency_up{component="db|redis|es|kafka"}`
- `carmonit_dependency_latency_ms{component=...}`（5s 缓存；ES 恒 0）
- `carmonit_worker_pool_pending/active/capacity`
- `carmonit_db_pool_live/max`

注意：`/health` 的 HTTP 200 不代表依赖健康；依赖级判定看
`carmonit_dependency_up` 告警（`deploy/monitoring/alerts.yml`）。

## 4. 日志

| 项目 | 说明 |
|---|---|
| 位置 | 相对工作目录 `logs/car-monit-api.log`；容器内 `/app/logs`（emptyDir/卷） |
| 轮转 | `logging.max-file-mb` × `logging.max-files`（默认 50MB × 5），`0` 关闭 |
| 格式 | 文本；`CM_LOG_JSON=true` 时每行 JSON，含 `requestId` |
| 级别 | `CM_LOG_LEVEL=debug/info/warn/error` |
| 敏感信息 | 不记录口令/token/SQL 明文参数；排障时也不要临时打开 |

关键日志与含义：

| 日志文本 | 含义 / 动作 |
|---|---|
| `已加载配置文件: ...` / `已加载本地覆盖配置: ...` | 配置来源确认 |
| `数据库凭据校验未通过：...` | 口令为空/仍是占位；设置 `CM_PG_PASSWORD` 后重启，**不会发起连接** |
| `数据库连接成功: host:port/db` | 启动期 `SELECT 1` 成功 |
| `数据库连接失败（启动继续，请求时重试）: ...` | DB 不可达；启动未阻断，请求会失败 |
| `Redis 连接失败，缓存相关功能将按 Java 侧降级语义处理` | Redis 不可用；缓存降级，选主暂停 |
| `Kafka 生产者已启动: ...` / `启动失败（继续启动）` | Kafka 可用性；失败仍可服务 |
| `收到停机信号，停止接受新请求（在途请求最多等待 Nms）` | 优雅停机开始 |
| `优雅停机超时（Nms），强制退出（在途请求未完成）` | 超时；进程退出码 1 |
| `端口监听失败: N` | 端口占用/权限不足；进程退出码 1 |
| `未捕获异常导致进程退出: ...` | 顶层兜底；查栈与最近业务日志 |

## 5. 常见故障排查

### 5.1 数据库连不上（`/health` database DOWN/UNKNOWN）

判定依据：

- 日志出现 `数据库连接失败` 或 `/metrics` 中 `carmonit_dependency_up{component="db"} 0`；
- `/health` 的 `components.database.liveConnections` 为 0。

步骤：

1. `CM_PG_HOST`/`CM_PG_PORT`/`CM_PG_DATABASE` 是否正确（注意 `RuoYi` 大小写敏感）；
2. 从宿主机/容器内测试连通：`pg_isready -h <host> -p <port>` 或 `nc -vz <host> <port>`；
3. 检查防火墙/安全组/DNS；
4. TLS 模式是否匹配：本地 PG 无 TLS 时 `CM_PG_SSLMODE=disable`；生产 `require/verify-full`
   并配置 CA；
5. 连接池上限（`druid.maxActive`）与 DB `max_connections` 是否耗尽；
6. 数据库侧 `pg_stat_activity` 是否有大量空闲连接/慢查询。

### 5.2 数据库认证失败（28P01/28000）

判定依据：

- 日志包含 `28P01` / `28000` / `password authentication failed`；
- 之后连接池不再自动重建连接（`reconnect-after-auth-failure=0`，默认熔断）。

步骤：

1. **不要反复重启服务**：每次启动都会产生一次失败登录，可能触发 openGauss
   `failed_login_attempts` 账号锁定；
2. 核对 `CM_PG_PASSWORD`（是否空、是否仍是 `${...}`、是否被 Shell 转义）；
3. 在 DB 侧确认账号状态，必要时解锁/重置口令；
4. 修正后重启进程；如需临时放宽重连，把
   `spring.datasource.dynamic.druid.reconnect-after-auth-failure` 调大（谨慎）；
5. 认证恢复前，HTTP 仍可服务非 DB 端点，但 DB 相关接口会失败。

### 5.3 Redis 不可用

判定依据：

- `/health` `components.redis.status=DOWN`；
- 日志 `Redis 连接失败`；
- 选主相关日志：抢锁失败/续期失败；后台调度暂停（`fail-open=false`）。

步骤：

1. `redis-cli -h <host> -p <port> ping`；
2. 检查认证/TLS（`CM_REDIS_PASSWORD`、`CM_REDIS_TLS*`）；
3. 检查网络与 Redis 内存/最大连接数；
4. 多实例场景确认所有副本连的是**同一个 Redis**；
5. Redis 恢复后选主会自动接管，无需重启；如长期不可用且必须恢复后台任务，
   评估后临时设置 `CM_LEADER_FAIL_OPEN=true`（可能导致多实例重复执行）。

### 5.4 Kafka broker 不可达

判定依据：

- 启动日志 `Kafka 生产者启动失败（继续启动）`；
- `/health` `components.kafka.status=DOWN`；
- 消息发送失败日志/delivery 回调错误；`kafka_message_record` 中 `status=2`、`retry_count` 增长。

步骤：

1. 校验 `CM_KAFKA_BOOTSTRAP`（容器内不能用 `localhost`，要用 service DNS）；
2. `kafka-broker-api-versions.sh --bootstrap-server <host>:9092`；
3. 检查 topic 是否存在/权限、`acks`/幂等配置；
4. broker 不可达不会阻断启动；失败消息按重试策略落库，必要时启用
   `CM_KAFKA_FALLBACK_REDIS=true` 写 Redis 降级队列（`mq:pending:<topic>`）；
5. 恢复后确认积压消息重发，`kafka_message_record.status` 归零。

### 5.5 Elasticsearch 不可用/降级

判定依据：

- `carmonit_dependency_up{component="es"} 0`（ES 为被动状态：未调用时 UNKNOWN；
  调用失败后进入 30s 冷却 DOWN）；
- 查询日志出现 ES 请求失败并回退 DB。

步骤：

1. `curl http://<host>:9200/_cluster/health`；
2. 检查用户名/口令（无 `CM_*` 覆盖，需 `config.local.yaml`/Secret）；
3. 检查索引是否存在、`auto-create` 是否关闭导致写入失败；
4. ES 故障时查询自动降级 DB，但延迟会上升；关注 P99 与 DB 压力。

### 5.6 端口占用

判定依据：日志 `端口监听失败: 9901`，进程退出码 1。

```bash
# Linux
ss -lntp | grep 9901
# Windows PowerShell
Get-NetTCPConnection -LocalPort 9901 | Select-Object OwningProcess
```

处理：停止占用进程，或改 `CM_SERVER_PORT`（同时更新 Service/Ingress/探针端口）。

### 5.7 磁盘/日志增长

- 日志按大小轮转；容器日志由 compose `logging` 限制（10MB×3）；
- 导出目录 `optimization.export.dir`（容器 `/data/export`）需要定期清理；
- 磁盘剩余 < 1GB 时先停止写入并扩容，不要带病运行。

## 6. 优雅重启与回滚

### 6.1 单机/二进制

```bash
kill -TERM <pid>       # 等待不超过 shutdown-timeout-ms
# 确认进程退出码 0（超时为 1）；再启动新版本
```

不要直接 `kill -9`，否则在途请求、Kafka flush、连接池释放都会被跳过。

### 6.2 Kubernetes

```bash
kubectl -n car-monit-api set image deploy/car-monit-api \
  car-monit-api=registry.example.com/car-monit-api:<new-tag>
kubectl -n car-monit-api rollout status deploy/car-monit-api

# 回滚
kubectl -n car-monit-api rollout undo deploy/car-monit-api
kubectl -n car-monit-api rollout undo deploy/car-monit-api --to-revision=<N>
```

### 6.3 Docker Compose

```bash
CAR_MONIT_API_IMAGE=car-monit-api:<new-tag> docker compose up -d api
# 回滚：改回旧 tag 后再次 up -d api
```

回滚前确认数据库 schema 变更向后兼容（本次运维支线不改业务代码/DDL）。

## 7. 多实例注意事项

- 副本数 > 1 时，调度器与全量/增量同步依赖 Redis 分布式锁选主；所有副本必须共享
  同一个 Redis，`CM_LEADER_ELECTION_ENABLED=true`。
- Redis 不可用时后台任务暂停但 HTTP 继续服务（`fail-open=false`），`/health` 显示
  DEGRADED；不要为了让探针变绿而改成 fail-open。
- 滚动发布期间可能短暂出现锁续期竞争；TTL 30s、续期 10s，正常情况下主副本退出后
  30s 内完成接管。
- HPA 扩缩容不影响单活语义，但缩容会触发选主切换，建议保留至少 2 副本（PDB
  `minAvailable: 1`）。
