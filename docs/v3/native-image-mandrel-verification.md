# Spring Boot 4 / Mandrel 原生镜像实机验证与运维记录

> 记录时间：2026-11-15 14:45–19:32 (GMT+8)
> 环境：Windows 11（13.84 GB / 12 逻辑 CPU）+ WSL2 `openEuler-24.03-LTS-SP4`；k3d `v3`；Spring Boot 4.1.2；六个 JDK 工作树
> 工具：Windows Mandrel `D:\jdk\mandrel-25.0.4.1-Final`；Linux Mandrel `/home/dev/tools/mandrel-25`；Windows Maven `D:\work\apache-maven`
> 证据目录：`D:\work\runtime-logs\v3-ops\evidence\`；进度快照：`D:\work\runtime-logs\v3-ops\PROGRESS-SNAPSHOT-20261115.md`

---

## 0. 结论速览（如实）

| 项 | 结果 |
| --- | --- |
| `wsl.exe` 黑名单 | 已解除，本轮全部实机执行 |
| 三节点过时镜像清理 | ✅ 删除 12 个，每节点每仓库只留 1 份 `ci-v2` |
| 单机/集群互斥 | ✅ 保持 standalone；WSL `Mem.used` 6019→3474 MB（−2545 MB），java 进程 10→4，k3d 4 节点 Exited |
| 常态配额 | ✅ `4GB / 2GB swap / 2核`，实测 `nproc=2`、`Mem.total=3919MB`、**宿主可用 5.12 GB**（任务开始时 1.86 GB） |
| VHDX 回收 | ✅ 首次 42.812→38.315 GB（−4.497 GB）；Linux 构建后最后一次 41.045→39.79 GB（−1.255 GB）；D 盘最终 4.59 GB |
| stale jar 重建 | ⚠️ api-jdk25 已重建（−4.63 MiB）；其余 3 个仍未重建 |
| Windows 原生 exe | ✅ 端到端构建成功 `348,528,640 B / 332.38 MB`，14:40，峰值 RSS 10.11 GB |
| Linux 原生 ELF | ✅ 端到端构建成功 `340,921,056 B / 325.13 MB`，28:44，峰值 RSS 10.11 GB |
| 原生镜像**运行** | ⚠️ **未完整启动**：Forest 反射已修复，但两个平台一致卡在 MyBatis-Plus `sqlSessionFactory` 缺失（Spring Boot 4 AOT 兼容问题），稳态 RSS 未测得 |
| 容器镜像 | ✅ `car-monit-api:native-jdk25` 493 MB（152 MB 基础 + 341 MB ELF），对比 JVM `ci-v2` 645 MB（−152 MB / −23.6%） |
| CICD | ⚠️ workflow 已同步六分支、两个自托管 runner 在线、本地等价实跑并产出双平台 artifact；**云端 Actions run 未触发**（无 gh CLI、workflow 未提交） |

---

## 1. 实机基线

| 项 | 值 |
| --- | --- |
| 宿主 | 13.84 GB 总；初始可用 1.86 GB，最终 5.12 GB |
| WSL 原配额 | `8GB / 4GB swap / 4核` → `nproc=4`、`Mem=7944MB`、vmmem 4247 MB |
| VHDX | `D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx` 45,969,571,840 B（42.812 GB），非稀疏 |
| WSL docker | 25.0.3 / overlay2；Images 17 个 10.86 GB、Volumes 39 个 11.55 GB |
| k3d | `v3` 1 server + 2 agents，Deployment 各 3/3，镜像 `car-monit-{api,backend}:ci-v2` |
| 同时运行的两套服务 | **单机**：systemd `car-monit-api.service`/`car-monit-backend.service`（`/opt/car-monit-*/app.jar`，JDK17，9902/9989，由 `wslrelay.exe` 转发）；**集群**：k3d 6 Pod。二者同时运行，违反单实例约束 |
| WSL Java | 系统 BiSheng 1.8 / Maven 3.6.3；CI 缓存 `/home/dev/.cache/ci-toolchain/` 有 Linux JDK 17/21/25 + Maven 3.9.9 |
| Windows 工具链 | VS2022 Community（`vcvarsall.bat x64` / `cl.exe`）、Maven 3.9.9、Mandrel 25；Windows `.m2` 原本为空 |

证据：`probe-native-20261115.log`、`probe-mandrel.log`、`inventory-live.log`、`service-mode-probe.log`。

---

## 2. 三节点镜像清理（实机）

`v3-prune-node-images.sh` 先 dry-run 再 `--apply`。判定依据：`kubectl get pods -o jsonpath` 取运行中 Pod 的 `containerStatuses.imageID`，保留该 digest；无法确定唯一保留对象时整组跳过。

- 每节点原有 3 个 api 版本（`ci-v2` 650MB / `ci-verify` 520MB / `slim` 439MB）和 3 个 backend 版本（`ci-v2` 585MB / `ci-verify` 488MB / `slim` 406MB）。
- **保留 6 个，删除 12 个**；`crictl rmi --prune` 另清 untagged `mirrored-pause:3.6`（3 节点）与 `mirrored-coredns-coredns:1.14.3`（agent-0），k3s 需要时会重新拉取。
- 验证：三个节点各只剩 `car-monit-api:ci-v2` 与 `car-monit-backend:ci-v2` 一行。

证据：`prune-dryrun.log`、`prune-apply.log`、`prune-plan-20261115-151823.txt`。回滚：`k3d image import car-monit-api:ci-v2 car-monit-backend:ci-v2 -c v3`。

---

## 3. 单实例互斥（实机）

**更正**：上一轮交付的 `v3-switch-mode.ps1` 假设单机版是 Windows java 进程；实测发现单机版在 **WSL 内由 systemd 管理**。已重写为 Windows 包装器，实际切换委托给 WSL 内 `v3-enforce-single-mode.sh`。

实测 `standalone`（保留 systemd 单机、停 k3d）：

| | 切换前 | 切换后 |
| --- | --- | --- |
| WSL `Mem.used` | 6019 MB | **3474 MB**（−2545 MB） |
| WSL `Mem.available` | 1924 MB | 4469 MB |
| java 进程数 | 10 | 4 |
| 集群 ready 副本 | 6 | 0 |

证据：`switch-standalone.log`。恢复集群：`bash v3-enforce-single-mode.sh cluster`。最终状态见 §4。

---

## 4. 配额与 VHDX 回收（实机）

Guest 侧先清理（`guest-clean-for-compact.sh`）：删 `ci-verify`/`slim`/`eclipse-temurin:17-jre` 与悬空镜像，Images 17→11（10.86→10.18 GB），`sudo fstrim -av` 修剪 964.1 GiB 逻辑空间。

严格按用户给定序列（`v3-compact-wsl.ps1 -Apply`）：

```powershell
$d = 'openEuler-24.03-LTS-SP4'
wsl.exe --shutdown
wsl.exe --manage $d --set-sparse false
wsl.exe --manage $d --compact
fsutil sparse queryflag 'D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx'
```

| 轮次 | VHDX 前 → 后 | 回收 | D 盘 |
| --- | --- | --- | --- |
| 首次（15:24） | 42.812 → 38.315 GB | **4.497 GB** | 8.7 → 13.2 GB |
| 编译期两次（18:49/18:51） | 39.174 → 39.146 GB | 0.026–0.033 GB | ≈4.9 → 6.22 GB |
| 收尾（19:31） | 41.045 → 39.79 GB | **1.255 GB** | 3.37 → 4.63 GB |

- Linux Mandrel 解压与 native 构建让 VHDX 从 39.15 GiB 增长到 41.045 GB；清理 ext4 临时目录 `/home/dev/native-work`（686 MB）+ fstrim 后成功回收 1.255 GB。
- 两次早期 compact 中 `wsl.exe --manage --set-sparse false` 报 `WSL_E_DISTRO_NOT_STOPPED`（VHD 句柄未释放）；因 VHDX 原本就是非稀疏，`--compact` 仍可正常执行，未影响结果。
- 脚本的 `-MinFreeGB 8` 保护在 D 盘 <8 GB 时会拦截，本轮两次用 `-Force` 放行；原位压缩实际不需要等量临时空间，已实测无误。
- 编译期临时把配额提到 `12GB/4GB/6核`（`v3-wsl-quota.ps1 -Profile custom`），结束后恢复 `4GB/2GB/2核`；每次配额变更都靠 `wsl --shutdown` 生效。

最终复核（`final-state-check2.log`）：`nproc=2`、`Mem.total=3919MB`、单机服务 `active/active`、DB/中间件 4 容器 `Up`、k3d 4 节点 `Exited`、宿主可用 **5.12 GB**、D 盘 4.59 GB。

---

## 5. Mandrel 双平台工具链（实机）

### 5.1 Windows 版（用户给定 7z）
`D:\jdk\mandrel-25.0.4.1-Final.7z`（156,932,232 B）经 `7z l` 确认是 **Windows x64**（`bin/native-image.cmd`、`java.exe`、`*.dll`、`*.pdb`，6114 文件 / 解压 598 MB）。解压工具：本机无 7-Zip 安装，但 `C:\ProgramData\chocolatey\tools\7z.exe` (24.09) 与 `D:\work\vm16.2.1\7za.exe` 可用；Windows 自带 `tar.exe` 不支持 LZMA。

`native-image 25.0.4.1` + VS2022 `cl.exe` 闭环：Hello → **13.43 MB exe / 38 s / 峰值 RSS 1.21 GB**。**它只能产出 Windows PE，不能产 Linux ELF。**

### 5.2 Linux 版（本轮下载安装）
按需求下载与 Windows 同版本的 Linux amd64 包：

| 项 | 值 |
| --- | --- |
| 文件 | `D:\jdk\mandrel-java25-linux-amd64-25.0.4.1-Final.tar.gz` |
| 大小 / sha256 | 221,899,480 B / `e47ff6bfe6a8dbb482fdc65c9a49fc6f3ba2fa61ef3cc8fb6229a88989054c31` |
| 来源 | GitHub `graalvm/mandrel` release `mandrel-25.0.4.1-Final`（官方 API asset 534182209） |
| 安装 | 解压到 WSL **ext4** `/home/dev/tools/mandrel-java25-25.0.4.1-Final`（575 MB，符号链接 `/home/dev/tools/mandrel-25`），保留 symlink/可执行位 |
| C 工具链 | `sudo dnf install -y gcc gcc-c++ glibc-devel zlib-devel libstdc++-devel`（原系统 gcc/g++/ld 全部缺失） |
| 冒烟 | Hello ELF 13,372,128 B / 2m48s / 峰值 RSS 1.13 GB / 输出 `hello native` |

**下载坑（已固化到 `download-mandrel-linux.py`）**：本机 `curl.exe` 走代理报 `CONNECT tunnel failed, response 502`；`github.com/.../releases/download/...` 直链报 `RemoteDisconnected`。可用路径是 **GitHub API asset 端点 + `Accept: application/octet-stream`**（重定向到 `release-assets.githubusercontent.com`），并实现了 Range 断点续传与 sha256 校验；222 MB 实测 82.2 s 完成。

证据：`download-mandrel-linux.log`、`setup-mandrel-linux.log`。

---

## 6. 发版 jar 重建（实机，部分）

上一轮审计发现 api/backend 的 jdk21/25 共 4 个 jar 早于 pom 瘦身改动（STALE）。本轮 native 构建阶段一用当前 pom 重建了 `car-monit-api-jdk25`：

| | 重建前 | 重建后 |
| --- | --- | --- |
| `api jdk25` jar | 215,881,278 B | **211,027,173 B**（−4,854,105 B / −4.63 MiB） |
| 非目标平台 native | 13 | 3 |
| STALE | YES | no |

其余 3 个（api jdk21、backend jdk21、backend jdk25）仍未重建。陷阱（保留）：fat jar 的 `BOOT-INF/lib/*.jar` 全是 ZIP_STORED，不可重压；`pulsar-client` 有真实代码引用，不可删；Flink 依赖为 provided。

---

## 7. Spring Boot 4 AOT + native-image 构建（实机）

### 7.1 Windows Maven 准备
把 WSL CI 缓存 `/home/dev/.m2/repository`（789 MB）复制到 `D:\work\maven-repo`，新建 `C:\Users\abelz\.m2\settings.xml` 指向该仓库 + 阿里云镜像。`mvn -v` = Maven 3.9.9 / Java 25.0.4.1；`native-maven-plugin:1.1.14` 与 reachability metadata 1.0.15 由镜像补齐。

### 7.2 失败链与修复（逐轮实测）

| # | 错误 | 修复 |
| --- | --- | --- |
| 1 | `NoClassDefFoundError: KeyedBroadcastProcessFunction`（Flink Job 在主 classpath，依赖 provided） | Maven profile `native-flink-exclude` 编译期排除 `**/flink/VehicleTrackFlinkJob.java`；构建命令必须带 `clean` |
| 2 | `UnsatisfiedLinkError: NativeStaticallyReferencedJniMethods.sslSignRsaPkcsSha1()` 等 5 个 tcnative 类 | `--initialize-at-run-time=io.grpc.netty.shaded`（整包）+ 具体类 |
| 3 | Logback `Logger` → `LoggerContext` → `BasicStatusManager` → `TurboFilterList` 逐类报错 | `--initialize-at-build-time=ch.qos.logback`（**整包**，一次收敛） |
| 4 | fastjson2 `JSONFactory$CacheItem`、`ObjectWriterBaseModule`、`ToDouble`、`ObjectReaderImplString`、`JSONReader$Context` 逐类报错 | `--initialize-at-build-time=com.alibaba.fastjson2`（整包）+ 具体类 |
| 5 | 误加 `--initialize-at-build-time=org.slf4j` 会让 SLF4J 在构建期绑定 NOP provider | 已移除。日志中 `SLF4J(W): No SLF4J providers` 是 **native-image builder 自身**告警，产物运行日志正常 |

**关键结论**：`META-INF/native-image/.../native-image.properties` 里的 `Args =` 对 Spring Boot fat jar 不生效；参数必须写在模块 pom 的 `native-maven-plugin <buildArgs>`。曾用 `native-retry-from-args.bat` 复用 `@argfile` 跳过 3 分钟 AOT，配合 `native-iterate.py` 自动解析报错追加参数，共 6 次端到端失败 + 8 轮快速迭代后收敛。

**最终 13 条 buildArgs**（`evidence/native-iterate-final.args`，已固化六分支模块 pom，XML 校验通过）：

```text
--initialize-at-run-time=io.grpc.netty.shaded
--initialize-at-run-time=io.grpc.netty.shaded.io.netty.internal.tcnative
--initialize-at-run-time=io.grpc.netty.shaded.io.netty.handler.ssl
--initialize-at-run-time=io.grpc.netty.shaded.io.netty.util.internal.SystemPropertyUtil
--initialize-at-run-time=io.grpc.netty.shaded.io.netty.util.ResourceLeakDetectorFactory
--initialize-at-build-time=ch.qos.logback
--initialize-at-build-time=com.alibaba.fastjson2
--initialize-at-build-time=ch.qos.logback.classic.Logger
--initialize-at-build-time=com.alibaba.fastjson2.JSONFactory$CacheItem
--initialize-at-build-time=com.alibaba.fastjson2.writer.ObjectWriterBaseModule
--initialize-at-build-time=com.alibaba.fastjson2.function.impl.ToDouble
--initialize-at-build-time=com.alibaba.fastjson2.reader.ObjectReaderImplString
--initialize-at-build-time=com.alibaba.fastjson2.JSONReader$Context
```

### 7.3 运行时反射（GraalVM tracing agent）
第一次产物（342,769,664 B）启动失败：`forest.retryer` 按类名字符串绑定 `com.dtflys.forest.retryer.BackOffRetryer`，类在 `forest-core-1.8.0.jar` 里但被 native-image 裁剪；用 `--forest.retryer=java.lang.Object` 探测后遇到第二处 `ForestBeanRegister` 通过 `Class.newInstance()` 反射实例化 `com.dtflys.forest.logging.DefaultLogHandler`。

按 GraalVM 官方实践，用 JVM fat jar + `-agentlib:native-image-agent=config-output-dir=...,config-write-period-secs=10` 采集，得到 `reachability-metadata.json`（**1333 reflection + 806 resources**，确认含上述两个类），放到六分支 `src/main/resources/META-INF/native-image/com.ruoyi/<module>-agent/`（**独立子目录**，避免被 Spring AOT 同名输出覆盖）。端到端构建分析阶段反射注册类型从 19,592 增至 20,219，证明配置生效。

### 7.4 端到端构建结果（双平台）

| | Windows `.exe` | Linux ELF |
| --- | --- | --- |
| 命令 | `native-build.bat <worktree> pro-business-api api-jdk25-final` | `v3-native-build-linux.sh api 25 <worktree>`（`WORK_ROOT` 把源码同步到 ext4） |
| 日志 | `native-api-jdk25-final.log` | `native-api-jdk25-linux.log` |
| 结果 | BUILD SUCCESS，Total 14:40，native-image 11m7s | BUILD SUCCESS，Total 28:44，native-image 28m8s |
| 产物 | `pro-business-api.exe` **348,528,640 B / 332.38 MB** + 8 个 JDK `.dll` | `pro-business-api` **340,921,056 B / 325.13 MB**（ELF x86-64, dynamically linked, stripped）+ 8 个 `.so` |
| sha256 | `8E505CAC08C9E615579B03F32B38545B4839BC7A21088FC4572EB3385C42AA1A` | `9399D12952BEA5CB8622E209B1E308F44E1FA0C7F5E8CFC3C793E1573D00D7B1` |
| 峰值 RSS | **10.11 GB** | **10.11 GB**（`[3/8]`；12GB 配额下 GC 占 63%，`[7/8]` 单独耗时 524 s） |
| 可达类型 | 58,260 types / 20,219 reflection | 58,479 types / 20,211 reflection |

Linux 编译期需把 WSL 临时提到 `12GB/4GB/6核` 并停掉非必需容器与单机 java 服务；Windows 编译期必须 `wsl --shutdown`。**两个平台编译不能并行**（内存各约 10 GB）。

### 7.5 运行验证（如实：未完整启动）
两个平台最终产物均**越过 Forest 反射阻塞**（日志正常输出 Logback、Spring Boot banner），但一致失败于：

```text
UnsatisfiedDependencyException: ... 'dwdLcztFwqjcxxMapper':
Property 'sqlSessionFactory' or 'sqlSessionTemplate' are required
  at org.mybatis.spring.support.SqlSessionDaoSupport.checkDaoConfig
