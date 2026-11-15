# WSL / k3d 镜像清理、单实例互斥、资源配额与 VHDX 回收（可复现运维记录）

> 记录时间：2026-11-15 14:39–14:55（GMT+8）
> 目标环境：WSL2 `openEuler-24.03-LTS-SP4`；k3d 集群 `v3`（`k3d-v3-server-0` / `k3d-v3-agent-0` / `k3d-v3-agent-1`）
> 参考输入：三份历史会话导出（`Docker images and containers status`、`JDK 17 21 25 分支 SpringBoot 升级与实测验证`、`Java V3工作树代码审核与实机联调测试`）

---

## 0. 本轮结论（先读）

| 目标 | 本轮状态 | 说明 |
| --- | --- | --- |
| 清除三个 k3d 节点内 car-monit-backend/api 过时镜像 | **脚本已交付，实机未执行** | `wsl.exe` 被会话的命令安全黑名单拦截，无法进入 WSL/docker |
| 单机版与 k3d 集群版互斥运行 | **脚本已交付，实机未执行** | 同上；当前 9989/9902/6379 由 `wslrelay.exe` 转发，说明有一套服务在跑 |
| 按实测分配内存/CPU，提升 Windows 可用内存 | **已执行配置修改** | `.wslconfig` 由 `8GB/4GB/4核` 改为 `4GB/2GB/2核`（实测稳定档）；已备份；**需 `wsl --shutdown` 才生效** |
| 各 JDK 版本发版 jar 最小化打包 | **只读审计已实机完成；重建/镜像构建脚本已交付、未执行** | 发现 4 个 jar 是瘦身改动前的旧产物，这是最大可回收点 |
| 清理 WSL 多余磁盘占用 / compact VHDX | **脚本已交付，实机未执行** | 当前 VHDX 为 **42.812GB**，不是命令注释里的 16.454GB |
| 可复现文档 + 运维脚本 | **已完成** | 本文 + `scripts/v3/ops/` 下 7 个脚本 |

**阻塞原因（如实记录）**：本会话执行 `wsl.exe --list --verbose` 返回 `Permission denied`，工具层提示 `PROGRAM BLOCKED BY SECURITY POLICY ... wsl.exe ... Program Blacklist`，并明确不可通过其它 shell/脚本重试或等价绕过；Windows PATH 中也没有 `docker` CLI（历史 docker 命令全部走 `wsl -d ... -- docker ...`）。因此**所有 WSL 内部的删除、切换、构建、compact 动作本轮都没有实际执行，也没有产生任何删除结果**。要继续实机执行，需用户在「安全中心 → 命令安全 → 程序黑名单」移除 `wsl.exe` 后让我接续，或自行运行本文给出的脚本。

---

## 1. 实机基线（本轮 Windows 侧采集，2026-11-15 14:41）

| 项 | 实测值 |
| --- | --- |
| 物理内存 / 可用 | 13.84 GB / **1.86 GB** |
| 逻辑 CPU | 12 |
| `vmmemWSL` 工作集 | **4247 MB** |
| `.wslconfig`（改前） | `memory=8GB`、`swap=4GB`、`processors=4`、`vmIdleTimeout=3600000`、`kernelCommandLine=vsyscall=emulate`、`[general] instanceIdleTimeout=-1` |
| VHDX | `D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx` = **43,840 MB (42.812 GB)** |
| `fsutil sparse queryflag` | **该文件没有设为稀疏**（已满足 `--compact` 前置） |
| swap VHDX | `D:\wsl\swap\swap.vhdx` = 2054 MB |
| 磁盘余量 | C: 9.07 GB，D: **10.72 GB** |
| 监听端口 | 9989 / 9902 / 6379，均由 `wslrelay.exe` (PID 61848) 转发 → WSL 内有服务在跑 |
| WSL 进程 | `wslservice.exe`、`vmmemWSL`、多个 `wsl.exe`/`wslhost.exe`（另有会话在用 WSL） |

