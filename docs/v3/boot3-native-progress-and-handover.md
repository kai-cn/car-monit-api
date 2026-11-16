# Spring Boot 3 / 原生镜像 进度与交接（2026-11-16 14:30）

> 本文是**进度快照 + 交接单**，回答三个问题：现在到哪一步了、卡在哪、下一步按什么命令继续。
> 技术细节与根因链在 `docs/v3/native-image-cicd-and-runtime-verification.md`（下称"主文档"），
> 本文只做状态汇总与索引，避免主文档继续膨胀。

---

## 0. 一眼看懂：三个分支的状态

| 分支 | 框架 | 代码状态 | JVM 构建 | native 构建 | native 运行 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `car-monit-api-jdk25` | Boot 4.1.2 | 已推送 `0efed7f` | 通过 | **通过**（358,222,560 B） | 进程起、Tomcat 绑定、`http_root_code=404` | 卡在 native 内 **JDBC 取连接失败** |
| `feature/springboot3`（jdk21） | Boot 3.5.6 | 已推送 `bb9508f` | 通过 | **通过 r8**（269,552,352 B，1070 s，stripped） | **未跑（唯一下一步）** | Druid、Forest、validation 三个坑已修，等验证 |
| `feature/springboot3-jdk17`（jdk17） | Boot 3.5.6 | 已推送 `5b6e43c`（与 jdk21 同 5 个提交） | 未跑 | 未跑 | 未跑 | 代码已同步，构建未验证 |

**一句话结论**：JDK17/21 想跑原生镜像必须走 Boot 3（Boot 4 的 native 硬性要求 Java 25，已实测
`NativeImageRequirementsException`）；Boot 3 线的镜像现在**能构建出来了**，只剩运行态验证这一道。

---

## 1. 已完成、可复现的部分

1. **Boot 4 线（jdk25）Linux 原生镜像**：构建脚本 + 运行采样脚本齐备，镜像能起、端口能通，
   唯一未解是 native 内的 JDBC 认证/连接（JVM 下同配置正常）。
2. **Boot 3 迁移（api 侧）**：`scripts/v3/ops/v3-migrate-to-boot3.py` 固化 8 条 pom 映射规则 +
   Jackson 3→2 的源码重写；jdk21 分支 JVM 构建 BUILD SUCCESS。
3. **Boot 3 native 打通到"构建成功"**：8 轮迭代把 Forest、Druid、validation 三处 native 不兼容
   逐个拔掉，r8 产出 269 MB stripped ELF。
4. **分支治理**：8 个仓库全部推送到远端；`feature/springboot3` / `feature/springboot3-jdk17` /
   `car-monit-api-jdk25` / `car-monit-api-java-V3`（rebase 后）均已同步 origin。
5. **配套脚本（`scripts/v3/ops/`）**：

| 脚本 | 用途 |
| --- | --- |
| `v3-setup-mandrel-linux.sh` | 安装 Mandrel 17/21/25 到 WSL ext4 |
| `v3-native-build-linux.sh <api\|backend> <25\|21\|17> <dir> [label]` | 一键 `clean install` + native-image，产物与日志落 evidence |
| `v3-run-native-linux.sh` / `v3-run-jvm-linux.sh` | 同口径启动采样（启动耗时 / RSS / 线程 / HTTP 探活） |
| `v3-compare-native-jvm.sh` | native vs jar A/B |
| `v3-patch-mybatis-aot-scan.py` | 字节码改写 MyBatis-Plus AOT 扫描（收敛到 `-H:Class`） |
| `v3-native-scan-audit.py` | 埋雷类审计（方法签名引用缺失类型） |
| `v3-migrate-to-boot3.py` | Boot 4 → Boot 3.5.6 迁移（默认 dry-run，`--apply` 落盘） |

---

## 2. Boot 3 / jdk21 的 8 轮迭代（每轮 ~13–18 min）

| 轮次 | 动作 | 结果 |
| --- | --- | --- |
| r1 | 首次构建 | 失败：Boot 3.5 BOM 把 `native-maven-plugin` 管到 0.10.6 → `GraalVM 22 required but 21 detected` |
| r2 | 固定插件 1.1.14 | 同上（校验来自默认 `requiredVersion`） |
| r3 | 加 `<requiredVersion>21.0</requiredVersion>` | 构建成功 271 MB；运行卡 `forest.retryer` 绑定 `ClassNotFound` |
| r4 | 注释 `forest:` 配置块 | 构建成功；运行卡 Forest 自动配置 `Class.newInstance(DefaultLogHandler)` |
| r5 | **彻底移除 Forest** | 构建 269.9 MB；运行推进到数据源 |
| r6 | dynamic-datasource 4.3.0 → 4.6.0 | 构建 269.8 MB；仍卡 `DruidDataSource.setConnectProperties(null)` NPE |
| r7 | 排除 `DruidDataSourceAutoConfigure` + 清空 `druid.filters`/`connectionProperties` + `-H:IncludeResources=com/mysql/cj/LocalizedErrorMessages.*` | 构建 288.6 MB；**Druid 通过**；运行卡 Hibernate Validator 的 JBoss Logging |
| r8 | 排除 `ValidationAutoConfiguration` | **构建成功 269,552,352 B（stripped），1070 s**；运行待验证 |

