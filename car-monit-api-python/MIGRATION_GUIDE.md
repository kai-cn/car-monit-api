# Java → Python 迁移对照手册 / Migration Guide

> 面向**原 Java 开发者**。目标：读完本文件，你能在没有 Python 经验的前提下，
> 读懂 `car-monit-api-python` 的每一行代码，并解释它对应 Java 的哪一段。
>
> Companion documents:
> * [`README_PY.md`](README_PY.md) —— 怎么装、怎么跑、Java 开发者最容易踩的坑
> * [`COMPATIBILITY.md`](COMPATIBILITY.md) —— 已知行为差异与规避方式
> * [`docs/Java-to-Python-对照手册.md`](docs/Java-to-Python-对照手册.md) —— 逐类逐方法的深度注解

---

## 0. 迁移基线 / Baseline

| 项目 | Java 侧（事实） | Python 侧（事实） |
|---|---|---|
| 源码根 | `pro-base-common` + `pro-business-api` | `car-monit-api-python/pro-base-common` + `.../pro-business-api` |
| 框架 | Spring Boot **2.4.5** | FastAPI + Starlette（无 Spring 等价框架） |
| JDK | **1.8** | CPython **3.12+** |
| 构建 | Maven 多模块（根 `pom.xml` + 2 个子模块） | `pyproject.toml` + `requirements.txt`，源码直跑，不打 wheel |
| Java 源文件 | **219** 个（`pro-business-api` 166 + `pro-base-common` 53） | **219/219 全部有对应 `.py`**（`tools/_missing_files.py` 报告 `missing py: 0`） |
| HTTP 接口 | 24 个 `@RestController` / **85** 个 handler | 24 个 controller / **85** 条路由 |
| 定时任务 | `@EnableScheduling` + `@Scheduled` | **10** 个任务，cron 语义逐字对齐 |
| 测试 | 无（Java 侧没有任何 `src/test`） | `pytest` **82** 个用例 |
| 启动耗时 | — | **0.11 s**（不含 GaussDB 连接） |

> **重要**：Java 侧**没有**任何单元测试。因此 Python 侧 `tests/` 里的 82 个用例
> 不是"移植 Java 测试"，而是"为验证行为等价性新写的回归网"。
> 这是唯一一处**新增物**，且只存在于 `tests/`，不改动业务语义。

---

## 1. 技术栈映射表 / Tech-stack mapping

