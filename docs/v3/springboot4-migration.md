# Spring Boot 4.1.2 迁移与踩坑记录（api / openGauss）

> 分支：`car-monit-api-jdk17`（`jdk21` / `jdk25` 分支只差 `java.version`）
> 迁移日期：2026-11-14　目标：把 Spring Boot 从 2.7.18 升到 **JDK 17 可运行的最新稳定版 4.1.2**，并实机跑通。
> 与 backend 侧同源，本文件只记录 api 侧特有的部分；通用规则见 `car-monit-backend` 同名文档。

## 1. 版本结论

| 项 | 迁移前 | 迁移后 | 说明 |
| --- | --- | --- | --- |
| JDK | 17 | 17 | 21/25 分支只改 `java.version` |
| Spring Boot | 2.7.18（starter-parent） | **4.1.2**（starter-parent） | Boot 4.1.x 的 JDK 基线是 17 |
| Spring Framework | 5.3.39 | 7.0.10（BOM） | |
| Servlet | javax 4.0 | jakarta 6.1 | |
| Jackson | 2.13 | **3.1.7（`tools.jackson.*`）** | |
| MyBatis-Plus | 3.5.5 | 3.5.18（`mybatis-plus-spring-boot4-starter` + `extension` + `jsqlparser-4.9`） | |
| PageHelper | 1.4.7（Boot 2 线） | 4.1.1（Boot 4 线） | |
| Druid | `druid-spring-boot-starter` 1.2.20 | `druid-spring-boot-4-starter` 1.2.28 | |
| dynamic-datasource | 3.4.0 | `dynamic-datasource-spring-boot4-starter` 4.6.0 | |
| Kafka | `spring-kafka` 2.8.11 | **`spring-boot-starter-kafka`**（spring-kafka 4.1.2） | Boot 4 把 KafkaAutoConfiguration 拆成独立模块 |
| RocketMQ | `rocketmq-spring-boot-starter` 2.2.3 | 2.3.5 | |
| Pulsar | pulsar-client 2.10.4 | Boot 4 `pulsar-bom` 4.1.3 | |
| Flink | 1.13.2（Scala 2.11） | **移除**（见第 4 节） | |
| 接口文档 | knife4j 3.0.3（springfox 内核） | **移除**（工程内无任何 swagger 注解） | |
| MySQL 驱动 | `mysql:mysql-connector-java` 8.0.27 | `com.mysql:mysql-connector-j`（BOM 9.7.0） | 仅用于读 carmonitdb 的 plate_color 字典 |
| Jedis | 4.3.1 | 4.4.8（显式钉版） | Jedis 5/6 的 `JedisCluster` 构造 API 变化，先钉 4.x |
| javassist | 由 orika 传递 | 显式 3.30.2-GA | Orika 1.5.4 在 JDK 17 需较新 javassist |

## 2. 依赖/代码改动

### 2.1 POM
1. parent 升级到 `spring-boot-starter-parent:4.1.2`；
2. `spring-boot-starter-web` → `spring-boot-starter-webmvc`；`spring-boot-starter-aop`(test) → `spring-boot-starter-aspectj`(test)；
3. `spring-kafka` → `spring-boot-starter-kafka`（否则 `@KafkaListener` 报 “Consider defining a bean named 'kafkaListenerContainerFactory'”）；
4. 去掉 knife4j（springfox 内核，Boot 3/4 起不可用；工程内 0 处 swagger 注解）；
5. 去掉 `com.alibaba:fastjson` 1.2.83（仅 `SecurityInterceptor` 用 `JSON.toJSONString`，改用 fastjson2）；
6. 去掉 `guava:11.0.2`（0 处 import）；补 `commons-lang3`（原来靠传递引入）；
7. `httpclient` 4.x 显式钉 4.5.14（Boot 4 只管理 httpclient5，而 ES 7.17 / Forest / 阿里 SDK 仍用 4.x）；
8. ES 两个依赖加 `<exclusion>org.elasticsearch:jna</exclusion>`（同 backend：与官方 JNA 抢 `com.sun.jna` 包名）。

### 2.2 代码
| 文件/位置 | 改动 |
| --- | --- |
| 69 个 java 文件 | `javax.servlet/annotation/validation` → `jakarta.*`；MP `extension.service` → `spring.service`；Jackson 2 → 3 |
| `JSONHandler` | 改用 `JsonMapper.builder()...build()`；读写不再声明 `IOException`（Jackson 3 非受检）；`fieldNames()`→`propertyNames()` |
| `KafkaProducerService` / `DataReliabilityService` | `ListenableFuture.addCallback(Success/Failure)` → `CompletableFuture.whenComplete((r,e)->…)`（`org.springframework.util.concurrent` 整包已从 Framework 6 移除） |
| `RetRedisCacheWriter` | Spring Data Redis 4.x 给 `RedisCacheWriter` 加了 4 个抽象方法：`retrieve` / `store` / `evict` / `clear`，按同步实现补齐 |
| `SecurityInterceptor` | `com.alibaba.fastjson.JSON` → `com.alibaba.fastjson2.JSON` |
| `TrafficEsIndexService` | `JsonNode.fieldNames()` → `propertyNames()`（Jackson 3 更名） |
| `VehicleTrackFlinkJob` | 删除（无调用点，见第 4 节） |

