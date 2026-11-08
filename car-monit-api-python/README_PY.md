# car-monit-api — Python 版上手指南 / Getting Started

> 你是一个 Java 开发者，面前是一个"长得像 Java 工程"的 Python 工程。
> 本文件只讲一件事：**怎么把它跑起来，以及你会踩哪些坑。**
>
> 设计细节看 [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)；
> 行为差异看 [`COMPATIBILITY.md`](COMPATIBILITY.md)；
> 本机环境与真实中间件集成测试 runbook 看 [`docs/LOCAL-ENV.md`](docs/LOCAL-ENV.md)。

---

## 1. 一分钟启动 / Quick start

```bat
cd car-monit-api-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

然后验证：

```bat
:: 另开一个窗口
curl http://127.0.0.1:9901/health
:: 或直接跑自检
.venv\Scripts\python.exe scripts\smoke_test.py --live http://127.0.0.1:9901
```

**等价关系**：

| Java | Python |
|---|---|
| `mvn -DskipTests package` | *(不需要，源码直跑)* |
| `java -jar pro-business-api.jar` | `python run.py` |
| `application.yml` 里的 `server.port` | 同上，`run.py` 会读它（默认 9901） |

### 只需要跑自检、不需要起服务

```bat
.venv\Scripts\python.exe scripts\smoke_test.py
```

这个模式**不进入应用生命周期**，所有 Mapper 走内存实现，**不连 GaussDB / Kafka / ES**，
适合 CI 和"改完代码快速看有没有弄坏契约"。

---

## 2. 环境要求 / Requirements

| 项 | 要求 | 说明 |
|---|---|---|
| Python | **3.12+** | 用了 `from __future__ import annotations`、`datetime.UTC` 风格、`list[str]` 内建泛型 |
| 操作系统 | Windows / Linux / macOS | 已在 Windows 21H2 验证 |
| 数据库 | GaussDB（PostgreSQL 协议） | **不是必需**：连不上也能启动，`/health` 会报 `DEGRADED` |
| Redis / ES / Kafka | **可选** | 未配置 URL 时为进程内替身；设置 `CAR_MONIT_REDIS_URL` / `CAR_MONIT_ES_URL` / `CAR_MONIT_KAFKA_URL` 切真实读写，见 `COMPATIBILITY.md` §2.3 |
| Pulsar / RocketMQ | **不需要** | 仍是进程内替身（Java 侧本身未启用或无消费闭环） |

> **虚拟环境是必须的**。系统 Python 里装这些东西会污染环境，而且本项目
> 用 `.venv` 承载全部依赖（`pyproject.toml` 里 `package = false`，不装成 wheel）。

---

## 3. 目录导览 / Where is everything

第一次打开这个工程，你大概会想找这几样东西：

| 你想找 | Java 里在哪 | Python 里在哪 |
|---|---|---|
| 启动类 | `com.ruoyi.EcBusinessApiApplication` | **`run.py`** → `app/main.py:app` |
| `@RestController` | `com/ruoyi/base/controller/*.java` | 同路径 `.py` |
| 路由路径 | `@RequestMapping` 注解 | **`app/routes/generated.py`**（一张表）+ `app/routes/registry.py` |
| Service | `com/ruoyi/base/service/**` | 同路径 `.py` |
| Entity | `com/ruoyi/base/domain/*.java` | 同路径 `.py` |
| Mapper 接口 | `com/ruoyi/base/mapper/*.java` | 同路径 `.py` |
| Mapper SQL | `.../mapper/xml/*.xml` | **同一个 `.xml` 文件**（原样保留） |
| `application.yml` | `pro-business-api/src/main/resources/` | **同一个 yml 文件**（原样保留，被 `Environment.py` 读取） |
| `AjaxResult` / `TableDataInfo` | `com/ruoyi/common/core/domain/` | 同路径 `.py` |
| 全局异常处理 | `@ControllerAdvice`（**不存在**） | `app/web/errors.py`（复刻 `BasicErrorController`） |
| JDK 类（`HashMap`、`LocalDateTime`…） | JDK | `java/**`、`javax/**` 替身层 |
| 三方库（`QueryBuilders`、`CronExpression`…） | jar | `com/**`、`org/**` 替身层 |

**关键认知**：`com/`、`java/`、`javax/`、`org/` 这 4 个目录**不是业务代码**，
是"JDK + 第三方库的 Python 替身"。它们被 `bootstrap.py` 注册为 import 根，所以
业务代码可以原封不动地写 `from java.util import HashMap`。

```
car-monit-api-python/
├── app/            ← FastAPI 宿主（Java 无对应，含 middleware 适配层）
├── com/ java/ javax/ org/   ← JDK + 三方库替身（172 个 .py）
├── pro-base-common/src/main/java/com/ruoyi/common/      ← 业务：公共模块（54 个 .py）
├── pro-business-api/src/main/java/com/ruoyi/            ← 业务：主模块（166 个 .py）
├── tests/          ← pytest（单元 + SQL golden + 集成）
├── tools/          ← 验证/门禁脚本（含 check_secrets）
├── scripts/        ← smoke_test.py
├── bootstrap.py    ← 把上面几个根塞进 sys.path（= Maven classpath）
└── run.py          ← 入口（= java -jar）
```

---

## 4. 配置对照 / Configuration

**原则**：`application.yml` 一字未改，仍由 Python 侧读取。Python **不引入**
`.env` 文件解析（Java 侧没有这个机制），只支持**环境变量覆盖**——这正是 Spring 的行为。

### 4.1 优先级（与 Spring 完全一致）

```
环境变量  >  application.yml  >  @Value 占位符里的默认值
```

### 4.2 常用配置项

| `application.yml` 键 | 默认值 | 怎么覆盖 | 说明 |
|---|---|---|---|
| `server.port` | `9901` | `set CAR_MONIT_PORT=9901` | `run.py` 优先读环境变量 |
| `server.servlet.context-path` | `/` | — | 保持 `/`，路径前缀不额外拼接 |
| `spring.datasource.dynamic.datasource.master.url` | `jdbc:postgresql://192.168.56.10:5432/RuoYi` | 改 yml | `jdbc:` 前缀会被剥掉交给 psycopg |
| `spring.datasource.dynamic.datasource.master.username` | `gaussdb` | 改 yml | |
| `spring.datasource.dynamic.datasource.master.password` | `${SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD:}` | 环境变量 / `application-local.yml` | **不要**提交真实密码（上线前必须轮换，见 §10） |
| `spring.datasource.dynamic.druid.maxActive` | `20` | 改 yml | 连接池上限 |
| `spring.redis.host` / `port` | `127.0.0.1:6379` | 改 yml | `/health` 展示；**真实读写**走 `CAR_MONIT_REDIS_URL` |
| `elasticsearch.host` / `port` | `localhost:9200` | 改 yml | `/health` 展示；**真实读写**走 `CAR_MONIT_ES_URL` |
| `spring.kafka.bootstrap-servers` | `localhost:9092` | 改 yml | `/health` 展示；**真实生产/消费**走 `CAR_MONIT_KAFKA_URL` |
| `app.scheduler.enabled` | `true` | `set APP_SCHEDULER_ENABLED=false` | **Python 独有**开关，见 4.3 |
| `isLocalhost` | `local` | 改 yml | `local` / `prod` 部署标记 |

### 4.3 Python 侧新增的环境变量（宿主层行为，不改业务）

**运行模式与启动（V2 新增，见 `app/runtime.py`）**：

| 变量 | 默认 | 作用 |
|---|---|---|
| `CAR_MONIT_RUNTIME` | `shim` | `shim`=开发/测试（替身可用）；`prod`=生产（**替身假成功操作抛错拒绝**：Kafka/ES/Redis 写等中间件替身在无真实适配器时会显式失败，等价 Java 中间件宕机路径） |
| `CAR_MONIT_STARTUP_FAIL_FAST` | `true` | `false` → Mapper/路由/调度器启动失败仅记日志（应急排障用；默认与 Spring 一致失败即退出） |
| `CAR_MONIT_DOCS_ENABLED` | shim 开 / prod 关 | `/docs` 与 `/openapi.json` 开关 |
| `CAR_MONIT_HEALTH_VERBOSE` | shim 开 / prod 关 | `/health` 是否携带 `config`（中间件地址）细节 |
| `APP_BEANS_ENABLED` | `false` | `true` → 启动 Java 侧 `@Service#@PostConstruct` 后台 Bean（全量/增量同步、Kafka 重试；**启用前须确认决策②③**，见 `app/beans.py`） |

**连接与部署**：

| 变量 | 默认 | 作用 |
|---|---|---|
| `CAR_MONIT_HOST` | `0.0.0.0` | uvicorn 绑定地址（对应 Tomcat 的 `address`） |
| `CAR_MONIT_PORT` | `server.port` | uvicorn 端口（同时是 `settings.server_port` 的最高优先级） |
| `CAR_MONIT_WORKERS` | `1` | uvicorn 进程数；**>1 会复制进程内状态**（调度器/内存替身/导出任务表），真实中间件接入前慎用 |
| `CAR_MONIT_RELOAD` | `false` | `true` → 热重载（**仅开发用**，等价于 `spring-boot-devtools`） |
| `CAR_MONIT_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |
| `CAR_MONIT_REDIS_URL` | *(空)* | 如 `redis://127.0.0.1:6379/0`：Redis 全量读写走真实服务；不设置则纯内存 |
| `CAR_MONIT_ES_URL` | *(空)* | 如 `http://127.0.0.1:9200`：ES 查询/写入走真实 REST/DSL；不设置则内存索引 |
| `CAR_MONIT_KAFKA_URL` | *(空)* | 如 `127.0.0.1:9092`：生产/消费走真实 broker；不设置则内存 producer |
| `CAR_MONIT_REDIS_FALLBACK` / `..._ES_FALLBACK` / `..._KAFKA_FALLBACK` | prod=`error`，shim=`memory` | `error`=失败抛错（Java 宕机语义）；`memory`=熔断回落替身（60s 半开、单探测） |
| `CAR_MONIT_METRICS_ENABLED` | prod 关 / shim 开 | `/metrics` 开关（关闭时 404） |
| `APP_SCHEDULER_ENABLED` | `true` | `false` → 不启动 10 个定时任务（自检时会用） |

> **密钥（P0-6）**：随包 `application.yml` 只含 `${ENV:}` 占位符；真实口令写
> `pro-business-api/src/main/resources/application-local.yml`（已 gitignore，
> 优先级：环境变量 > local 文件 > yml > 占位符默认值），或经环境变量注入。

### 4.4 代码里怎么读配置

```python
# Java
@Value("${server.port:9901}")
private int port;

// Java（Environment 方式）
environment.getProperty("server.port", Integer.class, 9901);
```

```python
# Python —— 两种都有，与 Java 一一对应
from app.settings import settings
port: int = settings.server_port

# 或直接走 Environment（业务类里大量使用这种）
from org.springframework.core.env.Environment import getEnvironment
environment = getEnvironment()
port: int = environment.getProperty("server.port", Integer, 9901)
```

---

## 5. 你会踩的坑 / Pitfalls for Java developers

### 5.1 `None` ≠ `null`，且 `None` **不参与**大部分运算

```java
String s = null;
s.length();            // NullPointerException
"abc".equals(s);       // false —— 安全
```
```python
s = None
s.length()             # AttributeError: 'NoneType' object has no attribute ...
s == "abc"             # False —— 安全
len(s)                 # TypeError
```

**对策**：判断用 `is None` / `is not None`（**不要**用 `== None`）。
本项目业务代码沿用 Java 习惯：`value is not None and len(value) > 0`。

### 5.2 可变默认参数（**Java 里不存在这个陷阱**）

```python
def add(item, bucket=[]):     # ← 错！默认值只创建一次
    bucket.append(item)
    return bucket

def add(item, bucket=None):   # ← 对
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

**Java 对照**：Java 的 `void m(List<String> l)` 不允许默认值，所以没这个问题。
Python 的默认值在**函数定义时**求值一次，之后共享。

本项目所有可选集合参数都写成 `Optional[...] = None` + 内部建空容器。

### 5.3 整数除法

```java
int a = 7 / 2;         // 3
double b = 7 / 2;      // 3.0  （先整除再赋值！）
double c = 7 / 2.0;    // 3.5
```
```python
a = 7 // 2             # 3   ← 整除用 //
b = 7 / 2              # 3.5 ← / 永远是浮点除法
```

**注意**：`int` 在 Python 里**没有溢出**（`long` 也不需要），但有符号取整规则
和 Java 一样是向负无穷取整：`-7 // 2 == -4`（Java 也是 `-4`），`-7 % 2 == 1`
（**Java 是 `-1`**）。分页计算里用到的都是正数，无影响。

### 5.4 `==` 与 `equals`

```java
String a = new String("x");
a == "x"               // false（比引用）
a.equals("x")          // true
```
```python
a = "x"
a == "x"               # True（比值）
a is "x"               # 不要用！比身份，结果依实现而定
```

**规则**：Python 里**永远用 `==` 比较值**，`is` 只用于 `None / True / False`。
本项目的字符串比较全部是 `==`。

### 5.5 异常：没有受检异常，没有 `finally` 里的 `return` 覆盖

```java
try { return a(); }
catch (Exception e) { return b(); }
finally { return c(); }    // Java：返回 c，吞掉异常！
```
```python
try:
    return a()
except Exception:
    return b()
finally:
    return c()             # Python：同样返回 c，同样吞异常 —— 但会打印警告
```

**语义一致**，但 Python 侧**不要这么写**。本项目的 `finally` 只做日志
（见 `UnifiedQueryService.query`）。

```java
// Java 的 catch (Exception e) → Python 的 except Exception
// Java 的 catch (RuntimeException e) → Python 没有对应，统一 except Exception
// finally 一定会执行 —— 两边一致
```

**抛异常的写法**：

```python
raise RuntimeError("boom")                     # = throw new RuntimeException("boom")
raise RuntimeError("boom") from cause           # = throw new RuntimeException("boom", cause)
```

### 5.6 `async` / `await` —— **本项目业务代码全部是同步的**

这是最容易误解的一点。

* Java 侧：Spring MVC 是同步阻塞模型（Tomcat 线程池）。
* Python 侧：FastAPI 是 ASGI，**但**本项目的路由函数全部声明为普通 `def`，
  FastAPI 会把它们丢进 **threadpool** 执行 —— 等价于 Tomcat 线程池。

```python
@app.get("/x")
def handler():          # ← 普通 def，跑在线程池（= Tomcat worker）
    return service.doSomething()

@app.get("/y")
async def handler2():   # ← async def，跑在事件循环（阻塞会卡死全站！）
    ...
```

**所以**：你在业务代码里看到的都是 `def`，**不需要**理解 `await`。
只有当你在 `app/` 里加新东西时才需要关心。

**自检脚本里** `time.sleep(0.1)` 是安全的，因为它在线程池里跑。

### 5.7 GIL

Python 线程是**真 OS 线程**，但同一时刻只有一个线程执行 Python 字节码。

* CPU 密集 → 多线程不加速。
* I/O 阻塞 → 多线程照常并发（本项目的工作线程全部是 I/O 型）。

**行为影响**：并发写入的**中间态交错顺序**可能与 JVM 不同，**最终状态一致**
（所有对外结果都汇集到任务状态机/dict，读操作加锁）。

### 5.8 类属性 vs 实例属性（**Java 里没有的坑**）

```python
class Foo:
    cache = {}                 # 类属性 —— 所有实例共享！（等价于 Java static）
    def __init__(self):
        self.items = []        # 实例属性 —— 每实例独立
```

**Java 对照**：`private static Map cache = new HashMap();` 是静态字段，
和 `cache = {}` 等价。所以上面**是对的**，只要你心里清楚它是 `static`。

本项目里 `JavaBean._FIELD_MAP_CACHE` 就是刻意做成类级缓存。

### 5.9 名字改写（`@Override` → 装饰器，`del` → `delete`）

| Java | Python | 原因 |
|---|---|---|
| `@Override` | 不需要（鸭子类型） | Python 不检查方法签名一致性 |
| `@Data` / `@Getter` / `@Setter` | 继承 `JavaBean` | `__getattr__` 动态合成 |
| `interface` | `abc.ABC` / 直接继承 | 无编译期契约 |
| `RedisUtil.del(...)` | `RedisUtil.delete(...)` | **`del` 是 Python 关键字**，无法作方法名 |
| `toString()` | `toString()`（保留）+ `__str__` | 两侧都能调 |
| `equals(obj)`、`hashCode()` | `__eq__`、`__hash__` | 业务类按原样保留 `equals()` |

### 5.10 线程不会让进程退出

Java 的非 daemon 线程池同理。本项目导出/同步线程池的 worker **不是 daemon**，
所以 CLI 脚本末尾必须强杀：

```python
sys.stdout.flush(); sys.stderr.flush()
os._exit(exit_code)          # 等价于 System.exit()
```

`scripts/smoke_test.py`、`tools/smoke_all_routes.py` 都这么做了。
**不要**改成 `sys.exit()`，线程池会把它挂住。

### 5.11 集合类型对照

| Java | Python | 注意 |
|---|---|---|
| `List<T>` | `list` | 可变、有序 |
| `Map<K,V>` | `dict` | **3.7+ 保证插入顺序**（= `LinkedHashMap`，**不是** `HashMap`） |
| `Set<T>` | `set` | 无序 |
| `T[]` | `list` | 没有定长数组 |
| `Optional<T>` | `Optional[T]` / `None` | 仅类型提示，运行期不强制 |
| `BigDecimal` | `decimal.Decimal` | 本项目用替身 `java.math.BigDecimal` |
| `ConcurrentHashMap` | `dict` + `threading.Lock` | 见替身层 |

### 5.12 日志写法

| Java | Python |
|---|---|
| `log.info("a={}, b={}", a, b)` | `log.info("a=%s, b=%s", a, b)` |
| `log.error("x", a, e)`（末参是异常） | `log.error("x", a, exc_info=True)` |
| `log.debug("x: " + v)` | `log.debug("x: %s", v)`（**不要**用 `+`，惰性求值会失效） |

日志格式已复刻 Logback：`2026-10-30 14:46:28.962 [MainThread] INFO  app.main:132 - 消息`

---

## 6. 调试 / Debugging

### 6.1 热重载

```bat
set CAR_MONIT_RELOAD=true
set CAR_MONIT_LOG_LEVEL=DEBUG
python run.py
```

等价于 `spring-boot-devtools`。**只改 `app/` 下的文件会生效**；
改 `pro-business-api/**` 需要重启（uvicorn 的 reload 只监听 `app/`）。

### 6.2 断点

* **VS Code**：装 Python 扩展 → `Run and Debug` → 选 `Python File` → 目标是 `run.py`。
* **PyCharm Professional**：直接 `Debug run.py`。
* 项目没有提交 `.vscode/launch.json`，需要自己建。

### 6.3 看不出来是哪一段 Java 代码

每个 Python 文件/方法都有溯源注释：

```python
# Migrated from: pro-business-api/.../UnifiedQueryService.java

def shouldRouteToEs(self, ...) -> bool:
    """# Java: com.ruoyi.base.service.optimization.UnifiedQueryService#shouldRouteToEs"""
```

直接搜 Java 方法名即可定位：

```bat
findstr /s /c:"shouldRouteToEs" pro-business-api\src\main\java\*.py
```

### 6.4 启动日志怎么看

```
MyBatis: 23 mapper(s), 58 statement(s) (4 from annotations), 58 method(s) bound to SQL
Scheduler: 10 task(s)
Started EcBusinessApiApplication in 0.11 seconds
```

如果看到：

```
ERROR ... mapper method without statement: com.ruoyi.base.mapper.XxxMapper#yyy
```

那是**正常**的（Java 侧同样没有该语句，调用会抛 `BindingException`）。
详见 `MIGRATION_GUIDE.md` §4.6。

---

## 7. 测试 / Tests

```bat
:: 全部回归网（单元 + SQL golden + 23 个冒烟脚本；集成测试默认跳过）
.venv\Scripts\pytest.exe -q

:: 一键门禁（pytest/覆盖率 + check_* + secret 扫描 + 3 个 smoke，同 CI 顺序）
powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1
```

| 文件 | 覆盖 |
|---|---|
| `tests/test_phase2a.py` | 基础设施：配置、日志、健康检查 |
| `tests/test_phase2b.py` | 路由注册、参数绑定、响应契约 |
| `tests/test_phase2c.py` | MyBatis XML 解释、QueryWrapper、分页 |
| `tests/test_phase2d.py` | 调度器、CronExpression |
| `tests/test_phase2e.py` | 中间件替身（Redis / ES / Kafka / Pulsar） |
| `tests/test_v2_p0.py` | V2 P0 回归：运行时模式守卫、Bean 生命周期、事务、fail-fast、密钥 |
| `tests/test_v2_p1.py` | V2 P1 回归：Decimal 精度、worker 线程、请求 ID/metrics |
| `tests/test_v2_p2.py` | V2 P2 回归：Redis/ES/Kafka 真实适配、熔断窗口、FastJson 兼容、优雅关闭 |
| `tests/business/test_smoke_scripts.py` | 23 个迁移期冒烟脚本（子进程隔离，清空真实中间件 URL） |
| `tests/business/test_sql_golden.py` | 54 条 statement 渲染 SQL 逐字节锁定 |
| `tests/business/test_integration_db.py` | 真实 GaussDB 集成（`CAR_MONIT_TEST_DB=1` 开启，默认跳过） |

### 真实中间件集成测试（Redis / ES / Kafka）

默认全部 skip。磁盘、端口与启动顺序见 [`docs/LOCAL-ENV.md`](docs/LOCAL-ENV.md)；
满足前置条件后一条命令：

```powershell
$env:CAR_MONIT_IT_DATA_DIR = "E:\car-monit-it-data"   # 剩余 ≥8GB 的卷
powershell -ExecutionPolicy Bypass -File scripts\run_integration.ps1 -DataDir $env:CAR_MONIT_IT_DATA_DIR
```

只复用已运行的中间件（不启动容器）：`-SkipStart`；
测试 Linux VM：`-SkipStart -ServiceHost 192.168.56.10`。

### 验证工具（比 pytest 更适合"改完看有没有弄坏"）

```bat
.venv\Scripts\python.exe tools\check_routes.py        :: 85 条路由
.venv\Scripts\python.exe tools\check_mappers.py       :: XML 绑定
.venv\Scripts\python.exe tools\check_parity.py        :: 方法级对照，Tier B 必须为 0
.venv\Scripts\python.exe tools\smoke_all_routes.py    :: 85 条路由全打一遍
.venv\Scripts\python.exe scripts\smoke_test.py        :: 交付自检
```

---

## 8. 数据库连不上怎么办 / GaussDB troubleshooting

这是当前环境**唯一**的红灯项（`/health` 报 `DEGRADED`，`db: DOWN`）。

**症状**：

```json
{"status":"DEGRADED","components":{"db":{"status":"DOWN",
 "error":"ConnectionTimeout: connection timeout expired"}}}
```

**先按顺序排查**：

```bat
:: 1) 主机可达吗？
ping 192.168.56.10

:: 2) 本机有 192.168.56.x 网段吗？
ipconfig | findstr /c:"192.168.56"

:: 3) 路由存在吗？
route print -4 | findstr 192.168.56

:: 4) 端口开着吗？
.venv\Scripts\python.exe tools\verify_db.py
```

**如果 1~3 全部失败**，说明这台机器上**根本没有** `192.168.56.0/24` 网段。
GaussDB 通常跑在 VirtualBox/VMware 的 host-only 虚拟机上，需要：

1. 启动承载 GaussDB 的虚拟机；
2. 确认宿主机有对应的 host-only 网卡（Windows 上是"VirtualBox Host-Only Network"，
   常见为 `192.168.56.1`）；
3. 或在 `application.yml` 里把 `master.url` 改成实际的库地址。

**启动不受影响**：Mapper 会在第一次查询时失败，接口返回 Spring 风格的 500 错误体
（`{timestamp,status,error,path}`），而不是 Python traceback。
`scripts/smoke_test.py` 会自动识别这种状态并断言错误体契约。

---

## 9. 我改代码时要注意什么

1. **不要动 `com/` `java/` `javax/` `org/` 替身层**，除非你确认 Java 侧也这么写。
2. **`application.yml` 和 `*.xml` 是原文件**，改它们要同步改 Java 侧，否则两边会漂移。
3. 改路由 → 改 `app/routes/generated.py`，同时更新 `"java"` 行的行号。
4. 新增业务代码 → 放在镜像路径下，方法名保持 `camelCase`，加 `# Java:` 注释。
5. 改完跑 `tools\check_parity.py`（Tier B 必须 0）和 `scripts\smoke_test.py`（必须全绿）。

---

## 10. 上线前检查清单 / Release checklist

| # | 项 | 要求 | 验证方式 |
|---|---|---|---|
| 1 | **口令轮换（必须，阻断上线）** | GaussDB / Redis / ES / RabbitMQ 的历史口令曾出现在旧文档/注释中；上线前必须由运维在**生产侧轮换**，仓库内只保留 `${ENV:}` 占位符 | 运维工单 + `python tools\check_secrets.py` |
| 2 | 密钥注入 | 真实口令只经环境变量或 `application-local.yml`（gitignored）注入；禁止写回 `application.yml` / 文档 / 注释 | `python tools\check_secrets.py` |
| 3 | 运行模式 | `CAR_MONIT_RUNTIME=prod`（禁止 shim 替身承载生产流量） | `/health` 的 `runtime` 字段 = `prod` |
| 4 | 中间件连接 | 按需设置 `CAR_MONIT_REDIS_URL` / `CAR_MONIT_ES_URL` / `CAR_MONIT_KAFKA_URL`，并确认 `/health/ready` 为 200 | `curl /health/ready` |
| 5 | 启动 fail-fast | 保持 `CAR_MONIT_STARTUP_FAIL_FAST=true`（默认）；Mapper/路由缺失会拒绝启动 | 启动日志 `all gates` + 进程退出码 |
| 6 | 端点收敛 | prod 默认关闭 `/docs`、`/openapi.json`、`/metrics`、`/health` 的 `config` 细节 | `curl /docs` 应为 404 |
| 7 | 全量门禁 | `powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1` 全绿 | 退出码 0 |
