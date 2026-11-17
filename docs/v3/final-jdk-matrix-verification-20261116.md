# API 侧 JDK/框架矩阵收官验证（2026-11-16）

> 范围：`car-monit-api` 六个组合（jdk25/21/17 × Boot4/Boot3），Linux（WSL2 openEuler）实机。
> 证据目录：`D:\work\runtime-logs\v3-ops\evidence\`（WSL 内 `/mnt/d/work/runtime-logs/v3-ops/evidence`）。
> 本文只写实际跑过的结果；未执行/不可行项显式标注，不填推测值。

---

## 0. 结论摘要

| 组合 | JVM jar | native 构建 | native 运行 | 备注 |
| --- | --- | --- | --- | --- |
| JDK25 + Boot4.1.2 | 通过 | 通过（358,222,560 B） | **通过**：4.0 s 端口就绪、HTTP 200（1016 行业务数据）、0 ERROR | 此前"native 取不到 JDBC 连接"是**运行脚本漏注入 MySQL 凭据**，非 native 缺陷（见 §2） |
| JDK21 + Boot4.1.2 | 通过（16.0 s / 423 MB） | 历史 r15 曾构建成功（93.9 MB ELF） | **不可行**：Boot4 框架硬门槛，报 `NativeImageRequirementsException` | native 只能 Java 25；见 §4 |
| JDK17 + Boot4.1.2 | 通过（16.0 s / 409 MB） | 未重跑（门槛同上） | **不可行**（同上） | JVM 交付 |
| JDK21 + Boot3.5.6 | 通过 | r8 曾构建成功；本轮 r9 重建见 §5 | 见 §5 | 三处 native 不兼容已修（Forest/Druid/validation） |
| JDK17 + Boot3.5.6 | 通过（17.1 s / 421 MB，首次实跑） | 见 §5 | 见 §5 | 分支此前从未跑过构建 |

---

## 1. 验证方法（统一口径）

1. 所有组合用同一套脚本，端口统一 **19902**（9902 被 `[::]:9902` IPv6 双栈占用，`ss -lntp` 看不到）。
2. 数据库凭据在运行时从容器 env 读取并只导出给子进程，**不写盘、不打印**：
   - openGauss：`GS_PASSWORD` → `SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_{USERNAME,PASSWORD}`；
   - MySQL：`MYSQL_ROOT_PASSWORD` → `CARMONIT_MYSQL_{USERNAME,PASSWORD}`。
3. 端口预检：启动前若 19902 已被监听直接退出，避免历史上 `startup_ms=6` 那种"探到别的进程"的假阳性。
4. 启动后先探 `/`（404 属正常），再探真实业务端点
   `/base/feerecords/list?pageNum=1&pageSize=1`（命中 openGauss），记录 HTTP 码、响应字节、ERROR 行数。

脚本入口：

```
scripts/v3/ops/build-jvm-jar.sh                 # 指定 JDK 构建 JVM jar
scripts/v3/ops/v3-native-build-linux.sh          # AOT + native-image
scripts/v3/ops/v3-run-native-linux.sh            # native 启动采样（已修复）
scripts/v3/ops/v3-run-jvm-linux.sh               # JVM 启动采样（已修复）
scripts/v3/ops/v3-probe-http.sh                  # 业务端点探活（native/jar 通用）
scripts/v3/ops/v3-compare-native-jvm.sh          # A/B 长时间对比（已修复）
scripts/v3/ops/v3-verify-jdk-matrix.sh           # 全矩阵复现入口
```

---

## 2. 关键纠错：JDK25 native 的 "Failed to obtain JDBC Connection"

`PlateColorDictionary.refresh()` 用的**不是** openGauss 主数据源，而是单独一个
`DriverManagerDataSource` 连 MySQL `127.0.0.1:3307/carmonitdb`：

```java
// pro-business-api/.../plate/PlateColorDictionary.java:73-76
DriverManagerDataSource dataSource = new DriverManagerDataSource(
        config.getUrl(), config.getUsername(), config.getPassword());
dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
```

配置里 `username: ${CARMONIT_MYSQL_USERNAME:}`、`password: ${CARMONIT_MYSQL_PASSWORD:}` 默认为空。
旧版 `v3-run-native-linux.sh` 只注入了 openGauss 凭据，于是 MySQL 连接失败并打出
"plate_color 字典加载失败 … Failed to obtain JDBC Connection"。**主文档 §8.4 r5 把它判为
"native 侧驱动/认证链路问题"是误判，本轮纠正。**

同时发现旧 summary 的 `startup_ms=6` 是假阳性：9902 上已有 systemd JVM api 在监听，
TCP 探活探到的是它；native 自己随后因端口冲突 `APPLICATION FAILED TO START`。

修复内容（三个脚本）：`v3-run-native-linux.sh`、`v3-run-jvm-linux.sh`、
`v3-compare-native-jvm.sh`（另新增 `v3-probe-http.sh`）。

---

## 3. JDK25 Boot4 实测（native 已打通）

native 二进制：`car-monit-api-jdk25/pro-business-api/target/pro-business-api`，358,222,560 B。

| 项 | native | JVM（同机同凭据） |
| --- | --- | --- |
| 产物 | ELF 358,222,560 B | fat jar 212,271,942 B |
| 端口就绪 | **4,016 ms** | 17,045 ms |
| HTTP `/` | 404（正常） | 404（正常） |
| 业务端点 | **200，3,391 B，total=1016** | 200，3,391 B，total=1016 |
| 稳态 RSS | 284 MB | 420 MB |
| 线程 | 82 | 93 |
| ERROR 行 | 0 | 0 |

证据：`evidence/native-run-linux-api-jdk25-linux-r5-dbcreds.{log,summary.txt}`、
`evidence/http-probe-api-jdk25-native-http.{log,summary.txt,body.json}`、
`evidence/jvm-run-linux-api-jdk25-jvm-baseline.summary.txt`。
长时间 A/B（`v3-compare-native-jvm.sh`）结果见 §6。

---

## 4. JDK21 / JDK17 Boot4

两者都用对应 JDK 重新 `clean package`，**BUILD SUCCESS**：

| 组合 | 构建日志 | jar 字节 | 启动 | RSS | 线程 |
| --- | --- | --- | --- | --- | --- |
| jdk21 Boot4 | `jvm-build-api-boot4-jdk21-jvm.log` | 211,436,499 | 16,042 ms | 423 MB | 92 |
| jdk17 Boot4 | `jvm-build-api-boot4-jdk17-jvm.log` | 206,201,059 | 16,043 ms | 409 MB | 93 |

native 不可行的框架级证据（`native-run-linux-api-jdk21-linux-r17.log`）：

```
org.springframework.boot.SpringApplication$NativeImageRequirementsException:
  Native Image requirements not met. Native Image must support at least Java 25
  but Java 17 was detected
```

结论：JDK21/17 的 Boot4 线以 **JVM jar 交付**；native 只能走 Boot3（§5）。
r15/r17 的构建期改动（MyBatis-Plus AOT 扫描收敛、class-init 参数）保留但不可运行。

---

## 5. Boot3（jdk21 / jdk17）原生镜像

（构建完成后补录）

---

## 6. 长时间 A/B 与稳定性（JDK25 Boot4）

`v3-compare-native-jvm.sh --duration 120 --interval 5 --probe / --label api-jdk25-ab` 实跑结果，
详见 `evidence/compare-api-jdk25-ab-20261116-150757.{csv,json}`：

| 指标 | native | JVM | 差异 |
| --- | --- | --- | --- |
| 端口就绪 | 3,740 ms | 20,435 ms | native 快 5.5× |
| 启动峰值 RSS | 280.0 MB | 544.8 MB | −48.6% |
| 稳态平均 RSS（20 样本） | 281.8 MB | 547.8 MB | −48.6% |
| HTTP 平均延迟（`/`，20 样本） | 3.7 ms | 18.6 ms | native 快 5× |
| HTTP 成功率 | 20/20 | 20/20 | 均无失败 |
| 120 s 稳定性（24 样本） | 24/24 成功，RSS 283.9→236.2 MB（漂移 −47.7 MB） | — | 无内存增长趋势 |

注意：这是**同机同凭据**的启动/静态探活对比，不是完整业务压测；HTTP 探的是 `/`（404 亦计成功）。

---

## 7. 复现命令

```bash
OPS=/mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops
BASE=/mnt/d/work/IdeaProjects

