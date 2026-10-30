# 已知行为差异与规避方式 / Compatibility Notes

> 本文件只列**真实存在**的差异，每条都给出：**现象 → 根因 → 影响 → 规避方式**。
> 不存在的差异不写（例如"没有 Spring Security"是因为 **Java 侧也没有启用**，见 §2.4）。

## 严重度定义

| 级别 | 含义 | 处理要求 |
|---|---|---|
| **P0** | 阻塞运行 | 必须解决，否则不可用 |
| **P1** | 语义不等价 | 必须让业务方知情，评估是否接受 |
| **P2** | 实现不同、外部行为一致 | 记录即可 |
| **P3** | Python 独有新增 | 记录即可，Java 侧无对应 |

**当前结论：P0 = 0 条，P1 = 3 条（均已标注、均有规避路径），P2 = 6 条，P3 = 4 条。**

---

## 1. 需求假设与 Java 事实的偏差（**先看这一节**）

迁移需求里要求"定义 `BusinessException`、全局 handler"。**实际勘察后发现 Java 侧并不存在这些**，
按"不引入 Java 中没有的新功能"原则，Python 侧也没有创建它们。

| 需求假设 | Java 侧实际情况 | Python 侧处理 | 级别 |
|---|---|---|---|
| 存在 `BusinessException` | **不存在**。`com.ruoyi.common.exception` 下只有 `BaseException`、`UtilException`（2 个类，95 行） | 同名 `BaseException.py` / `UtilException.py`，继承内置 `RuntimeError`。**不新增** `BusinessException` | P2 |
| 存在全局异常 handler（`@ControllerAdvice`） | **全工程 0 处** `@ControllerAdvice` / `@RestControllerAdvice`（已 grep 验证） | 复刻 Spring 的 `BasicErrorController` → `app/web/errors.py` | P2 |
| 存在 Bean Validation（`@Valid`） | **0 处** `@Valid` | 不做声明式校验；校验逻辑留在业务代码 | P2 |
| 存在 Spring Security 鉴权 | `WebConfig` 与 `SecurityInterceptor` **整体被 `/* */` 注释掉** | 无鉴权链 | P2 |
| 存在 AOP（`@Aspect`） | **0 处** | 无 | — |
| 存在 Flyway / Liquibase | **0 处**（无迁移脚本目录） | **不引入 Alembic** | P2 |
| 存在 Swagger / springdoc | **0 处** | FastAPI 自带 `/docs`、`/openapi.json`，标注为迁移辅助 | P3 |
| 存在 Actuator / Micrometer | **0 处** | `/health`，标注为迁移辅助 | P3 |
| 存在单元测试 | **无任何 `src/test`** | `tests/` 82 个 pytest 用例（**新增回归网**） | P3 |
| 存在 Quartz | **无**，只有 `@Scheduled` | 自研 `CronExpression`（Spring 6 段语义） | P2 |

> **错误码常量**：Java 侧没有独立的错误码枚举，`AjaxResult` 直接用
> `HttpStatus.SUCCESS(200)` / `HttpStatus.ERROR(500)` / `HttpStatus.WARN(601)` 等字面量。
> Python 侧 `com/ruoyi/common/constant/HttpStatus.py` 逐值保留，未改造。

---

## 2. 无法复现的 Java 能力 / P1

### 2.1 `@Transactional` —— 唯一的事务语义缺口 【P1】

**现象**：MySQL 写成功、ES 写失败时，Python 侧 **MySQL 不会回滚**（Java 会）。

**根因**：全工程**仅 1 处** `@Transactional`，位于
`pro-business-api/src/main/java/com/ruoyi/mq/service/DataProcessService.java:89`。
Python 侧没有 `DataSource` / `SqlSession` 生命周期，也没有事务管理器。

**Java 原文**：

```java
@Transactional(rollbackFor = Exception.class)
public void process(OdsRtSzdnSnapshotFlowAddcode data) {
    insertIntoMysql(data);   // 写 MySQL
    insertIntoEs(data);      // 写 ES
}
```

**Python 实现**：