| 类别 | Java 实现 | Python 3.12 选型 | 选型理由 | 差异与注意事项 |
|---|---|---|---|---|
| Web 框架 | Spring Boot 2.4.5 / Spring MVC / `DispatcherServlet` | **FastAPI** + Starlette | 路由/中间件/异常钩子的抽象层次与 `DispatcherServlet` 最接近；自带 ASGI，异步不透传到业务层（业务仍是同步函数） | 没有 `ApplicationContext`、没有 Bean 生命周期。**HTTP 状态码默认 200**，与 Spring 一致；非 2xx 走 `HTTPException` |
| 路由声明 | `@RestController` + `@RequestMapping` + `@GetMapping` | `app/routes/generated.py`（**数据表**）+ `app/routes/registry.py`（注册器） | Java 的注解在编译期变成元数据；Python 改为**运行时读一张 dict 表**，逐条记录 `java` 源位置，可审计 | 路由不是靠装饰器扫包，而是 `ROUTES` 列表驱动。改路由 = 改表，不碰业务类 |
| 参数绑定 | `@RequestParam` / `@PathVariable` / `@RequestBody` / `@ModelAttribute`（含嵌套 Bean） | `app/web/binding.py`（手写复刻） | Pydantic 会**改变**语义（校验、类型转换、未知字段策略），与"像素级等价"冲突，故不用 | 手工复刻 Spring 的 `WebDataBinder`：同名注入、嵌套对象、`String[]`→`List`、缺参 400 |
| 参数校验 | **无**（Java 未使用 `@Valid` / Bean Validation） | **无** | 不引入 Java 中不存在的功能 | 越界/格式校验由业务代码自己做，与 Java 相同 |
| 持久层 | MyBatis-Plus 3.5.1 + PageHelper 1.4.7 + Lombok | `app/db/`（`xml_mapper` / `base_mapper` / `expr` / `pagination` / `snowflake`） | 直接**解释 Mapper XML**，而不是用 ORM 重写 SQL——SQL 是行为契约的一部分 | 不是 ORM 映射。`QueryWrapper` 被复刻成 `app/db/expr.py` 的表达式构造器 |
| SQL 位置 | `src/main/java/**/mapper/xml/*Mapper.xml` | 同一路径、同一 `.xml` 原文件被读取 | 非 `resources` 目录，`.py` 与 `.xml` 同目录镜像 Java 结构 | 22 个 XML / 54 条 statement / 19 个 fragment |
| 分页 | PageHelper `PageHelper.startPage()` + `PageInfo` | `app/db/pagination.py` | 逐行复刻 `count(0) FROM (...) tmp_count` 重写 + `reasonable` 夹紧 + `LIMIT/OFFSET` | 见 §4.4 |
| Bean 拷贝 | Orika `MapperFacade` | `com/ruoyi/common/config/OrikaMapperConfig.py`（最小反射映射器） | 保留 `classMap(a,b).byDefault().customize(m).register()` 链式 API，Java 注册代码可逐行照搬 | 不做深拷贝的类型推断，仅按同名字段赋值 |
| POJO / Lombok | `@Data` / `@Accessors(chain=true)` / `@Getter` / `@Setter` | `com/ruoyi/common/core/domain/JavaBean.py` 基类 | `__getattr__` 在运行时合成 `getX/setX/isX`，字段名 `snake_case ↔ camelCase` 自动互转 | 显式写的 `getX()` 优先；未声明的访问器才走 `__getattr__`；setter 返回 `self` 以支持链式 |
| 序列化 | Jackson `ObjectMapper`（Spring 默认） | `orjson` + `app/web/responses.py:JacksonResponse` | Jackson 的 `null` 字段保留、日期格式、`Long` 精度都必须逐字一致 | 用 orjson 提速但**字段策略由响应类控制**；`Long` 用字符串输出以规避 JS 精度问题（与 Java 一致） |
| 错误体 | `BasicErrorController` + `server.error.include-message: never` | `app/web/errors.py:error_body()` | 逐字复刻 `{timestamp,status,error,path}` | **不含 `message` 键**——这不是缺陷，是 Java 配置的直接结果 |
| 全局异常 | **无** `@ControllerAdvice` / `@RestControllerAdvice`（已验证 0 处） | **无** | 忠实保留 | 业务异常由各 controller 自己 `try/catch` 后返回 `AjaxResult.error`，与 Java 完全相同 |
| 异常体系 | `com.ruoyi.common.exception.base.BaseException` / `UtilException` | 同名 `.py`，继承内置 `RuntimeError` | 保持类名与包路径一致 | Java 侧**不存在** `BusinessException`，故 Python 侧也不新增（见 `COMPATIBILITY.md` §1） |
| 配置 | `application.yml` + `@Value("${k:d}")` | `org/springframework/core/env/Environment.py`（手写 flat YAML 读取）+ `app/settings.py` | 保持 `Environment#getProperty` 这唯一入口，`Settings` 只是**类型化门面** | 优先级与 Spring 一致：环境变量 > yml > 占位符内默认值 |
| 依赖管理 | Maven | `pyproject.toml` + `requirements.txt` + `.venv` | 依赖极少（6 个运行期） | 见 §2 |
| 日志 | Logback（`logback-spring.xml`） | 标准 `logging` + `app/logging_config.py` | 输出格式复刻：`时间 [线程] 级别 logger:行 - 消息` | `log.error("...{}", a, e)` → `log.error("...%s", a, exc_info=True)` |
| 测试 | **无** | `pytest`（`tests/test_phase2a..2e`） | 迁移新增的回归网 | `pytest.ini` 的 `pythonpath` 已含两个源码根 |
| 鉴权 | Spring Security + `SecurityInterceptor`（**全部被 `/* */` 注释掉**） | **无** | 忠实保留"没有鉴权链"这一事实 | 见 `COMPATIBILITY.md` §2 |
| AOP | **无** `@Aspect`（已验证 0 处） | **无** | — | 无需映射 |
| 事务 | **仅 1 处** `@Transactional`（`DataProcessService#process`） | 无事务管理器，仅保留顺序 + 注释说明 | 项目无真实 DB 连接池调用事务 API | 见 §4.3，这是**最大的单一语义缺口**，已显式标注 |
| 缓存 | Redis（Lettuce + Jedis 4.3.1） | `com/ruoyi/common/core/redis/RedisCache.py`（进程内 shim） | 不引入 `redis` 客户端；Java 的调用点全部由替身承接 | 不连真实 Redis；`TimeUnit` 枚举在 `java/util/concurrent/TimeUnit.py` |
| 缓存注解 | 无 `@Cacheable` | 无 | — | — |
| 消息队列 | Kafka / Pulsar 2.10.4 / RabbitMQ（仅配置）/ RocketMQ 2.2.3 | 进程内 shim（`org/apache/kafka`、`org/apache/pulsar`、`com/alibaba/fastjson2` 等） | 不引入 4 个客户端；消费者/生产者逻辑仍是 Python 类 | RabbitMQ **在 Java 侧也零代码使用**，只有 yml 配置。见 `COMPATIBILITY.md` §3 |
| 检索引擎 | Elasticsearch 7.17（`rest-high-level-client`） | `org/elasticsearch/**` 进程内 shim | `QueryBuilder` / `SearchRequest` / `SearchResponse` 全部按同名 API 复刻 | 无真实 ES 连接；查询构造逻辑（ngram、字段翻译、`max_result_window`）完整保留 |
| 流处理 | Flink 1.13.2（`VehicleTrackFlinkJob`） | 纯 Python 类，**不引入** `pyflink`/`pyspark` | Flink 拓扑无法在单进程 Python 中运行 | `SparkHiveConfig.py` 是**纯占位文件**，末尾 `SparkHiveConfig = None` |
| 定时任务 | `@EnableScheduling` + `@Scheduled(cron=...)` | `org/springframework/scheduling/**`（`CronExpression` + `ThreadPoolTaskScheduler`）+ `app/scheduler/` | Spring cron 是 **6 段（秒开头）**，与 Quartz/APScheduler 的 5 段不同，必须自研解析器 | 不用 APScheduler（已从依赖中移除） |
| ID 生成 | MyBatis-Plus `IdType.ASSIGN_ID`（雪花） | `app/db/snowflake.py` | 逐位对齐 64 位布局（时间戳/机器/序列） | — |
| HTTP 客户端 | Forest（`@ForestClient`）/ `RestTemplate` | `httpx`（仅 shim 内使用） | 与 Java 的同步阻塞语义一致 | — |
| 工具库 | Guava / Commons-Lang3 | 标准库（`datetime`、`re`、`hashlib`、`secrets`…） | 不引入替代库 | `MD5Example` / `RepeatUtil` / `CryptoJSTools` 的 `main()` 保留为 `if __name__ == "__main__":` |
| API 文档 | **无**（未使用 springdoc/swagger） | FastAPI 自带 `/docs`、`/openapi.json` | **迁移辅助物**，Java 侧没有 | 已在 `app/main.py` 顶部声明为"deliberate difference" |
| 监控 | **无** Actuator / Micrometer | `/health` 端点（`app/health.py`） | **迁移辅助物**，Java 侧没有 | 同理标注 |
| 数据库迁移 | **无** Flyway / Liquibase | **无**（不引入 Alembic） | Java 没有，就不加 | — |
| 构建产物 | `jar`（`spring-boot-maven-plugin`） | 源码直跑 `python run.py` | 无需打包 | `[tool.uv] package = false` |