# 0) 前置：opengauss + mysql_wsl 两个容器在运行；端口 19902 空闲
docker ps --format '{{.Names}}'

# 1) 构建 JVM jar（按分支切换工作树后执行）
bash /mnt/d/work/runtime-logs/v3-ops/build-jvm-jar.sh \
  $BASE/car-monit-api-jdk25 /home/dev/tools/mandrel-25 api-jdk25-jvm

# 2) 构建 native（JDK21 Boot3 用 Mandrel 21）
MANDREL_HOME=/home/dev/tools/mandrel-21 bash $OPS/v3-native-build-linux.sh \
  api 21 $BASE/car-monit-api-jdk21 api-boot3-jdk21-linux-r9

# 3) 启动 + 业务端点验证
bash $OPS/v3-run-native-linux.sh <elf> <label> 20 19902
bash $OPS/v3-probe-http.sh <elf|jar> <label>-http 19902

# 4) 一键复现全部已有产物
bash $OPS/v3-verify-jdk-matrix.sh all
```

注意：`v3-verify-jdk-matrix.sh` 不负责切分支；jdk21/jdk17 工作树的 Boot4 与 Boot3 jar 共用
同一路径，切换分支后需重新构建，脚本只验证当前存在的产物。

---

## 8. WSL/ext4 + Linux Maven 全量构建（2026-11-16 晚）

### 8.1 环境与 git
- Windows 侧 worktree 在 Windows shell 下 git 正常；WSL 中这些副本的 `.git` 原本是
  `gitdir: D:/...` 指针，git 不可用。已批量转换为 WSL 独立仓库（指针备份在
  `D:\work\runtime-logs\v3-ops\git-pointers\`），现在 IDEA 可直接在 WSL 打开开发。
- 两侧源码 `diff -qr`（排除 `.git/target/build/node_modules`）一致；仅原生构建配置的有意修改不同。

### 8.2 编译性能对比（同一 api jdk21 分支）

| 方式 | Maven | 源码位置 | 总耗时 | native-image 阶段 | 峰值 RSS |
| --- | --- | --- | --- | --- | --- |
| 原方式 | `/mnt/d/work/apache-maven/bin/mvn` | `/mnt/d` (drvfs) | 18 分 17 秒 | 12 分 22 秒 | 未采集 |
| ext4 + Linux Maven | `/home/dev/.cache/ci-toolchain/apache-maven-3.9.9/bin/mvn` | `/home/dev/IdeaProjects` (ext4) | **12 分 48 秒** | **11 分 51 秒** | 11.08 GB |
| ext4 + 免二次 clean | 同上 | 同上 | **12 分 34 秒** | 11 分 29 秒 | 10.76 GB |
| ext4 + `-J-Xmx8g` | 同上 | 同上 | 失败（GC overhead） | — | 9.97 GB |

结论：**ext4 + Linux Maven 提速约 32%**；去掉二次 `clean` 再省约 2%。
`-J-Xmx8g` 不可用；`-J-XX:MaxRAMPercentage=85` + 4 线程 + 构建期停库容器可让 jdk25 在 12 分 49 秒完成。
**构建期必须停 MySQL/openGauss 容器**，否则 native-image 只拿到 8.2 GB 内存并 OOM；验证前再启动。

### 8.3 JDK25 Boot4 原生镜像（WSL/ext4 重建）
- api jdk25：`353,700,576 B`，构建 741 s，峰值 RSS 11.63 GB，产物业务端点验证通过。
- backend jdk25：`413,731,552 B`（绑定 `process-aot` 后），构建 961 s，峰值 RSS 11.68 GB。

### 8.4 完整业务完整性对拍（native vs JVM，7 端点）
脚本：`D:\work\runtime-logs\v3-ops\v3-compare-business.sh`。
结果文件：`evidence/api-jdk{25,21,17}-*-business-business.json`。

| 组合 | 端点数 | 字节完全一致 | 语义一致 | 备注 |
| --- | --- | --- | --- | --- |
| api JDK25 Boot4 | 7 | **7/7** | 7/7 | 含 900 KB 大列表 |
| api JDK21 Boot4 | 7 | **7/7** | 7/7 | 同上 |
| api JDK17 Boot4 | 7 | **7/7** | 7/7 | 同上 |

端点：`/base/feerecords/list`、`/base/gantry/list`、`/base/gantry/listAll`、`/base/toll/list`、
`/api/v1/bigscreen/stats/audit`、`escape`、`warning-top`。

### 8.5 backend native 阻塞（如实记录）
backend 原生镜像可构建，但运行仍失败：
1. `org.slf4j.MarkerFactory` 初始化失败 → 运行时加
   `-Dorg.apache.commons.logging.LogFactory=org.apache.commons.logging.impl.Slf4jLogFactory` 绕过；
2. Logback XML 配置器反射缺失 → 已补 appender/encoder/filter/level 等 196 条反射元数据；
3. 根因之一：`spring-boot-maven-plugin` 未绑定 `process-aot`，导致 AOT 初始化类缺失；已补 `<execution>`，镜像增大到 413 MB；
4. 继续修复：`process-aot` 绑定后镜像达 413 MB；补 Druid 字段反射、显式 Druid 连接参数后，
   依次暴露 P6Spy 的 `ClassHasher` NPE（native 下不可用，需用直接 MySQL 驱动）和
   `mybatis/mybatis-config.xml` 资源缺失（已加 `IncludeResources`）。
5. 最新构建 r14 成功（413,797,088 B，`build_seconds=1495`，峰值 RSS 见 evidence），
   但**运行仍未通过**：原生模式对 Druid/P6Spy/MyBatis 的配置绑定与资源加载尚未完全适配。
   backend Boot3/JDK17/21 原生对拍尚未开始。
6. 旁证：Boot3 jdk21 的 r9 原生构建此前已成功（272,763,616 B，`native-aot` 8分26秒），
   只是产物后来被 Boot4 构建覆盖；日志见 `evidence/native-api-boot3-jdk21-linux-r9.log`。

## 9. 云 runner 续推结果（2026-11-17 晚）

> 本节全部结论来自 GitHub Actions 云 runner 的 job 日志，不再下载 artifact。

- **H8b api saveRedis 修复完成**：`car-monit-api-jdk25` 反射配置注册 `com.ruoyi.base.domain.SysUtil`；
  run `44015161206`：79 端点、status_match=79、exact=68、nondet=11、**fails=0**，
  `/base/sysutil/saveRedis` 200/200 exact。
- **Boot3 + Mandrel25 完成**：
  - `feature/springboot3`（JDK21）run `44033248438`：native 启动 1207 ms / 318.8 MB，JVM 8123 ms / 516.1 MB；
    延迟 2.71 ms vs 17.82 ms；79 端点 fails=0。
  - `feature/springboot3-jdk17`（新建分支）run `44033253040`：native 1207 ms / 319.3 MB，JVM 8415 ms / 506.4 MB；
    延迟 3.29 ms vs 16.43 ms；79 端点 fails=0。
  - 两者 exact=68、nondet=11、fails=0；NONDET 不豁免 status，status_match=79。
- **backend native 仍阻塞**：逐层修复后 JVM 基线恢复（2 端点 success），native 仍 rc=1；
  当前错误为 MyBatis `Could not resolve type alias 'genTableColumn'`，即 native 下 typeAliases 包扫描失效。
  后续需显式注册类型别名或改 mapper 全限定名。已注册 domain 类反射但不足以解决别名注册问题。

## 10. 边界与风险

- 本轮业务验证只覆盖「启动 + 一个读端点」；Redis/Kafka/ES 链路未逐一回归。
- Boot3 的 `-Ob`（迭代期快速优化）仍留在 pom，交付级构建应去掉并重跑一次 -O2。
- `9902` 占用是环境既有问题，非应用缺陷；所有验证统一 19902。
- 凭据只由容器 env 在运行时注入；本文及证据文件不含任何明文口令。