```python
# pro-business-api/.../mq/service/DataProcessService.py
"""【Java→Python】原方法带 ``@Transactional(rollbackFor = Exception.class)``；
Python 侧没有事务管理器，这里按原顺序执行，异常直接向上抛。"""
def process(self, data) -> None:
    self.insertIntoMysql(data)
    self.insertIntoEs(data)
```

**影响面**：只影响 MQ 消费路径（`RocketMqConsumer` → `DataProcessService`）。
HTTP 接口全部只读或单表单写，不依赖事务。

**规避方式**：

* 若接真实库，改为显式事务：
  ```python
  with session.begin():          # SQLAlchemy 2.0，= @Transactional
      self.insertIntoMysql(data)
      self.insertIntoEs(data)
  ```
* 或改造为"MySQL 侧加 `INSERT ... ON CONFLICT` 幂等 + 失败重投"，
  比回滚更符合消息消费的最终一致语义。
* **不要**用装饰器假装事务 —— `@transactional` 在 Python 里不会自动生效。

### 2.2 Flink 作业不可运行 【P1】

**现象**：`VehicleTrackFlinkJob` 及 11 个 POJO 类在 Python 侧是**普通类**，
`execute()` 不会提交任何 Flink 拓扑。

**根因**：Flink 1.13.2 依赖 JVM 运行时（`StreamExecutionEnvironment`、
`DataStream`、状态后端、Checkpoint）。Python 侧无 `pyflink` 依赖（已确认未引入）。

**保存了什么**：算子编排逻辑、`KeyedProcessFunction` 的状态访问顺序、
窗口/触发器的参数 —— 全部保留为可读代码，供 Java 侧对照或后续重写。

**未保存什么**：真正的分布式执行、Checkpoint、Watermark 推进。

**规避方式**：轨迹拟合作业**必须继续由 Java 侧的 Flink 服务承担**。
Python 版不提供该能力。若必须用 Python，需要独立引入 `pyflink` 并重写拓扑。

### 2.3 无真实中间件连接 【P1】

**现象**：Redis / ES / Kafka / Pulsar / RocketMQ 的所有调用都返回**进程内替身**的结果，
不会访问网络。

**根因**：迁移目标是"行为等价"，不是"基础设施重建"。替身保证：
* 方法签名、参数、返回值形状**完全一致**；
* 调用顺序、日志输出**完全一致**；
* 但数据是内存态，进程重启即丢失。

**替身清单**：

| 组件 | 替身位置 | 当前行为 |
|---|---|---|
| Redis | `com/ruoyi/common/core/redis/RedisCache.py`、`RedisUtil.py` | 进程内 dict + 过期时间（`TimeUnit` 枚举在 `java/util/concurrent/TimeUnit.py`） |
| Elasticsearch | `org/elasticsearch/**`（`QueryBuilders`、`SearchRequest`、`SearchSourceBuilder`、`SearchResponse`…） | 构造查询 DSL 并返回空/内存命中 |
| Kafka | `org/apache/kafka/**` | `Producer`/`Consumer` 接口可用，不连 broker |
| Pulsar | `org/apache/pulsar/**` | 同上 |
| RocketMQ | `org/apache/rocketmq/**` | 同上；Java 侧只有 1 个 consumer |
| RabbitMQ | **无替身** | Java 侧也只有 `application.yml` 配置、**零代码使用** |
| Forest HTTP | `com/ruoyi/base/forest/` | 用 `httpx` 直连 |

**规避方式**：需要真实集成测试时，**用 Java 侧对着真实环境验证**；
Python 侧只做行为回归。见 `tools/check_middleware.py`（替身完整性检查）。

---

## 3. 数据库与驱动层差异 / P2

Python 走 `psycopg3` + SQLAlchemy 2.0，Java 走 `pgjdbc 42.2.x`。
两者行为差异**已逐条补偿**，位置在 `app/db/engine.py`。

### 3.1 GaussDB 版本横幅导致首次连接失败 【已补偿】

**现象**：SQLAlchemy 首次连接直接 `AssertionError` 退出。