### 2.3 配置（`pro-business-api/src/main/resources/application.yml`）
| 迁移前 | 迁移后 | 原因 |
| --- | --- | --- |
| `spring.redis.*` | `spring.data.redis.*` | Boot 3 改名（`lettuce.pool` 同步缩进） |
| `spring.mvc.pathmatch.matching-strategy: ant_path_matcher` | 删除 | Framework 7 只有 PathPatternParser |
| `spring.main.allow-circular-references: true` | 删除 | Framework 6.2 起永久禁止 |
| `spring.autoconfigure.exclude: com.alibaba.druid.spring.boot.autoconfigure.DruidDataSourceAutoConfigure` | `...spring.boot4.autoconfigure...` | druid boot4 starter 包名 |
| （无） | `dynamic.druid.wall.select-where-alway-true-check: false` + `multi-statement-allow: true` | 见踩坑 3 |

## 3. 踩坑清单（api 特有）

1. **POM 注释里的 `--add-opens` 让 XML 解析失败**：XML 注释内不能出现 `--`，Maven 直接 `Non-parseable POM`。注释里改写为“add-opens 参数”。
2. **`RedisCacheWriter` 接口扩了方法**：Spring Data Redis 4.x 新增 `retrieve/store/evict/clear` 抽象方法，自定义 writer 不实现就编译不过。
3. **druid wall 拦截 `WHERE 1 = 1`**：报 `sql injection violation, dbType postgresql, druid-version 1.2.28, select alway true condition not allow`。
   - 关键点：真正的开关是 **`select-where-alway-true-check`**（`WallConfig#setSelectWhereAlwayTrueCheck`），不存在 `select-always-true-allow` 这个属性；写错时启动日志会打 `druid wall does not have param xxx`。
   - 本工程走 `dynamic-datasource`，配置位置是 `spring.datasource.dynamic.druid.wall.*`（扁平 Map，经 `DruidWallConfigUtil` 反射到 `WallConfig`）。
4. **`ListenableFuture` 整体移除**：`KafkaTemplate.send` 现在返回 `CompletableFuture`，`addCallback` 编译不过。
5. **`kafkaListenerContainerFactory` 缺失**：只引 `spring-kafka` 不够，Boot 4 要 starter。
6. **Orika + JDK 17**：启动即 `InaccessibleObjectException: Unable to make ... java.lang.Object.clone() accessible`，必须加 JVM 参数 **`--add-opens=java.base/java.lang=ALL-UNNAMED`**（已写入启动脚本；容器/CI 的 JAVA_OPTS 也要加）。
7. **openGauss 连接**：旧配置写死 `192.168.56.10:5432`（VM）。当前环境 openGauss 已迁到 WSL docker，Windows 侧经 `127.0.0.1:5432` 访问，**URL 由启动脚本用 `--spring.datasource.dynamic.datasource.master.url=...` 覆盖**，口令由 `SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD` 注入，仓库内不落任何凭据。
8. **ES 未启动**：`ElasticsearchConfig` 启动时会做一次连通性探测，失败只 WARN，不影响启动（`traffic.query.engine=legacy`、`es.auto-bootstrap=false`）。
9. **`/base/snapshotflow/list` 偶发 500**：`Cannot invoke "…setId(String)" because "rtn" is null`。
   - 根因不在升级：MyBatis 对“所有映射列都是 NULL”的结果行默认返回 **null 元素**，而 `decorate()` 直接遍历并调用 `rtn.setId(...)`；
   - 该表数据在联调期间持续增长（total 251 → 936），出现脏行后就会整页 500；JDK 17/21/25 表现一致；
   - 修复：`decorate()` 跳过 null 元素并打 WARN（不静默吞掉，便于追数据源）。

## 4. 为什么移除 Flink 1.13.2（决策记录）

- Flink 1.13（Scala 2.11）在 JDK 17 上需要大量 `add-opens`，akka 2.11 的反射调用在 17 上不稳定；
- 工程内 `VehicleTrackFlinkJob` **没有任何调用点**：不是 `@Component`，没有 per-job 启动脚本，也没有任何 CI/运维入口调用；
- 保留它等于为了死代码把 40MB+ 的不兼容依赖塞进 fat jar，并持续污染类路径。
- 后续若要做实时轨迹计算：按 Flink 1.20+（或 Flink 2.x）重新引入，并按新 API 重写该 Job（`FlinkKafkaConsumer` 已在 1.18 移除，改用 `KafkaSource`）。
- 需要历史实现时：`git log --diff-filter=D -- pro-business-api/src/main/java/com/ruoyi/base/flink/VehicleTrackFlinkJob.java`。

