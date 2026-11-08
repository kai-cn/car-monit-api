# CI/CD 流水线方案（GitHub Actions）

> 状态：PR / 主分支 / 发布流水线已实现；CD 为占位（等两项决策）。未在 GitHub 上真跑，
> 本机也未执行长构建/全量测试（按用户要求：只写 YAML 与方案）。
> 进度记录见 [CI-CD-PROGRESS.md](CI-CD-PROGRESS.md)。

## 1. 事实核查（2026-11-08）

| 项目 | 结论 |
| --- | --- |
| 远端 | `origin https://github.com/kai-cn/car-monit-api.git` |
| 当前分支 | `master`（本地）；**远端默认分支实际是 `main`**（`git ls-remote --symref origin HEAD`），需在 GitHub Settings 手动改为 `master`，本机无凭据无法修改 |
| 分支口径 | 所有 workflow 的触发/PR 基线统一为 `master`，不再保留 `main` 兼容分支 |
| 仓库形态 | **单仓库多目录**：`car-monit-api-cpp/go/python/rust` 均无独立 `.git`，非 submodule（无 `.gitmodules`） |
| Rust 目录 | 仍被根 [.gitignore L77](../.gitignore) `car-monit-api-rust/` **整体忽略**，`git ls-files` 为空 → 该语言流水线**当前不会在 GitHub 触发**（代码写好后需先取消忽略并入库） |
| C# / Kotlin | `car-monit-api-csharp`、`car-monit-api-kotlin` 内只有迁移提示词 `.md`，无可构建代码 → 不建流水线 |
| 现有 workflow | 本次重构前仅根 `.github/workflows/ci.yml`（Python 专用）。现已替换为 9 个统一风格 workflow，详见下表 |
| 构建工具链 | Maven（Spring Boot 2.4.5 / source-target 1.8，2 模块，`packaging=pom` + `pro-business-api` repackage）；CMake 3.20 + C++20 + MSVC（无 `CMakePresets.json`）；Go 1.24.1（module `github.com/ruoyi/car-monit-api-go`，入口 `./cmd/api`）；Python 3.12（`requirements.txt` + `requirements.lock.txt`，pytest/coverage，`Dockerfile`，`docker-compose.integration.yml`）；Rust 1.90.0（`Cargo.toml` 单 crate，`rust-toolchain.toml` 已锁 1.90.0 + rustfmt + clippy） |
| 测试现状 | Java 无 `src/test`；C++ 有 `tests/test_main.cpp`（ctest）；Go 有 8 个 `*_test.go`；Python 有完整 pytest + tools 门禁；Rust 有 `tests/parity_test.rs`、`router_test.rs` |

## 2. 流水线矩阵

统一约定：五个语言各一个**可复用 workflow**（`_java.yml` / `_cpp.yml` / `_go.yml` / `_python.yml` / `_rust.yml`），
PR / 主分支 / 发布三套入口只负责触发、路径分诊与汇总，不复制检查逻辑；所有入口统一 `permissions: contents: read`（发布入口额外 `contents: write` 用于 Release）。