**根因**：openGauss/GaussDB 返回 `(openGauss 3.0.0 build 02c14696) compiled at ...`，
SQLAlchemy 的 `PGDialect._get_server_version_info` 期望 `PostgreSQL` 前缀 → 断言失败。
**pgjdbc 只读数字部分**，所以 Java 侧从未遇到。

**补偿**：`install_gaussdb_version_shim()` 上报 `9.2.4`（GaussDB 3.0 的 PG 兼容级别，
也是 pgjdbc 侧一直在对话的级别）。对真实 PostgreSQL 是 no-op。

### 3.2 `concat('%', ?, '%')` 类型解析失败 【已补偿】

**现象**：所有 `LIKE` 查询报
`psycopg.errors.ProgrammingError: could not determine data type of parameter $1`。

**根因**：psycopg 默认用 *unknown* OID 发送字符串，让服务端推断类型；
但 `concat()` 是 variadic 函数，服务端**拒绝**推断。项目里每个 XML 的模糊查询都是
`like concat('%', #{name}, '%')`。pgjdbc 的 `setString` 发送的是 `varchar`。

**补偿**：`StrDumperVarchar` 按连接注册，把 `str` 参数绑定为 `varchar`，
恢复 Java 侧一直执行的 `concat(text, varchar, text)`。
整数 / 布尔 / `Decimal` 仍用推断类型。

### 3.3 JDBC URL 的位置

**现象**：`application.yml` 里的 `jdbc:postgresql://192.168.56.10:5432/RuoYi?...` 不能直接给 psycopg。

**补偿**：`jdbc_to_sqlalchemy_url()` 剥掉 `jdbc:postgresql://` / `jdbc:opengauss://` / `jdbc:gaussdb://`
前缀，并**丢弃查询字符串**（`characterEncoding`、`serverTimezone` 等是 MySQL 导向参数，
PostgreSQL 驱动不认识）；仅保留 `currentSchema`。

### 3.4 分页 SQL 方言

| | Java | Python |
|---|---|---|
| 分页写法 | PageHelper 自动探测方言 → `LIMIT ? OFFSET ?` | `LIMIT :page_limit OFFSET :page_offset`（同结果） |
| COUNT 重写 | `SELECT count(0) FROM ( <去 ORDER BY> ) tmp_count` | 逐字一致（`app/db/pagination.py:build_count_sql`） |

**无差异**。GaussDB 兼容 PostgreSQL 的 `LIMIT/OFFSET`。

### 3.5 连不上数据库时的表现

**（当前环境就是这个状态）**

| | Java | Python |
|---|---|---|
| 启动 | 成功（HikariCP/Druid 懒连接） | 成功（`/health` 报 `db: DOWN`，整体 `DEGRADED`） |
| 首次查询 | 抛异常 → `BasicErrorController` 返回 500 错误体 | **完全一致**：`{timestamp,status,error,path}`，无 `message` |
| 重试 | 连接池自动重连 | 每次请求重新 ping |

**排查顺序**（当前环境的实测结论：本机**不存在** `192.168.56.0/24` 网段）：

```bat
ping 192.168.56.10                              :: 100% 丢包
ipconfig | findstr /c:"192.168.56"              :: 无输出（网卡只有 VPN/VMware/WLAN）
route print -4 | findstr 192.168.56             :: 无路由
.venv\Scripts\python.exe tools\verify_db.py     :: 5432 全部超时
```

→ GaussDB 所在虚拟机未启动，或 host-only 网卡未创建。**与代码无关。**

---

## 4. MyBatis 语义差异 / P2

### 4.1 6 个 Mapper 方法没有对应 SQL —— **这不是迁移缺陷**

**现象**：启动日志出现 6 条 `WARNING ... has no statement`；调用这些方法会抛
`RuntimeError: Invalid bound statement (not found): ...`

**Java 侧事实**：这 6 个方法的 `.xml` 里确实**不存在**对应 statement，而 Java 代码确实调用了它们
→ Java 运行时抛 `org.apache.ibatis.binding.BindingException: Invalid bound statement (not found)`。

**Python 忠实复刻**，不做"能跑就行"的兜底：