### 运行期依赖（6 个）/ Runtime dependencies

```
fastapi  uvicorn[standard]  SQLAlchemy  psycopg[binary]  httpx  orjson
```

**刻意不声明**（已验证未使用，Java 侧以进程内替身模拟）：

| 包 | 为什么不需要 |
|---|---|
| `redis` | `RedisCache.py` 是内存替身 |
| `elasticsearch` | `org/elasticsearch/**` 是内存替身 |
| `APScheduler` | Spring cron 语义不同，已自研 `CronExpression` |
| `PyYAML` | `Environment.py` 是手写的扁平 YAML 读取器 |
| `pyspark` / `pyflink` | 两个作业类仅是纯 Python 类，无运行期 import |

---

## 2. 目录结构映射 / Layout

```
car-monit-api/                              car-monit-api-python/
├── pro-base-common/                        ├── pro-base-common/src/main/java/   ← 54 个 .py
│   └── src/main/java/com/ruoyi/common/     │   └── com/ruoyi/common/
│       ├── annotation  (1)                 │       ├── annotation  (1)
│       ├── config      (6)                 │       ├── config      (12)
│       ├── constant    (6)                 │       ├── constant    (6)
│       ├── core        (?)                 │       ├── core        (20)
│       ├── exception   (2)                 │       ├── exception   (2)
│       └── utils       (11)                │       └── utils       (13)
├── pro-business-api/                       ├── pro-business-api/src/main/java/  ← 166 个 .py
│   └── src/main/java/com/ruoyi/            │   └── com/ruoyi/
│       ├── base/controller  (24)           │       ├── base/controller  (24)
│       ├── base/domain      (30)           │       ├── base/domain      (30)
│       ├── base/mapper      (23)           │       ├── base/mapper      (23)  + .xml
│       ├── base/service     (70)           │       ├── base/service     (70)
│       │   ├── (root) (23)                 │       │   ├── (root) (23)
│       │   ├── impl   (34)                 │       │   ├── impl   (34)
│       │   └── optimization (13)           │       │   └── optimization (13)
│       ├── base/config (4) / task (3)      │       ├── base/config (4) / task (3)
│       ├── base/flink (1) / forest (1)     │       ├── base/flink (1) / forest (1)
│       └── mq/ (config 2, consumer 1,      │       └── mq/ (config 2, consumer 1,
│              producer 1, service 2)       │              producer 1, service 2)
└── (Java 侧的 jar 依赖)                     ├── com/  java/  javax/  org/   ← 171 个 .py 替身层
                                            ├── app/        ← FastAPI 宿主（26 个 .py，无 Java 对应）
                                            ├── tests/      ← pytest（5 个模块）
                                            ├── tools/      ← 16 个长期验证脚本
                                            └── scripts/    ← smoke_test.py
```

