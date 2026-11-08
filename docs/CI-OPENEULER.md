# CI/CD 运行环境：openEuler 24.03 LTS

> 目标：构建/测试 job 跑在 openEuler；Windows/MSVC 与 Docker 镜像构建为明确例外。
> 方案 A（默认，GitHub 托管 runner + openEuler 容器）已落地；方案 B（自托管 openEuler runner）给出切换步骤。

## 1. 事实核查（2026-11-08）

| 项 | 结论 |
| --- | --- |
| 镜像 | `openeuler/openeuler:24.03-lts`（Docker Hub）。本机 Docker Hub API 503、无 Docker，**未能在本地确认 tag**；以 GitHub 容器 job 实际拉取为准。若该 tag 不可用，备选 `hub.oepkgs.net/openeuler/openeuler:24.03-lts`（需按 registry 实际可用性切换）。 |
| JDK 8 | **openEuler OS/update 仓库自带 `java-1.8.0-openjdk-devel`**；实际 run 解析到 `1.8.0.462.b08`（update 仓库）。用 `dnf` 安装并自动设置 `JAVA_HOME`；不需要 Temurin。发行版差异只影响厂商实现，不影响 `source/target=1.8` 编译目标。 |
| Maven | openEuler 仓库只有 `maven-plugin`，**没有 Maven 本体**；使用 Apache 官方 `apache-maven-3.9.9-bin.tar.gz`。 |
| gcc / g++ | `gcc 12.3.1`、`gcc-c++ 12.3.1` 在 OS 仓库；满足 C++20。 |
| clang | `clang 17.0.6` 在 OS 仓库。 |
| cmake / ninja | `cmake 3.27.9`（OS）、`ninja-build 1.11.1`（everything 仓库）。 |
| cppcheck | `cppcheck 2.13.2`（everything 仓库）。 |
| Go | openEuler 仓库仅 `golang 1.21.4`，低于 `go.mod 1.26.10`；由 `actions/setup-go` 下载官方 1.26.10（openEuler glibc 2.38 兼容）。 |
| Python | `python3.12` 在 OS/everything/EPOL 列表均未命中；由 `actions/setup-python@v5` 下载 standalone Python 3.12。 |
| 其它 | `git`、`tar`、`gzip`、`unzip`、`curl`、`ca-certificates`、`libpq-devel`、`openssl-devel`、`which` 均可用。 |

## 2. 方案 A：GitHub 托管 runner + openEuler 容器（默认）

已改为容器 job 的构建/测试：

| workflow / job | 容器 | 说明 |
| --- | --- | --- |
| `_java.yml` build | `openeuler/openeuler:24.03-lts` | dnf 安装 OpenJDK 8 + Apache Maven 3.9.9 |
| `_go.yml` checks | 同上 | dnf 安装 git/gcc 等；setup-go 安装 1.26.10（race 需 gcc） |
| `_python.yml` gates | 同上 | setup-python 3.12 + pip |
| `_python.yml` integration | 同上 | 带 `services`（Redis/ES/Kafka），按服务名访问 |
| `_cpp.yml` linux（gcc/clang） | 同上 | dnf 安装 gcc/g++/clang/cmake/ninja/libpq/openssl |
| `_cpp.yml` linux-sanitizer | 同上 | clang + ASan/UBSan |
| `_cpp.yml` static-analysis | 同上 | dnf 安装 cppcheck，定向排除 2 条性能提示 |

**例外（无法在 Linux 容器中执行）**：

1. `_cpp.yml` 的 `build`（Windows/MSVC）保留 `windows-latest`：openEuler 无法运行 MSVC。
2. `_image.yml` 镜像构建 job：GitHub 容器 job 没有 DinD，无法访问宿主 Docker daemon → 保留 `ubuntu-latest`。
3. `release.yml` 的 `publish`：使用 `gh` CLI（openEuler 仓库无 gh 包）→ 保留 `ubuntu-latest`。
4. `deploy.yml`：手工 K8s 编排，使用 kubectl + setup-kubectl → 保留 `ubuntu-latest`。
5. `master.yml`/`pr.yml` 的 `presence`/`changes`/`PR Gate`/`Master Gate`：纯编排与聚合，不装语言工具链，保留轻量宿主。

### 2.1 容器 job 内的服务容器网络（重要）

容器 job 与 `services` 在同一个 Docker 网络：

- 访问地址必须用**服务名**：`redis:6379`、`elasticsearch:9200`、`kafka:9092`；**不能用 `127.0.0.1`**。
- Kafka 的 `KAFKA_ADVERTISED_LISTENERS` 必须是 `PLAINTEXT://kafka:9092`，`KAFKA_CONTROLLER_QUORUM_VOTERS` 用 `1@kafka:9093`。
- 服务容器内的 health-check 仍在服务自身容器里执行，继续用 `127.0.0.1`。
- `_python.yml` 已按以上规则改完；若将来移除 `container:`（例如自托管裸机模式），必须把 env 改回 `127.0.0.1`。

## 3. 方案 B：自托管 openEuler runner（可切换）

### 3.1 在 openEuler 机器上注册 runner

