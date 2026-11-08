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

**当前结论：P0 = 0 条，P1 = 1 条（Flink 作业不可运行，见 §2.2），P2 = 6 条，P3 = 4 条。**
（2026-11-08 修复轮次后，事务与中间件两项 P1 已关闭：§2.1 / §2.3。）

**真实环境接口对等校验：75 / 75 一致（0 处差异）**，详见 §0。

---

## 0. 真实环境接口对等校验 / Real-infra parity run

同一份 `pro-business-api-1.0.jar`（:9902）与本 Python 端（:9901）**同时启动**，
连接**同一套真实依赖**——openGauss 3.0.0（`192.168.56.10:5432/RuoYi`，schema
`jl_data01`）、Redis 8.10.2（`127.0.0.1:6379`）、Elasticsearch 7.15.2
（`127.0.0.1:9200`）——用**相同参数**逐接口比对：HTTP 状态码 + 响应体结构
（键名、值类型、`null` 语义、`total` 行数）。

| 轮次 | 一致 / 总数 | 关键动作 |
|---|---|---|
| 基线 | 51 / 75 | 错误响应体缺 `message` 键 |
| + 错误体对齐 | 56 / 75 | `app/web/errors.py` |
| + 重启生效 | 65 / 75 | 之前比对的是旧进程 |
| + ES 异常 / `/error` | 71 / 75 | 见下表 #2 #4 |
| **最终** | **75 / 75** | 0 处差异 |

### 已修正的 6 类差异

| # | 差异现象 | 根因 | 修正位置 |
|---|---|---|---|
| 1 | 404/400/500 响应体 Python 少 `message` 键（15 例） | `server.error.include-message=never` 只是不写**内容**，键始终存在（空串）；Python 直接省了键 | `app/web/errors.py` |
| 2 | `GET/POST/.../error`：Java 500 + `status:999`，Python 404 | 直接命中 `/error` 不走错误派发，Spring 写入占位值 `999` / `error:"None"`，且**没有 `path` 键** | `app/main.py` → `spring_basic_error_controller` |
| 3 | `/api/v1/large/snapshot`、`/api/v1/unified/snapshot/list`：Java 10 行、Python 0 行 | `@TableName(value=..., schema="jl_data01")` 的 schema 丢了；连接的 `search_path` 是 `"$user",public`，同名表在 public 下存在但**为空**（0 行 vs 900 行） | `tools/gen_java_meta.py` 新抽 `TABLE_SCHEMAS` → `BaseMapper.getTableName()` |
| 4 | `/api/v1/large/stats/group`：Java `code:500` + ES 异常文案，Python `code:200` + `data:{}` | ES 替身对不存在的索引静默返回空；真实 ES 7.15.2 返回 404 `index_not_found_exception`，Java 因此进入“降级 MySQL”分支并抛出统计异常 | `org/elasticsearch/ElasticsearchException.py`（新增）+ `RestHighLevelClient._resolveIndices()` |
| 5 | `/base/sysutil/getByTrailBo`：`borderWeighingCaptureBo` vs `...CaptureBO` | `java_meta.py` 的键是 Java 全限定类名，而 Python 模块路径**本身就是** FQCN，再拼一次类名得到 `...TrailBo.TrailBo`，元数据查询全部静默落空（`@JsonFormat` 也一直没生效） | `app/compat/meta_key.py`（新增）；同时修掉 `gen_java_meta.py` 漏抓包级私有字段 |
| 6 | `/base/snapshotflow/list`：`total` 900 vs 251 | Python 的 Redis 替身读不到 `sys_config:data_query="queryall"`，于是走了 `flag='JiAnDong'` 降级分支 | `com/ruoyi/common/core/redis/_RespClient.py`（新增，只读穿透，仅标量） |

> 上表 #3 #5 #6 都是**真实的 Java 语义**，不是 Python 的“优化”：我的迁移最初把 schema、
> 包级私有字段、Redis 配置读丢了，真实环境一跑就暴露了。

### 如何复跑

```bash
# 1) 拉起双端（Java 用原 jar，Python 用 .venv）
D:/work/Git/bin/bash.exe _probe/restart_py.sh          # Python :9901
D:/work/Git/bin/bash.exe _probe/status.sh              # 双端 + Gauss/Redis/ES 存活
# 2) 逐接口比对（75 个用例，含 5 个 HTTP 方法的 /error）
D:/work/Git/bin/bash.exe _probe/run_compare.sh
# 明细落盘在 _probe/compare.txt 与 _probe/diff.json
```