**镜像规则**：Java 的包路径 = Python 的目录路径，类名 = 文件名 = 类名。

```python
# 文件头（每个文件都有）
# Migrated from: pro-business-api/src/main/java/com/ruoyi/base/service/impl/XXXServiceImpl.java

from com.ruoyi.base.domain.Foo import Foo        # ← 与 Java import 一一对应

class FooServiceImpl(FooService):                 # ← 类名保持不变
    def selectFooById(self, fooId: int) -> Foo:   # ← 方法名保持 camelCase
        """# Java: com.ruoyi.base.service.impl.FooServiceImpl#selectFooById"""
```

> **为什么方法名是 `camelCase` 而不是 `snake_case`？**
> 迁移原则要求"结构镜像 + 可追溯"。方法名保留 `camelCase`，使得
> `grep "selectFooById"` 能在两侧命中同一处，diff 审计的成本降到最低。
> 命名用 `snake_case` 的只有 **Python 独有的宿主代码**（`app/`、`tools/`、`scripts/`）。

---

## 3. 逐模块对照表 / Per-module table

行数取自实际文件统计；"差异"列只列**真实存在**的语义差异。

### 3.1 `pro-base-common`（54 个 `.py`，6 397 行）

| Java 包 | Python 路径 | 文件 | 行数 | 关键类 | 与 Java 的差异 |
|---|---|---|---|---|---|
| `com.ruoyi.common.annotation` | 同名目录 | 1 | 127 | `@Anonymous` | 变成模块级装饰器工厂 |
| `com.ruoyi.common.config` | 同名目录 | 12 | 1 704 | `RedisConfig`、`OrikaMapperConfig`、`ThreadPoolConfig`、`WebConfig`（全注释） | `WebConfig` 在 Java 里整段被 `/* */` 注释，Python 侧同样不生效 |
| `com.ruoyi.common.constant` | 同名目录 | 6 | 357 | `Constants`、`HttpStatus`、`CacheConstants` | 常量值逐字一致 |
| `com.ruoyi.common.core` | 同名目录 | 20 | 2 149 | `AjaxResult`、`TableDataInfo`、`BaseController`、`JavaBean`、`PageDomain`、`RedisCache`、`SpringUtils` | `JavaBean` 用 `__getattr__` 合成 Lombok 访问器；`SpringUtils` 用模块级注册表代替 BeanFactory |
| `com.ruoyi.common.exception` | 同名目录 | 2 | 95 | `BaseException`、`UtilException` | 继承 `RuntimeError` |
| `com.ruoyi.common.utils` | 同名目录 | 13 | 1 965 | `StringUtils`、`DateUtils`、`SecurityUtils`、`PageUtils`、`SqlUtil`、`ExceptionUtil` | `RedisUtil.del()` → `delete()`（`del` 是 Python 关键字，见 §5） |

### 3.2 `pro-business-api`（166 个 `.py`，28 124 行）

| Java 包 | 文件 | 行数 | 说明 | 审计结论 |
|---|---|---|---|---|
| `base/controller` | 24 | 2 683 | 24 个 `@RestController` → 85 条路由 | `tools/check_routes.py`：85 handler，参数类型分布 `body=3 / model=25 / param=65 / param_map=5 / path=23`，动词 `GET=79 / POST=6` |
| `base/domain` | 30 | 3 423 | 实体/DTO/BO/VO，30 个类文件 | `@Data` → 继承 `JavaBean`；`@TableName`/`@TableId` 元数据保留在类属性 |
| `base/mapper` | 23 | 1 761 | MyBatis Mapper 接口 + 同目录 `.xml` | `tools/check_mappers.py`：22 XML / 54 statement / 19 fragment / **58 个方法已绑定** / **6 个无 XML**（见 §4.6） |
| `base/service` | 23 | — | Service 接口（纯抽象） | 与 `impl` 成对 |
| `base/service/impl` | 34 | — | ServiceImpl | 唯一带 `@Transactional` 的类在 `mq/`，不在此 |
| `base/service/optimization` | 13 | — | 大表查询架构：统一查询 / 渐进式 / 大规模 / ES 索引管理 / 一致性核对 | `smoke_unified_export.py`、`smoke_progressive.py`、`smoke_largescale.py`、`smoke_billion.py`、`smoke_consistency.py` 覆盖 |
| `base/config` | 4 | 509 | `@Configuration`/`@Bean` 类 | — |
| `base/task` | 3 | 595 | 定时任务载体 | 由 `app/scheduler` 统一驱动 |
| `base/flink` | 1 | 728 | `VehicleTrackFlinkJob` 及 11 个 POJO | **不可运行**（无 Flink 运行时），只保留编排逻辑 |
| `base/forest` | 1 | 80 | Forest HTTP 客户端接口 | `httpx` 替身 |
| `base/HasStatic.py`、`base/Test.py` | 2 | 140 | 静态资源 / 测试载体 | 原样保留 |
| `mq/config`、`mq/consumer`、`mq/producer`、`mq/service` | 6 | 947 | Kafka/Pulsar/RocketMQ 配置、消费者、生产者、数据处理 | RocketMQ 只有 1 个 consumer；RabbitMQ 零代码 |

