# car-monit-api (C++) 发布手册（RELEASE）

本手册约束 `car-monit-api-cpp` 的版本构建、镜像标签、灰度与回滚。部署步骤见
`docs/RUNBOOK.md` 与 `deploy/README.md`。

## 1. 发布物

| 产物 | 路径/说明 |
|---|---|
| Linux 可执行文件 | `build/car-monit-api` |
| Windows 可执行文件 | `build/car-monit-api.exe` + libpq/OpenSSL 运行时 DLL（CMake post-build 复制） |
| 运行时配置 | `configs/config.yaml`（口令为 `${CM_PG_PASSWORD}` 占位） |
| 容器镜像 | `registry.example.com/car-monit-api:<version>-<short-sha>` |
| 部署清单 | `deploy/k8s/*`、`docker-compose.yml` |
| 监控资产 | `deploy/monitoring/*` |

发布物中**禁止**包含真实口令、密钥、`config.local.yaml`、`.env`、日志或契约采集数据。

## 2. 版本与镜像标签规范

- 语义化版本：`MAJOR.MINOR.PATCH`，与变更性质对应。
- 镜像标签：`<MAJOR.MINOR.PATCH>-<git short sha>`，例如 `1.4.0-a1b2c3d`；该标签不可变，
  重复发布必须使用新版本号/新 commit。
- 生产只允许引用不可变 tag 或 digest（`@sha256:...`），不要用 `latest`/`main`。
- 每次构建把 `VERSION` / `GIT_SHA` 注入镜像 OCI label：

```bash
docker build \
  --build-arg VERSION=1.4.0 \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  -t registry.example.com/car-monit-api:1.4.0-a1b2c3d \
  car-monit-api-cpp
```

## 3. 发布前检查清单

| # | 检查项 | 判定 |
|---|---|---|
| 1 | 工作区干净，发布 commit 已合入受保护分支 | `git status` 无未提交改动 |
| 2 | CI（Windows MSVC + Linux GCC/Clang + ASan/UBSan + cppcheck）全绿 | 全部 job 通过 |
| 3 | 构建与测试 | `cmake --build` 成功；`ctest --output-on-failure` 全绿 |
| 4 | 契约测试（如本次涉及接口/序列化） | `contracts` diff 无不一致，或差异已评审 |
| 5 | 配置变更 | 新增配置项有默认值，可由 `CM_*`/配置文件覆盖 |
| 6 | 数据库变更 | DDL 向后兼容；回滚不需要破坏性回退；已在预发验证 |
| 7 | 凭据 | 新口令/密钥只通过 Secret/环境变量注入，仓库无明文 |
| 8 | 资源与容量 | requests/limits、HPA、PDB 与目标 QPS 匹配 |
| 9 | 监控 | 新指标/告警已更新 `deploy/monitoring` |
| 10 | 文档 | `docs/RUNBOOK.md`、`docs/RELEASE.md`、`README_CPP.md` 与实际一致 |
| 11 | 镜像 | 非 root、healthcheck 可用、基础镜像/依赖无高危 CVE |

构建命令（Linux，与 CI 一致）：

```bash
cd car-monit-api-cpp
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCM_WERROR=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Windows（MSVC + Ninja，需先初始化开发环境）：

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCM_WERROR=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

## 4. 发布流程

### 4.1 构建并推送镜像

```bash
docker build --build-arg VERSION=<ver> --build-arg GIT_SHA=<sha> \
  -t registry.example.com/car-monit-api:<ver>-<sha> car-monit-api-cpp