> 用户命令注释中的 `16.454GB -> 9.617GB` 是**更早一次** compact 的历史值；历史会话里也有「VHDX 仍 16.454GB、NOT sparse」的记录。本轮 VHDX 已增长到 42.812GB，compact 的预期回收量不能用旧数字推算。

### 历史实测基线（用于"根据实测分配"）

| WSL 配额 | `vmmemWSL` | Windows 可用内存 | 稳定性结论 |
| --- | --- | --- | --- |
| 6GB / 4 核 | 5505 MB（峰） | **0.00 GB** | 实际只用 1.78GB，差额全是 WSL2 不归还的 page cache；重度换页 |
| **4GB / 2 核** | **2469 MB** | **3.71 GB** | 3 节点 Ready 持续 13 分钟、coredns/local-path-provisioner `1/1`、双 runner online，稳定 |
| 3GB / 2 核 | 1620 MB | **5.07 GB** | 单机/DB 可用；**k3s 冷启动 apiserver 不就绪**（并非 OOM，是余量不足） |
| 8GB / 4 核（本轮改前） | 4247 MB | 1.86 GB | 配额越大 `vmmem` 越大，宿主越紧张 |

组件明细（4GB 稳态）：WSL 内峰值 1.78GB / 空闲 1.52GB；4 个 k3d 容器合计 **662MB**（server 355 / agent-0 160 / agent-1 140 / lb 7）；`k3s`×3 ≈840MB、`containerd`×3 ≈483MB、两个 `Runner.Listener` ≈258MB、`dockerd` 109MB、coredns 59MB。
其它已验证结论：`autoMemoryReclaim=gradual` 会让 k3s apiserver 间歇 `ServiceUnavailable`、runner 掉线，**不要常开**；WSL 内 `drop_caches` 对 `vmmem` 无效，唯一可靠手段是调低 `memory` 上限。

业务资源实测：
- k3s Pod：`api` workingSet 271–338 MiB、`backend` 259–263 MiB；`300Mi` 时 backend 登录 `Java heap space` OOM，**`400Mi` + 瘦身 jar + jlink runtime 后完整功能打通**。清单 `manifests-final.yaml` 当前为 `requests 400Mi/100m`、`limits 400Mi/2000m`、`replicas: 3`、`imagePullPolicy: Never`、镜像 `car-monit-api:slim` / `car-monit-backend:slim`。
- DB：`mysql_wsl` 峰值 32.02MiB → 上限 `256m`；`opengauss` 峰值 81.02MiB → 上限 `256m`；硬上限 500m（脚本 `D:\work\runtime-logs\set-db-memory-limits.sh`）。
- 单机版：Low 档两个 java 各 `768m` + ES 512m + Kafka 512m，预算 ≈2.6GB（`scripts/v3/start-v3-all.ps1`）。

---

## 2. 内存/CPU 分配：本轮已执行的修改

**已备份**：`D:\work\runtime-logs\v3-ops\backup\.wslconfig.bak-20261115-1445`（原 `8GB/4GB/4核`）

**已修改** `C:\Users\abelz\.wslconfig`（只改 3 行，其余段/键原样保留）：

```diff
 [wsl2]
-memory=8GB
-swap=4GB
-processors=4
+memory=4GB
+swap=2GB
+processors=2
 swapFile=D:\\wsl\\swap\\swap.vhdx
 localhostForwarding=true
 vmIdleTimeout=3600000
 kernelCommandLine=vsyscall=emulate
```

选择 4GB 而不是 3GB 的原因：4GB 是**唯一同时验证过「k3d 三节点 + 双 runner + DB」稳定**的档位，宿主可用内存从 1.86GB 提升到实测 3.71GB（约 +1.85GB）。3GB 虽然实测宿主可用 5.07GB，但 k3s 冷启动会失败，只有在**确认 k3d 已停**后才可用。