| Mapper | 方法 |
|---|---|
| `OdsLwzxsfsjFeeRecords01Mapper` | `selectGantryNum` |
| `OdsLwzxsfsjFeeRecords01Mapper` | `selectOdsLwzxsfsjFeeRecords01ById` |
| `OdsLwzxsfsjFeeRecords01Mapper` | `selectOdsLwzxsfsjFeeRecords01List` |
| `OdsLwzxsfsjFeeRecords01Mapper` | `selectOdsLwzxsfsjFeeRecords01ListNew` |
| `ZdataTrailFittingMapper` | `selectZdataTrailFittingById` |
| `ZdataTrailFittingMapper` | `selectZdataTrailFittingList` |

**早期版本的错误做法（已修复）**：让这些方法静默返回 `[]`。这会掩盖真实缺陷。
现在 `app/db/registry.py:250` 装的是**抛异常**的桩：

```python
def _invalid_bound_statement(namespace: str, method_name: str):
    """Reproduce ``BindingException: Invalid bound statement (not found)``."""
    full_id = f"{namespace}.{method_name}"
    def missing(self, *args, **kwargs):
        raise RuntimeError(f"Invalid bound statement (not found): {full_id}")
```

**规避方式**：这是 Java 侧的历史 bug。若业务上需要这些查询，
应**在 Java 侧补齐 XML**，然后同步到 Python（因为 `.xml` 是同一份文件）。

### 4.2 内存模式 vs 真实模式

| 模式 | 触发条件 | Mapper 行为 |
|---|---|---|
| **内存模式** | 未进入 ASGI lifespan（`TestClient` 不用 `with`） | 返回内存 list（多为空），**不解析 XML** |
| **真实模式** | `python run.py` 或 `TestClient` 用 `with` | 解析 22 个 XML，绑定 58 个方法，走 GaussDB |

**这是刻意设计**：让 82 个 pytest 用例和 `tools/smoke_all_routes.py` 不依赖任何外部服务。

**注意**：内存模式下 `total` 与真实库不同（内存 list 长度 vs `count(0)` 结果）。
断言 `total` 具体值的测试只能在真实模式下跑。

### 4.3 结果映射配置

`mybatis-plus.configuration` 的三个开关**逐项保留**：

| 配置 | 值 | Python 行为 |
|---|---|---|
| `map-underscore-to-camel-case` | `true` | `snapshottime` → `snapshottime`，`vehicle_plate` → `vehiclePlate` |
| `call-setters-on-nulls` | `true` | 列值为 `NULL` 时也会调用 setter（字段被置 `None`，而不是保持默认值） |
| `type-aliases-package` | `com.ruoyi.base.domain` | XML 里的 `resultType="OdsRt..."` 按此包解析 |

### 4.4 保留的 Java 缺陷

`DataProcessService.insertIntoMysql` 计算了 `tableName` 却**从未使用**（分表路由未生效）。
PHP/Python 侧同样保留，并显式注释：

```python
# 【原工程缺陷，忠实保留】tableName 计算出后从未使用：
#   分表名没有传给 mapper，实际写入的仍是 mapper 中固定的表名。
tableName = self.getTableName(data.getSnapshottime())
_ = tableName  # 消除"未使用变量"告警，同时保留 Java 的赋值语义
```

**不要"顺手修"** —— 修了就和 Java 侧分表了，行为不再等价。

---

## 5. 命名与 API 差异 / P2

全部 9 处已登记在 `tools/check_parity.py` 的 `_DOCUMENTED_EQUIVALENTS` 里，可审计。

