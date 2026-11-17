# 11 云端全接口 + 资源性能对比验收（native vs JVM，跨 JDK/平台，跨语言）

> 日期：2026-11-17。承接 10-public-cicd-native-verification.md。
> 目标：在 GitHub 云 runner 上，对 backend/api 的 JDK 25/21/17 × windows/linux，
> 做 native image 与普通 JVM jar 的**全接口校验 + 资源性能比较**；并把其他语言实现
> （Go/Python/Rust）与 backend master（Java8）做同口径对比。如实记录坑点与复现方法。

## 1. 架构与可复现组件

所有组件随分支入库，工作流 `workflow_dispatch` 触发。

### 1.1 探针/对比工具（`scripts/v3/ops/parity/`）
| 文件 | 作用 |
| --- | --- |
| `parity_probe.py` | 启动单个变体（jar 或 native），等端口就绪，逐个探测端点，记录 status/bytes/latency/body-sha；采样**进程树**峰值 RSS；支持 `--check-stability`（同一端点连续两次比对 sha，标记数据非确定性端点）|
| `parity_compare.py` | 对比两份探针 JSON：status/exact(字节)/semantic(去易变字段的 JSON)/nondet（非确定性端点，仅豁免 body 不豁免 status）；输出 JSON + Markdown |
| `endpoints/api.txt` | api 的 **79 个 GET 端点**（从 Java Controller 全量提取）|
| `endpoints/backend.txt` | backend 免认证 GET 端点（`/captchaImage`、`/`）|
| `sql/schema_jl_data01.sql` | api openGauss `jl_data01` schema（44 表，从本地库 information_schema 生成，兼容原生 postgres）|
| `sql/seed_jl_data01.sql.gz` | api 种子数据（27 表共 2709 行，压缩 468KB）|
| `sql/mysql_dict.sql` | api 依赖的 MySQL 字典表（plate_color 等）|
| `sql/schema_carmonitdb.sql` | backend MySQL 全量 84 表结构 |
| `sql/seed_carmonitdb.sql` | backend 核心表种子（sys_user/role/menu/dept/dict 等）|

### 1.2 工作流
- api：`.github/workflows/parity-verify-cloud.yml`（jdk × platform 矩阵）
- backend：`.github/workflows/parity-verify-cloud.yml`（同上，MySQL+Redis）
- 跨语言：`.github/workflows/crosslang-parity-cloud.yml`（backend master，Java8 基线 vs Go/Python/Rust）

## 2. 数据准备方法（可复现）

api 用 openGauss（postgres 协议兼容），云 runner 无 openGauss 镜像，因此：
1. 本地 WSL 的 openGauss `RuoYi` 库已含 `jl_data01` 真实数据（59 表）。
2. `gen_ddl.py`：从 `information_schema.columns/constraints` 生成 `CREATE TABLE`（openGauss 专属类型
   `tinyint/mediumint` 等映射为 postgres 等价类型），跳过 `gen_table*/qrtz_*/v3_migration*`。
3. `gen_seed.py`：用 `COPY (SELECT ... LIMIT 150) TO STDOUT` 导出 27 张核心表种子。
4. 在**纯 postgres:16** 上验证 DDL+seed 可完整还原（44 表、2709 行、0 错误）——证明云上可复现。

backend 直接复用仓库内 `schema.carmonitdb.local.sql` + 本地上限行导出。

## 3. 关键坑点（如实记录）

### 3.1 native 构建缺兄弟模块（已修）
- 现象：`mvn -Pnative native:compile -pl pro-business-api` 报
  `Could not find artifact com.ruoyi:pro-base-common:jar:1.0`。
- 根因：`package` 不 install 兄弟模块到 `~/.m2`；`native:compile` 从本地仓库解析依赖。
- 修复：jar 步骤改用 `mvn ... -am install`；native 步骤不再 `clean`（否则删掉刚复制的 jar）。

### 3.2 native 构建失败会连锁跳过基线探针（已修）
- 现象：native 构建失败 → 后续 datastores/probe/compare 全部 skipped。
- 修复：native 构建步骤 `continue-on-error: true`；jar 基线独立产出于 `out/baseline.jar`，探针始终运行。