**生效条件**：`.wslconfig` 需 `wsl.exe --shutdown` 后重启 WSL 才生效。本轮未执行 shutdown（会中断其它会话正在使用的 WSL 服务）。执行方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1 -Profile cluster -Apply -Shutdown
```

若要**最大化 Windows 可用内存**（目标 ≈5GB），按此顺序：

```powershell
# 1) 先停 k3d，只保留单机（互斥）
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1 -Mode standalone -Apply
# 2) 再切 3GB 档并重启 WSL
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1 -Profile lean -Apply -Shutdown
# 3) 采样复核
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-measure.ps1 -Seconds 60 -Interval 5
```

`-Profile auto` 会自动探测集群 deployment 副本数，>0 用 4GB、否则用 3GB。DB 容器在 shutdown 后需 `docker start mysql_wsl opengauss`。

---

## 3. 三节点 k3d 镜像清理（未执行，脚本可复现）

### 判定逻辑
历史多次执行 `k3d image import car-monit-api:slim car-monit-backend:slim -c v3`，同一 tag 被反复导入，containerd 会把旧 digest 变成 untagged 残留，节点内因此累积多个版本的 car-monit 镜像。脚本按**每个仓库（`car-monit-api` / `car-monit-backend`）在每个节点各保留 1 份**处理：

1. 从 `kubectl get pods ... -o jsonpath` 取运行中 Pod 的 `containerStatuses.imageID` → 这是"在用版本"，优先保留；
2. 无在用 Pod 时，保留带 `:slim` tag 的镜像（可用 `--keep-tag` / `--keep-digest` 指定）；
3. **无法确定唯一保留对象、或出现多个候选（滚动更新中）时整组跳过，绝不猜测删除**；
4. 其余同仓库镜像 `crictl rmi`，最后 `crictl rmi --prune` 清 untagged 残留；
5. 默认 dry-run，`--apply` 才删除；计划与结果写入证据文件。

### 复现命令（在 WSL 内）

```bash
OPS=/mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops
bash $OPS/v3-inventory.sh                         # 只读盘点，落证据
bash $OPS/v3-prune-node-images.sh                 # dry-run，输出 KEEP/DROP 清单
bash $OPS/v3-prune-node-images.sh --apply        # 实际删除
bash $OPS/v3-prune-node-images.sh --apply --keep-tag min-jdk25 --no-prune   # 切到新镜像时用
```

`crictl` endpoint 沿用已验证的 `unix:///run/k3s/containerd/containerd.sock`（`crictl ps --name` 匹配不到 k3s 容器名，故用 kubectl 取 imageID）。

**回滚**：镜像只从节点的 containerd 删除，WSL docker 里的源镜像不动；需要时 `k3d image import car-monit-api:slim car-monit-backend:slim -c v3` 重新导入即可。

---

## 4. 单机 / 集群互斥（未执行，脚本可复现）

`v3-switch-mode.ps1` 的检测口径：

- 单机 = Windows java 监听 `9989`(backend) / `9902`(api)，由 `start-v3-all.ps1` 管理（`v3-pids.json`）；
- 集群 = `k3d-v3-server-0` 内 `kubectl get deploy car-monit-api car-monit-backend` 的 ready 副本数 > 0。

