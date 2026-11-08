# CI/CD 流水线方案（GitHub Actions）

> 状态：PR / 主分支 / 发布流水线已实现；CD 为占位（等两项决策）。未在 GitHub 上真跑，
> 本机也未执行长构建/全量测试（按用户要求：只写 YAML 与方案）。
> 进度记录见 [CI-CD-PROGRESS.md](CI-CD-PROGRESS.md)。

## 1. 事实核查（2026-11-08）

| 项目 | 结论 |
| --- | --- |
| 远端 | `origin https://github.com/kai-cn/car-monit-api.git` |
| 运行环境 | **openEuler 24.03 LTS**：构建/测试 job 在 `openeuler/openeuler:24.03-lts` 容器内执行；Windows MSVC 保留 `windows-latest`。详见 [CI-OPENEULER.md](CI-OPENEULER.md) |
| 当前分支 | `master`（本地）；已推送到 `origin/master`（最新 SHA 见 [CI-CD-PROGRESS.md](CI-CD-PROGRESS.md)）。远端默认分支已由用户改为 **`master`**，CI 触发/PR 基线口径一致 |
| 分支口径 | 所有 workflow 的触发/PR 基线统一为 `master`，不再保留 `main` 兼容分支 |
| 仓库形态 | **单仓库多目录**：`car-monit-api-cpp/go/python/rust` 均无独立 `.git`，非 submodule（无 `.gitmodules`） |
| Rust 目录 | 仍被根 [.gitignore L77](../.gitignore) `car-monit-api-rust/` **整体忽略**，`git ls-files` 为空 → 该语言流水线**当前不会在 GitHub 触发**（代码写好后需先取消忽略并入库） |
| C# / Kotlin | `car-monit-api-csharp`、`car-monit-api-kotlin` 内只有迁移提示词 `.md`，无可构建代码 → 不建流水线 |
| 现有 workflow | 本次重构前仅根 `.github/workflows/ci.yml`（Python 专用）。现已替换为 10 个统一风格 workflow，详见下表 |
| 构建工具链 | Maven（Spring Boot 2.4.5 / source-target 1.8，2 模块，`packaging=pom` + `pro-business-api` repackage）；CMake 3.20 + C++20 + MSVC（无 `CMakePresets.json`）；Go 1.26.10（module `github.com/ruoyi/car-monit-api-go`，入口 `./cmd/api`）；Python 3.12（`requirements.txt` + `requirements.lock.txt`，pytest/coverage，`Dockerfile`，`docker-compose.integration.yml`）；Rust 1.90.0（`Cargo.toml` 单 crate，`rust-toolchain.toml` 已锁 1.90.0 + rustfmt + clippy） |
| 测试现状 | Java 无 `src/test`；C++ 有 `tests/test_main.cpp`（ctest）；Go 有 8 个 `*_test.go`；Python 有完整 pytest + tools 门禁；Rust 有 `tests/parity_test.rs`、`router_test.rs` |

## 2. 流水线矩阵

统一约定：五个语言各一个**可复用 workflow**（`_java.yml` / `_cpp.yml` / `_go.yml` / `_python.yml` / `_rust.yml`），
PR / 主分支 / 发布三套入口只负责触发、路径分诊与汇总，不复制检查逻辑；所有入口统一 `permissions: contents: read`（发布入口额外 `contents: write` 用于 Release）。