## 5. 实机验收记录（2026-11-14，Windows + JDK 17.0.21）

JVM：`-Xms512m -Xmx1024m --add-opens=java.base/java.lang=ALL-UNNAMED`，端口 9902，库 openGauss（`jl_data01` / `RuoYi`）。

| # | 用例 | 结果 |
| --- | --- | --- |
| 1 | `GET /api/v3/es/readiness` 无令牌 | 403（内部端点守卫生效） |
| 2 | 同上带 `X-Internal-Token` | 200，`activeEngine=legacy` |
| 3 | `GET /api/v3/export/capabilities` 带令牌 | 200，`modes=[display,full]`、`tables=[snapshot,fee,trail]` |
| 4 | `GET /base/section/list` | 200，total=85 |
| 5 | `GET /base/gantry/list` | 200，total=1526 |
| 6 | `GET /base/org/list` | 200，total=481 |
| 7 | `GET /base/snapshotflow/list` | 200，total=251 |
| 8 | backend → `GET /api/v1/bigscreen/stats/warning-top`、`/stats/income` | 令牌校验通过（非 403），api 侧按 `traffic.bigscreen.stats-enabled=false` 返回 503，backend 按契约回退 `LEGACY_DB` |
| 9 | backend `POST /manager/bigScreen/export/display` | 200，返回 taskId（跨服务导出提交打通） |

## 6. 复现步骤

```powershell
# 1. 构建
$env:JAVA_HOME='D:\jdk\temurin-17\jdk-17.0.21+9'
& 'D:\work\apache-maven\bin\mvn.cmd' -B -DskipTests package

# 2. 注入 DB 口令后启动（脚本在 D:\work\runtime-logs，不进仓库）
$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD = '<由环境注入>'
& 'D:\work\runtime-logs\rebuild-restart-api.ps1'

# 3. 内部端点自检
curl -H "X-Internal-Token: <与 backend TRAFFIC_API_INTERNAL_TOKEN 一致>" http://127.0.0.1:9902/api/v3/es/readiness
```

## 7. 回滚

- 代码：`git revert` 迁移提交（单提交，便于整体回滚）。
- 无 DDL/DML 变更；回滚只需换回旧制品。
- 若回滚到 Boot 2.7 版本，需要同时去掉启动参数 `--add-opens`（Orika 在 8/17 均可用，但 17 上仍建议保留）。

## 8. JDK 21 / 25

`car-monit-api-jdk21` / `-jdk25` 与本分支差异：

```xml
<java.version>21</java.version>   <!-- jdk21 分支 -->
<java.version>25</java.version>   <!-- jdk25 分支 -->
```

注意点：

1. **JDK 25 分支必须加 `-proc:full`**：JDK 23 起 `javac` 默认不跑注解处理器，Lombok 生成的构造器/Getter 会成片报
   `constructor ... cannot be applied to given types` / `cannot find symbol`。jdk25 的 `maven-compiler-plugin`
   增加 `<proc>full</proc>`（该取值 JDK 21 才有，17/21 分支不要加）。
2. **字节码基线**：升级前 api 的 jdk25 分支把 `release` 锁在 21（Spring 5.3 内嵌 ASM 只认到 major 65，
   Boot 2.7 的 repackage 在 major 69 上直接报错）。升级到 Boot 4.1.2 后 ASM 已支持 major 69，
   故 jdk25 分支改为 `release=25`，真正产出 Java 25 字节码。
3. JDK 24+ 移除 `SecurityManager`；`--add-opens=java.base/java.lang=ALL-UNNAMED` 仍然需要（Orika）。
4. Pulsar 4.1.3 / RocketMQ 2.3.5 / ES 7.17 客户端在 21 与 25 上均通过实机验证（列表查询、内部端点、令牌门禁）。

### 8.1 三支实机验收结论（2026-11-14）

| 分支 | 编译/打包 | 启动 | `/api/v3/es/readiness` | 令牌门禁(无令牌) | section/gantry/org/snapshotflow 列表 |
| --- | --- | --- | --- | --- | --- |
| jdk17 (17.0.21) | ✅ | ✅ | 200 | 403 | 200 / 200 / 200 / 200 |
| jdk21 (21.0.12) | ✅ | ✅ | 200 | 403 | 200 / 200 / 200 / 200 |
| jdk25 (25.0.4.1) | ✅（含 `-proc:full`） | ✅ | 200 | 403 | 200 / 200 / 200 / 200 |
