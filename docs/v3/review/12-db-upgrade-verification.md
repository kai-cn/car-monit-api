# 12. 数据库大版本升级云验证（MySQL 8.0→9.7 / openGauss 3.0→7.0）

> 结论先行：在 GitHub 云 runner 上完成三格验证，**业务一致性 fails=0**；MySQL 走真实逻辑导出/导入，openGauss 因 `gs_dump` 失败回退到同一夹具（未验证真实数据迁移）。以下数字全部来自云端 job 日志，未下载 artifact 到本地。凭据值仅在运行时由 masked Secret 注入，文档不记录。

## 1. 目标版本结论（联网核实）

| 目标 | 结论 |
|---|---|
| MySQL 9.7 | 有效 LTS（2026-04 GA，EOL 2034-04）；9.0 起删除 `mysql_native_password` 与 `default_authentication_plugin` |
| openGauss 7.0.0 LTS | 2026-09-30 GA，社区维护至 2029-09-30；Docker Hub 可用镜像为 `opengauss/opengauss:latest` / `opengauss-server:latest`，实测版本串为 **7.0.0-RC3**（非最终 7.0.0 GA 包，见坑点） |

因此必须逻辑导出/导入重建实例，不能原地升级；认证与 JDBC 参数需同步调整。

## 2. 分支与交付物

- 基于 `car-monit-api-jdk25@45699077` / `car-monit-backend-jdk25@e34166b3` 新建 `feature-dbupgrade`。
- 新增 `.github/workflows/db-upgrade-cloud.yml`（`workflow_dispatch`）；脚本 `scripts/v3/ops/dbupgrade/{db_cell.sh,db_dump.sh,gate.py,report.py}`。
- 工作流镜像到两仓库 `master` 以暴露 dispatch；执行代码来自 `feature-dbupgrade` ref。
- 凭据用仓库 Secret `CI_DB_TEST_PASSWORD`，**仅在 step 级 env** 引用。

## 3. 验证方法

每个 cell 用同一 jar、同一端点清单：
1. old 侧起旧版容器（mysql:8.0 / enmotech/opengauss:3.0.0），加载夹具，跑探针并采 DB 资源。
2. `db_dump.sh` 逻辑导出 old；new 侧起新版容器（mysql:9.7.4 / openGauss 7.0.0-RC3）还原。
3. `gate.py` 硬门禁（0 端点或 app 未就绪即失败）；`parity_compare.py` 判 status/exact/semantic/nondet/fails；`report.py` 汇总启动/RSS/延迟/DB 资源。
4. api 的 MySQL 字典、backend 的 Redis 在两侧保持一致以隔离变量。

## 4. 云验证结果（fails=0，全部通过）

### api × MySQL 8.0.46 → 9.7.4（run `44068812191`，79 端点）
- 一致性：status_match=79，exact=20，semantic=20，nondet=59，fails=0（nondet 为时间戳/排序抖动，非真实差异）。
- 迁移：`mysqldump` 真实导出 36,045 B 并在 9.7.4 还原成功。
- 资源/性能：启动 8720→7816 ms；峰值 RSS 501.8→540.8 MB；稳态 RSS 514.2→540.8 MB；平均延迟 9.77→9.14 ms。

### backend × MySQL 8.0.46 → 9.7.4（run `44077700396`，2 个免认证端点）
- 一致性：status_match=2，exact=1，semantic=1，nondet=1，fails=0。
- 迁移：`mysqldump` 真实导出 341,688 B 并在 9.7.4 还原成功。
- 资源/性能：启动 10820→9918 ms；稳态 RSS 768.1→736.8 MB；平均延迟 767.86→177.97 ms；DB 内存 386.2→465.5 MiB。

