# V3 原生镜像：云/自托管 CICD、业务完整启动修复与 native/JVM 实测

> 记录时间：2026-11-15 (GMT+8)
> 适用：`car-monit-api` / `car-monit-backend` 六个 JDK 工作树（jdk25 / jdk21 / jdk17）
> 证据目录：`D:\work\runtime-logs\v3-ops\evidence\`
> 本文所有数值均来自实机日志；**未执行 / 未完成项均显式标注**，不填推测值。
> 上一阶段文档：`docs/v3/native-image-mandrel-verification.md`

---

## 0. 结论摘要

| 项 | 结论 |
| --- | --- |
| GitHub 云 runner | **实测不可用**。canary run `43711910286` 被 GitHub 以「付款失败 / spending limit」直接拒绝，job 1 秒失败、无 runner、无日志。按用户预设条件切换到 self-host runner |
| 云 CICD 模板 | 已编写并写入两个仓库 `master` 默认分支 + 六个工作树分支；账单恢复后可直接用 |
| self-host runner | **实测可用**：两个仓库 canary run 均 `conclusion=success`（账单受限不阻断自托管 job）。三个 workflow 已写入各自 `master`；六分支修复已全部推送 |
| Spring Boot 4 AOT + MyBatis | **根因定位并修复**：AOT 生成的 `Mapper__BeanDefinitions` 丢弃 `AUTOWIRE_BY_TYPE`，`sqlSessionFactory` 未注入。新增 `NativeMapperSqlSessionFactoryRegistrar` 显式写入 `RuntimeBeanReference` |
| MyBatis type alias | **根因定位并修复**：native image 无 `.class` 文件，`type-aliases-package` 扫描静默失效。六分支 90 个 XML、405 处简写别名改为全限定类名 |
| 数据源认证 | Windows 经 WSL2 端口转发访问 openGauss 时源 IP 走 `0.0.0.0/0 md5` 规则，必须注入密码；已用容器 env 运行时读取，不落盘、不入库 |
| 新发现：native 段错误 | 第三个阻塞：产物运行到 Spring refresh 早期发生 **GC 扫描 image heap 段错误**（非 Java 异常）。fastjson2 的 `Unsafe` 偏移固化是**已确认的错误配置**（v2 已消除全部 7 条 `RecomputeFieldValue` 警告），但**不是段错误的充分原因**——早前 aotfix exe 同样带 7 条警告却能正常进入业务异常。鉴别仍在继续，见 §8.2 |
| 业务完整启动 | 尚未达成（被段错误阻断），见 §8 |
| 稳定性 / native-JVM 对比 | **未执行**（前置条件「业务完整启动」未满足），见 §8 |
| jdk21 / jdk17 | CICD 模板与三套 Mandrel 工具链已就绪；**原生编译未执行**。见 §9 |
| 本次会话状态 | 2026-11-15 21:44 恢复执行中：fastjson2 修复已推送六分支；v2 构建成功（14m29s）但运行仍段错误；v3（移除全部手动 build-time）构建中。WSL 编译期保持 Stopped |

---

## 1. 任务与决策链

用户要求顺序：

1. 编写 backend/api × jdk25/21/17 原生镜像 CICD，优先使用 GitHub 云 runner 编译。
2. 若云端 run 次数耗尽 / 账单受限，才使用 self-host runner。
3. 修复 backend/api jdk25 原生镜像的业务完整启动。
4. 业务能完整启动后，实机测服务稳定性，并与普通 fat jar 做性能/资源等对比。
5. 再推进 jdk21 / jdk17 分支。
6. 全程记录可复现文档、脚本与运维命令。

实际决策链（均以实测为依据）：

```
探测云 runner 配额
  ├─ billing REST /users/kai-cn/settings/billing/actions -> 404（GCM OAuth token 无 billing scope）
  └─ 直接触发 canary（真实云 job，最可靠）
       └─ 失败 annotation: "recent account payments have failed or your spending limit needs to be increased"
          => 触发用户预设的「账单受限」条件 => 切 self-host runner
```

---

## 2. 云 runner 配额实测（证据：`evidence/github-actions-quota.log`、`cloud-runner-blocked.log`）

环境与权限（`v3-github-actions-quota.py`）：

| 项 | 值 |
| --- | --- |
| 凭据 | Git Credential Manager，`gho_` OAuth token（脚本运行时读取，**不打印**） |
| `kai-cn/car-monit-api` | private，默认分支 `master`，账号 admin |
| `kai-cn/car-monit-backend` | private，默认分支 `master`，账号 admin |
| 现有 workflows | 16 个；历史 66 次 runs，近期多为 `self-hosted-ci` |
| billing REST | `/users/.../settings/billing/actions`、`/user/settings/billing/actions` 均 HTTP 404 → 无法读取剩余分钟数 |

canary 实测：

```
dispatch repo=kai-cn/car-monit-api workflow=native-image-cloud.yml ref=master
run_id=43711910286  status=completed conclusion=failure
job=canary  started=12:03:36Z completed=12:03:37Z  runner_name=""  steps=[]
annotation_level=failure:
  "The job was not started because recent account payments have failed or your
   spending limit needs to be increased. Please check the 'Billing & plans'
   section in your settings"
```

这不是 workflow 语法问题（jobs 已创建、labels 解析为 `ubuntu-latest`），而是**账户级拒绝分配 GitHub-hosted runner**。日志 blob 404 也证实 job 从未启动。

另有 GitHub 提示：`ubuntu-latest` 自 2026-10-19 起迁移到 Ubuntu 26。

**结论**：云 runner 编译无法在本轮实跑；云 workflow 保留，账单恢复后可用。

### 2.1 self-host runner 可用性实测（切换决策成立）

WSL 恢复后两个 runner 均 `status=online, busy=false`。写入最小
`selfhost-canary.yml`（`runs-on: ${{ inputs.runner_label }}`，只打印 CPU/内存/gcc/Mandrel）到
两个仓库 `master` 并 dispatch：

| 仓库 | run id | conclusion | 耗时 |
| --- | --- | --- | --- |
| `kai-cn/car-monit-api` (`wsl-k3s-api`) | 43716127318 | **success** | 10 s |
| `kai-cn/car-monit-backend` (`wsl-k3s`) | 43716152235 | **success** | 10 s |

证明「账单受限」只阻止 GitHub-hosted runner 分配，**自托管 job 仍可正常执行**，按用户预设条件切换是正确的。

三个 workflow 均已写入两个仓库 `master` 并被 Actions 识别为 active：
`native-image-cloud` / `native-image-selfhosted` / `selfhost-canary`。

### 2.2 六分支代码发布

`v3-publish-native-branches.sh` 用白名单只提交 native 相关文件（workflow、模块 pom、
AOT 修复类、agent 元数据、改过的 Mapper XML），不触碰用户其它未提交改动。
六分支均已 commit 并 push 到各自 origin（每个分支领先 origin 0 个 commit）。

网络坑位：Windows Git 经代理时 `schannel` 报 `server closed abruptly`、
`openssl` 报 `unable to get local issuer certificate`；`v3-push-pending-branches.sh`
交替使用两种后端 + 有界重试，最终全部成功，从不 force push。

---

## 3. Spring Boot 4 AOT + MyBatis-Plus 启动阻塞：根因与修复

### 3.1 现象

上一阶段 Windows `.exe` 与 Linux ELF 双平台运行日志**完全一致**地失败：

```
BeanCreationException: Error creating bean with name 'dwdLcztFwqjcxxMapper':
  Property 'sqlSessionFactory' or 'sqlSessionTemplate' are required