注意：Python 必须带 `CAR_MONIT_REDIS_URL=redis://127.0.0.1:6379/0` 启动（`restart_py.sh`
已内置），否则 #6 会重新出现——见 §2.3。

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
| 存在单元测试 | **无任何 `src/test`** | `tests/` pytest 回归网（单元 + SQL golden + 真实中间件集成测试骨架） | P3 |
| 存在 Quartz | **无**，只有 `@Scheduled` | 自研 `CronExpression`（Spring 6 段语义） | P2 |

> **错误码常量**：Java 侧没有独立的错误码枚举，`AjaxResult` 直接用
> `HttpStatus.SUCCESS(200)` / `HttpStatus.ERROR(500)` / `HttpStatus.WARN(601)` 等字面量。
> Python 侧 `com/ruoyi/common/constant/HttpStatus.py` 逐值保留，未改造。

---

## 2. 无法复现的 Java 能力 / P1

### 2.1 `@Transactional` —— 事务语义已补齐 【原 P1，已修复】

**现象（修复前）**：MySQL 写成功、ES 写失败时，Python 侧 MySQL 不会回滚。

**现状**：`app/db/engine.py` 提供 `Database.transaction()`（REQUIRED 传播、
异常回滚、同事务读可见），`DataProcessService.process` 已按 Java 的
`@Transactional(rollbackFor = Exception.class)` 边界包住“写库 + 写 ES”：

```python
with database.transaction():
    self.insertIntoMysql(data)
    self.insertIntoEs(data)
```

**语义对照**：

| Java | Python |
|---|---|
| `@Transactional(rollbackFor = Exception.class)` | `with Database.transaction():` |
| 嵌套调用加入外层事务（REQUIRED） | 复用 `_TX_LOCAL` 上的同一个连接（无 savepoint，语义平铺） |
| 运行时异常回滚 | `engine.begin()` 异常自动 rollback |

**影响面**：只影响 MQ 消费路径（`RocketMqConsumer` → `DataProcessService`）；
HTTP 接口全部只读或单表单写，不依赖事务。

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

### 2.3 中间件默认为替身，可一键切换真实读写 【原 P1，已修复】

**现象（修复前）**：Redis / ES / Kafka 的调用默认返回进程内替身，数据不出进程，
多实例各自为政。

**现状**：Python 侧已提供**真实读写适配器**（`app/middleware/real_*.py`），
设置环境变量即切换；未设置时保持纯内存替身（开发/测试/CI 无需外部服务）。

| 环境变量 | 作用 | 读写语义 |
|---|---|---|
| `CAR_MONIT_REDIS_URL`（如 `redis://127.0.0.1:6379/0`） | 真实 Redis 读写 | 全量操作走 redis-py；编解码兼容 Java FastJson（`@type` 白名单、`52650L`、毫秒/文本日期） |
| `CAR_MONIT_ES_URL`（如 `http://127.0.0.1:9200`） | 真实 Elasticsearch REST/DSL | 查询/写入/scroll/索引管理全部走 elasticsearch-py；响应 `parse_float=Decimal` 保留金额精度 |
| `CAR_MONIT_KAFKA_URL`（如 `127.0.0.1:9092`） | 真实 Kafka 生产/消费 | `acks=all`、幂等、lz4、超时与 Java 配置对齐；消费者按 Flink `at-least-once` 语义提交位点 |

**降级与熔断**（`CAR_MONIT_REDIS_FALLBACK` / `..._ES_FALLBACK` / `..._KAFKA_FALLBACK`）：

* `error`（prod 默认）：真实服务失败**抛错**，对齐 Java 的“中间件宕机”失败路径；
* `memory`（shim 默认）：失败后熔断，后续请求回落进程内替身；窗口 60 秒，
  半开只放行一个探测；**降级期间的写入不会回灌真实服务**；
* 三者的 `degraded` 状态已接入 `/health` 与 `/health/ready`（熔断中 = 组件 DOWN）。