| 流水线 | 触发条件 | 路径分诊 | 检查内容 | 产物形态 |
| --- | --- | --- | --- | --- |
| **PR** (`pr.yml`) | `pull_request` → `master`（opened/synchronize/reopened/ready_for_review），支持手动 dispatch | `dorny/paths-filter`：`java`=`pom.xml|pro-base-common/**|pro-business-api/**`；`cpp/go/python/rust` 各自目录；未受影响的语言 job 跳过 | Java：JDK **8** Temurin + Maven `clean package`（无测试/无静态检查配置，见缺口）；C++：**windows-latest** + VS2022 + CMake C++20 + `ctest`；Go：`gofmt -l` + `go vet` + `go build` + `go test -race -cover`；Python：pytest（分支覆盖）+ 业务覆盖率 ≥65% 门禁 + `check_routes/mappers/parity/env/secrets` + 两个冒烟 + Redis/ES/Kafka service containers 集成测试；Rust：`cargo fmt --check` + `clippy -D warnings` + `cargo test` | 无发布产物（Python 覆盖率 HTML/XML 作为 artifact）；汇总 job `PR Gate` 作为唯一必需检查 |
| **主分支** (`master.yml`) | `push` → `master`，支持手动 dispatch | 全量（不分诊） | 五语言全部检查（Python 含集成测试）+ `Dockerfile` 构建校验（不推送） | `java-jar`、`cpp-windows-x64`、`go-linux-amd64`、`rust-linux-amd64`、`python-coverage` artifacts，保留 14 天 |
| **发布** (`release.yml`) | `push` tag `v*.*.*`；手动 dispatch 时在 UI 选择 tag 作为 ref | 全量 | 与主分支一致 + 校验和生产 | 五个 artifact 汇总后由 `gh release create/upload` 挂到 GitHub Release（含 `SHA256SUMS`）；Python 额外导出 `docker save` 镜像 tar.gz（registry 未定前不 push） |
| **部署** (`deploy.yml`) | 仅 `workflow_dispatch` | — | **占位，不可执行**：`push-images` / `deploy` 由 `vars.CD_REGISTRY_CONFIGURED` / `vars.CD_DEPLOY_TARGET_CONFIGURED` 显式开关控制（默认未设置=跳过），`guard` job 显式报错阻止误操作 | 待定 |

### JDK 版本口径

- 主仓库 pom `source/target=1.8`、Spring Boot 2.4.5 → 流水线固定 **JDK 8**；`_java.yml` 暴露 `jdk-version` 入参，未来 Kotlin（Gradle）等 JVM 模块若需 21/25，由调用方显式传参，不会共用同一个版本。
- C# 不涉及 JDK；无 25 的 JVM 模块可跑，不做臆测。

## 3. 需要用户确认的两个未知项（阻塞 CD，不阻塞 CI）

1. **镜像推送到哪里**：GHCR（`ghcr.io/<org>/<repo>`）还是私有 registry（Harbor/Nexus 等）？
   - 影响：镜像命名、`docker/login-action` 的 registry 参数、所需 secrets（`GHCR` 走 `GITHUB_TOKEN`；私有需 `REGISTRY_HOST/USERNAME/PASSWORD`）。
   - 当前处理：只在主分支/发布做 `docker build` 校验，**不推送**。
2. **部署目标形态**：K8s / 单机（SSH + docker compose / systemd）/ 只出 jar 与二进制不部署？
   - 影响：`KUBE_CONFIG_DATA` 或 `SSH_HOST/SSH_USER/SSH_KEY` 等 secrets、环境（staging/production）与审批策略。
   - 当前处理：`deploy.yml` 仅占位，未写任何地址、凭据或猜测的部署命令；用 `vars.CD_REGISTRY_CONFIGURED` / `vars.CD_DEPLOY_TARGET_CONFIGURED` 作显式启用开关，未设置时占位 job 跳过、guard job 阻止误操作。

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
| YAML 语法 | 本机 PyYAML 解析通过；actionlint 0 findings（9 个 workflow，含常量 `if` 检查） |
| GitHub 实跑 | **未验证**：未 push，未在远端触发 |
| 本地长构建/全量测试 | **未执行**（按用户要求，重启前不做） |
| Rust 流水线 | **已写好但不会触发**（目录被忽略、未入库） |
| CD | **占位**，等待 registry 与部署目标确认 |

## 7. 启用方式（操作提示）

1. 推送后到仓库 Settings → Branches 将默认分支改为 **`master`**（当前远端 HEAD 指向 `main`），再把必需检查指向 **`PR Gate`**（旧 `ci / gates` 检查名随 `ci.yml` 移除而消失）。
2. Rust 入库：从 `.gitignore` 删除 L77，`git add car-monit-api-rust`，确认 `Cargo.lock` 一并提交。
3. CD：见第 8-10 节（GHCR + K8s 已按决策实现，K8s 首次部署需人工 bootstrap）。

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