```bash
# 1) 下载 runner（版本用 GitHub 页面最新版替换 <runner-version>）
mkdir -p /opt/actions-runner && cd /opt/actions-runner
curl -fsSL -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v<runner-version>/actions-runner-linux-x64-<runner-version>.tar.gz"
tar xzf runner.tar.gz

# 2) 注册（token 从仓库 Settings → Actions → Runners → New self-hosted runner 获取）
./config.sh \
  --url https://github.com/kai-cn/car-monit-api \
  --token <RUNNER_TOKEN> \
  --name openeuler-01 \
  --labels self-hosted,linux,openeuler \
  --work /opt/actions-runner/_work

# 3) 安装为系统服务
sudo ./svc.sh install
sudo ./svc.sh start
```

### 3.2 切换 `runs-on`

所有 Linux job 已使用：

```yaml
runs-on: ${{ fromJSON(vars.CI_RUNNER_LABELS || '["ubuntu-latest"]') }}
```

在仓库/组织 Variables 设置：

```
CI_RUNNER_LABELS = ["self-hosted","linux","openeuler"]
```

- 未设置时默认 `ubuntu-latest`（方案 A）。
- Windows job 仍固定 `windows-latest`，不受该变量影响。
- 镜像/发布/部署 job 仍固定 `ubuntu-latest`；若要迁到自托管，需在 runner 上装 Docker/gh/kubectl 并手动改这几个 job。

### 3.3 自托管 runner 预装工具

若继续使用 `container:`（需要 runner 上有 Docker）：

- Docker Engine + 可拉取 `openeuler/openeuler:24.03-lts`。
- 其余依赖由容器内 dnf/安装脚本处理。

若去掉 `container:` 直接在欧拉主机跑，需要预装：

- `git tar gzip unzip curl ca-certificates which`
- `java-1.8.0-openjdk-devel`、Maven 3.9.9（/opt + PATH）
- `gcc gcc-c++ clang cmake ninja-build make libpq-devel openssl-devel cppcheck`
- Go 1.26.10、Python 3.12（或用 setup-go / setup-python）
- 镜像 job：Docker；发布 job：gh；部署 job：kubectl

## 4. 验证状态（2026-11-08）

实测 run：

| 项 | 结果 |
| --- | --- |
| master run | **`42499755525`（sha `0191d95`）success** |
| Java 容器 job | **success**：dnf 安装 `java-1.8.0-openjdk-devel 1.8.0.462.b08` + Apache Maven 3.9.9 tarball，`mvn clean package` 通过 |
| Python gates 容器 job | **success**：setup-python 3.12.16 + `python -m pip`（不能直接用 `pip` shim） |
| Python integration 容器 job | **success**：`services` 与 job 容器同网络，`redis:6379` / `elasticsearch:9200` / `kafka:9092` 连通，Kafka advertised listener `kafka:9092` |
| Go 容器 job | **success**：setup-go 1.26.10 + dnf gcc（race/cgo）+ `GOFLAGS=-buildvcs=false` + govulncheck 0 可达漏洞 |
| 镜像 job | success（保留 ubuntu 宿主，需 Docker daemon） |
| C++ Linux 容器 job | **未验证**：master 上 `cpp` 被 presence 跳过；容器化代码已提交，需从 `car-monit-api-cpp` 开 PR 才能实际执行 windows/linux/clang/ASan/cppcheck 全链路 |
| `deploy` | 未运行（无 K8s 凭据） |

> 已知容器内环境差异：`setup-python` 自带的 pip shim 在 openEuler 容器内不可执行 → 统一用 `python -m pip`；`go build` 的 buildvcs 在容器 checkout 上会失败 → `GOFLAGS=-buildvcs=false`。dnf 偶发镜像超时但会自动重试，最终成功。

## 5. ARM64（已搁置，TODO）

用户决定 ARM64 先搁置；本次**未落任何 ARM64/ARCH/buildx/QEMU 代码**。

- 硬约束：GitHub 托管 Linux runner 均为 x86_64；arm64 托管 runner 仅公开仓库可用，本仓库私有不可用。
- 可选路径：
  1. 自托管 ARM64 openEuler 真机 runner（唯一真验证），标签建议 `[self-hosted, linux, arm64, openeuler]`；
  2. `ubuntu-latest` + `docker run --platform linux/arm64` QEMU 模拟（慢 5–20 倍，JVM 构建可能超时）；
  3. 交叉编译（只验证编得过，验证不了运行）。
- 接入前需要补齐：
  - workflow 增加 `ARCH: amd64|arm64` 参数（默认 amd64）；
  - `_image.yml` 改 `docker/buildx` + `--platform linux/$ARCH`，发布链路支持 `linux/amd64,linux/arm64` 多架构 manifest；
  - 增加 QEMU 模拟验证 job（明确标注"模拟，性能数字不作参考"）；
  - deploy 阶段做架构校验或只部署与 manifest 匹配的架构，避免 x86 集群拉 arm64 镜像 `exec format error`。
- 自托管 ARM64 的注册步骤与工具清单可复用本文 §3，仅把 labels 改为 `self-hosted,linux,arm64,openeuler`，并在 ARM64 机器上重新验证 dnf 包（`java-1.8.0-openjdk-devel`、gcc、cmake、ninja、cppcheck 等）可得性。