| 流水线 | 触发条件 | 路径分诊 | 检查内容 | 产物形态 |
| --- | --- | --- | --- | --- |
| **PR** (`pr.yml`) | `pull_request` → `master`（opened/synchronize/reopened/ready_for_review），支持手动 dispatch | `dorny/paths-filter`：`java`=`pom.xml|pro-base-common/**|pro-business-api/**`；`cpp/go/python/rust` 各自目录；未受影响的语言 job 跳过 | Java：JDK **8** Temurin + Maven `clean package`（无测试/无静态检查配置，见缺口）；C++：**windows-latest** + VS2022 + CMake C++20 + `ctest`；Go：`gofmt -l` + `go vet` + `go build` + `go test -race -cover`；Python：pytest（分支覆盖）+ 业务覆盖率 ≥65% 门禁 + `check_routes/mappers/parity/env/secrets` + 两个冒烟 + Redis/ES/Kafka service containers 集成测试；Rust：`cargo fmt --check` + `clippy -D warnings` + `cargo test` | 无发布产物（Python 覆盖率 HTML/XML 作为 artifact）；汇总 job `PR Gate` 作为唯一必需检查 |
| **主分支** (`master.yml`) | `push` → `master`，支持手动 dispatch | 全量（不分诊） | 五语言全部检查（Python 含集成测试）+ 镜像构建并推送 GHCR（`sha-<短哈希>` + `latest`） | 语言 artifacts（14 天）+ GHCR 镜像 |
| **发布** (`release.yml`) | `push` tag `v*.*.*`；手动 dispatch 时在 UI 选择 tag 作为 ref | 全量 | 与主分支一致 + 校验和生产 + 镜像推送 GHCR（`sha-<短哈希>` + `<semver>`） | 五个 artifact 汇总后由 `gh release create/upload` 挂到 GitHub Release（含 `SHA256SUMS`）；GHCR 版本化镜像 |
| **部署** (`deploy.yml`) | 仅 `workflow_dispatch`（选 environment / language） | 按所选语言构建对应镜像 | 前置校验 vars/secrets → 构建推送所选语言镜像 → `kubectl set image` + `rollout status` | GHCR 镜像 + Deployment 滚动更新 |

### JDK 版本口径

- 主仓库 pom `source/target=1.8`、Spring Boot 2.4.5 → 流水线固定 **JDK 8**；`_java.yml` 暴露 `jdk-version` 入参，未来 Kotlin（Gradle）等 JVM 模块若需 21/25，由调用方显式传参，不会共用同一个版本。
- C# 不涉及 JDK；无 25 的 JVM 模块可跑，不做臆测。

## 3. CD 决策（2026-11-08 已确认）

1. **镜像推送 GHCR**：`ghcr.io/<github.repository_owner>/<service>`，owner 取仓库实际归属 `kai-cn`（workflow 用 `github.repository_owner`，不写死）。
   - 认证：`GITHUB_TOKEN` + `permissions: packages: write`；不新建 PAT 假设。
   - 标签：`sha-<7位短哈希>`（每次构建）+ `<semver>`（tag `v*.*.*`）+ `latest`（仅 `refs/heads/master`）。
2. **部署形态 K8s**：`kubectl set image` + `kubectl rollout status`，kubeconfig 读 `secrets.KUBE_CONFIG`；仓库无 K8s manifest，只对**已存在的 Deployment**做镜像更新，首次部署需人工 bootstrap（见 §10）。
   - 命名空间 / Deployment 名 / 容器名 / imagePullSecret 名全部走 `vars`，job 前置校验，缺变量显式失败。

## 4. 现状缺口（不在本任务中顺手修）

1. **Java 无测试、无静态检查**：`pro-business-api`、`pro-base-common` 无 `src/test`，pom 未配置 checkstyle/spotbugs；PR 门禁仅到"可编译可打包"。未添加插件，避免改动业务构建。
2. **C++ 无格式/静态检查配置**：仓库无 `.clang-format` / `.clang-tidy`，MSVC 只有 `/W3`。PR 门禁为编译 + ctest。
3. **Rust 未入库**：`.gitignore` L77 整体忽略，`pr.yml` 的 `car-monit-api-rust/**` 过滤器永远不会命中；需取消忽略并提交后流水线才生效。
4. **Python 依赖未完全锁定**：CI 按 `requirements.txt` 的区间安装（`requirements.lock.txt` 是运行时而 CI 需要 dev 依赖），存在上游漂移风险。
5. **Java 的 Pulsar 版本风险**：`pulsar-client 2.10.4` 在 pom 注释中写明"2.10+ 要求 JDK 11+"，与 JDK 8 目标冲突；本机未跑构建，**未验证**是否能编译/运行，仅记录。
6. **构建产物仓库内残留**：`target/`、`bin/`、`build/` 等本地产物存在但不入库（已在 `.gitignore`），CI 不受影响。

