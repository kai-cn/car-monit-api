# car-monit-api (C++) 部署资产

本目录提供 C++ 服务的容器化、本地联调、Kubernetes 与可观测性资产。所有示例凭据均为占位值，
**禁止把真实口令、密钥、内部 IP 凭据提交到仓库**。

## 目录

| 路径 | 用途 |
|---|---|
| `../Dockerfile` | 多阶段生产镜像（Debian 12 + GCC 12 + CMake/Ninja） |
| `../.dockerignore` | 构建上下文排除项 |
| `../docker-compose.yml` | 本地联调：PostgreSQL + Redis + Kafka(KRaft) + 本服务 |
| `initdb/` | compose 初始化 SQL（建 schema、占位表、真实 kafka 表 DDL、种子数据） |
| `k8s/` | Deployment/Service/ConfigMap/Secret 示例/HPA/PDB |
| `monitoring/` | Prometheus 抓取与告警、Grafana 面板 JSON |
| `../docs/RUNBOOK.md` | 运维手册（启停、配置、排障、日志、回滚） |
| `../docs/RELEASE.md` | 发布流程与检查清单 |

## 1. 本地一条命令起环境

前置：Docker Engine 24+ / Docker Compose v2；构建阶段需要访问 GitHub（FetchContent 下载
libpqxx 7.10.0、hiredis 1.5.0、librdkafka 2.6.1 源码包），离线环境见 `.dockerignore` 之外的
CMake 离线参数说明（`FETCHCONTENT_SOURCE_DIR_*`）。

```bash
cd car-monit-api-cpp
cp deploy/.env.example .env          # 可选；修改占位口令
docker compose up -d --build

# 等 api 变为 healthy
docker compose ps
curl -s http://127.0.0.1:9901/health
curl -s 'http://127.0.0.1:9901/metrics?format=prometheus' | head
```

预期：

- `/health` 返回 HTTP 200，`status=UP`（ES 未接入时为 `UNKNOWN`，不判降级）。
- `/metrics?format=prometheus` 返回 Prometheus 文本（`carmonit_requests_total` 等）。
- DB/Redis/Kafka 全部 healthy 后 api 才启动（`depends_on: condition: service_healthy`）。

常用命令：

```bash
docker compose logs -f api                 # 服务日志
docker compose down                        # 停止（保留数据卷）
docker compose down -v                     # 停止并删除数据卷（会重跑 initdb）
docker compose --profile observability up -d   # 额外启动 Prometheus + Grafana
```

可观测性入口：

- Prometheus: http://127.0.0.1:9090
- Grafana: http://127.0.0.1:3000（账号 `admin`，口令为 `.env` 的 `GRAFANA_ADMIN_PASSWORD`）

## 2. 初始化 SQL 与 schema 限制

`deploy/initdb/` 按文件名顺序执行：

1. `01-schema.sql`：创建 `jl_data01` schema、设置 `search_path`、安装 `pg_trgm` / `btree_gin`。
2. `02-placeholder-tables.sql`：**占位 schema**。表名/列名取自
   `src/meta/entities_generated.h`（与 Java 实体、MyBatis resultMap 对齐），类型按实体类型
   近似映射（`TEXT` / `INTEGER` / `BIGINT` / `TIMESTAMP` / `NUMERIC` / `JSONB`），没有分区、
   索引与业务约束。
3. `03-kafka-message-record.sql`：真实 DDL，来源
   `setup_script/sql/10_kafka_message_record.pg.sql`。
4. `04-seed.sql`：最小种子数据，仅用于本地验证 DB 列表接口。

**仓库内没有完整生产 DDL**：`pro-business-api/src/main/resources/sql/partition_scheme.sql`
只有 3 张核心表的设计样例，且列集合与 Mapper 实际查询不完全一致。因此：

- 本地联调：占位 schema 足够让服务启动、`/health` 与非数据库端点通过；部分依赖真实列语义的
  查询可能返回空结果或 SQL 错误，属于预期。
- 预发/生产：必须用数据仓提供的真实 DDL 替换 `02-placeholder-tables.sql`，并按需执行
  `partition_scheme.sql` / `index_optimization.sql` 中的分区与索引方案。

## 3. 环境变量与凭据注入

优先级（从低到高）：

1. `configs/config.yaml` 内置默认值；
2. `configs/config.local.yaml`（同目录覆盖文件，已在 `.gitignore` 中忽略）；
3. 环境变量 `CM_*`（`Config::apply_env_overrides()`，见 `README_CPP.md` §4.2）。

数据库口令必须通过 `CM_PG_PASSWORD`（或 Secret 挂载的 `config.local.yaml`）注入。口令为空或
仍是未展开的 `${...}` 时，进程会在建立任何连接前退出（退出码 1）。

常用变量：

| 变量 | 说明 | 本地默认 |
|---|---|---|
| `CM_SERVER_PORT` | 监听端口 | `9901` |
| `CM_PG_HOST` / `CM_PG_PORT` / `CM_PG_USER` / `CM_PG_DATABASE` | 数据库 | `postgres` / `5432` / `gaussdb` / `RuoYi` |
| `CM_PG_PASSWORD` | 数据库口令（必填） | 占位 `change-me-local` |
| `CM_PG_SSLMODE` | libpq TLS 模式 | 本地 `disable`，生产建议 `require`/`verify-full` |
| `CM_REDIS_HOST` / `CM_REDIS_PORT` | Redis | `redis` / `6379` |
| `CM_KAFKA_ENABLED` / `CM_KAFKA_BOOTSTRAP` | Kafka 开关与地址 | `true` / `kafka:9092` |
| `CM_LEADER_ELECTION_ENABLED` | Redis 选主开关 | 本地单实例 `false` |
| `CM_LOG_JSON` / `CM_LOG_LEVEL` | 结构化日志与级别 | `false` / `info` |
| `CM_SHUTDOWN_TIMEOUT_MS` | 优雅停机等待上限 | `30000` |

完整清单见 `README_CPP.md` §4.2 与 `docs/RUNBOOK.md`。

## 4. 镜像链接策略

- `libpqxx` / `hiredis` / `librdkafka`：静态链接（CMake 中 `BUILD_SHARED_LIBS=OFF`、
  `RDKAFKA_BUILD_STATIC=ON`），运行镜像不需要对应开发包。
- `libpq` / `OpenSSL`：动态链接系统库，运行镜像安装 `libpq5` + `libssl3`。
- `librdkafka` 关闭 SSL/SASL/zlib/zstd/curl（与 Java 侧 PLAINTEXT + LZ4 一致）。

镜像内置 `HEALTHCHECK` 访问 `/health`。注意 `/health` 在依赖 DOWN 时仍返回 HTTP 200
（body `status=DEGRADED`），健康检查只证明进程可服务；依赖级告警由 Prometheus 规则承担。

## 5. 校验方式

- YAML：`docker compose config`（需要 Docker）；无 Docker 时用 YAML 解析器做语法校验。
- Kubernetes：`kubectl apply --dry-run=client -k deploy/k8s`（需要集群/客户端）。
- 镜像：`docker build -t car-monit-api:local .` + `docker compose up`，检查 healthcheck 与
  `/health`、`/metrics`。
- JSON：`python -m json.tool deploy/monitoring/grafana/dashboards/car-monit-api.json`。