```

堆栈落在 `org.springframework.beans.factory.aot.AutowiredFieldValueResolver`，说明走的是 AOT 生成代码路径。

### 3.2 根因

直接读 AOT 产物 `pro-business-api/target/spring-aot/main/sources/.../DwdLcztFwqjcxxMapper__BeanDefinitions.java`：

```java
RootBeanDefinition beanDefinition = new RootBeanDefinition(MapperFactoryBean.class);
beanDefinition.getPropertyValues().addPropertyValue("mapperInterface", ...);
beanDefinition.getPropertyValues().addPropertyValue("addToConfig", true);
beanDefinition.setInstanceSupplier(...);
// 没有 sqlSessionFactory，也没有 setAutowireMode(AUTOWIRE_BY_TYPE)
```

`@MapperScan` 通过 `ClassPathMapperScanner` 注册 mapper 时设置 `AUTOWIRE_BY_TYPE`，依赖 Spring 运行时按类型调用 `setSqlSessionFactory(...)`。**Spring Framework 7 的 AOT BeanDefinition 代码生成器不序列化 `autowireMode`**，于是 native 运行时该注入消失。

反编译 `mybatis-plus-spring-boot-native-image-3.5.18.jar` 确认：其
`MyBatisPlusNativeImageConfiguration` 自带
`MyBatisMapperFactoryBeanPostProcessor`（只补 `targetType` / 构造参数）与
`MyBatisBeanFactoryInitializationAotProcessor`（只注册 SQL provider 的 runtime hints），
**均不负责 `sqlSessionFactory` 注入**。这是库层适配缺口，不是反射元数据可修补。

### 3.3 修复（生产最小侵入）

新增 `NativeMapperSqlSessionFactoryRegistrar`（源码在六分支，包名按 app 分别为
`com.ruoyi.base.config` / `com.ruoyi.framework.config`）：一个静态 `@Bean` 的
`BeanFactoryPostProcessor`，遍历所有 `MapperFactoryBean` BeanDefinition，把隐式
by-type autowire 明确化为 `RuntimeBeanReference("sqlSessionFactory")`。

设计要点：

- `BeanFactoryPostProcessor`（不是 `BeanDefinitionRegistryPostProcessor`）→ 在
  `MapperScannerConfigurer` 注册完所有 mapper 之后执行。
- 遍历 `getBeanDefinitionNames()` + `hasBeanClass()`/`getBeanClassName()` 判定类型，
  不做 `getBeanNamesForType` 以规避 FactoryBean 类型预测与提前实例化。
- 已有 `sqlSessionFactory` / `sqlSessionTemplate` 属性时跳过（幂等）。
- 找不到 `SqlSessionFactory` 定义时保留原行为，不破坏自定义多数据源。
- JVM fat jar 与 native 共用同一份代码；显式引用与 by-type 语义等价。

### 3.4 快速验证（不跑 15 分钟 native-image）

只跑 `process-aot`（`mvn -Pnative,native-flink-exclude ... clean package`），检查生成代码：

```
[native-aot] explicit sqlSessionFactory reference patched into 23 MapperFactoryBean definition(s) -> sqlSessionFactory
.../DwdLcztFwqjcxxMapper__BeanDefinitions.java:
  import org.springframework.beans.factory.config.RuntimeBeanReference;
  beanDefinition.getPropertyValues().addPropertyValue("sqlSessionFactory",
      new RuntimeBeanReference("sqlSessionFactory"));
```

证据：`evidence/aot-verify-1.log`。修复后原生运行时日志显示
`patched into 0 MapperFactoryBean definition(s)` —— 说明生成的定义已自带引用，注入生效。

---

## 4. 数据源认证坑（Windows ↔ WSL2）

修复 MyBatis 后启动日志变成：

```
DruidDataSource: init datasource error
org.postgresql.util.PSQLException: The server requested password-based
authentication, but no password was provided by plugin null
```

排查结论：

| 事实 | 说明 |
| --- | --- |
| `application.yml` | `password: ${SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD:}`，默认**空** |
| openGauss `pg_hba.conf` | `127.0.0.1/32 trust`、`0.0.0.0/0 md5` |
| WSL2 `localhostForwarding` | 本次实测 `127.0.0.1:5432/3307/6379` **OPEN**（上一阶段不通是容器未就绪 / OOM） |
| Windows 经端口转发访问 | 连接到达容器时源 IP 被 NAT 成 docker 网关，落入 `md5` 规则 → 必须带密码 |
| 凭据位置 | 容器 env `GS_PASSWORD`，配置文件 `/etc/car-monit/api.env` 为空 |

处理：`v3-read-db-password.py` 在运行时通过 `docker inspect ... --format` 读取，
`v3-run-native-with-db.ps1` 注入 `SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_*`
环境变量后启动。**密码不写入命令行、日志、文档或仓库**。

坑位记录：PowerShell 直接用 `wsl.exe -- docker inspect` 拿到的 JSON 不完整，
且 Go template 花括号在 PowerShell 原生命令参数传递中被破坏；因此把 WSL 调用
委托给独立 Python 脚本。

---

## 5. MyBatis type alias：native 特有的第二个阻塞

### 5.1 现象与对照

注入密码后，native 启动进入 MyBatis XML 解析，然后失败：

```
Failed to parse mapping resource: 'file [/com/ruoyi/base/mapper/xml/KafkaMessageRecordMapper.xml]'
Could not resolve type alias 'KafkaMessageRecord' -> ClassNotFoundException
```

**关键对照实验**：同一份代码用 JVM fat jar 启动（带
`--add-opens=java.base/java.lang=ALL-UNNAMED`，Orika 需要）→ **8 秒端口就绪，启动成功**。
证明这是 native 特有问题。

### 5.2 根因

`mybatis-plus.type-aliases-package: com.ruoyi.base.domain` 在运行时靠扫描 classpath
里的 `.class` 文件注册别名。GraalVM native image 里没有 `.class` 文件，扫描静默返回空，
所有简写别名（如 `resultMap type="KafkaMessageRecord"`）无法解析。

### 5.3 修复

`v3-fix-mapper-type-aliases.py`：扫描六分支 Java 源码建立「简单类名 → FQN」索引，
把 Mapper XML 中 `resultType` / `parameterType` / `type` 的简写别名替换为全限定类名。

| 分支 | XML 数 | 别名种类 | 修改文件 | 替换次数 |
| --- | --- | --- | --- | --- |
| api × jdk17/21/25 | 23 each | 1 each | 1 each | 1 each |
| backend × jdk17/21/25 | 76 each | 29 each | 29 each | 134 each |
| **合计** | — | — | **90** | **405** |

备份：`D:\work/runtime-logs/v3-ops/backup/mapper-xml-20261115-202608\`。
`C` 等内置/误匹配项列入 BUILTIN 忽略；`mvn package` 后 XML 校验通过。

这个改法同时消除了 JVM 版的隐式包扫描，启动更确定，且不引入运行时代码。

### 5.4 预验证（避免盲目重编译 20 分钟）

用新 jar 在 **禁用别名包扫描** 的条件下启动 JVM 版：

```
mvn -B -ntp -DskipTests package -pl pro-business-api
java --add-opens=java.base/java.lang=ALL-UNNAMED -jar pro-business-api-1.0.jar \
     --server.port=19903 --mybatis-plus.type-aliases-package=