## 5. 安全约束落实

- 所有凭据只通过 `secrets` 引用；新增 workflow 中**没有任何**明文口令、token、内网 IP。
- 保留 Python `tools/check_secrets.py` 作为 secret 扫描门禁（历史明文口令问题）。
- `permissions` 最小化：CI 只读；`release.yml` 才给 `contents: write`，`deploy.yml` 仍只读。
- PR 汇总 job `PR Gate` 统一判定失败/取消；未受影响语言以 skipped 计入通过，避免路径过滤导致必需检查永久 pending。

## 6. 验证状态

| 项 | 状态 |
| --- | --- |
| YAML 语法 | 本机 PyYAML 解析通过；actionlint 0 findings（10 个 workflow，含常量 `if` 检查） |
| GitHub 实跑 | **已验证**：`master` run `42491418177`（`465aeba`）与 `42491455889`（`a6b6398`）均 success；java/go/python gates+integration、image-java/python/go 全绿，cpp/rust 按预期 skip |
| 本地长构建/全量测试 | Python/Go/Java 已本地验证（见 §12.4）；镜像构建以 GitHub runner 为准 |
| Rust 流水线 | 已写好；`master` 上目录未入库 → 跳过；分支已推送但为旧快照（见 §11） |
| CD | **已实现（GHCR + K8s），未实跑**：无 K8s 集群/凭据，`kubectl` 步骤未验证 |

## 7. 启用方式（操作提示）

1. 默认分支已改为 **`master`**（远端 HEAD 已确认）；到 Settings → Branches 给 `master` 配保护规则，必需检查指向 **`PR Gate`**（旧 `ci / gates` 检查名随 `ci.yml` 移除而消失）。
2. Rust 入库：从 `.gitignore` 删除 L77，`git add car-monit-api-rust`，确认 `Cargo.lock` 一并提交。
3. CD：在 GitHub Environment 配 `secrets.KUBE_CONFIG` 与 `vars.K8S_NAMESPACE/K8S_DEPLOYMENT/K8S_CONTAINER/K8S_IMAGE_PULL_SECRET`；首次部署先按 §10.2 建 imagePullSecret 并确保 Deployment 引用它。

## 8. 镜像构建补全（Dockerfile）

| 语言 | Dockerfile | 构建上下文 | 基础镜像 | 说明 |
| --- | --- | --- | --- | --- |
| Java | `docker/java.Dockerfile` | 仓库根 | 构建 `maven:3.9-eclipse-temurin-8`；运行 `eclipse-temurin:8-jre-jammy` | pom `source/target=1.8`，必须 JDK 8；运行只要 JRE；glibc 规避 Alpine 兼容风险 |
| Python | `car-monit-api-python/Dockerfile`（既有） | `car-monit-api-python/` | `python:3.12-slim` | 原文件未改动 |
| Go | `docker/go.Dockerfile` | `car-monit-api-go/` | 构建 `golang:1.24-bookworm`；运行 `debian:12-slim` | `CGO_ENABLED=0` 静态产物；运行期需 tzdata + CA |
| C++ | `docker/cpp.Dockerfile` | `car-monit-api-cpp/` | 构建/运行均 `debian:12-slim` | C++20 用 g++12；运行需 libstdc++/CA/tzdata；distroless 缺 CA/无 shell，不用 |
| Rust | `docker/rust.Dockerfile` | `car-monit-api-rust/` | 构建 `rust:1.90-slim-bookworm`；运行 `debian:12-slim` | 与 `rust-toolchain.toml` 1.90.0 对齐；rdkafka cmake-build 需 cmake/g++/zlib |

- **配置不打包进镜像**：Go/C++/Rust 的 `configs/config.yaml`、`config/application.yaml` 可能含连接串/口令，镜像只放二进制；由 K8s 以 ConfigMap/Secret 挂载到约定路径。Java 的 `application.yml` 已打入 jar，口令走环境变量覆盖。
- **构建缺口（如实声明）**：
  - `master` 只跟踪 11 个 C++ 文件，完整源码在 `car-monit-api-cpp` 分支 → master 上 C++ 构建/镜像会被 presence 检查显式跳过，不会产出假镜像。
  - `car-monit-api-rust/` 未入 master → rust 镜像同样跳过；且该分支当前是旧快照（见 §11）。