```

- `--spring.main.lazy-initialization=true` 无效；`--debug`/AOT 输出检查未见 `sqlSessionFactory` bean 定义。
- 与平台无关（Windows/Linux 完全相同），判断为 **Spring Boot 4 AOT 与 MyBatis-Plus 3.5.18 的 BeanFactoryPostProcessor/MapperFactoryBean 注册兼容问题**，不是 native-image 反射元数据可解决的问题，需库升级或自定义 `BeanFactoryInitializationAotProcessor`。
- Windows 侧连 WSL 依赖：`127.0.0.1` 转发不到 docker 映射端口（5432/3307 timeout），改用 **WSL 实际 IP `172.29.27.7`** 可直连 5432/3307/6379（9200/9092 仍超时）。
- DB 容器原本 256m 限额在 WSL 反复重启下 OOM（exit 137）；编译期临时放宽 768m，常态调整为 **512m**。
- 日志：`native-run-api-jdk25-win-final3-*.log`、`native-run-api-jdk25-win-lazy-*.log`、`native-run-api-jdk25-linux-*.log`。

---

## 8. 资源占用实测（如实）

| 维度 | JVM 基线 | Native 实测 |
| --- | --- | --- |
| 发版 jar | 211–212 MB | — |
| 可执行文件 | — | Windows 332.38 MB / Linux 325.13 MB |
| 容器镜像 | `car-monit-api:ci-v2` **645 MB** | `car-monit-api:native-jdk25` **493 MB**（152 MB 基础层 + 341 MB ELF 层，**−152 MB / −23.6%**） |
| 稳态 RSS（JVM） | 单机 api ≈393 MB、backend ≈281 MB；k3d Pod workingSet 271–338 MiB | **未测得**（业务上下文初始化失败，见 §7.5） |
| 启动阶段峰值 RSS | — | Linux ELF **29.8 MB**（0.5 s 采样，进程在 Spring 上下文刷新阶段即退出） |
| 启动到端口就绪 | — | **未达成** |
| 构建期峰值 RSS | — | Windows 10.11 GB / Linux 10.11 GB |
| 构建耗时 | — | Windows 11m7s / Linux 28m8s（6 核，GC 压力大） |

容器化：`templates/Dockerfile.native` + `v3-native-docker-build.sh`，构建上下文只含 ELF。生产首选 `distroless/base-debian12`（~25 MB）可把镜像压到 ~366 MB，但本机 `docker pull debian:12-slim` 超时（网络受限），**实际使用本地离线基础镜像 `car-monit-sys:local`（152 MB）**，如实记录。

结论边界：本轮可确认「产物体积、容器镜像体积、构建期资源、启动阶段内存」；**不能**据此宣称 native 版本业务稳态内存/启动时间优于 JVM 版。

---

## 9. CICD

- `scripts/v3/ops/templates/native-image.yml` 已同步到六个分支 `.github/workflows/native-image.yml`（backend 分支 runner 标签 `wsl-k3s-backend`）。`workflow_dispatch` 参数 `app / jdk / platform / run_bench`；job `native-windows`（Windows self-hosted）与 `native-linux`（WSL runner + Linux Mandrel）分别调用 `native-build.bat` 与 `v3-native-build-linux.sh`，含 artifact 收集 + sha256。
- 本机两个自托管 runner 在线（`Runner.Listener` ×2，目录 `/opt/actions-runner`、`/opt/actions-runner-api`）。
- **未触发云端 Actions run（如实）**：本机无 `gh` CLI、无可用 PAT，且 `git status` 显示 workflow 文件为未跟踪 `??`（未提交/推送），云端不存在该 workflow。
- **本地等价实跑**：按 workflow 步骤在本机执行了构建与 artifact 收集，产物在 `D:\work\runtime-logs\v3-ops\dist\`：
  - `api-jdk25-windows-amd64.exe`（348,528,640 B，sha256 见 §7.4）
  - `api-jdk25-linux-amd64`（340,921,056 B，sha256 见 §7.4）
  - 各自 `.sha256` 与 `evidence/native-artifact-*.json` manifest（含 git_sha `0a76585`）
- 要跑真实 CI：提交并推送 workflow，注册 Windows runner 或用具备 `actions:write` 的 token 执行 `workflow_dispatch`。

---

## 10. 脚本与运维命令索引

| 文件 | 位置 | 用途 |
| --- | --- | --- |
| `v3-inventory.sh` | `scripts/v3/ops/` | WSL/docker/k3d 只读盘点 |
| `v3-prune-node-images.sh` | 同上 | 每节点每仓库只留 1 份镜像（默认 dry-run） |
| `v3-enforce-single-mode.sh` / `v3-switch-mode.ps1` | 同上 | WSL 内单机/集群互斥 + Windows 包装器 |
| `v3-wsl-quota.ps1` | 同上 | `.wslconfig` 分档 + 备份（本轮用 `custom 12GB/6核` 与 `cluster`） |
| `v3-compact-wsl.ps1` | 同上 | VHDX 回收（本轮实跑 4 次） |
| `v3-jar-audit.py` / `v3-slim-jars.sh` | 同上 | jar 审计 / 重建 + jlink + 分层镜像 |
| `v3-native-bench.ps1` / `v3-native-bench-linux.sh` | 同上 | 双平台原生可执行文件大小/启动/RSS/CPU 实测 |
| `v3-setup-mandrel-linux.sh` | 同上 | Linux Mandrel 解压 + gcc 工具链 + Hello 冒烟 |
| `v3-native-build-linux.sh` | 同上 | Linux AOT + native-image（支持 `WORK_ROOT` ext4 同步） |
| `v3-native-docker-build.sh` / `templates/Dockerfile.native` | 同上 | 最小容器镜像打包 |
| `v3-native-cicd-local.ps1` | 同上 | artifact + sha256 + manifest 本地等价实跑 |
| `templates/native-image.yml` | 同上 | CICD workflow 模板 |
| `download-mandrel-linux.py` | `D:\work\runtime-logs\v3-ops\` | GitHub API asset 下载 + Range 续传 + sha256 |
| `native-build.bat` / `native-retry-from-args.bat` / `native-iterate.py` | 同上 | Windows 端到端构建 / 快速 args 迭代 / 参数自动收敛 |
| `collect-native-agent-config.sh` | 同上 | tracing agent 采集反射元数据 |
| `run-linux-native-build.sh` / `run-linux-native-bench.sh` / `linux-build-prep.sh` | 同上 | Linux 构建/实测/编译前置包装 |
| `guest-clean-for-compact.sh` / `restore-after-compact.sh` | 同上 | compact 前置清理 / 重启恢复 |

一键复现顺序：

```text
[WSL]  v3-inventory.sh → v3-prune-node-images.sh --apply
[WSL]  v3-enforce-single-mode.sh standalone
[Win]  v3-wsl-quota.ps1 -Profile cluster -Apply
[WSL]  guest-clean-for-compact.sh
[Win]  v3-compact-wsl.ps1 -Apply                      # shutdown + compact，配额同时生效
[WSL]  restore-after-compact.sh
[WSL]  v3-setup-mandrel-linux.sh                      # Linux Mandrel + gcc
[Win]  native-smoke\build.bat                         # Windows 工具链冒烟
[Win]  native-build.bat <worktree> <module> <label>  # 需 wsl --shutdown 释放内存
[WSL]  v3-native-build-linux.sh api 25 <worktree>     # 需临时 12GB/6核 配额
[Win]  v3-native-cicd-local.ps1 -Exe <exe> -Platform windows
[WSL]  v3-native-docker-build.sh <elf> car-monit-api:native-jdk25
[Win]  v3-wsl-quota.ps1 -Profile cluster -Apply -Shutdown   # 恢复常态
```

静态校验：8 个 sh `bash -n` 通过；3 个 py `py_compile` 通过；7 个 ps1 `[Parser]::ParseFile` 0 错误且纯 ASCII 无 BOM（PS 5.1 GBK 坑）。删除类脚本默认 dry-run，`--apply`/`-Apply` 才执行。

---

## 11. 风险与未解决项（如实）

1. **业务完整启动未通过**：Spring Boot 4 AOT + MyBatis-Plus `sqlSessionFactory` 缺失（平台无关）。需升级 MyBatis-Plus / 提供 `BeanFactoryInitializationAotProcessor` 或补充 AOT bean-definition hints，属业务代码与库适配，不在本轮运维范围。修复前不建议把 native 镜像投入生产。
2. **fastjson2 整包 build-time 的警告**：`RecomputeFieldValue.FieldOffset ... sun.misc.Unsafe.objectFieldOffset` 无法自动重算（JDKUtils / ObjectWriterImplMap）。构建通过但**运行时 fastjson2 正确性需业务接口验证**；若出现异常，应改回逐类 build-time 并仅保留 heap 必需类。
3. **单一工具链**：只有 Mandrel 25；jdk17/21 分支用其编译，native 运行时语义是 JDK25，不等价于同版本 GraalVM。六个组合仅 `api/jdk25` 在双平台构建完成。
4. **3 个 stale jar 未重建**（api jdk21、backend jdk21、backend jdk25）。
5. **编译资源**：native-image 峰值约 10.11 GB，Windows 编译需关闭 WSL、Linux 编译需临时 12GB/6核；两者不能并行。Linux 在 12GB 配额下 GC 占 63%，若内存更充裕（≥14GB）可显著缩短 28 分钟编译时间。
6. **磁盘**：D 盘最终 4.59 GB；`docker system df` 显示 Volumes 仍有 **4.995 GB 可回收**（23 个未引用卷），未擅自删除，列为后续可选回收项。
7. **CICD 未云端触发**：见 §9。
8. **DB 限额**：256m 实测在重启压力下 OOM(137)，常态已调为 512m；如再出现 137 需进一步评估。
9. **Windows → WSL 依赖访问**：`localhostForwarding` 对 docker 映射端口不可靠，需使用 WSL 实际 IP（本轮 `172.29.27.7`，重启后会变），运行脚本应动态取 IP。