### api × openGauss 3.0.0 → 7.0.0-RC3（run `44083066192`，79 端点）
- 一致性：status_match=79，exact=69，semantic=69，nondet=10，fails=0。
- 迁移：`gs_dump` 失败（dump bytes=0），new 侧**回退为同一夹具**，未验证真实跨版本数据迁移。
- 资源/性能：启动 14145→13535 ms；稳态 RSS 638.2→638.5 MB；平均延迟 25.83→21.48 ms；old DB 内存 455.1 MiB。
- 镜像：`enmotech/opengauss:3.0.0` → `opengauss/opengauss-server:latest`（实测 7.0.0-RC3 build 2026-03-25）。

## 5. 踩坑点（如实记录）

1. **凭据泄露（已修）**：初版把测试口令放在 workflow 级 `env:`，GitHub 会把该块回显进公开日志。改为仓库 Secret + 仅 step 级 env 引用，后续日志显示 `CI_DB_PASSWORD: ***`。早期泄露的是一次性 CI 测试值（非真实生产凭据），机制已根治。
2. **假绿（已修）**：初版 `|| log` 吞掉探针失败，openGauss app `rc=1`、0 端点却显示 job success。新增 `gate.py` 硬门禁 + `set -euo pipefail`，0 端点/未就绪立即失败。
3. **账号选择弹窗（已修）**：GCM 每次 `git credential fill` 弹账号选择；一次性缓存 token 到仓库外 `.gh_token_cache`，所有运维脚本改为读缓存。
4. **git ref 歧义**：`origin/xxx` 曾 reset 到过期提交，必须用 `refs/remotes/origin/xxx` 全限定名。
5. **backend deploy key 无写权限**：SSH key 仅对 api 仓库有效；backend 用 HTTPS + 缓存 token 推送。
6. **Spring env 命名**：backend 误用 Python 风格双下划线 `SPRING__...` 导致数据源覆盖失效；改为 `SPRING_DATASOURCE_DRUID_MASTER_*` 单下划线。
7. **MySQL 9.7 认证**：容器删除 `mysql_native_password`；new 侧去掉该参数并加 `allowPublicKeyRetrieval=true`。
8. **openGauss 镜像坑**：`opengauss/opengauss:latest` 缺 `libopenblas.so.0` 无法启动；容器启动需带 `LD_LIBRARY_PATH=/usr/local/opengauss/lib`；最终用 `opengauss/opengauss-server:latest`，实测为 7.0.0-RC3。
9. **openGauss 管理员/夹具**：JDBC 用户是 `gaussdb`（非 omm）；容器内 gsql 需 uid 70 + socket；3.0 不支持 `CREATE SCHEMA IF NOT EXISTS`，已用 DO 块改写。
10. **gs_dump 未通**：`gs_dump` 导出仍失败，openGauss 跨版本真实迁移未验证（以同一夹具对比代替），属未完成项。
11. **dispatch 匹配旧 run**：自建 dispatch 脚本曾返回同 workflow 的旧 run，已改为按 `created_at` 取最新。
12. **nondet 端点**：api-mysql 59 个非确定性端点为数据/排序抖动，按既有口径只豁免 body、status 不一致仍判 DIFF。

## 6. 未完成 / 后续

- openGauss `gs_dump` 真实跨版本迁移（当前回退夹具）；尽量获取 7.0.0 GA 正式镜像替换 RC3。
- WSL 本地在拉取大镜像后一度 `E_FAIL`（不影响云端结论），需宿主侧恢复后复测本地。
- db-upgrade harness 同步到 jdk21/jdk17/javaV3 分支（见分支提交）。

## 7. 复现命令

```powershell
# 工作流镜像到 master（一次性）
python scripts/v3/ops/v3-github-actions-dispatch.py ensure-default `
  --template <jdk25 worktree>/.github/workflows/db-upgrade-cloud.yml `
  --path .github/workflows/db-upgrade-cloud.yml --repos <repo>
# 触发（口令由 Secret 注入，无 input）
python D:/work/runtime-logs/dispatch-redacted.py <repo> db-upgrade-cloud.yml feature-dbupgrade db_scope=both
```