- **验证状态**：本机**没有 docker**（`docker version` 不可用），所有镜像均**未实测构建/未实测运行期依赖**，仅做静态审阅。首次启用 CI 时以 GitHub runner 构建结果为准。

## 9. GHCR 镜像命名与标签

| 服务 | 镜像 |
| --- | --- |
| Java | `ghcr.io/kai-cn/car-monit-api` |
| Python | `ghcr.io/kai-cn/car-monit-api-python` |
| Go | `ghcr.io/kai-cn/car-monit-api-go` |
| C++ | `ghcr.io/kai-cn/car-monit-api-cpp` |
| Rust | `ghcr.io/kai-cn/car-monit-api-rust` |

- 实现：`.github/workflows/_image.yml`（可复用），由 `master.yml` 与 `release.yml` 调用；`deploy.yml` 也复用它构建所选语言。
- 标签（`docker/metadata-action`）：
  - `sha-<7位短哈希>`：任何构建都生成，部署按此 tag 固定到具体提交；
  - `<semver>`：仅在 tag `v*.*.*` 上生成（如 `v1.2.3` → `1.2.3`）；
  - `latest`：仅 `github.ref == refs/heads/master` 时生成。
- 权限：job 级 `permissions: contents: read, packages: write`，登录用 `GITHUB_TOKEN` + `github.actor`。
- 注意：`master` 上 C++（缺 `src/main.cpp`）与 Rust（目录未入库）会通过 presence 检查跳过镜像构建；`release` 同样跳过，不会产出空镜像。

## 10. K8s 部署（现有 Deployment 滚动更新）

仓库内**没有任何 K8s manifest**（无 `deploy/`、无 `k8s/`、无 Helm chart），因此 `deploy.yml` 只做：

1. 构建并推送所选语言镜像（tag 固定到提交，默认 `sha-<7位短哈希>`）；
2. `kubectl -n <ns> set image deployment/<deploy> <container>=<image>`；
3. `kubectl -n <ns> rollout status deployment/<deploy> --timeout=300s`。

**首次部署必须人工 bootstrap**：创建 namespace、Deployment（含 pod 模板/Service/配置挂载）、imagePullSecret。CD 不负责创建这些对象。

### 10.1 必需配置（全部走 vars/secrets，缺一显式失败）

| 类型 | 名称 | 用途 |
| --- | --- | --- |
| secret | `KUBE_CONFIG` | kubeconfig；建议 base64，脚本兼容明文。建议配在 `staging` / `production` Environment 下 |
| var | `K8S_NAMESPACE` | 目标命名空间 |
| var | `K8S_DEPLOYMENT` | 已存在的 Deployment 名 |
| var | `K8S_CONTAINER` | Pod 模板中的容器名（`kubectl set image` 用） |
| var | `K8S_IMAGE_PULL_SECRET` | 已存在的 imagePullSecret 名 |

workflow 会先校验变量齐全，再校验 Deployment 存在、Secret 存在、且 Deployment 的 pod 模板确实引用该 imagePullSecret；缺任何一项都直接失败，不会带病滚动。

### 10.2 私有 GHCR 的 imagePullSecret（否则 Pod 会 ImagePullBackOff）

`GITHUB_TOKEN` 只在 Actions 运行期有效，**不能给集群拉镜像**。首次 bootstrap 需要一份有 `read:packages` 权限的长期凭据（PAT 或 GitHub App token），在目标命名空间手工创建：

```bash
# 变量用占位符，按实际环境替换；下面命令不含任何真实集群地址/命名空间
kubectl create namespace "$K8S_NAMESPACE"        # 首次；已存在可跳过

kubectl -n "$K8S_NAMESPACE" create secret docker-registry "$K8S_IMAGE_PULL_SECRET" \
  --docker-server=ghcr.io \
  --docker-username="<GitHub 用户名>" \
  --docker-password="<具备 read:packages 的 PAT>" \
  --docker-email="<邮箱>"
```