### 3.3 RSS 采到 shell 而非进程（已修）
- 现象：`peak_rss=2.0MB`（明显错误）。
- 根因：`subprocess.Popen(shell=True)` 的 `proc.pid` 是 `/bin/sh`；JVM/native 是它的子进程。
- 修复：Linux 下遍历 `/proc/*/stat` 求**进程树**的 RSS 之和；本地验证 java 树 RSS=564MB（正确）。
- Windows 用 `GetProcessMemoryInfo`（PSAPI）。

### 3.4 端点数据非确定性（真实存在，需甄别）
- `/base/feeGantry/list`：每次调用 `id` 是随机 UUID → 5 次调用 sha 全不同。
- `/base/vehicleweight/map`：无 `ORDER BY` 的查询，跨进程行序可能不同（同进程内稳定）。
- 处理：`--check-stability` 连打两次，`stable=False` 的端点判 `NONDET`——**仅豁免 body 差异，
  不豁免 status 差异**（否则会把 `200 vs 500` 的真实 bug 误判为“非确定性”）。

### 3.5 真实 native 回归（已定位，未修业务代码）
- `/base/sysutil/saveRedis`：JVM 200 / native **500**。
- 根因（native 日志）：`java.lang.IllegalStateException: No primary or single unique constructor
  found for class com.ruoyi.base.domain.SysUtil` —— AOT 反射元数据缺失。
- 这是 native-image 相对 JVM 的**真实行为差异**，属需补 `@RegisterReflectionForBinding` /
  reachability metadata 的业务修复，不在本次“验收”范围内，如实记录。

### 3.6 backend `process-aot` 绑定默认生命周期（已修）
- 现象：backend jar 构建 `mvn ... install` 失败：`spring-boot-maven-plugin:4.1.2:process-aot ... exit code`。
- 根因：`ruoyi-admin/pom.xml` 把 `process-aot` 绑定在默认 lifecycle，AOT 会真实启动应用，
  需要 logback 目录 `/home/ruoyi/logs`。
- 修复：jar 构建前 `sudo mkdir -p /home/ruoyi/logs`。

### 3.7 Boot4 native 只能跑在 Java 25（JDK17/21 仅构建）
- 现象：JDK17/21 的 native 二进制能构建，但启动即 `NativeImageRequirementsException`。
- 处理：矩阵仍跑，但 JDK17/21 的 native 探针缺失时由 compare 标注“build-only”，如实记录。

### 3.8 Windows runner 无 service containers
- 现象：GitHub Windows runner 不支持 `services:`，无法起 postgres/mysql。
- 处理：Windows 单元跑 `mode=reachability`（无 DB，仅状态/字节/延迟/启动/RSS），
  全接口 DB 级对比仅在 Linux 完成，文档明确区分。

### 3.9 其他语言端点覆盖有限
- Go/Python/Rust 都实现 `/captchaImage`、`/login`、`/getInfo` 等核心端点，但**不是全部**。
  C#/Kotlin/C++ 在本仓库**没有可运行的 HTTP 服务**（代码为部分迁移），无法做接口对比。
- 处理：跨语言对比用共同免认证 GET 端点（`/captchaImage`），并把“未实现/无服务”如实记录。

## 4. 复现步骤

```bash
# 1) 触发 api native-vs-jvm（jdk25 linux）
gh workflow run parity-verify-cloud.yml -R kai-cn/car-monit-api \
   --ref car-monit-api-jdk25 -f jdk=25 -f platform=linux -f repeat=2

# 2) 全矩阵（jdk 17/21/25 × linux/windows）
gh workflow run parity-verify-cloud.yml -R kai-cn/car-monit-api \
   --ref car-monit-api-jdk25 -f jdk=all -f platform=both

# 3) backend
gh workflow run parity-verify-cloud.yml -R kai-cn/car-monit-backend \
   --ref car-monit-backend-jdk25 -f jdk=25 -f platform=linux

# 4) 跨语言（Java8 vs go/python/rust）
gh workflow run crosslang-parity-cloud.yml -R kai-cn/car-monit-backend \
   --ref master -f langs=all
```

下载证据：`gh run download <run-id> -n parity-25-linux`（含 `jar.json`/`native.json`/`report.md`）。

## 5. 结果与状态
见 `docs/v3/review/11-results.md`（本文件为方法与坑点；结果数字随运行更新）。