切换动作：
- `→ standalone`：先把两个 deployment `scale --replicas=0`，可选 `docker stop k3d-v3-*` 彻底释放 ~662MB 容器 + ~1.3GB k3s/containerd；已监听则不重复拉起 java；再 `start-v3-all.ps1 -Minimal -MemoryProfile Low`。
- `→ cluster`：`start-v3-all.ps1 -Stop`（按 pid 文件停，不盲杀）→ 等端口释放 → `docker start k3d-v3-*` → 等 3 节点 Ready → `scale 3+3` + `rollout status`。
- `-Mode status` 只读；默认 dry-run，`-Apply` 才执行；切换后做 post-check，两者同时活跃会告警。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1                # status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1 -Mode standalone -Apply
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1 -Mode cluster -Apply
```

---

## 5. 六个 JDK 发版 jar 的最小化打包

### 5.1 本轮已实机完成的只读审计

命令：`python scripts\v3\ops\v3-jar-audit.py`（纯 zipfile central directory，不解压、不修改任何 jar）
证据：`D:\work\runtime-logs\v3-ops\evidence\jar-audit-20261115-145209.txt` / `.csv`

| APP | JDK | JAR_BYTES | 嵌套 lib 数 | lib 字节 | classes 字节 | 非目标平台 native | STALE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| api | 17 | 211,030,817 | 296 | 209,822,690 | 825,713 | 3 | no |
| api | 21 | 215,881,053 | 296 | 214,703,313 | 801,806 | 13 | **YES** |
| api | 25 | 215,881,278 | 296 | 214,703,339 | 802,004 | 13 | **YES** |
| backend | 17 | 178,301,142 | 335 | 177,418,151 | 571,194 | 0 | no |
| backend | 21 | 199,747,840 | 339 | 198,864,541 | 571,041 | 0 | **YES** |
| backend | 25 | 199,749,631 | 339 | 198,866,348 | 571,024 | 0 | **YES** |

### 5.2 关键发现：4 个 jar 是瘦身改动前的旧产物

逐一核对后，**六个分支 `spring-boot-maven-plugin` 的 `excludeGroupIds` / `excludes` 配置完全一致**（api 排 `org.apache.flink` + 10 个 classifier；backend 排 `org.apache.calcite,org.apache.groovy,com.aliyun.mns`）。差异不在源码，而在**构建时间**：

| | jar 生成 | pom 瘦身改动 |
| --- | --- | --- |
| api/backend jdk17 | 11-14 22:00 / 22:01 | 11-14 21:06 / 21:09 |
| api/backend jdk21/25 | **11-14 12:46–13:01** | 同上（晚于构建约 8 小时） |

因此 jdk21/25 的 jar 仍带着本该被排除的依赖：

- `backend jdk21/25` 比 jdk17 多 **4 个 jar / 21,448,068 B**：`calcite-core-1.40.0` 8,667,143、`groovy-5.0.8` 8,070,650、`aliyun-sdk-mns-1.1.8.8` 4,191,724、`calcite-linq4j` 518,551。
- `api jdk21/25` 比 jdk17 净多 **4,881,037 B**，其中 4 个非 linux-x86_64 的 `netty-codec-native-quic` 变体合计 **9,331,379 B**（linux-aarch_64 2,718,748 / osx-x86_64 2,555,112 / osx-aarch_64 2,403,673 / windows-x86_64 1,645,346）。

**结论：最小化打包收益最高的第一步不是改代码，而是用现有 pom 重新 `mvn package` 这 4 个 jar。**

### 5.3 已验证的瘦身链路（历史，作为基线不要重复造轮子）

| 环节 | 前 → 后 |
| --- | --- |
| api fat jar | 275,304,862 → 211,030,709 B（−23.3%，排 Flink provided + 非目标平台 Netty native）；backend −10.7% |
| jlink runtime | JDK 303MB → **66MB**（`--strip-debug --no-man-pages --no-header-files --compress=zip-9`，模块集含 `jdk.net`，缺它会 `ClassNotFoundException: jdk.net.ExtendedSocketOptions`） |
| 基础镜像 `car-monit-sys:local` | 255MB → **152MB**（卸载残留 MySQL RPM；`docker export \| docker import` 拍平，单纯 `RUN rm` 只加白障层） |
| backend 镜像 | 965MB → 504MB → **401MB** |
| api 镜像 | 1.04GB → 537MB → **434MB** |

### 5.4 本轮新增方案（`v3-slim-jars.sh`）

- `--rebuild-jars`：用各自的 JDK（`JAVA_HOME=$JH/bin`）对 6 个工作树执行 `mvn -B -ntp -DskipTests package -pl <module> -am`，打印前后字节差；不改任何 pom。
- `--audit`：只读体积报告。
- `--build --strip`：jdeps 按版本算模块 → 每个 JDK 生成独立 jlink runtime → 共享 `car-monit-jre:jdkN` 层 → `car-monit-api:min-jdkN` / `car-monit-backend:min-jdkN`（**不动 `:slim`，可回滚**）；`--strip` 只删确证无用的非 linux-x86_64 native / 文档条目，且写到新文件、保留 STORED 方式。
- `--flat`：`docker export | docker import` 拍平，仅用于单镜像交付；**会破坏多版本共享层**，本地存储不要用。
- 构建后自动删除临时 jar 副本（D 盘基线仅剩 10.72GB，避免再堆 6×200MB）。

```bash
OPS=/mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops
bash $OPS/v3-slim-jars.sh --audit
bash $OPS/v3-slim-jars.sh --build --rebuild-jars          # 重建 6 jar + 6 分层镜像
bash $OPS/v3-slim-jars.sh --build --rebuild-jars --jdk 25 --app api --strip
# 复核重建效果
python /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-jar-audit.py --root /mnt/d/work/IdeaProjects
# 导入集群（如需）
k3d image import car-monit-api:min-jdk25 car-monit-backend:min-jdk25 -c v3
```

**两个必须避开的坑**：
1. 审计显示 `LIB_CMP == LIB_UNCMP`，即 `BOOT-INF/lib/*.jar` 全是 **ZIP_STORED**。Spring Boot loader 要求嵌套 jar 不压缩才能随机加载，**把 fat jar 重新压成 DEFLATED 会直接导致 `java -jar` 启动失败**，不要为了几个百分点这么做。
2. `pulsar-client-4.2.5.jar`（27,646,206 B，最大单项）在 `PulsarConsumerConfig` / `SnapshotFlowPulsarConsumer` / `PulsarProducerService` 中有真实引用，**不可删**。其余大项 `elasticsearch` 14.4MB、`grpc-netty-shaded` 10.9MB、`kafka-clients` 10.2MB 亦为在用依赖。

---

## 6. WSL 磁盘回收（未执行，脚本可复现）

用户给定的序列原样保留在 `v3-compact-wsl.ps1`，并补了前置检查、guest 侧清理和前后体积记录：

```powershell
$d = 'openEuler-24.03-LTS-SP4'
wsl.exe --shutdown
wsl.exe --manage $d --set-sparse false          # 必须非稀疏，否则 compact 报错
wsl.exe --manage $d --compact
fsutil sparse queryflag 'D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx'
```

本轮 `fsutil` 已确认 VHDX **本来就是非稀疏**，所以 `--set-sparse false` 是幂等兜底。

**compact 只回收 guest 已释放的空间**，所以顺序必须是：先清节点内过时镜像 + `docker image prune -f` / `docker builder prune -f` / `sudo fstrim -av`，再 shutdown + compact。脚本 `-CleanFirst` 会自动做这一步（**不删 volume、不删任何业务日志**）。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-compact-wsl.ps1                       # 预检 + dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-compact-wsl.ps1 -Apply -CleanFirst
```

风险提示：
- D 盘仅剩 **10.72GB**，脚本默认要求 ≥8GB 空闲才放行，不足需先清理或 `-Force`；
- `wsl --shutdown` 会终止**所有** WSL 发行版与容器，重启后 DB 需手动 `docker start mysql_wsl opengauss`；
- 当前 42.812GB 与旧记录 16.454GB 差距很大，回收量以脚本输出的 `size_before/size_after/reclaimed` 实测为准，不预设数字。

---

## 7. 推荐复现顺序（解除黑名单后一次性做完）

```text
[Win]  1. v3-wsl-quota.ps1 -Profile cluster -Apply          # 写 4GB/2核（不要立刻 shutdown）
[WSL]  2. v3-inventory.sh                                    # 盘点留证
[Win]  3. v3-switch-mode.ps1                                 # 先看哪套在跑
[Win]  4. v3-switch-mode.ps1 -Mode standalone -Apply         # 选一套，停另一套
[WSL]  5. v3-prune-node-images.sh --apply                    # 清三个节点旧镜像
[WSL]  6. v3-slim-jars.sh --build --rebuild-jars             # 重建 4 个过期 jar + 分层镜像
[WSL]  7. docker image prune -f ; docker builder prune -f ; sudo fstrim -av
[Win]  8. v3-compact-wsl.ps1 -Apply -CleanFirst              # shutdown + set-sparse false + compact
[Win]  9. v3-wsl-quota.ps1 -Profile auto -Apply -Shutdown    # 按最终模式定档（集群4GB / 单机3GB）
[Win] 10. v3-measure.ps1 -Seconds 60 -Interval 5             # 验证宿主可用内存
[WSL] 11. docker start mysql_wsl opengauss && bash set-db-memory-limits.sh
```

---

## 8. 脚本清单（`scripts/v3/ops/`，全部已通过语法校验）

| 文件 | 运行位置 | 作用 | 默认安全性 |
| --- | --- | --- | --- |
| `v3-inventory.sh` | WSL | 只读盘点 WSL/docker/三节点 crictl 镜像/Pod imageID，写证据 | 只读 |
| `v3-prune-node-images.sh` | WSL | 每节点每仓库只保留 1 份最新镜像 | dry-run，`--apply` 才删 |
| `v3-switch-mode.ps1` | Windows | 单机/集群互斥切换 | `-Mode status` / dry-run |
| `v3-wsl-quota.ps1` | Windows | `.wslconfig` 分档（auto/cluster/lean/custom）+ 备份 | dry-run，`-Apply` 才写 |
| `v3-slim-jars.sh` | WSL | 6 分支 jar 重建 / jlink / 分层镜像 / 体积报告 | `--audit` 只读 |
| `v3-jar-audit.py` | Windows/WSL | 6 个 fat jar 只读体积与依赖审计（**本轮已实跑**） | 只读 |
| `v3-compact-wsl.ps1` | Windows | VHDX 回收与前后校验 | dry-run，`-Apply` 才执行 |
| `v3-measure.ps1` | Windows | 采样 `vmmemWSL` / 宿主可用内存 / WSL free | 只读 |

校验记录：`bash -n` 三个 `.sh` 全部 OK；`py_compile` OK；PowerShell 4 个 `.ps1` 用 `[Parser]::ParseFile` 静态解析 0 错误。所有 `.ps1` 内容保持**纯 ASCII**，避开 PowerShell 5.1 把无 BOM UTF-8 按 GBK 解析导致「字符串缺少终止符」的历史坑。

证据目录：`D:\work\runtime-logs\v3-ops\evidence\`（`jar-audit-*.txt/.csv`、`inventory-*.log`、`prune-plan-*.txt`、`compact-*.log`、`mem-*.csv`）
备份目录：`D:\work\runtime-logs\v3-ops\backup\`

---

## 9. 未执行项与验收口径

| 步骤 | 预期可观测结果 | 本轮实际 |
| --- | --- | --- |
| 三节点镜像清理 | 每节点 `crictl images \| grep car-monit` 只剩 `car-monit-api` + `car-monit-backend` 各 1 行；`docker system df` 镜像占用下降 | 未执行 |
| 单实例互斥 | `9989/9902` 与集群 ready 副本数不同时 >0 | 未执行（当前 9989/9902/6379 在监听） |
| 配额生效 | `vmmemWSL` ≈2469MB、宿主可用 ≈3.71GB（4GB 档） | 配置已写入，**未 shutdown，尚未生效** |
| jar 重建 | api jdk21/25 非目标平台 native 13→3、backend jdk21/25 减少约 21.45MB，`STALE` 全部变 `no` | 未执行 |
| 镜像最小化 | `:min-jdkN` 分层镜像体积 ≤ 现有 `:slim`（401/434MB） | 未执行 |
| VHDX compact | `size_after < size_before`，`fsutil` 仍显示非稀疏 | 未执行 |

所有删除类脚本都保留 dry-run 默认、备份与回滚路径；本文不记录任何推测出的"已回收"数字。