=> JVM_NO_ALIAS_SCAN_READY after 8s
```

证据：`evidence/jvm-preverify-package.log`、`jvm-preverify-noalias.log`。

---

## 6. 六分支 CICD 设计

两个独立仓库、六个分支：

| 仓库 | 分支 | self-host runner label |
| --- | --- | --- |
| `kai-cn/car-monit-api` | `car-monit-api-jdk{17,21,25}` | `wsl-k3s-api` |
| `kai-cn/car-monit-backend` | `car-monit-backend-jdk{17,21,25}` | `wsl-k3s` |

### 6.1 云 workflow：`templates/native-image-cloud.yml`

- `workflow_dispatch` only（无 push 触发，省分钟数）；`concurrency` 串行。
- `canary` job：真实云 run 探测配额 + `graalvm/setup-graalvm` 装 Mandrel + 报 CPU/RAM/磁盘。
- `prepare` job：按 inputs 生成**动态 matrix**（`fromJSON`），被跳过的组合不占用 runner。
  注意：GitHub Actions 的 `jobs.<id>.if` **不能引用 `matrix` 上下文**，故不能用 job 级 if 过滤。
- `build` job：app × jdk(25/21/17) × platform(linux/windows)，`max-parallel: 2`，
  `fail-fast: false`；Linux 装 gcc/zlib，Windows 用 `ilammy/msvc-dev-cmd` 提供 cl.exe。
- 产物 + sha256 + `manifest.json`（app/jdk/platform/git_sha/bytes/sha256/run_id），
  `actions/upload-artifact@v4`，保留 14 天。
- `runner_mode` + `linux_runner` / `windows_runner` inputs 支持一键切自托管标签。
- 关键不变量：13 条 `--initialize-at-*` 在各自模块 pom 的
  `native-maven-plugin <buildArgs>`；**禁止 `-DbuildArgs`**（会覆盖 pom 列表）；
  必须 `-Pnative,native-flink-exclude` + `clean`。

### 6.2 自托管 workflow：`templates/native-image.yml`

- `runs-on: ${{ inputs.runner_label }}`，本机 WSL 内已装 Mandrel 25 与 gcc。
- `v3-setup-mandrel-linux.sh <jdk>` 支持 25/21/17，缺归档时自动从 GitHub API asset 下载。
  固定版本：25→`25.0.4.1-Final`、21→`23.1.13.0-Final`、17→`23.0.6.0-Final`。
- 复用 `v3-native-build-linux.sh`（源码同步到 ext4 避免 drvfs 慢）。
- 无 Windows 自托管 runner，因此 Windows `.exe` 由本地
  `native-build.bat`（Mandrel Windows + VS2022）构建。

### 6.3 触发 / 观测脚本（无需 `gh` CLI）

- `v3-github-actions-quota.py`：只读查身份、仓库权限、billing、workflows、近期 runs。
- `v3-github-actions-dispatch.py`：`ensure-default` / `dispatch` / `list` / `status`。
  token 一律运行时从 `git credential fill` 读取，不落盘。
  `ensure-default` 用 GitHub Contents API 把云 workflow 写到两个仓库 `master`
  ——`workflow_dispatch` 要求 workflow 存在于默认分支。
- `v3-publish-native-branches.sh` / `v3-push-pending-branches.sh`：白名单提交六分支的
  native 文件，避免误推用户其它未提交工作；Windows Git schannel 经代理会断连，
  用 `-c http.sslBackend=openssl` + 有界重试。

---

## 7. 复现命令（按顺序）

```bash
OPS=D:/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops

# 1. 只读配额 / 账单 / runner 状态
python $OPS/v3-github-actions-quota.py kai-cn/car-monit-api

# 2. 云 workflow 写入两个仓库默认分支
python $OPS/v3-github-actions-dispatch.py ensure-default \
  --template $OPS/templates/native-image-cloud.yml

# 3. canary 实测云 runner 是否可用
python $OPS/v3-github-actions-dispatch.py dispatch \
  --repo kai-cn/car-monit-api --workflow native-image-cloud.yml \
  --ref master --input stage=canary --input runner_mode=cloud
python $OPS/v3-github-actions-dispatch.py status --repo kai-cn/car-monit-api --run-id <id>

# 4. 六分支修复同步与提交（白名单）
python $OPS/v3-apply-aot-mybatis-fix.py
python $OPS/v3-fix-mapper-type-aliases.py --apply
bash $OPS/v3-publish-native-branches.sh            # dry-run
bash $OPS/v3-publish-native-branches.sh --apply
bash $OPS/v3-push-pending-branches.sh              # 网络重试