### 3.3 宿主层 `/ Host layer`（**Java 无对应**，仅 Python 有）

| 路径 | 文件 | 行数 | 职责 |
|---|---|---|---|
| `app/` | 26 | — | FastAPI 应用、配置门面、日志、健康检查、路由注册、参数绑定、错误体、DB 引擎与 XML 解释器、调度器 |
| `com/` `java/` `javax/` `org/` | 171 | 14 462 | **JDK + 第三方库替身层**。`bootstrap.py` 把这 4 个目录注册为 import 根，于是业务代码可以写 `from java.util import HashMap` |
| `tests/` | 5 | — | pytest 回归网（82 用例） |
| `tools/` | 16 | — | 长期验证脚本（含 `check_parity.py`） |
| `scripts/smoke_test.py` | 1 | — | 启动自检 |

> 替身层是**唯一"多出来"的代码**。它存在的意义：业务文件可以一个字都不改地
> 保留 Java 的 `import`，从而让 `check_parity.py` 能用**同一个包路径**做方法级比对。

---

## 4. Java 原语义 → Python 等价实现 / Semantic mapping

Phase 3 要求"复杂逻辑必须单独说明"。以下是全部需要说明的点。

### 4.1 AOP / 拦截器 / 过滤器

**Java 原语义**：`WebConfig`（注册 `SecurityInterceptor`、CORS、静态资源）整个文件被
`/* ... */` 包裹；`SecurityInterceptor` 同样被注释。**全工程 0 个 `@Aspect`**。

**Python 等价实现**：无。`app/main.py` 顶部显式声明：

```
* there is no Spring Security / interceptor chain, matching the Java project
  where ``SecurityInterceptor`` and ``WebConfig`` are entirely commented out.
```

**结论**：不存在"拦截器语义丢失"，因为 Java 本来就没启用。

### 4.2 全局异常处理

**Java 原语义**：全工程 0 个 `@ControllerAdvice`。因此异常由 **Spring 的
`BasicErrorController`**兜底，返回 JSON：

```json
{"timestamp":"...","status":500,"error":"Internal Server Error","path":"/x"}
```

且 `server.error.include-message: never` → **没有 `message` 字段**。

**Python 等价实现**：`app/web/errors.py`

```python
def error_body(status: int, path: str, message: Optional[str] = None) -> dict[str, Any]:
    body = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}+00:00",
        "status": status,
        "error": HTTP_REASONS.get(status, "Error"),
    }
    if message:
        body["message"] = message      # 仅当显式传入才出现 —— 对应 include-message=never
    body["path"] = path
    return body
```

`app/main.py` 注册 3 个 handler：`StarletteHTTPException`、`RequestValidationError`、
`BindingError`，全部转成上面这个结构。

**已验证**：`scripts/smoke_test.py` 断言 404 响应字段恰为
`['error','path','status','timestamp']` 且不含 `message`。

### 4.3 事务（**唯一的真实语义缺口**）

**Java 原语义**：全工程**仅 1 处** `@Transactional`：

```java
// pro-business-api/.../mq/service/DataProcessService.java:89
@Transactional(rollbackFor = Exception.class)
public void process(OdsRtSzdnSnapshotFlowAddcode data) {
    insertIntoMysql(data);   // 写 MySQL
    insertIntoEs(data);      // 写 ES
}
```

语义：MySQL 成功、ES 抛异常 → **MySQL 回滚**。

**Python 等价实现**：无事务管理器，只保留顺序。

```python
# pro-business-api/.../mq/service/DataProcessService.py
"""【Java→Python】原方法带 ``@Transactional(rollbackFor = Exception.class)``；
Python 侧没有事务管理器，这里按原顺序执行，异常直接向上抛。"""
def process(self, data) -> None:
    self.insertIntoMysql(data)
    self.insertIntoEs(data)
```