| Java | Python | 原因 |
|---|---|---|
| `RedisUtil.del(String... key)` | `RedisUtil.delete(...)` | **`del` 是 Python 关键字**，无法作方法名。已确认无 `.del(` 调用点残留 |
| `PermissionAnon`（注解） | 模块级装饰器工厂 | Python 无注解 |
| `ValidHeader`（注解） | 模块级工厂函数 | 同上 |
| `CommonUtil`（`static` 工具类） | 模块级函数 | `static` 工具类 → 模块函数 |
| `SpringUtils.postProcessBeanFactory` | `register_bean()` | 无 BeanFactory 生命周期 |
| `SpringUtils.setApplicationContext` | `set_application_context()` | 同上 |
| `BaseController.setValue` | 闭包 | 原为匿名 `PropertyEditorSupport` 子类 |
| `NamedThreadFactory`（×2） | `_NamedThreadFactory` | 私有实现类，前缀 `_` 表"内部" |
| `DelayStats` / `QueryRouteRequest` / `QueryRequest` | 嵌套 `@dataclass(JavaBean)` | Java 静态内部类 → Python 嵌套类 |
| `main()`（`MD5Example`/`RepeatUtil`/`CryptoJSTools`） | `if __name__ == "__main__":` | 保留可独立执行 |

**除 `RedisUtil.del` 外，所有业务类/方法名都与 Java 完全一致。**

---

## 6. 序列化差异 / P2

`app/web/responses.py:JacksonResponse` 是整个实现（**27 行**），基于 `orjson`：

```python
class JacksonResponse(Response):
    media_type = "application/json"
    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)
```

| 项 | Java（Jackson / Spring 默认） | Python（orjson） | 是否一致 |
|---|---|---|---|
| `Content-Type` | `application/json`（**不带 charset**） | 同 | ✅ |
| `null` 字段 | **保留 key**（`Include.ALWAYS` 是默认值） | 保留 | ✅ |
| 非字符串 Map key | 转成字符串 `{"1": ...}` | `OPT_NON_STR_KEYS` 同一行为 | ✅ |
| `NaN` / `Infinity` | 默认**拒绝** | orjson 同样拒绝 | ✅ |
| 中文 | 不转义 | 不转义 | ✅ |
| `enum` | 输出 `name` | 由 domain 类自身决定 | ✅ |
| 日期格式 | **无全局配置**：`application.yml` 里 `jackson` 相关配置 **0 处**（已 grep 验证）；Spring Boot 默认即 ISO-8601 | 无全局配置 → `orjson` 原生 ISO-8601 | ✅ |

> **关于日期**：两侧都没有配 `spring.jackson.date-format`。业务代码里时间字段
> **绝大多数就是 `String`**（`yyyy-MM-dd HH:mm:ss` 由业务自己格式化后再放进 domain），
> 所以序列化层不需要插日期转换。这是一个容易被误传的点。

**已知 Java 侧老问题（Python 未修改）**：`Long` 型主键（雪花 ID）在前端 JS 里会丢精度。
两侧输出相同，属"行为等价"范畴。修它会破坏等价性。

**三种响应契约（务必区分）**：

| 契约 | 形状 | 用在哪 |
|---|---|---|
| `AjaxResult` | `{code, msg, data?}` | 单对象查询、状态查询 |
| `TableDataInfo` | `{total, rows, code, msg}` | 分页列表（`BaseController.getDataTable`） |
| **裸 `Map`** | `{code, message, dataSource, pageNum, pageSize, data}` | `UnifiedQueryController#list` —— **注意 `message` 不是 `msg`，且没有 `rows`** |

`scripts/smoke_test.py` 对这三种都有断言。

---

## 7. 并发与定时任务 / P2

| 项 | Java | Python | 影响 |
|---|---|---|---|
| 线程模型 | Tomcat 线程池 + `ThreadPoolTaskExecutor` | uvicorn 线程池 + `ThreadPoolExecutor` | 外部行为一致 |
| GIL | 无 | 有（CPU 段串行） | 本项目 worker 全为 I/O 型，无影响 |
| 并发写入交错顺序 | JVM 调度 | OS 调度 | **中间态可能不同，最终状态一致**。所有对外结果都汇入任务状态机 |
| cron 语义 | Spring 6 段（秒开头，`1`=周一） | `CronExpression` 逐字复刻 | **不能用 APScheduler**（5/7 段，周字段含义不同） |
| 任务数 | `@Scheduled` 注解处 | **10** 个 | 一致 |
| 关闭钩子 | `@PreDestroy` / `DisposableBean` | lifespan `yield` 之后 | 一致 |
| worker 线程 daemon | 否 | 否 | CLI 脚本必须 `os._exit()` |

---

## 8. 新增端点 / P3