三处 native 不兼容的定性：

- **Forest 1.8**：无 native 支持（反射 + `Class.newInstance` 建日志实现），项目实际只有一处调用
  → 用 Spring `RestClient` 单点替换（`com.ruoyi.base.forest.SysBaseClient`），整包移除。
- **Druid**：`DruidDataSourceCreator` 把 `null` 的 `connectProperties` 传进 `DruidDataSource`
  → 属性置空 + 排除自动配置，走"不用 filter"的分支。
- **Hibernate Validator**：`Version.<clinit>` 触发 JBoss Logging 动态找 `Log_$logger` 实现，
  native 下无生成 → 项目未使用任何 `jakarta.validation` 注解，直接排除 `ValidationAutoConfiguration`。

---

## 3. 当前唯一未闭环的点

**r8 二进制没跑过。** 构建在 WSL 里 13:25 完成后 WSL 被关机，`manual-native-start-19902.log`
里躺着的还是 r7 的日志（validation 报错）。

其余待办（在 r8 之后）：

1. PageHelper 反射配置（Boot3 分支还没加 `v3-native-hints/reflect-config.json`）；
2. Lettuce 的 `-H:+SharedArenaSupport`（jdk25 已加，Boot3 待加）；
3. native vs jar A/B；
4. jdk17 分支的 Boot3 JVM 构建 + native 构建；
5. backend 侧按 api 的结论复制。

---

## 4. 继续执行的命令

```bash
# 0) 先进 WSL，确认内存余量（native-image 分析期要 10GB+）
wsl -d openEuler-24.03-LTS-SP4
free -g

# 1) 起 r8 二进制验证（端口必须用 19902，9902 被 [::]:9902 占用）
#    脚本都在 /mnt/d/work/runtime-logs/v3-ops/evidence 下
cd /mnt/d/work/runtime-logs/v3-ops/evidence
bash manual-native-port.sh 19902

# 2) 若需重建（改完 pom/配置后）
bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-native-build-linux.sh \
     api 21 /mnt/d/work/IdeaProjects/car-monit-api-jdk21 api-boot3-jdk21-linux-r9

# 3) jdk17 侧（代码已同步，构建从没跑过）
bash .../v3-native-build-linux.sh api 17 /mnt/d/work/IdeaProjects/car-monit-api-jdk17 api-boot3-jdk17-linux-r1
```

构建前把抢内存的容器停掉，只留 `opengauss`：

```bash
docker stop es-wsl kafka-wsl mysql_wsl
```

---

## 5. 环境约束与已踩过的坑

| 坑 | 现象 | 处理 |
| --- | --- | --- |
| 宿主内存 13.8 GB / WSL 12 GB | native-image 分析期 GC 占 50% 时间，构建从 8 min 劣化到 38 min | 构建期停 es/kafka/mysql，只留 opengauss |
| 端口 9902 | IPv4 绑定 `BindException`，`ss -lntp` 看不到占用者 | 实际是 `[::]:9902` IPv6 双栈（uid 0），读 `/proc/net/tcp6` 定位；验证统一走 19902 |
| 构建脚本 `install` 不 clean | 删掉的类还留在 `target/classes`，native 里报 `NoClassDefFoundError` | 脚本第一步改为 `clean install` |
| `.sh` 被 CRLF 污染 | WSL 里 `bad interpreter` | 13 个脚本批量转 LF |
| MySQL 驱动 | native 启动 `MissingResourceException: LocalizedErrorMessages` | `-H:IncludeResources=com/mysql/cj/LocalizedErrorMessages.*` |
| PyYAML 写 yml | `\n` 被写成字面 `/n` | 字节级修复；以后改 yml 用文本编辑而非脚本拼接 |

---

## 6. 证据索引（`D:/work/runtime-logs/v3-ops/evidence/`）

| 文件 | 内容 |
| --- | --- |
| `native-api-boot3-jdk21-linux-r1..r8.log` | Boot3 jdk21 每轮构建全量日志 |
| `manual-native-start-19902.log` | r7 运行日志（validation 报错现场） |
| `druid-nofilter-19902.log` + `druid-nofilter-probe.sh` | Druid 去 filter 后的验证 |
| `native-run-linux-api-jdk25-linux-r5-clean.summary.txt` | jdk25 native 启动采样（RSS 281 MB / 10 线程 / JDBC 失败） |
| `who-port.sh` | 读 `/proc/net/tcp6` 定位 9902 占用者 |

---

## 7. 提交记录（本轮相关）

```
jdk21  feature/springboot3
  bb9508f fix(boot3,native): exclude ValidationAutoConfiguration (JBoss Logging unusable in native)
  03239fe fix(boot3,native): include MySQL ResourceBundle, disable Druid filters
  6f98081 fix(boot3,native): remove Forest entirely, pin native plugin, align dynamic-datasource
  a80b338 feat(boot3): migrate api to Spring Boot 3.5.6 (JVM build compiles)

jdk17  feature/springboot3-jdk17   （同上 5 个提交，cherry-pick）
  ... 5b6e43c 为 HEAD

jdk25  car-monit-api-jdk25
  0efed7f refactor(forest): drop unused Forest dependency and config
  21bfdcf fix(native): make JDK25 linux native image business-start ready
```