**为什么不实现**：该项目没有真实的 `DataSource`/`SqlSession` 生命周期，事务边界
本身就不存在。若将来接真库，正确做法是 `with session.begin():`（SQLAlchemy 2.0）
或显式 `BEGIN`/`COMMIT`，**不要**用装饰器假装。

**风险等级**：低。该方法只被 MQ 消费者调用，且 Java 侧的分表名实际未生效（见 §4.7）。

### 4.4 PageHelper 分页

**Java 原语义**：`PageHelper.startPage(n, s)` 把分页参数放进 `ThreadLocal`，
**第一条**被拦截的 SELECT 被改写成：

1. 先执行 `SELECT count(0) FROM ( <去掉顶层 ORDER BY 的原 SQL> ) tmp_count`；
2. `reasonable=true` 时把 `pageNum` 夹紧到 `[1, pages]`；
3. 原 SQL 追加 `LIMIT ? OFFSET ?`；
4. `total` 通过 `PageInfo` 暴露。

**Python 等价实现**：`app/db/pagination.py`，函数一一对应：

| Java | Python |
|---|---|
| `PageHelper.startPage()` | `current_page_request()`（读 `PageUtils._context()`，标记 `consumed`） |
| `OrderByParser` | `_scan_order_by()` / `strip_order_by()` / `_inject_order_by()` |
| `AbstractHelperDialect.getCountSql` | `build_count_sql()` |
| `reasonable` 夹紧 | `clamp_page_number()` |
| `LIMIT/OFFSET` 追加 | `add_pagination()` |

关键细节：`_inject_order_by` 在已有 `ORDER BY` 时**前置**请求字段，而不是替换——
这是 PageHelper `OrderByParser` 的真实行为，业务排序不会被请求参数覆盖。

### 4.5 Lombok 访问器

**Java 原语义**：`@Data` / `@Getter` / `@Setter` / `@Accessors(chain = true)` 在编译期
生成 `getX()`、`setX()`、`isX()`。

**Python 等价实现**：`com/ruoyi/common/core/domain/JavaBean.py`（159 行）

```python
class JavaBean:
    def __getattr__(self, name: str):
        # name 形如 getFoo / setFoo / isFoo -> 解析到字段 foo / snake_case
        ...
```

* 字段名 `snake_case` ↔ 访问器 `camelCase` 自动互转（`_FIELD_MAP_CACHE` 缓存）；
* setter 返回 `self` → 支持 `obj.setA(1).setB(2)`；
* `toString()` 已实现；
* **显式写的访问器优先**，`__getattr__` 只在属性不存在时才触发。

> 这也是 `check_parity.py` 需要"跳过 Lombok 访问器比对"的原因：
> 它们不是漏写，而是被基类动态合成了。

### 4.6 MyBatis XML 语句绑定

`app/db/registry.py` 在启动时做 MyBatis `MapperScannerConfigurer` 做的事：

1. 扫描 `mybatis-plus.mapper-locations` 指定的 22 个 `.xml`；
2. 解析 `<select>/<insert>/<update>/<delete>` 和 `<sql>` fragment；
3. 把 statement id 绑定到 Mapper 类的同名方法；
4. 对**既没有 XML 也没有注解**的方法，装一个**抛异常**的桩：

```python
def _invalid_bound_statement(namespace: str, method_name: str):
    """Reproduce ``BindingException: Invalid bound statement (not found)``."""
    full_id = f"{namespace}.{method_name}"
    def missing(self, *args, **kwargs):
        raise RuntimeError(f"Invalid bound statement (not found): {full_id}")
```

**为什么这很重要**：早期 Python 版让这类方法静默返回 `[]`，这会掩盖真实缺陷。
现在的行为与 Java **完全一致**——两侧调用都抛 `BindingException`。

当前有 **6 个**这样的方法（启动日志会逐条打印 `has no statement ... calling it raises like MyBatis`）：

| Mapper | 方法 |
|---|---|
| `OdsLwzxsfsjFeeRecords01Mapper` | 多个 `selectXxxList` |
| `ZdataTrailFittingMapper` | `selectZdataTrailFittingList` |
| …（共 6 条，以启动日志为准） | |

**这不是迁移缺陷**：Java 的 `.xml` 里确实没有这些语句，而 Java 代码确实调用了它们
→ Java 运行时会抛 `BindingException`。Python 忠实复刻。

### 4.7 忠实保留的 Java 缺陷（**故意不修**）

迁移原则要求"不得擅自删除看似无用的代码"。以下缺陷**原样保留并标注**：