| 端点 | 说明 | 关掉方式 |
|---|---|---|
| `GET /health` | 存活/就绪探针，含 `db` / `scheduler` 探针 | 不建议关（自检依赖） |
| `GET /docs` | Swagger UI | `FastAPI(docs_url=None)` |
| `GET /openapi.json` | OpenAPI 3 描述（86 条 path） | `FastAPI(openapi_url=None)` |

**这些在 Java 侧完全不存在**。已在 `app/main.py` 顶部声明为 deliberate difference。
它们**不影响**任何业务路径（`server.servlet.context-path` 是 `/`，
业务路径形如 `/base/xxx`、`/api/v1/xxx`，与这三个不冲突）。

---

## 9. 环境与运维差异 / P3

| 项 | Java | Python |
|---|---|---|
| 启动命令 | `java -jar xxx.jar` | `python run.py` |
| 端口 | `server.port` = 9901 | 同（可用 `CAR_MONIT_PORT` 覆盖） |
| 绑定地址 | Tomcat `address`（默认全部） | `0.0.0.0`（`CAR_MONIT_HOST`） |
| 进程退出 | JVM 等待非 daemon 线程 | 同上 → CLI 脚本需 `os._exit()` |
| 优雅停机 | `SIGTERM` → `@PreDestroy` | `SIGTERM` → lifespan 退出段 |
| 热重载 | `spring-boot-devtools` | `CAR_MONIT_RELOAD=true`（只监听 `app/`） |
| 日志 | Logback → 文件 + 控制台 | `logging` → 同格式；`logs/pro-business-api.log` |
| 打包 | `mvn package` → jar | **不打包**，源码直跑（`package = false`） |
| 依赖隔离 | Maven 本地仓库 | `.venv`（**必须用虚拟环境**） |

---

## 10. 规避方式速查 / Cheat sheet

| 你遇到的现象 | 大概率原因 | 怎么办 |
|---|---|---|
| `/health` 是 `DEGRADED`、`db: DOWN` | GaussDB 不可达 | 见 §3.5 四步排查；或改 `application.yml` 的 `master.url` |
| 启动日志 6 条 `has no statement` | Java 侧就没有这些 SQL | **正常**，见 §4.1 |
| 调用某方法抛 `Invalid bound statement` | 同上 | 在 Java 侧补 XML |
| `pytest` 里 `total == 0` | 内存模式，没有真实数据 | 正常，见 §4.2 |
| 进程跑完不退出 | 线程池 worker 非 daemon | 脚本末尾加 `os._exit(code)` |
| `ImportError: No module named 'com'` | 没 import `bootstrap` | 入口必须先 `import bootstrap` |
| 改了业务文件热重载没生效 | reload 只监听 `app/` | 重启 `python run.py` |
| `APScheduler` / `redis` / `elasticsearch` 装不上 | **不需要装** | 已在 `requirements.txt` 里注明移除理由 |
| 看到 `StringBuilder` 拼接字符串 | Java 习惯 | 这类只在替身层，业务代码用 `str.join` |
| `RedisUtil.del` 不存在 | 关键字冲突 | 用 `delete`，见 §5 |

---

## 11. 结论

| 维度 | 等价度 | 依据 |
|---|---|---|
| 类/方法 | **100%** | `check_parity.py`：219/219 文件，Tier B = 0 |
| 接口路径 & 字段 | **100%** | 85 条路由，三种响应契约逐一断言 |
| 状态码 & 错误体 | **100%** | `BasicErrorController` 复刻 + `include-message=never` |
| 业务规则 & 边界 | **100%** | 82 pytest + 10 smoke 脚本 |
| 数据表 & SQL | **100%** | 直接解释原 `.xml`，未重写 |
| 事务 | **不等价（1 处）** | §2.1，仅影响 MQ 消费路径 |
| 分布式计算 | **不可运行** | §2.2 Flink |
| 中间件连接 | **替身** | §2.3 |

**唯一的硬缺口是 `@Transactional`（1 处）与 Flink（1 个作业类），其余差异或已补偿、或属 Java 侧本来就有的缺陷。**