# 5. 只跑 AOT，快速验证 mapper BeanDefinition 修复
mvn.cmd -B -ntp -Pnative,native-flink-exclude -DskipTests -pl pro-business-api clean package
grep sqlSessionFactory pro-business-api/target/spring-aot/main/sources/com/ruoyi/base/mapper/*__BeanDefinitions.java

# 6. Windows 原生 exe 端到端构建（会先 wsl --shutdown 释放内存）
D:/work/runtime-logs/v3-ops/native-build.bat \
  D:/work/IdeaProjects/car-monit-api-jdk25 pro-business-api api-jdk25

# 7. 注入 DB 凭据并实测启动 / RSS
powershell -File $OPS/v3-run-native-with-db.ps1 -Exe <.../pro-business-api.exe>

# 8. 稳定性 + native/JVM 对比
powershell -File $OPS/v3-compare-native-jvm.ps1 -NativeExe <exe> -Jar <jar> -DurationSec 180
bash $OPS/v3-compare-native-jvm.sh --native <elf> --jar <jar> --java <java> --duration 180

# 9. 自托管 CICD（runner 在线时）
python $OPS/v3-github-actions-dispatch.py dispatch \
  --repo kai-cn/car-monit-api --workflow native-image.yml \
  --ref car-monit-api-jdk25 \
  --input app=api --input jdk=25 --input runner_label=wsl-k3s-api
```

---

## 8. 业务完整启动 / 稳定性 / native-JVM 对比实测

### 8.1 三轮 Windows 原生构建的启动验证轨迹

| 轮次 | 构建日志 | 产物 | 运行结果 |
| --- | --- | --- | --- |
| 1（仅 AOT mapper 修复） | `native-api-jdk25-aotfix.log`，19:25，峰值 10.19GB | 348,545,024 B | 越过 MyBatis 注入；先因 JDBC URL 覆盖触发 md5 认证失败，改默认配置后 → **type alias `KafkaMessageRecord` 解析失败** |
| 2（+ 数据源凭据注入，未改源码） | 同上 | 同上 | `sqlSessionFactory` 成功解析；失败于 Mapper XML 别名（native 特有） |
| 3（+ XML 全限定名修复） | `native-api-jdk25-aliasfix.log`，19:40，16m27s | 348,545,024 B | **进程级段错误**，见 8.2 |

JVM 对照组（同一份代码、同一 DB）：

| 场景 | 结果 |
| --- | --- |
| `java -jar`（无 `--add-opens`） | 失败于 `OrikaMapperConfig` / `InaccessibleObjectException` |
| `java --add-opens=java.base/java.lang=ALL-UNNAMED -jar` | **8 秒端口就绪，完整启动** |
| 同上 + `--mybatis-plus.type-aliases-package=`（模拟 native 无扫描） | **8 秒端口就绪，完整启动**（证明 XML 全限定名修复有效） |

### 8.2 第三个阻塞：native image 段错误（fastjson2 修复已验证无效，继续收敛中）

第三次构建的 exe 启动只打印 Spring Boot banner 与
`[native-aot] explicit sqlSessionFactory reference patched into 0 ...` 后进程退出，
**stdout 无 Java 异常**；stderr 是 GraalVM SegfaultHandler：

```
[ [ SegfaultHandler caught a segfault in thread ... ] ]
siginfo: ExceptionCode: -1073741819, reading address ... (heapBase + 325408552)
RIP ... com.oracle.svm.core.genscavenge.remset.AlignedChunkRememberedSet.walkObjects
RDI ... com.oracle.svm.core.genscavenge.GreyToBlackObjectVisitor
```

- 连续 3 次稳定复现（含 `-Xmx1g`），不是偶发内存不足。
- 归档的上一阶段 exe（`dist/api-jdk25-windows-amd64.exe`，同样整包 fastjson2 参数）
  对照运行**无段错误**，正常失败在旧的 MyBatis `sqlSessionFactory` 错误 → 说明是
  本轮产物布局变化暴露了潜伏的坏 image-heap 引用。
- 两次构建的 `RecomputeFieldValue.FieldOffset ... failed` 警告数量均为 7，
  涉及 `com.alibaba.fastjson2.util.JDKUtils` 与
  `com.alibaba.fastjson2.writer.ObjectWriterImplMap` 的 `sun.misc.Unsafe.objectFieldOffset`：
  build-time 固化了运行时才有效的字段偏移，GC 扫描 image heap 时把脏值当引用。
- fastjson2 2.0.66 jar **自带官方** `META-INF/native-image/.../native-image.properties`，
  只把 22 个（含 JDKUtils）类设为 build-time。项目的
  `--initialize-at-build-time=com.alibaba.fastjson2` **整包**规则额外固化了官方未列出的类，
  属于偏离官方配置的做法。

**8.2.1 根因定位（21:00–21:25 续作，证据完整）**

`fastjson2-2.0.66.jar` **自带官方** `META-INF/native-image/com.alibaba.fastjson2/fastjson2/native-image.properties`，
原文已归档到 `evidence/fastjson2-2.0.66-native-image.properties.txt`。其 `Args=` 把 22 个类
（`JSONFactory`、`JSONReader/Writer`、`JDKUtils`、`TypeUtils`、`ObjectReaderProvider`、
`ObjectWriterProvider` 等）设为 `--initialize-at-build-time`：

- `JDKUtils` / `ObjectWriterImplMap` 的类初始化调用 `sun.misc.Unsafe.objectFieldOffset`，
  GraalVM 无法重算（构建日志 7 条 `RecomputeFieldValue.FieldOffset automatic field value transformation failed`），
  于是**构建期 JVM 对象布局算出的字段偏移被固化进 image heap**；
  运行时 GC 在 `AlignedChunkRememberedSet.walkObjects` 遍历 image heap 时把脏值当对象引用 → 段错误。
- 项目额外加的整包规则 `--initialize-at-build-time=com.alibaba.fastjson2` 把官方未列出的类也固化了，放大问题。
- `native-iterate-pass3` 的 10 轮「逐类追加 build-time」（每轮 ~90s，共 ~16 分钟）是**错误方向**：
  只是让更多 fastjson2 对象合法进入 image heap、消除编译报错，坏引用依旧。
  证据 `native-iterate-summary.txt` → `RESULT=MAX_ROUNDS_REACHED`；
  `native-iterate-round01.log` 的对象溯源链显示根来自
  `JSONFactory.getDefaultObjectReaderProvider` 被常量折叠（build-time 初始化所致），
  再经 `org.aspectj.util.LangUtil.<clinit>` 的 `Throwable.printStackTrace` 解析上下文进入 heap。

**8.2.2 正确修复方向与两轮实验（结论未定）**

让 fastjson2 全部在**运行时**初始化，Unsafe 偏移在运行时重新计算：

```
--exclude-config
.*fastjson2.*[.]jar
^/META-INF/native-image/
--initialize-at-run-time=com.alibaba.fastjson2
```

同时删除 pom 里全部 6 条 `--initialize-at-build-time=com.alibaba.fastjson2*` 规则。
脚本 `scripts/v3/ops/v3-fix-fastjson2-init.py`（默认 dry-run，`--apply` 才写六分支 pom，
会自动备份 + XML 校验）已编写并静态验证。**2026-11-15 21:32 已 `--apply` 到六分支**：
每分支删除 6 条 build-time 规则、插入 4 条修复参数，`--verify` 全部通过
（`bad_rules=False fix_present=True`），备份在
`D:\work\runtime-logs\v3-ops\backup\pom-fastjson2-20261115-*`；
证据 `evidence/fix-fastjson2-apply.log`。六分支连同此前未提交的
workflow 参数化 / logback 适配一并提交并推送成功：

| 分支 | commit |
| --- | --- |
| car-monit-api-jdk25 | `44f0a0b` |
| car-monit-api-jdk21 | `c73efd2` |
| car-monit-api-jdk17 | `84579f6` |
| car-monit-backend-jdk25 | `8af62ad2` |
| car-monit-backend-jdk21 | `031e1463` |
| car-monit-backend-jdk17 | `c70c1c03` |

推送证据 `evidence/push-fastjson2-fix.log`，六个分支均 `PUSHED backend=schannel attempt=1`，
此前 `car-monit-api-jdk21` 的 `STILL_PENDING` 已清零。

| 轮次 | args | 结果 |
| --- | --- | --- |
| v1 | `native-image-fastjson2-runtime.args` | **失败**（1m20s）。我写的 Windows 路径 `\QD:\work\...\E` 经 `@argfile` 解析后变成 `\QD:/work/.../E`，`--exclude-config` 未匹配；日志仍有 5 条 `RecomputeFieldValue` + 16 个 `An object of type '...fastjson2...' was found in the image heap`。教训：**argfile 里不要写反斜杠**，用不含反斜杠的可移植正则 |
| v2 | `native-image-fastjson2-runtime-v2.args` | 改用 `.*fastjson2.*[.]jar` + `^/META-INF/native-image/`。日志前 47 行中 `sun.misc.Unsafe::arrayBaseOffset ... JDKUtils` 告警**已消失**（只剩 grpc-netty-shaded 的 `UnsafeAccess`），`RecomputeFieldValue` 计数 0，`An object of type` 计数 0 → 排除生效迹象明确。**但运行 3m44s 后按用户「暂停」要求主动终止，未得到 BUILD SUCCESS / FAIL 结论**。21:29 恢复任务后重跑（旧日志备份为 `native-fastjson2-runtime-v2-partial.log`），本轮同样保持 WSL Stopped 以避免 vmmem 抢占内存 |

两份 argfile 已从 `target/tmp/` 复制到 `evidence/argfiles/`（`mvn clean` 不会删掉）。
现有 exe 仍是 20:48 的段错误版本（348,545,024 B，
sha256 `72AA565492C96B45342B948C43CE248E51965D78CDFC38C44F093D8AD56EBE44`）。

**续接第一步**（WSL 保持 Stopped，编译需要 ~10GB 内存）：

```
powershell -NoProfile -Command "& 'D:\work\runtime-logs\v3-ops\native-retry-from-args.bat' 'D:\work\IdeaProjects\car-monit-api-jdk25\target\tmp\native-image-fastjson2-runtime-v2.args' 'fastjson2-runtime-v2'"
```

成功后顺序：`python scripts/v3/ops/v3-fix-fastjson2-init.py --apply` → 六分支 commit →
启动 WSL → `v3-run-native-with-db.ps1` 验证业务完整启动 → `v3-compare-native-jvm.ps1` → §9。

**8.2.3 v2 构建成功但段错误依旧 → 根因判断修正（21:43–21:47）**

v2 重跑得到 `NATIVE_OK`（`evidence/native-fastjson2-runtime-v2.log`，14m29s，
Peak RSS 9.94GB，产物 350,167,040 B / sha256 `c9871f5f29a6d8882cf08860c22fefe74283c4ba2a942cb34c5b8001661fd4ae`），
构建期 `RecomputeFieldValue=0`、image-heap 对象错误=0。但
`v3-run-native-with-db.ps1` 启动后进程仍在 Spring refresh 早期段错误
（`native-run-api-jdk25-win-fastjson2-v2-20261115-214428.err.log`，栈顶仍是
`AlignedChunkRememberedSet.walkObjects`）。

**推翻「fastjson2 是唯一根因」的关键对照**：`native-api-jdk25-aotfix.log`（19:25 的 exe，
能走到 MyBatis 业务异常、无段错误）与 `native-api-jdk25-aliasfix.log`（19:40 的 exe，段错误）
**构建期都有同样的 7 条 `RecomputeFieldValue` 失败警告**。也就是说那 7 条警告本身并不必然导致
段错误；段错误只在业务启动走得更深（aliasfix 修复了 MyBatis 注入与 XML 别名之后）才暴露。
fastjson2 整包 build-time 仍是**错误配置**（v2 已纠正），但不是本次崩溃的充分原因。

**v3 实验（进行中）**：当前全部手动 build-time 规则只剩
`--initialize-at-build-time=ch.qos.logback` 与 `...Logger` 两条，且「整包 build-time」与当初
fastjson2 的错误模式同类。生成 `evidence/argfiles/native-image-runtime-only-v3.args`
（v2 基础上移除这两条），启动构建 `native-runtime-only-v3.log`。

**v3 结果（21:47）：1m03s 构建失败（`NATIVE_FAIL`，非段错误）**。日志明确指出
`ch.qos.logback.classic.Logger` 对象由
`io.grpc.netty.shaded.io.netty.channel.ChannelHandlerMask$2.run()` 在 build-time 创建并进入
image heap，类型未标记 build-time 初始化，GraalVM 以 `UnsupportedFeatureException` 拒绝。
**结论：logback build-time 规则是必需的，不能删除**；`--initialize-at-run-time=grpc`
与 `ChannelHandlerMask` 的 build-time 初始化存在边界冲突，如需收敛应只 runtime 化
`ChannelHandlerMask` 而非删除 logback 规则。

**上游缺陷对照（重要）**：检索到 Oracle Graal 官方 issue
[#13177 / GR-74266](https://github.com/oracle/graal/issues/13177)：**Windows + GraalVM 25.0.2 +
Serial GC 首次真实 GC 即崩溃**，栈顶同为
`AlignedChunkRememberedSet.walkObjects` / `blackenDirtyImageHeapRoots`，
报错 `Fatal error: Object with invalid hub type`；最小复现含 Netty 4.2.7 + Logback 1.5.32，
且服务已成功监听、在处理请求时才崩。这与本项目 JDK25 Windows 现象高度吻合
（Mandrel 25.0.4.1 基于 GraalVM 25，Netty 4.2.19 + Logback，崩溃于 Spring refresh 早期第一次 GC）。
issue 中 `-R:MinHeapSize=512m` **未能规避**。据此更合理的解释是**平台/版本缺陷**，
而不是项目 pom 参数；不建议继续在项目侧堆叠 `--initialize-at-*` 去「修」它。
可行规避：改用 Linux 原生镜像（G1 在 Linux 可用，且该 Windows 崩溃未见于 Linux），
或等上游修复。jdk21/17 的 Linux 构建因此成为主验证路径。

**策略调整**：JDK25 线已排除「fastjson2 整包 build-time」与「删除全部 build-time」两个方向，
段错误涉及更深的 image-heap 引用链。按用户要求并行推进 JDK21/17：若 Mandrel 23.x 上业务可
完整启动，则可判定为 Mandrel 25 / Spring Boot 4 版本组合问题，JDK21 先交付，JDK25 留作上游
问题跟踪；若同样段错误，则问题在项目 AOT 元数据，回到 JVM tracing agent 重新采集。

### 8.3 稳定性 / native-JVM 对比

**未执行**。用户设定的前置条件是「业务可以完整启动成功后」。当前 native 产物被 8.2 的
段错误阻断，不做无意义的数字填充。脚本已就绪并可复现：

- Windows：`v3-compare-native-jvm.ps1`（复用 `v3-native-bench.ps1`，两变体 A/B + native 稳定性阶段，输出 CSV/JSON）
- Linux：`v3-compare-native-jvm.sh`（curl 探活、RSS/CPU 采样、RSS 漂移、HTTP 成功率）

已有的 JVM 基线数据（供后续对比）：启动 **8 秒**（`jvm-control-aotfix2.log`、`jvm-preverify-noalias.log`）。

### 8.4 JDK25 的 Linux 路线（绕过 Windows 段错误）

Windows + GraalVM 25 的段错误（GR-74266）无法在项目侧规避，因此 JDK25 改用
**Linux ELF** 作为交付形态（生产本来也是 Linux）。构建机为 WSL2 + Mandrel 25.0.4.1，
脚本 `scripts/v3/ops/v3-native-build-linux.sh`。

**r1 构建（`evidence/native-api-jdk25-linux-r1.log`）**：成功，但产物 **342,756,064 B**，
并额外生成 `libjvm.so / libawt.so / libfontmanager.so` 等 JDK 库——说明当时是
**fallback 镜像**（JDK25 pom 未加 `--no-fallback`）。构建耗时 37m56s，
分析阶段 Peak RSS 7.73GB，宿主 13.8GB 内存被打满（GC 占 50% 时间）。

**r1 运行（`evidence/native-run-linux-api-jdk25-linux-r1.log`）**：Spring Banner 正常，
AOT 生效（`[native-aot] explicit sqlSessionFactory reference patched ...`），随后失败于：

```
Field sysUtilService in com.ruoyi.base.controller.SysTestController required a bean of type
'com.ruoyi.base.forest.HttpSysUtilApiService' that could not be found.
```

根因：**Forest 1.8 没有任何 GraalVM 支持**（`forest-core` / `forest-spring` /
`forest-spring-boot3-starter` 三个 jar 中 native-image 相关文件数均为 0），
其客户端 bean 依赖启动期注解扫描 + 动态代理，AOT/native 下拿不到 bean 定义。

**修复（生产最小改动，单点替换）**：新增
`com.ruoyi.base.forest.SysBaseClient`，用 Spring 自带 `RestClient` 复刻原 Forest 调用：
`POST {sysbaseUrl}/manager/suspicious/syncSuspiciousCarTask`，请求体仍用 fastjson2 序列化、
响应仍用 fastjson2 解析为 `JSONObject`，`SysUtilServiceImpl` 的注入点从
`HttpSysUtilApiService` 换成 `SysBaseClient`（全仓库仅 1 处调用）。同时在 JDK25 pom
的 `buildArgs` 补 `--no-fallback`，避免再产出 342MB 的 fallback 镜像。

**数据库连接已单独验证**：`docker exec` 进 openGauss 用 `gsql -d RuoYi -U gaussdb` 执行
`select 1` 通过；native 产物在 DEBUG 下可见 PostgreSQL 驱动正常发起 5 次
`Connecting with URL: jdbc:postgresql://127.0.0.1:5432/RuoYi?...` 且无鉴权异常。
早前日志里的 `Failed to obtain JDBC Connection` 来自一次手工运行（shell 转义把密码变量
吃空），非应用缺陷。

**r2 运行（`evidence/native-run-linux-api-jdk25-linux-r2.log`）**：Forest 缺失已修复，
启动继续推进（RSS 258MB / 16 线程 / CPU 3s），随后出现第二个 native 不兼容点：

```
Error creating bean with name 'orikaMapperConfig': Instantiation of supplied bean failed
```

排查：全仓库只有 `pro-base-common/.../config/OrikaMapperConfig.java` 一处提到 Orika，
**没有任何 `MapperFacade.map(...)` 调用**——该 bean 是死代码。Orika 在运行期用
javassist 生成 mapper 字节码，native image 无法支持。处理：删除该配置类（git 历史保留），
同时静态排查确认项目源码没有使用 javassist / byte-buddy / janino / reflections / groovy。

**迭代加速**：单次 O2 构建受宿主 13.8GB 内存限制要 30+ 分钟，迭代期在 JDK25 pom
加 `-Ob`（只做基本优化），把单轮压到 ~10 分钟；业务启动跑通后再去掉做交付级 -O2 构建。

**r3 运行（`evidence/native-run-linux-api-jdk25-linux-r3.log`）——三个新发现**：

1. **服务端口是 9902**（`application.yml` 的 `server.port: 9902`），不是 Spring 默认 8080。
   首次探活用 8080 导致误判"未启动"；改用 9902 后 `port_ready=1`、`http_root_code=404`
   （根路径无映射，404 属正常），Tomcat 已实际对外服务。
2. **Lettuce 7 需要 `-H:+SharedArenaSupport`**：Redis 连接线程抛
   `com.oracle.svm.core.jdk.UnsupportedFeatureError: Support for Arena.ofShared is not active`
   → `RedisException: Connection is closed`，Redis 相关功能全废。已加入 JDK25 pom buildArgs。
3. **构建脚本必须先 clean**：`mvn install`（不带 clean）不会删除 `target/classes` 里已删除源
   文件留下的旧 class，`pro-base-common` 的旧 `OrikaMapperConfig.class` 因此仍被打进 jar，
   native 镜像里 bean 依旧存在。已把 stage 1 改为 `clean install`。
4. orika bean 仍在 `r3-port9902` 运行中报错并导致 `Application run failed`，但此时
   Tomcat 已绑定端口、定时任务已运行，说明**只剩这一个 bean** 阻断完整启动。

**已知环境缺口**：WSL 内 6379 端口被占用（`docker run redis` 绑定失败），Redis 不可用；
Kafka / Elasticsearch / MySQL 容器在编译期被停掉以释放内存。因此本轮只验证"应用能完整
启动并对外服务"，业务链路（Redis 缓存、Kafka 消费、ES 检索）需在补齐依赖后单独验。

**r4 运行（`evidence/native-run-linux-api-jdk25-linux-r4.log`）**：Orika 已消失（clean 生效），
暴露第三个 native 不兼容点：

```
Caused by: com.github.pagehelper.PageException:
  java.lang.InstantiationException: com.github.pagehelper.PageHelper
Caused by: java.lang.NoSuchMethodException: com.github.pagehelper.PageHelper.<init>()
    at com.github.pagehelper.util.ClassUtil.newInstance
    at com.github.pagehelper.PageInterceptor.setProperties
    at PageHelperAutoConfiguration.afterPropertiesSet
```

PageHelper 的 `PageInterceptor` 用 `Class.newInstance()` 反射实例化 `PageHelper` 与方言类，
native image 里没有注册构造器元数据。处理：新增
`src/main/resources/META-INF/native-image/com.ruoyi/v3-native-hints/reflect-config.json`，
注册 `PageHelper` / `PageInterceptor` / `ClassUtil` 与 15 个 `dialect.helper.*Dialect`
的 `allDeclaredConstructors`（脚本化生成，条目随 pagehelper 版本可重新生成）。

> **native 适配的通用方法**：每轮只修"当前最先抛出的那一个"阻断点，用 `-Ob` 把单轮压到
> ~10-25 分钟，改完立刻重跑验证；候选类型按"运行期反射/动态字节码"特征排查
> （Orika=javassist 生成 mapper、Forest=注解扫描+代理、PageHelper=Class.newInstance）。

---

## 9. jdk21 / jdk17 推进记录

> **状态（21:58 更新）：jdk21 Linux 原生构建进行中，jdk17 待安装。** 由于 jdk25 Windows 产物
> 的段错误高度疑似上游缺陷 GR-74266（§8.2.3），按用户要求把 jdk21/17 提前为并行验证路径，
> 用 Linux 产物验证业务完整启动；这不再以 jdk25 前置条件为前提。

**已完成（有证据）**：

| 项 | 结果 |
| --- | --- |
| 六分支 pom / workflow | jdk17/21/25 × api/backend 均已同步 AOT Registrar、405 处 XML 全限定名、agent 反射元数据、`native-image.yml` / `native-image-cloud.yml`；六分支本地 commit 完成 |
| 远端推送 | **六分支全部已 PUSHED**（21:34 重试，`evidence/push-fastjson2-fix.log`，均 `schannel attempt=1`），此前 `car-monit-api-jdk21` 的 `STILL_PENDING` 已清零 |
| self-host canary | `run 43716127318`（api）/`43716152235`（backend）均 success；`ensure-selfhost-build-workflow.log` 显示两个仓库 master 的 `native-image.yml` 已写入 |
| Mandrel Linux 21/17 | `download-mandrel-21-17.log`：java21 tarball 262,698,482 B / sha256 `ac437f47…`，java17 244,052,887 B / sha256 `8b7c4262…`，均 SHA256_OK。**Mandrel 21 已于 21:50 在 WSL ext4 安装并冒烟通过**（`evidence/setup-mandrel-linux21.log`：`SETUP_OK mandrel=/home/dev/tools/mandrel-21`，Java 21.0.13，`hello native` 成功）；Mandrel 17 仍在 `D:\jdk` 未安装 |
| 版本核对 | 六分支 `fastjson2.version` 均 `2.0.66`、`spring-boot.version` 均 `4.1.2`，`java.version` 分别 25/21/17 → §8.2 的修复对六个组合同样适用 |
| 对比脚本 | `v3-compare-native-jvm.sh`（Linux）、`v3-compare-native-jvm.ps1`（Windows）静态校验通过，未实跑 |

**续接命令**（需先临时把 WSL 配额提到 `12GB/4GB/6核` 并 `wsl --shutdown`，编译期峰值约 10GB）：

```
# 1) 安装并冒烟 java21 / java17 Mandrel（tarball 已在 D:\jdk）
wsl -d openEuler-24.03-LTS-SP4 -- bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-setup-mandrel-linux.sh 21
wsl -d openEuler-24.03-LTS-SP4 -- bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-setup-mandrel-linux.sh 17

# 2) 先做 AOT 快检（约 4 分钟，避免盲目 28 分钟 native-image）
# 3) 完整 Linux ELF（每个约 28 分钟，需 MANDREL_HOME=/home/dev/tools/mandrel-21|17）
MANDREL_HOME=/home/dev/tools/mandrel-21 bash scripts/v3/ops/v3-native-build-linux.sh api 21 /mnt/d/work/IdeaProjects/car-monit-api-jdk21 api-jdk21-linux

# 4) 或用 self-host CICD 触发（runner 需在 WSL 内在线）
python scripts/v3/ops/v3-github-actions-dispatch.py dispatch \
  --repo kai-cn/car-monit-api --workflow native-image.yml \
  --ref car-monit-api-jdk21 --input app=api --input jdk=21
```

**jdk21 首轮实测（21:50–21:58，`evidence/native-api-jdk21-linux.log`）**：Maven install 与 Spring AOT
均成功（Registrar patch 了 **23** 个 MapperFactoryBean），native-image 阶段 5m59s 后失败：

```
The configured GraalVM reachability metadata repository ... provides a
reachability-metadata schema, but your GraalVM installation at
/home/dev/tools/mandrel-21 does not. Please update your GraalVM installation...
```

原因：native-maven-plugin 1.1.14 默认拉取的 reachability metadata 使用新 schema，
Mandrel 21（GraalVM 23.1 线）不支持。项目已自带 tracing-agent 元数据
（`META-INF/native-image/com.ruoyi/pro-business-api-agent/reachability-metadata.json`），
因此在 `car-monit-api-jdk21/pro-business-api/pom.xml` 的 native 插件配置中加
`<metadataRepository><enabled>false</enabled></metadataRepository>`（原文件备份
`backup/pom-jdk21-before-metadata-disable.xml`），并重跑 `api-jdk21-linux-r2`。
JDK25 分支保持 metadata repository 开启（Mandrel 25 支持新 schema）。

**jdk21 r2 实测（22:09，`evidence/native-api-jdk21-linux-r2.log`）**：禁用 metadata repository 后
native-image 进入分析阶段（1m39s）后失败：

```
Error: java.util.concurrent.ExecutionException: java.lang.NoClassDefFoundError:
       org/apache/pulsar/shade/org/tukaani/xz/LZMAInputStream
    at com.baomidou.mybatisplus.aot.FeatureUtils.registerSerializationLambdaCapturingClass(FeatureUtils.java:364)
    at com.baomidou.mybatisplus.aot.MybatisPlusFeature.lambda$serializedLambda$0(MybatisPlusFeature.java:69)
```

**根因（已用反编译 + JVM 最小复现确认，非 JDK25 的 fastjson2/GR-74266 问题）**：

- MyBatis-Plus 3.5.18 的 `MybatisPlusFeature` 在 analysis 阶段调用
  `findMainPackages()`，把 classpath 上**所有带 `public static void main` 的类**当作主类，
  再对其包树里每个类调 `Class.getDeclaredMethods()` 找 `$deserializeLambda$`。
- `pulsar-client-4.2.5.jar` 内含 shaded commons-compress 的
  `org.apache.pulsar.shade.org.apache.commons.compress.archivers.sevenz.CLI`（带 main 方法），
  被误判为主类 → 其包树里的 `LZMADecoder` / `LZMACompressorInputStream` 方法签名引用
  `org.apache.pulsar.shade.org.tukaani.xz.LZMAInputStream` 等类。
- 但 `pulsar-client-4.2.5.jar` **整个 shaded tukaani 包都缺失**（`unzip -l | grep -ci tukaani` = 0；
  两仓库 jar SHA256 一致 `5f730532…`，非本地损坏），是上游打包缺陷。
- 因此 `getDeclaredMethods()` 抛 `NoClassDefFoundError` 中断分析。JDK25 Windows 构建之所以能过，
  是因为其 Windows classpath 顺序/可达性不同，扫描未触达该残缺包，属"侥幸通过"，非根本差异
  （同一 JVM 25 上直接 `getDeclaredMethods()` 该 shaded 类同样抛异常）。

**第一次修复尝试（补 pulsar-xz，已验证"打地鼠"，不足以解决）**：

- 新增脚本 `scripts/v3/ops/v3-build-pulsar-xz-patch.py`：以本地仓库
  `org.tukaani:xz:1.12` 为源生成补丁，同时含**原始** `org/tukaani/xz/*` 与**重定位**
  `org/apache/pulsar/shade/org/tukaani/xz/*` 两份 class（123×2=246 类，327,938 B）。
- 落地方式：补丁 class 解压到 `pro-business-api/src/main/resources/`，由 Maven resources
  阶段复制进 `target/classes`（native-image classpath 首项），不改构建脚本与 pom 依赖。
  注意父 pom 对 `src/main/resources` 设了 `<filtering>true</filtering>`，二进制 class 会被当
  文本过滤而损坏（r4 报 `MalformedInputException`），故在 api 子模块
  `maven-resources-plugin` 加 `nonFilteredFileExtensions` 豁免 `.class`
  （脚本 `scripts/v3/ops/v3-add-nonfiltered-class.py`，三分支 api pom 已同步）。
- **r5 实测（22:31，`evidence/native-api-jdk21-linux-r5.log`）**：LZMA 卡点越过，
  但立刻暴露出下一个缺类 `org/apache/log4j/Priority`（66 次）。说明这是**系统性问题**，
  逐类补不可行。

**全量埋雷审计（新增可复现工具，一次性算清而不是逐轮试）**：

- 新增脚本 `scripts/v3/ops/v3-native-scan-audit.py`：解析真实 `-cp`（从构建日志
  `Executing: native-image -cp ...` 提取，307 个条目），按 MyBatis-Plus 的规则复现扫描
  （找出所有 `public static void main(String[])` 类的包作为递归前缀），再用最小 class
  文件解析器检查每个类的字段/方法描述符是否引用了 classpath 上不存在的类型。
- **实测结果（`evidence/scan-audit-api-jdk21.json`）**：93,606 个类 → 104 个 main 类 →
  **70 个扫描根包 → 26,912 个被扫类 → 159 个埋雷**。根包覆盖
  `org/springframework/boot`、`org/apache/kafka/*`、`org/elasticsearch/*`、`org/bouncycastle`、
  `io/netty/util`、`org/apache/catalina/*`、`org/apache/pulsar/shade/*` 等整片依赖。
  缺的类型是 micrometer、actuator、testcontainers、log4j2、OSGi、docker-compose 等
  可选依赖——都不在、也不该在 native classpath 上。
- 结论：**`MybatisPlusFeature` 的"全 classpath 找 main 类"兜底扫描在 Spring Boot fat
  classpath 上是设计缺陷**；补类路线彻底放弃。

**为什么 JDK25 分支能过**：Mandrel 25（GraalVM 25）的 hosted
`NativeImageClassLoader` 对缺失类型容忍，`getDeclaredMethods()` 不抛
`NoClassDefFoundError`；Mandrel 21（GraalVM 23.1）不容忍。证据：
`evidence/native-api-jdk25-linux.log` 中 `NoClassDefFoundError` 计数为 0。
这也意味着 JDK25 Windows 构建"通过"并非 classpath 侥幸，而是版本行为差异。

**最终修复（收敛扫描范围，不改业务代码与依赖版本）**：

- 关键事实：应用自己生成的
  `target/classes/META-INF/native-image/com.ruoyi/pro-business-api/native-image.properties`
  已声明 `Args = -H:Class=com.ruoyi.EcBusinessApiApplication`，即
  `CollectUtils.findMainClassesFromNativeImageProperties()` 本来就能得到正确的主类。
  有害的只是第二个来源——全 classpath 的 `findClasses(isMainClass)`。
- 新增脚本 `scripts/v3/ops/v3-patch-mybatis-aot-scan.py`：把
  `com.baomidou.mybatisplus.aot.CollectUtils.findMainClasses()` 的方法体改写为
  `return findMainClassesFromNativeImageProperties();`（字节码
  `2a b6 01a4 b0`，只复用已有常量池项 #420，不新增常量）。同一 class 的其余方法与
  `findMainPackages()`、`registerSerializationLambdaCapturingClass()`、
  MyBatis mapper/XML 注册、Wrapper 注册全部保持原样，因此
  `com.ruoyi` 包内的 lambda 捕获类仍会被 `RuntimeSerialization` 注册。
- 落地方式与 xz 补丁一致：补丁后的 `com/baomidou/mybatisplus/aot/CollectUtils.class`
  放入 `src/main/resources`，在 `target/classes` 中**遮蔽** jar 内同名类
  （classpath 首项优先），无需替换 jar、无需 `--exclude-config`。
- 已排除的更差方案：
  - `--allow-incomplete-classpath`：实测无效（r6，缺类从 log4j 1.x 变成 log4j2
    `PropertiesConfigurationFactory`，仍无产物）；
  - `--exclude-config` 掉 `mybatis-plus-spring-boot-native-image` 的
    `Args = --features=...`：会连同 MyBatis mapper 注册与 lambda 注册一起失效，
    而业务确实在用 `LambdaQueryWrapper`（`DataLossDetectionService`、
    `SnapshotFlowSyncService`），风险高于范围收敛；
  - 拆 `clean native:compile` 为 `clean process-aot` + 注入 + `native:compile`：
    `process-aot` 不是合法生命周期阶段，且 `native:compile` 内部会重跑 AOT，已撤销。

**r7 实测（`evidence/native-api-jdk21-linux-r7.log`）**：`CollectUtils` 补丁生效，
`NoClassDefFoundError` 归零、`org/apache/log4j/Priority` 与 pulsar-xz 全部消失；
构建推进到分析结束，只剩 Mandrel 21 的
`Error: Classes that should be initialized at run time got initialized during image building`。

**第二轮收敛：class-init 冲突（r8–r14，每轮约 2 分钟）**。
在 r5 的真实 `native-image` 命令上做重放（脚本 `evidence/replay-r8..r14.sh`），
用 `--trace-class-initialization` 逐一定位触发者：

| 轮次 | 关键动作 | 结果 |
| --- | --- | --- |
| r8 | 追踪 `MarkerFactory` / `ByteBufUtil` / `SLF4JProvider` | 触发者 = `org.springframework.data.core.TypedPropertyPathFeature.<clinit>` → `LogFactory.getLog`；另一条 = `io.netty.handler.ssl.JdkSslServerContext.<clinit>` → `ByteBufUtil` |
| r9 | 同一类同时声明 run-time + build-time | 失败：`Incompatible change of initialization policy` |
| r10 | `--initialize-at-run-time=io.netty.handler.ssl` + logging 全链 build-time | log4j2/slf4j 冲突消失 |
| r11 | 继续追踪 | 触发者 = `io.netty.channel.kqueue.KQueue.<clinit>`（macOS 专用，Linux 上也在构建期被初始化）、`io.grpc.netty.shaded...PlatformDependent0`、`org.springframework.data.core.SerializableLambdaReader` |
| r12 | 三者改 run-time | 冲突变成"声明 run-time 但实际 build-time"，未解决 |
| r13 | `--initialize-at-build-time=org.springframework.core,...` 整包 | 失败：`VfsUtils.<clinit>` 缺 `org.jboss.vfs.VFS`（Spring `core` 不能整包 build-time） |
| r14 | 精确到类 + kqueue/SSL run-time | **构建成功**：`Produced artifacts: target/pro-business-api-r14`，3m16s，Peak RSS 4.44GB |

**r15 实测（`evidence/native-api-jdk21-linux-r15.log`）**：把 r14 参数写进 pom、改由 Maven
正式构建后 **构建成功**：ELF 93,915,872 B，总耗时 8m01s（native-image 3m18s，
Peak RSS 4.06GB），`BUILD_OK label=api-jdk21-linux-r15`。

**r15 运行实测：AOT initializer 缺失**

```
org.springframework.boot.AotInitializerNotFoundException: Startup with AOT mode enabled failed:
  AOT initializer com.ruoyi.EcBusinessApiApplication__ApplicationContextInitializer could not be found
```

排查结论：`process-aot` 确实执行了（日志第 214 行），AOT 产物也已复制进
`target/classes`（`...__ApplicationContextInitializer.class` 存在，且是 `-cp` 首项），
AOT 生成的 `META-INF/native-image/com.ruoyi/pro-business-api/reachability-metadata.json`
（793KB、1362 条反射项、81 条资源项）也包含该类的注册：

```json
{ "type": "com.ruoyi.EcBusinessApiApplication__ApplicationContextInitializer",
  "condition": { "typeReached": "com.ruoyi.EcBusinessApiApplication" },
  "methods": [{ "name": "<init>", "parameterTypes": [] }] }
```

但镜像里就是没有这个类。**r17 实验（`evidence/native-api-jdk21-linux-r17.log`）证实了原因**：
额外用 `-H:ConfigurationFileDirectories` 传入一份**无条件**的 `reflect-config.json`
（内容同上、去掉 `condition`）后，该类立即被正确包含——说明
**Mandrel 21（GraalVM 23.1）不识别 reachability-metadata 的 `condition.typeReached`
条件项，会把带条件的条目静默忽略**；Mandrel 25 支持该字段，所以 JDK25 分支不需要这个处理。
可行的工程化修法：在 `process-aot` 之后把 AOT metadata 展开成无条件的
`reflect-config.json` / `resource-config.json`，用 `-H:ConfigurationFileDirectories` 注入。

**结论（关键，改变后续路线）：Spring Boot 4.1.2 的 native 只支持 Java 25。**
r17 修好 AOT initializer 后，镜像继续往下跑，被 Spring Boot 自己的硬性检查拦下：

```
org.springframework.boot.SpringApplication$NativeImageRequirementsException:
  Native Image requirements not met. Native Image must support at least Java 25
  but Java 17 was detected
    at org.springframework.boot.SpringApplication.addAotGeneratedInitializerIfNecessary(SpringApplication.java:425)
```

即：**JDK21/JDK17 分支无法产出可运行的 Spring Boot 4 原生镜像**，与项目 pom 参数无关
（构建能成功，运行被框架版本门槛拒绝）。因此：

- **JDK25 是 Spring Boot 4 唯一可行的 native 目标**；JDK21/JDK17 继续以 JVM jar 交付。
- JDK21/17 若将来必须上 native，只有两条路：升级 Spring Boot（等上游放宽），
  或把这两个分支锁在 Spring Boot 3.x + GraalVM 23.1 的依赖组合上（Netty 4.1 /
  Spring Data 3.x），代价是依赖栈回退。
- JDK21 侧已落地的两项改动保留但标注为"实验性/不可运行"：
  `CollectUtils` 扫描范围补丁（解决 159 处埋雷，通用有效）与 class-init 参数组
  （解决 Mandrel 21 的初始化策略冲突，通用有效）。这两项对将来 Spring Boot
  放宽版本门槛后直接可用。

Spring Boot 4.1.2 / Spring 7 AOT 产物在 GraalVM 23.1 上的兼容性问题（`condition` 元数据
被忽略、class-init 检查更严格）已按上述实测记录；禁用 metadata repository 后第三方库
（lucene / mysql-connector / jna 等）的反射元数据只能依赖项目自带 agent 文件。

---

## 9A. 附：本轮新增工具与用法

| 工具 | 用途 |
| --- | --- |
| `scripts/v3/ops/v3-native-scan-audit.py` | 用真实 `-cp` 复现 MyBatis-Plus AOT 扫描，一次性列出所有"方法签名引用缺失类型"的埋雷类 |
| `scripts/v3/ops/v3-patch-mybatis-aot-scan.py` | 字节码改写 `CollectUtils.findMainClasses()` 为只取 `-H:Class` 声明，收敛扫描范围 |
| `scripts/v3/ops/v3-build-pulsar-xz-patch.py` | 生成 pulsar shaded tukaani 补丁（含原始包与重定位包双份） |
| `scripts/v3/ops/v3-add-nonfiltered-class.py` | 给 api 子模块加 `nonFilteredFileExtensions=class`，避免 resources 过滤损坏二进制补丁 |
| `scripts/v3/ops/v3-run-native-linux.sh` | 在 WSL 内启动 ELF、等端口、采样 RSS/线程/CPU、抓 HTTP 状态并落 summary |
| `evidence/replay-rN.sh` | 从真实构建日志提取 `native-image` 命令后原样重放，用于 2 分钟级参数迭代 |

---

## 10. 已知风险与未完成项

- 云 runner 账单受限，本轮云端编译**未实跑**；云 workflow 只做了静态校验与默认分支写入。
- `graalvm/setup-graalvm` 对 `distribution: mandrel` + java17/21 的实际解析结果尚未在云端验证
  （云 runner 被拒）。本地侧固定版本清单已确认三个 Mandrel release 均存在。
- **段错误根因仍在收敛**：v2 已用 `--exclude-config` + 全包 run-time 消除 fastjson2 的
  7 条 `Unsafe` 偏移警告并成功构建（`evidence/native-fastjson2-runtime-v2.log`，`NATIVE_OK`），
  但运行**仍段错误**（栈顶 `AlignedChunkRememberedSet.walkObjects`）；对照发现早前能正常进入
  业务异常的 aotfix exe 也带同样 7 条警告，故 fastjson2 不是充分原因。v3 移除剩余两条 logback
  build-time 规则后**构建失败**（`evidence/native-runtime-only-v3.log`：
  `An object of type 'ch.qos.logback.classic.Logger' was found in the image heap`），
  证明 logback build-time 规则不能删，该方向已证伪。当前定位到 JDK25 Windows 段错误极可能是
  上游 GR-74266（见下条），项目侧参数收敛无法解决。
- `native-iterate.py` 的「逐类追加 build-time」自动收敛在 fastjson2 场景是反模式，
  10 轮 `MAX_ROUNDS_REACHED` 已证伪；该脚本仅适用于 Logback/grpc 那类「类初始化时机」问题。
- **`--exclude-config` 的路径正则不能含 Windows 反斜杠**（`@argfile` 会改写），
  CICD 跨 Windows/Linux 必须用 `.*fastjson2.*[.]jar` 这类可移植写法。
- `ch.qos.logback` 整包 build-time **不能删除**：v3 移除后 `ChannelHandlerMask$2.run()` 在
  build-time 创建的 `Logger` 对象被 GraalVM 拒绝进入 image heap（1m03s 构建失败）。
- **JDK25 Windows 段错误疑似上游缺陷 GR-74266**（Oracle Graal issue #13177）：
  Windows + GraalVM 25 + Serial GC 首次 GC 在 `AlignedChunkRememberedSet.walkObjects` 崩溃。
  项目侧参数收敛不能解决，优先用 Linux 镜像 / jdk21/17 规避。
- `car-monit-api-jdk21` 分支此前推送失败已于 21:34 重试成功（schannel 一次通过，
  证据 `evidence/push-fastjson2-fix.log`）；六分支远端均已含最新 CICD + fastjson2 修复提交。
- 云 workflow 的 `graalvm/setup-graalvm` 对 mandrel java17/21 的实际解析尚未在云端验证
  （云 runner 被拒）；本地固定版本清单已确认三个 release 存在。
- 编译期 native-image 峰值 RSS 10.1–10.2 GB，Windows 编译必须先关闭 WSL；
  Linux 编译需临时 12GB/6核 配额，不能与 Windows 编译并行。
- docker 未引用卷约 4.995 GB 未擅自清理。