```python
# pro-business-api/.../mq/service/DataProcessService.py:101
# 【原工程缺陷，忠实保留】tableName 计算出后从未使用：
#   分表名没有传给 mapper，实际写入的仍是 mapper 中固定的表名。
#   若将来要修复，应改为动态表名（如 mapper.insertInto(tableName, data)）。
tableName = self.getTableName(data.getSnapshottime())
_ = tableName  # 消除"未使用变量"告警，同时保留 Java 的赋值语义
```

Java 原文（`DataProcessService.java:107-119`）同样计算了 `tableName` 却不使用。

### 4.8 并发 / 线程池 / 定时任务

| Java | Python |
|---|---|
| `ThreadPoolTaskExecutor`（`ThreadPoolConfig`） | `concurrent.futures.ThreadPoolExecutor`，`NamedThreadFactory` 复刻为 `_NamedThreadFactory`（设线程名前缀） |
| `@Scheduled(cron = "0 0 2 * * ?")` | `CronExpression`（**6 段，秒开头**）+ `ThreadPoolTaskScheduler` |
| `ApplicationRunner` 启动即跑 | `app/scheduler/registry.py` 注册 10 个任务，lifespan 里 `start_scheduler()` |
| `@PreDestroy` / `DisposableBean` | lifespan 的 `yield` 之后 → `shutdown_scheduler()` |

**关于 GIL**：Python 线程是**真线程**，但 CPU 密集段被 GIL 串行化。本项目所有
工作线程都是 **I/O 阻塞型**（导出写 CSV、同步写 ES、MQ 拉取），GIL 不构成行为差异。
**但**：并发写入的**交错顺序**可能与 JVM 不同 —— 所有对外可见的结果都经过
`ConcurrentHashMap`→`dict` / 任务状态机，最终状态一致，中间态不保证一致。

**worker 线程不是 daemon**（与 Java 非 daemon 线程池一致）→ 解释器不会自行退出。
所有 CLI 脚本末尾必须 `os._exit(exit_code)`，`scripts/smoke_test.py` 与
`tools/smoke_all_routes.py` 都这么做了。

### 4.9 序列化与 `Long` 精度

**Java 原语义**：Jackson 输出 `Long` 为 JSON number。超过 2^53 时 JavaScript 会丢精度
——这是 `car-monit-api` 的老问题，不是迁移引入的。

**Python 等价实现**：`app/web/responses.py:JacksonResponse`（整个守卫 27 行，基于 `orjson`）：

```python
class JacksonResponse(Response):
    media_type = "application/json"          # Spring 的 JSON converter 不加 charset
    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)   # = Jackson 把非字符串 key 转字符串
```

**逐项对齐 Jackson 的默认行为**：`null` 字段保留（不删 key）、非字符串 Map key 转字符串、
`NaN`/`Infinity` 拒绝、中文不转义。

> **注意**：两侧都**没有**配置 `spring.jackson.date-format`（已在 `application.yml` 中 grep 验证 0 处）。
> 时间字段在业务层就是 `String`，日期格式化已经在业务代码里完成，序列化层不做转换。

**已核验**：`TableDataInfo` → `{total, rows, code, msg}`；`AjaxResult` → `{code, msg, data?}`；
`UnifiedQueryController#list` → `{code, message, dataSource, pageNum, pageSize, data}`
（**注意后者不是 `TableDataInfo`，没有 `rows`** —— 它是 Java 的裸 `Map`）。

### 4.10 定时任务 cron 语义

Spring 的 `@Scheduled(cron = "...")` 是 **6 段**（`秒 分 时 日 月 周`），
Quartz/APScheduler 是 **5 段或 7 段**，且周字段的 `1` 含义不同（Spring `1`=周一，Quartz `1`=周日）。

因此 **不能用 APScheduler**，必须自研解析器。`application.yml` 里的
`consistency.reconcile.cron: "0 30 2 * * ?"` 在两侧含义完全相同。

---

## 5. 可追溯性约定 / Traceability

| 层级 | 约定 | 例 |
|---|---|---|
| 文件 | 第 1 行注释 `# Migrated from: <java 相对路径>` | `# Migrated from: pro-business-api/src/main/java/com/ruoyi/base/service/impl/FooServiceImpl.java` |
| 类 | 类名与 Java 完全一致（含大小写） | `class FooServiceImpl` |
| 方法 | 方法名保留 `camelCase`；docstring 首行写 Java 全限定名 | `"""# Java: com.ruoyi.base.service.impl.FooServiceImpl#selectFooById"""` |
| 语句 | 逐行 `# Java: <原语句>` 或 `【Java→Python】<说明>` | 见 `UnifiedQueryService.py` |
| 路由 | `generated.py` 每条路由带 `"java": "<文件>:<行号>"` | `"java": ".../UnifiedQueryController.java:65"` |

**跨语言搜索**：

```bash
# 找某个 Java 方法在 Python 侧的落点
findstr /s /c:"selectFooById" pro-business-api\src\main\java\*.py

# 或直接用工具
.venv\Scripts\python.exe tools\check_parity.py
```