docker push registry.example.com/car-monit-api:<ver>-<sha>
```

建议在 CI 中完成镜像构建/扫描/推送，产物带 SBOM；本地构建仅用于验证。
构建阶段需要访问 GitHub（FetchContent 下载 libpqxx/hiredis/librdkafka），离线环境需
预置 `FETCHCONTENT_SOURCE_DIR_*` 或使用内部镜像源。

### 4.2 预发验证（Staging）

1. 用预发配置/Secret 部署新版本（1 个副本即可）。
2. 冒烟：
   - `GET /health` 返回 200，`status=UP`（ES 未接入允许 `UNKNOWN`）；
   - `GET /metrics?format=prometheus` 可抓取；
   - 非 DB 端点（如 `GET /progressive/scale-level`）返回 200；
   - 至少一个 DB 列表接口返回数据；
   - 日志无认证失败、无未捕获异常。
3. 观察 15–30 分钟：错误率、P99、依赖 UP、线程池队列、内存。

### 4.3 灰度发布

Kubernetes 推荐按副本灰度（本服务多副本依赖 Redis 选主，任意副本都可被替换）：

```bash
# 方式一：先发布 1 个副本（临时把 Deployment replicas 调为 1 或使用单独 canary Deployment）
kubectl -n car-monit-api set image deploy/car-monit-api \
  car-monit-api=registry.example.com/car-monit-api:<ver>-<sha>
kubectl -n car-monit-api rollout status deploy/car-monit-api

# 观察 15–30 分钟后恢复 replicas/HPA 正常范围
```

判定通过：错误率未上升、P99 未超过基线 20%、无依赖 DOWN、无线程池积压、内存无持续增长。
未通过则立即回滚（见 §5）。

### 4.4 全量发布

- `kubectl apply -k deploy/k8s`（镜像 tag 已更新）或 `kubectl set image`；
- 确认 `rollout status` 完成、Pod 全 Ready、Service 端点正常；
- Prometheus 抓取恢复、Grafana 面板无异常；
- 记录发布版本、commit、镜像 digest、变更摘要与验证人。

Docker Compose 单机：

```bash
CAR_MONIT_API_IMAGE=registry.example.com/car-monit-api:<ver>-<sha> docker compose up -d api
```

## 5. 回滚

### 5.1 Kubernetes

```bash
kubectl -n car-monit-api rollout history deploy/car-monit-api
kubectl -n car-monit-api rollout undo deploy/car-monit-api                # 上一版本
kubectl -n car-monit-api rollout undo deploy/car-monit-api --to-revision=<N>
kubectl -n car-monit-api rollout status deploy/car-monit-api
```

### 5.2 Docker Compose/单机

- 改回旧镜像 tag 或旧二进制，`docker compose up -d api` / 重启进程；
- 确认 `/health`、`/metrics`、关键接口与日志恢复。

### 5.3 数据库回滚约束

- 发布前必须确认 schema 变更向后兼容（新版本写旧版本可读）；
- 若必须做破坏性变更，先备份并准备独立回滚脚本，禁止直接回滚 DDL；
- 本运维支线不包含业务 DDL 变更。

## 6. 变更检查清单（提交 MR 时附上）

- [ ] 变更类型（feature/fix/refactor/ops/docs）与影响范围
- [ ] 是否修改业务代码逻辑（本运维支线应为“否”）
- [ ] 配置项新增/变更及默认值
- [ ] 数据库/索引/分区变更及回滚方案
- [ ] 镜像 tag、基础镜像、依赖版本变化
- [ ] 监控指标/告警/面板变化
- [ ] 安全影响（认证、CORS、限流、凭据注入）
- [ ] 验证记录（构建、ctest、契约、预发冒烟、灰度观察）
- [ ] 回滚步骤与责任人

## 7. 部署前需要业务/运维方准备

1. 镜像仓库地址与推送权限；
2. 生产数据库真实 DDL（替换 `deploy/initdb/02-placeholder-tables.sql`），以及账号/口令 Secret；
3. Redis、Kafka、Elasticsearch 的实际地址、认证与 TLS 材料（CA/客户端证书）；
4. Kubernetes Secret（`CM_PG_PASSWORD`，可选 ES `config.local.yaml`）；
5. Ingress/网关 TLS 终结与域名（服务本身监听明文 HTTP）；
6. cAdvisor（或等价容器指标采集）以启用进程内存/线程面板与内存增长告警；
7. 镜像扫描/签名与 SBOM 流程（如组织已有规范）。