并让 Deployment 的 pod 模板引用它（首次 bootstrap 时写进 manifest，或用 patch）：

```bash
kubectl -n "$K8S_NAMESPACE" patch deployment "$K8S_DEPLOYMENT" --type=merge \
  -p "{\"spec\":{\"template\":{\"spec\":{\"imagePullSecrets\":[{\"name\":\"${K8S_IMAGE_PULL_SECRET}\"}]}}}}"
```

如果 GHCR package 设为 public，可不需要 imagePullSecret；但默认按私有处理，否则滚动后必然 `ImagePullBackOff`。

### 10.3 配置与数据挂载（镜像内不含配置）

| 语言 | 容器内约定路径 | 说明 |
| --- | --- | --- |
| Java | 无（`application.yml` 在 jar 内） | 连接串/口令用环境变量覆盖（如 `SPRING_DATASOURCE_...`） |
| Python | 无（沿用其 Dockerfile 行为） | 环境变量注入 |
| Go | `/app/configs/config.yaml` | 需挂 ConfigMap/Secret；也可用 `--config` 覆盖 |
| C++ | `/app/configs/config.yaml` | 同上；二进制默认参数已指向该路径 |
| Rust | `/app/config/application.yaml` | 同上；可用 `CAR_MONIT_CONFIG` 覆盖 |

## 11. Rust 分支与主工作区副本的漂移（2026-11-08 核对）

- `origin/car-monit-api-rust` = `847441d`，166 个跟踪文件；主工作区被忽略副本 132 个源码级文件，最新修改 **2026-11-08 17:16**，分支最新 **2026-11-04 18:24**。
- 源码级对比：**117 个同名文件内容不同**，主副本独有 14 个，分支独有 48 个（后者多为 `docs/verify/*`、`tools/v2/*` 验证资产）。
- 关键差异：`src/mq.rs`、`src/config.rs`、`src/services/consumer.rs` 均不同；`tools/es-rebuild-snapshot-flow.sh`、`src/metrics.rs`、`docs/RUST-REVIEW-20261107.md`、`docs/RUST-FIX-LOG-20261108.md`、`resources/es/index/*.json` 只在主副本存在；`Cargo.toml`/`Cargo.lock` 不同。
- 结论：远端分支是**旧实现**，CI 跑它等于测旧代码。建议做法（未执行，需决策）：
  1. 把主副本最新修改**逐文件审查后**提交进 `car-monit-api-rust`（注意分支上还有 48 个主副本没有的验证资产，不能整体覆盖）；
  2. 或在文档声明该分支为历史快照，CI 不作为当前实现门禁。
- 禁止静默覆盖推送。

## 12. Actions 首轮失败修复（2026-11-08，静态定位）

> 无 `gh`、无 `GH_TOKEN`/`GITHUB_TOKEN`、未登录浏览器访问私有仓库 Actions 均为 404，
> **拿不到 run/job 日志**；以下为本地复现 + workflow 静态审查结果，未编造失败原因。

### 12.1 确定会失败（已修）

| 问题 | 证据 | 修复 |
| --- | --- | --- |
| Python `check_mappers` 红 | 本地跑 `tools/check_mappers.py`：`OdsLwzxsfsjFeeRecords01Mapper.xml`、`ZdataTrailFittingMapper.xml` 与 Java 源漂移 | 跑 `tools/sync_mapper_xml.py` 逐字节同步（22 个 XML 一致） |
| Python `pytest` 红 | `tests/business/test_sql_golden.py` 第 353 行语句顺序/内容不一致（同步 XML 后暴露） | `CAR_MONIT_UPDATE_GOLDEN=1 pytest tests/business/test_sql_golden.py` 重生成 golden 并复跑通过 |

### 12.2 高概率失败（已加固）