**仍是替身的部分**：Pulsar / RocketMQ（Java 侧本身未启用或无消费闭环）、
`JdbcTemplate`（空转）、Forest HTTP（直接 httpx）、Flink（见 §2.2）。

| 组件 | 当前行为 |
|---|---|
| Redis | 配 URL → 真实读写；未配 → 进程内 dict + 过期时间 |
| Elasticsearch | 配 URL → 真实 REST/DSL；未配 → 内存索引 + 与真实 ES 一致的 `index_not_found_exception` |
| Kafka | 配 URL → 真实 producer/consumer；未配 → 内存 producer |
| Pulsar / RocketMQ | 内存替身（沿用原迁移形态） |
| RabbitMQ | **无替身**（Java 侧只有配置、零代码使用） |
| Forest HTTP | `httpx` 直连 |

**规避方式**：生产按 §10 上线清单设置 URL 与 fallback=error；离线回归保持未设置
（或跑 `tools/run_checks.ps1`，冒烟脚本会主动清空 `CAR_MONIT_*_URL` 隔离真实集群）。
真实环境接口对等结果见 §0，连通性检查见 `tools/check_middleware.py`。

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

**这是刻意设计**：让 pytest 回归网和 `tools/smoke_all_routes.py` 不依赖任何外部服务
（冒烟脚本主动清空 `CAR_MONIT_*_URL`，真实集群只在 `tests/business` 集成测试中使用）。

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
| `GET /health` | 组件探针（db / redis / elasticsearch / kafka），失败时 `DEGRADED` | `CAR_MONIT_HEALTH_VERBOSE=false` 隐藏 `config` 细节 |
| `GET /health/live` | 纯存活探针（进程活着即 200） | 不建议关（容器 liveness） |
| `GET /health/ready` | 就绪探针（任一组件 DOWN → 503） | 由负载均衡使用 |
| `GET /metrics` | Prometheus 文本指标（QPS/错误/耗时/状态码） | prod 默认关闭；`CAR_MONIT_METRICS_ENABLED=true` 开启 |
| `GET /docs` | Swagger UI | prod 默认关闭；`CAR_MONIT_DOCS_ENABLED` 可覆盖 |
| `GET /openapi.json` | OpenAPI 3 描述（85 条业务 path） | 同上 |

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
| 优雅停机 | `SIGTERM` → `@PreDestroy` | `SIGTERM` → lifespan 退出段（Bean → 调度器 → Kafka/ES/Redis/DB 连接池，见 `shutdown_middleware`） |
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
| `redis` / `elasticsearch` / `confluent-kafka` 装不上 | 真实适配器依赖（即使不接真实服务，导入链也需要） | 已声明在 `requirements.txt`，用 `.venv` 安装 |
| `/health/ready` 503、`redis / elasticsearch / kafka: DOWN` | 适配器熔断降级（真实服务不可达） | 检查 `CAR_MONIT_*_URL` 与真实服务；见 §2.3 |
| `/metrics` 返回 404 | prod 默认收敛 | `CAR_MONIT_METRICS_ENABLED=true` 显式开启 |
| 看到 `StringBuilder` 拼接字符串 | Java 习惯 | 这类只在替身层，业务代码用 `str.join` |
| `RedisUtil.del` 不存在 | 关键字冲突 | 用 `delete`，见 §5 |

---

## 11. 结论

| 维度 | 等价度 | 依据 |
|---|---|---|
| 类/方法 | **100%** | `check_parity.py`：219/219 文件，Tier B = 0 |
| 接口路径 & 字段 | **100%** | 85 条路由，三种响应契约逐一断言 |
| 状态码 & 错误体 | **100%** | `BasicErrorController` 复刻 + `include-message=never` |
| 业务规则 & 边界 | **100%** | pytest 回归网 + 23 个迁移期冒烟脚本 |
| 数据表 & SQL | **100%** | 直接解释原 `.xml`，未重写 |
| 事务 | **等价（已补齐）** | §2.1，`Database.transaction()` |
| 分布式计算 | **不可运行** | §2.2 Flink |
| 中间件连接 | **可接真实** | §2.3；未配置 URL 时保持进程内替身 |

**唯一的硬缺口是 Flink（1 个作业类，需继续由 Java 侧承担）；事务与中间件已闭环，
其余差异或已补偿、或属 Java 侧本来就有的缺陷。**