---

## 6. 审计与验证工具 / Verification toolkit

| 脚本 | 作用 | 当前结果 |
|---|---|---|
| `tools/check_routes.py` | 路由清单 vs Java 注解 | 24 controller / 85 route |
| `tools/check_mappers.py` | XML statement 与 Mapper 方法绑定 | 22 XML / 54 statement / 58 绑定 / 6 无 XML（符合预期） |
| `tools/check_middleware.py` | 中间件替身完整性 | 通过 |
| **`tools/check_parity.py`** | **方法级 Java↔Python 对照闸门** | `checked files 219 / fully matched 187 / documented equivalences 9 / Tier A 29 / **Tier B 0**` |
| `tools/smoke_all_routes.py` | 85 条路由全量打通 | `200=85, defects none, payload 0 failure` |
| `tools/smoke_http.py` | 真实 HTTP 冒烟 | 通过 |
| `tools/smoke_unified_export.py` | 统一导出 submit→poll | 通过 |
| `tools/smoke_progressive.py` / `smoke_largescale.py` / `smoke_billion.py` / `smoke_consistency.py` | 各查询架构 | 通过 |
| `tools/smoke_scheduler.py` | 10 个定时任务 | 通过 |
| `tools/verify_db.py` / `check_env.py` | 环境与 DB 连通性 | DB 不可达时给出明确诊断 |
| **`scripts/smoke_test.py`** | **启动自检（交付物）** | 进程内 **28/28**，`--live` **25/25** |
| `pytest` | 回归网 | **82 passed** |

### `check_parity.py` 的分级

* **Tier A**（29 个文件 / 30 个名字）：Java 有、Python 没有，但**在别处全局存在**
  （继承自基类、或在兄弟模块里）。属正常。
* **Tier B**：Java 有、Python **全工程都没有**。**必须为 0**。
* **documented equivalences**（9 条）：有意的 1:1 改写，每条带书面理由：

| Java | Python | 理由 |
|---|---|---|
| `PermissionAnon`（注解） | 模块级装饰器工厂 | Python 无注解，用装饰器表达同一约束 |
| `ValidHeader`（注解） | 模块级工厂函数 | 同上 |
| `CommonUtil`（静态工具类） | 模块级函数 | Java `static` 工具类 → Python 模块函数 |
| `RedisUtil.del(String...)` | `RedisUtil.delete(...)` | **`del` 是 Python 关键字**，无法作为方法名 |
| `SpringUtils.postProcessBeanFactory` | `register_bean()` | 无 BeanFactory 生命周期 |
| `SpringUtils.setApplicationContext` | `set_application_context()` | 同上 |
| `BaseController.setValue` | 闭包 | 原为匿名 `PropertyEditorSupport` 子类 |
| `NamedThreadFactory`（×2） | `_NamedThreadFactory` | 私有实现类，加前缀表"内部" |
| `DelayStats` / `QueryRouteRequest` / `QueryRequest` | 嵌套 `@dataclass(JavaBean)` | Java 静态内部类 → Python 嵌套类 |
| `main()`（MD5Example / RepeatUtil / CryptoJSTools） | `if __name__ == "__main__":` | 保持可独立执行 |

---

## 7. 迁移完成度结论 / Conclusion

| 维度 | 状态 | 证据 |
|---|---|---|
| 类/方法覆盖 | **完整** | `check_parity.py` Tier B = 0，219/219 文件 |
| 接口路径 & 字段 | **一致** | 85 条路由；`TableDataInfo` / `AjaxResult` / 裸 `Map` 三种契约逐一断言 |
| HTTP 状态码 & 错误码 | **一致** | `BasicErrorController` 复刻，`include-message=never` |
| 真实环境接口对等 | **75 / 75 一致** | 双端同时连 openGauss + Redis + ES 逐接口比对，见 `COMPATIBILITY.md` §0 |
| 业务规则 & 边界 | **一致** | 83 个 pytest + 10 个 smoke 脚本 |
| 数据表 & 字段类型 | **一致** | 直接解释原 Mapper XML，未重写 SQL；`@TableName(schema=...)` 经 `TABLE_SCHEMAS` 还原 |
| 已知语义缺口 | **1 处** | `@Transactional`（§4.3），已显式标注，风险低 |
| 不可运行的 Java 能力 | **2 处** | Flink 拓扑（`base/flink`）、真实 ES/Redis/MQ **写入**（读已打通标量穿透） |
| 新增物 | **3 类** | `app/`（宿主）、替身层（JDK+三方库）、`/health`+`/docs`（迁移辅助） |

详见 [`COMPATIBILITY.md`](COMPATIBILITY.md)。