| 问题 | 原因 | 修复 |
| --- | --- | --- |
| Python 集成 Kafka 拉不起来 | `bitnami/kafka:3.7` 在 2025 年后已下架/迁移到 legacy，私有 runner 上会 ImagePull 失败 | 换 `apache/kafka:3.9.1`（KRaft 单节点 + 官方健康检查路径） |
| Go `-race` 可能在 runner 上失败 | 未显式设置 `CGO_ENABLED`，若环境默认 0 则 `-race requires cgo` | test step 显式 `CGO_ENABLED=1` |
| 镜像额外 tag 解析 | `type=raw,value=,enable=false` 的空 value 在 metadata-action 上是脆弱写法 | 删除 `extra-tag`，deploy 固定使用 `sha-<7位短哈希>` |
| 基础镜像浮动 tag 漂移 | `maven:3.9-...`、`golang:1.24-...`、`rust:1.90-...` 可能指向不同 patch | 固定 `maven:3.9.9-eclipse-temurin-8`、`golang:1.26.10-bookworm`、`rust:1.90.0-slim-bookworm` |
| 手动 dispatch 的 PR 流程跑 C++ | master 只有 11 个 C++ 文件，手动触发会直接失败 | `pr.yml` 增加 `cpp-present` 检查，缺失时跳过 |

### 12.3 只是不规范 / 需说明

- `paths-filter` 仅用于 `pull_request`，未在 `push` 上使用，不涉及 `fetch-depth: 0` 问题。
- `services` 其余镜像（`redis:7`、`elasticsearch:7.17.13`）健康检查与端口映射未改；无 MySQL。
- `PR Gate` / `Master Gate` 只在 `failure`/`cancelled` 时红；skip 视为通过，符合预期。
- 镜像 job 仍依赖 GHCR `packages: write`；若仓库策略禁止，需管理员放开，否则 master/release 会红。
- 本地无 Docker，镜像构建仍未实测；Java 本地 `mvn clean` 因 jar 被占用失败，但 `mvn compile` 成功，CI 全新 runner 不受影响。

### 12.4 本地验证结果（修复后）

| 检查 | 结果 |
| --- | --- |
| Python `pytest`（含 golden） | 215 passed / 19 skipped |
| Python `check_mappers` | 22 个 XML 与 Java 源一致 |
| Python `smoke_coverage` | 23/23 ok |
| Python `smoke_test` | 28/28 pass |
| Python `smoke_all_routes` | 85 路由，5xx=0 |
| Python 业务覆盖率 | 67.6%（≥65% 门禁） |
| Go `gofmt` / `go vet` / `go build` / `go test` | 全部通过（race 因本机无 gcc 未跑） |
| Java `mvn compile`（JDK 8 / Maven 3.9.9） | BUILD SUCCESS |

### 12.5 GitHub Actions 实测结果（只读+写权限 PAT，2026-11-08）

| workflow / 运行 | 分支 / SHA | 结论 | 说明 |
| --- | --- | --- | --- |
| `master` | master `024d2f9`（run 42495366929） | **success** | Go 1.26.10 + govulncheck 0 可达漏洞；image-java/python/go 全绿 |
| `master` | master `48705e7`（run 42495971365） | **success** | 含 release publish 修复 |
| `pr` | PR #1 noise（`1248155`，run 42495436926） | **success** | `changes` success；java/go/cpp/python/rust 全部 **skipped**（docs-only）；`PR Gate` success；PR 已关闭、临时分支已删除 |
| `release` | tag `v0.0.0-citest` @ `48705e7`（run 42496000954） | **success** | 首跑 42495556977 仅 publish 失败（`gh` 无 checkout 报 not a git repository），已用 `GH_REPO` 修复并复跑；资产 jar 216M / go 27M / python 镜像 73M / SHA256SUMS；tag 与 Release 已清理 |
| `deploy` | — | **未运行** | 无 K8s 集群/凭据 |
| `C++ CI`（旧分支 workflow） | `car-monit-api-cpp` `63bb3c9` | 已被删除 | 旧 `cpp-ci.yml` 已移除，检查并入统一 `_cpp.yml`；新检查待 PR 验证 |
| `car-monit-api-go CI`（旧分支 workflow） | `car-monit-api-go-V2` | 待合并后移除 | 分支 merge 冲突未解决；govulncheck 已在 master 统一 `_go.yml` 保留 |
| `ci`（旧 Python-only，java-fix 分支） | `car-monit-api-java-fix` | 已被 merge 移除 | 分支已 merge master，旧 `ci.yml` 自动删除 |

> 首轮 `master` 失败根因（真实日志）：① `test_sql_golden` 与 Mapper XML 不同步；② `bitnami/kafka:3.7` manifest unknown。其余语言 job 当轮即为 success，并非"全部语言都挂"。

### 12.6 GHCR 镜像实测清单（2026-11-08）

| 包 | 可见性 | 实际 tag（节选） |
| --- | --- | --- |
| `car-monit-api`（Java） | private | `latest`、`sha-48705e7`、`0.0.0-citest` 及历史 `sha-*` |
| `car-monit-api-python` | private | `latest`、`sha-48705e7`、`0.0.0-citest` 及历史 `sha-*` |
| `car-monit-api-go` | private | `latest`、`sha-48705e7`、`0.0.0-citest` 及历史 `sha-*` |
| `car-monit-java` / `car-monit-py` / `car-monit-go` / `car-monit-rust` | private | `sha-230372a`、`latest` 等；命名不符本仓库规则，判断为其它仓库/流水线产出，未触碰 |

- 本仓库 C++/Rust 镜像在 master 上按 presence 跳过，因此 GHCR 无 `car-monit-api-cpp` / `car-monit-api-rust`。

## 13. openEuler 运行环境

- 默认方案：GitHub 托管 runner + `container: openeuler/openeuler:24.03-lts`；JDK 8 用 openEuler 自带 OpenJDK，Maven/Go/Python 走官方 tarball 或 setup-*。
- 可切换方案：设置仓库变量 `CI_RUNNER_LABELS=["self-hosted","linux","x64","wsl","openeuler"]` 即切到 WSL openEuler 自托管 runner；注册命令与预装工具见 [self-hosted-runner.md](self-hosted-runner.md)。
- 例外：Windows MSVC、Docker 镜像构建、`gh` 发布、kubectl 部署四个环节保留 `ubuntu-latest`；原因与边界见 [CI-OPENEULER.md §2](CI-OPENEULER.md)。
- 实测状态：**已验证**。master run `42499755525`（sha `0191d95`）success：Java/Python gates/Python integration/Go 容器 job 与镜像 job 全绿；services 按容器网络服务名连通；JDK8 来自 openEuler dnf（`1.8.0.462.b08`）。C++ Linux 容器 job 仍待 PR 验证，详见 [CI-OPENEULER.md §4](CI-OPENEULER.md)。

## 14. 单机部署 CD（与 K8s 并存）

- 文件：`.github/workflows/cd-standalone.yml`；与 `deploy.yml`（K8s）互不影响。
- 触发：`push master` / tag `v*.*.*` / `workflow_dispatch`（可选 service、tag）。
- artifact：`car-monit-api-standalone-<sha>.tar.gz`，含 Java jar、Go Linux amd64 二进制、Python 源码 + 离线 wheels、systemd units、占位配置模板、参数化 `install.sh`/`uninstall.sh`、`SHA256SUMS`、README；Rust 因 master 未入库暂不包含。
- 完整生命周期验证 job：解包 → `sha256sum -c` → tar 清单 → 非 root 临时前缀 `install.sh` → 启动 Python（`CAR_MONIT_RUNTIME=shim`）→ `/health` → 停止 → `uninstall.sh` → 断言清理；报告作为 artifact 上传。
- 实测：run `42507567691` **success**（build + verify）；artifact `standalone-tar-…` **232,870,588 B**；`/health` **HTTP 200**，响应体 `status=DEGRADED`（DB 连接超时，Redis/ES/Kafka 为 shim UP），`cleanup=OK`。
- 自托管单机部署：`.github/workflows/deploy-selfhosted.yml` 默认关闭（`confirm=false` 已验证 run `42508196517` = **skipped**）；接入文档见 [self-hosted-runner.md](self-hosted-runner.md)（WSL openEuler，labels `self-hosted,linux,x64,wsl,openeuler`）。
