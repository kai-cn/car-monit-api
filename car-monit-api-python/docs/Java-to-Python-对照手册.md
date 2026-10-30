# Java → Python 迁移对照手册

> 面向 Java 开发者。目标：**让熟读 Spring 代码的人在 30 分钟内知道 Python 侧每一处“长得不一样”的地方为什么不一样、去哪里找对应实现、以及哪些差异是刻意的。**
>
> 迁移基线：`d:\work\IdeaProjects\car-monit-api`（Java 1.8 / Spring Boot 2.4.5）→ `d:\work\IdeaProjects\car-monit-api\car-monit-api-python`（Python 3.12 / FastAPI）。
> 迁移原则：**行为等价 > 结构镜像 > 可读性**。原代码的缺陷（错别字、写错的定时表达式、注释掉的类）一律保留，不做“顺手修复”。

---

## 0. 如何读这份手册 / 如何自己验证

```bat
cd /d d:\work\IdeaProjects\car-monit-api\car-monit-api-python

:: 1) start the service (same as `java -jar`)
.venv\Scripts\python.exe run.py

:: 2) route table: are all 24 controllers / 85 routes registered?
.venv\Scripts\python.exe tools\check_routes.py

:: 3) mapper XML <-> interface method binding
.venv\Scripts\python.exe tools\check_mappers.py

:: 3b) Java <-> Python 方法级对照（Tier B 必须为 0）
.venv\Scripts\python.exe tools\check_parity.py

:: 4) middleware connectivity (GaussDB / Redis / Kafka / ES)
.venv\Scripts\python.exe tools\check_middleware.py

:: 5) full test suite + 85-route smoke + 6 subsystem smokes
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe tools\smoke_all_routes.py
.venv\Scripts\python.exe tools\smoke_scheduler.py
```

手册中所有路径、行号、数量都可用上述命令复现；第 7 章给出最后一次实测结果。

**追踪约定**（贯穿全部 220 个 Python 文件）：

| 标记 | 位置 | 含义 |
|---|---|---|
| `"""com.ruoyi.base.Xxx"""` + `源文件：...Xxx.java` | 文件头 docstring | 与 Java 文件的一一对应关系 |
| `# Java: private String id;` | 字段/语句上方 | 逐行对照锚点 |
| `【Java→Python】` | 类/方法 docstring | **设计差异说明**，只写“为什么不一样”，不重复源码注释 |
| `# Migrated from:` | 编排层/替身层文件头 | 无同名 Java 文件的框架能力来源 |

---

## 1. 总览

### 1.1 迁移体量

| 模块 | Java | Python | 文件差 |
|---|---|---|---|
| `pro-business-api` | 166 文件 / 26,243 行 | 166 文件 / 28,124 行 | **0 缺 0 多** |
| `pro-base-common` | 53 文件 / 7,345 行 | 54 文件 / 6,397 行 | +1（`JavaBean`，Lombok 替代） |
| **业务代码合计** | **219 文件 / 33,588 行** | **220 文件 / 34,521 行** | 1:1 |

业务代码之外还有两层“让 Java 语义跑起来”的补充代码（Java 侧由框架/JVM 提供，Python 侧必须自己写）：

| 层 | 位置 | 规模 | 作用 |
|---|---|---|---|
| 框架替身层 | `com` `java` `javax` `org` | 171 文件 / 14,462 行 | 复刻 Spring / MyBatis-Plus / fastjson2 / ES / Flink / Kafka 等 API 的**签名与语义** |
| 编排层 | `app` | 26 文件 / 6,726 行 | Spring MVC 分发、参数绑定、PageHelper、GaussDB 连接池、调度器、启动装配 |
| 验证层 | `tests` `tools` | 5 + 16 文件 / 3,187 行 | pytest + 路由/中间件/对照审计/冒烟脚本 |

```text
业务代码行数几乎相等（33.6k → 34.5k，差 +933），说明迁移是“逐行搬运”而不是“重写”；
Spring/JVM 原本免费提供的能力，由 1.45 万行框架替身 + 0.67 万行编排层补上（不计入上面的业务对照）。
```

### 1.2 目录映射

Java 的 Maven 布局（`src/main/java` + `src/main/resources`）在 Python 侧**原样保留**，通过 `bootstrap.py` 注册为 import 根，而不是改成 Python 的扁平包布局：

```python
# bootstrap.py
ROOT = Path(__file__).resolve().parent
PACKAGE_ROOTS = (
    ROOT / "com", "java", "javax", "org", ...          # framework shims
    ROOT / "pro-business-api/src/main/java",           # -> import com.ruoyi.base.controller.Xxx
    ROOT / "pro-base-common/src/main/java",            # -> import com.ruoyi.common.utils.Xxx
)
```

| Java | Python | 说明 |
|---|---|---|
| `pro-business-api/src/main/java/com/ruoyi/base/controller/XxxController.java` | `.../com/ruoyi/base/controller/XxxController.py` | 同路径、同包名、同类名 |
| `pro-business-api/src/main/resources/application.yml` | 同路径 | **文件完全相同**（逐字节 diff 无差异） |
| `pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/*.xml` | **不复制**，原地读取 | 见 4.3：XML 是唯一事实来源 |
| `src/main/resources/es/index/*.json` | 同路径 | 3 个索引模板已复制 |
| `pom.xml` | `pyproject.toml` + `requirements.txt` | 见附录 A |
| `EcBusinessApiApplication.java` | `app/main.py`（编排）+ `.../EcBusinessApiApplication.py`（同名镜像） | Spring Boot 启动类 → FastAPI lifespan |

### 1.3 运行形态

| Spring Boot | Python 侧 | 位置 |
|---|---|---|
| `@SpringBootApplication` + `SpringApplication.run` | `FastAPI` 实例 + `uvicorn` | `app/main.py` |
| `DispatcherServlet` + `RequestMappingHandlerMapping` | 启动时把 85 条路由逐条 `app.add_api_route` | `app/routes/registry.py`、`app/routes/generated.py` |
| `HandlerMethodArgumentResolver` | `_bind_arguments()`，按 `source` 分派 6 种绑定 | `app/web/binding.py` |
| `MappingJackson2HttpMessageConverter` | `JacksonResponse`（orjson） | `app/web/responses.py` |
| `BasicErrorController` | `error_response()`（含 `include-message=never` 语义） | `app/web/errors.py` |
| `@EnableScheduling` + `TaskScheduler` | `app/scheduler/registry.py` | 见 5.11 |
| `@PostConstruct` | `__init__` 末尾显式调用 `self.init()` | 各业务类 |
| `@Autowired` | 构造器可选参数 + 缺省 `XxxServiceImpl()` | 各业务类 |

启动装配顺序（`app/main.py` lifespan）：

```text
1. logging_config.setup()                  <- logback-spring.xml
2. _install_persistence()                  <- DataSource + MapperRegistry.install()
3. _register_health_probes()               <- /health（迁移新增，Java 无）
4. start_scheduler() if app.scheduler.enabled
5. yield  -> 服务对外
6. shutdown_scheduler() -> engine.dispose()
```

---

## 2. 模块映射（219 个 Java 文件）

### 2.1 `pro-business-api`：17 个包

| 包 | Java 文件 / 行 | Py 文件 / 行 | 职责 | 代表性类 |
|---|---|---|---|---|
| `com.ruoyi` | 1 / 31 | 1 / 118 | 启动类 | `EcBusinessApiApplication` |
| `base` | 2 / 39 | 2 / 140 | 常量与测试标记 | `HasStatic`、`Test` |
| `base.config` | 4 / 413 | 4 / 509 | Kafka/Pulsar/线程池/调度配置 | `KafkaProducerConfig`、`SchedulingConfig` |
| `base.controller` | 24 / 2,488 | 24 / 2,683 | REST 入口（85 个 handler） | `OdsSzdnTollController` |
| `base.device` | 1 / 274 | 1 / 327 | 设备数据模拟器 | `DeviceDataSimulator` |
| `base.domain` | 30 / 4,672 | 30 / 3,423 | 实体/VO/DTO（22 张表） | `OdsSzdnToll`、`TrailBo` |
| `base.flink` | 1 / 640 | 1 / 728 | Flink 轨迹聚合 Job | `VehicleTrackFlinkJob` |
| `base.forest` | 1 / 17 | 1 / 80 | 外部 HTTP 声明式客户端 | `HttpSysUtilApiService` |
| `base.mapper` | 23 / 973 | 23 / 1,761 | MyBatis-Plus Mapper 接口 | `ZdataTrailTracksMapper` |
| `base.service` | 23 / 1,035 | 23 / 1,568 | 服务接口（`IXxxService`） | `ISysUtilService` |
| `base.service.impl` | 34 / 9,645 | 34 / 9,754 | 服务实现 + MQ 消费/生产者 | `SysUtilServiceImpl`（2,444 行） |
| `base.service.optimization` | 13 / 4,680 | 13 / 5,491 | 亿级查询/导出/一致性 | `UnifiedQueryService`、`BillionLevelQueryService` |
| `base.task` | 3 / 470 | 3 / 595 | 定时任务 | `TrackTask`、`DataFlowTask`、`CarTask`※ |
| `mq.config` | 2 / 186 | 2 / 268 | ES / RabbitMQ 配置 | `ElasticsearchConfig` |
| `mq.consumer` | 1 / 82 | 1 / 101 | RocketMQ 消费者 | `RocketMqConsumer` |
| `mq.producer` | 1 / 191 | 1 / 203 | RocketMQ 生产者 | `RocketMqProducer` |
| `mq.service` | 2 / 407 | 2 / 375 | 消息处理 / ES 查询 | `DataProcessService`、`EsQueryService` |

※ `CarTask.java` 整个文件被 `/* ... */` 注释，javac 编译后不存在该类；Python 侧同样**不定义类**（见 5.11.3）。

### 2.2 `pro-base-common`：17 个包

| 包 | Java | Py | 职责 |
|---|---|---|---|
| `common.annotation` | 1 | 1 | `@Excel` |
| `common.config` | 6 | 6 | Redis / fastjson2 / Orika / Spark / 线程池序列化 |
| `common.config.annotation` | 2 | 2 | `@PermissionAnon`、`@ValidHeader` |
| `common.config.base` | 1 | 1 | `Result` |
| `common.config.interceptor` | 2 | 2 | `SecurityInterceptor`、`WebConfig` |
| `common.config.writer` | 1 | 1 | `RetRedisCacheWriter` |
| `common.constant` | 6 | 6 | `HttpStatus`、`Constants`、`CacheConstants` 等 |
| `common.core.controller` | 1 | 1 | `BaseController`（分页入口） |
| `common.core.domain` | 9 | **10** | `AjaxResult`、`R`、`TableDataInfo` … + **`JavaBean`** |
| `common.core.page` | 3 | 3 | `PageDomain`、`TableSupport`、`TableDataInfo` |
| `common.core.redis` | 3 | 3 | `RedisCache`、`RedisConfig`、`RedisSourceFactory` |
| `common.core.text` | 3 | 3 | `Convert`、`StrFormatter`、`CharsetKit` |
| `common.exception` | 1 | 1 | `UtilException` |
| `common.exception.base` | 1 | 1 | `BaseException` |
| `common.utils` | 11 | 11 | `StringUtils`、`DateUtils`、`ServletUtils`、`PageUtils` … |
| `common.utils.spring` | 1 | 1 | `SpringUtils`（容器查找） |
| `common.utils.sql` | 1 | 1 | `SqlUtil`（SQL 注入过滤） |

唯一的 `+1` 文件是 `com/ruoyi/common/core/domain/JavaBean.py`：Lombok `@Data` 在 Python 侧没有注解处理器，改由基类用 `__getattr__`/`__setattr__` 动态生成 `getXxx()/setXxx()/isXxx()`，**并保留 `@Accessors(chain = true)` 的返回 `self` 语义**。这样 30 个实体类里 3,000 多处 `getter/setter` 调用点（`track.setCarNo(...)`、`vo.getStartTime()`）无需改写。

### 2.3 框架替身层（171 文件 / 14,462 行）

| 顶层包 | 文件 / 行 | 覆盖的 Java 生态 |
|---|---|---|
| `com` | 11 / 1,496 | `com.alibaba.fastjson2`（`JSON`/`JSONObject`/`JSONArray`）、`com.baomidou.mybatisplus`（`BaseMapper`/`IService`/`ServiceImpl`/`QueryWrapper`/`LambdaQueryWrapper`）、`com.fasterxml.jackson.databind`（`ObjectMapper`/`JsonNode`）、`com.github.pagehelper.PageInfo` |
| `java` | 28 / 2,594 | `java.lang`（`String`/`System`/`Thread`/`Runtime`）、`java.util`（`Date`/`Calendar`/`HashMap`/`Executors`/`CompletableFuture`…）、`java.time`（`LocalDateTime`…）、`java.math.BigDecimal`、`java.text.SimpleDateFormat`、`java.sql.Timestamp` |
| `javax` | 2 / 54 | `@PostConstruct`、`@PreDestroy` |
| `org` | 130 / 10,318 | `org.springframework`（26：`@Scheduled`、`Environment`、`KafkaTemplate`、`RedisTemplate`…）、`org.elasticsearch`（51）、`org.apache.flink`（53） |

> 替身层是**唯一允许“不逐行等价”的区域**：它只保证“Java 写法的调用点在 Python 里能跑且语义相同”，内部实现可以是进程内模拟（见 5.5–5.9）。每个替身文件头都写明与原 API 的差异清单。

### 2.4 类/语法映射速查

| Java | Python | 规则 |
|---|---|---|
| `@Service` / `@Repository` / `@Component` | 普通类 + `SpringUtils` 注册 | 注解保留语义，无运行期副作用 |
| `@Autowired` 字段注入 | 构造器可选参数，缺省 `XxxServiceImpl()` | 保持“单例共享”的装配关系（同一 Bean 只建一次） |
| `@Value("${k:default}")` | `Environment.value("${k:default}", int)` | 占位符解析器与 Spring 同规则（见 5.1） |
| `@Data` / `@Accessors(chain)` | `@dataclass` + `JavaBean` | setter 返回 `self` |
| `@TableName` / `@TableId` | 类属性 `TABLE_NAME` / `field(metadata=...)` | 纯元信息 |
| 匿名内部类（回调） | 模块级 `_XxxCallback` 类 | 持有外部 `service` + 参数 |
| `List<T>` / `Map<K,V>` | `list[T]` / `dict[K, V]` | —— |
| `Long` / `Integer` | `int` | 无装箱/拆箱 |
| `BigDecimal` | `Decimal`（计算）/ `float`（DTO 输出） | 见 4.4 |
| `Date` / `Timestamp` | `datetime` | 见 4.4 |
| `Optional<T>` | `Optional[T]` | 保留 `isPresent()` 写法 |
| `Stream().filter().map().collect()` | 列表推导 / `filter` + `map` | 惰性/求值差异已在注释标注 |
| `try-with-resources` | `with` | —— |
| `catch (Exception e)` | `except Exception as e` | 受检异常无对应物 |
| 方法重载 | 单方法 + 按参数类型分派 | 例：`AjaxResult.success(...)` 的 4 个重载 |

---

## 3. REST 路由（85 条）

### 3.1 生成与校验

路由表不是手写的：`tools/gen_routes.py` 解析 24 个 `*Controller.java` 的 `@RequestMapping/@GetMapping/@PostMapping`，生成 `app/routes/generated.py`（1,108 行，文件头标注 `DO NOT EDIT`）；`app/routes/registry.py` 在启动时把每条记录注册成 FastAPI 路由。

```text
控制台实测（tools\check_routes.py）：
  controllers : 24
  handlers    : 85
  verbs       : GET=79, POST=6
  param kinds : body=3, model=25, param=65, param_map=5, path=23
```

`check_routes.py` 会反向比对“Java 注解里的路径集合”与“FastAPI 实际注册的路径集合”，任何一侧多/少一条都会报 `MISS`/`EXTRA`。

### 3.2 参数来源（对应 Spring 的 HandlerMethodArgumentResolver）

| `source` | Spring 写法 | Python 绑定 | 条数 |
|---|---|---|---|
| `path` | `@PathVariable` | 从 `path_params` 取，`{name}` 与参数名必须一致 | 23 |
| `param` | `@RequestParam("x")` | 取**第一个**同名查询参数；无则 `None`/默认值 | 65 |
| `param_map` | `@RequestParam Map<String,String>` | 收集**全部**查询参数成 dict | 5 |
| `body` | `@RequestBody` | `await request.json()` → orjson 解析 | 3 |
| `model` | 无注解 POJO（`@ModelAttribute` 风格） | 按字段名从查询参数逐字段赋值 | 25 |
| —— | `HttpServletRequest/Response` | 不纳入 `params`，运行时注入 | —— |

### 3.3 全量路由表（85 条）

> `参数`列只列**业务参数**；`pageNum/pageSize` 统一由 `PageDomain`/`TableSupport` 解析。

#### `DwdLcztFwqjcxxController` — `/base/fwqjcxx`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/fwqjcxx/list` | `list` | `TableDataInfo` | `dwdLcztFwqjcxx:model` |
| GET | `/base/fwqjcxx/{agentPk}` | `getInfo` | `AjaxResult` | `agentPk:path` |
| GET | `/base/fwqjcxx/listAll` | `getListAll` | `List<DwdLcztFwqjcxx>` | —— |

#### `DwdLcztSfsjcxxController` — `/base/sfsjcxx`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/sfsjcxx/list` | `list` | `TableDataInfo` | `dwdLcztSfsjcxx:model` |
| GET | `/base/sfsjcxx/{agentPk}` | `getInfo` | `AjaxResult` | `agentPk:path` |
| GET | `/base/sfsjcxx/listAll` | `getListAll` | `List<DwdLcztSfsjcxx>` | —— |

#### `DwdLcztSfzjcxxController` — `/base/sfzjcxx`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/sfzjcxx/list` | `list` | `TableDataInfo` | `dwdLcztSfzjcxx:model` |
| GET | `/base/sfzjcxx/{agentPk}` | `getInfo` | `AjaxResult` | `agentPk:path` |
| GET | `/base/sfzjcxx/listAll` | `getListAll` | `List<DwdLcztSfzjcxx>` | —— |

#### `OdsCxztFwqcllsController` — `/manager/fwqclls`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/manager/fwqclls/list` | `list` | `TableDataInfo` | `odsCxztFwqclls:model` |
| GET | `/manager/fwqclls/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |

#### `OdsLwzxsfsjFeeGantryFusion01Controller` — `/base/feeGantry`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/feeGantry/list` | `list` | `TableDataInfo` | `odsLwzxsfsjFeeGantryFusion01:model` |
| GET | `/base/feeGantry/{bigId}` | `getInfo` | `OdsLwzxsfsjFeeGantryFusion01` | `bigId:path` |

#### `OdsLwzxsfsjFeeRecords01Controller` — `/base/feerecords`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/feerecords/list` | `list` | `TableDataInfo` | `odsLwzxsfsjFeeRecords01:model` |
| GET | `/base/feerecords/listToExport` | `listToExport` | `List<OdsLwzxsfsjFeeRecords01>` | `odsLwzxsfsjFeeRecords01:model` |
| GET | `/base/feerecords/{bigId}` | `getInfo` | `OdsLwzxsfsjFeeRecords01` | `bigId:path` |

#### `OdsLwzxsfsjFeeStationEnter01Controller` — `/base/feeStationEnter`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/feeStationEnter/list` | `list` | `TableDataInfo` | `odsLwzxsfsjFeeStationEnter01:model` |
| GET | `/base/feeStationEnter/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |

#### `OdsLwzxsfsjFeeStationExit01Controller` — `/base/feestationexit`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/feestationexit/list` | `list` | `TableDataInfo` | `odsLwzxsfsjFeeStationExit01:model` |
| GET | `/base/feestationexit/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |

#### `OdsRtSzdnSnapshotFlowAddcodeController` — `/base/snapshotflow`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/snapshotflow/list` | `list` | `TableDataInfo` | `odsRtSzdnSnapshotFlowAddcode:model` |
| GET | `/base/snapshotflow/listToExport` | `listToExport` | `List<...Addcode>` | `odsRtSzdnSnapshotFlowAddcode:model` |
| GET | `/base/snapshotflow/{bigId}` | `getInfo` | `OdsRtSzdnSnapshotFlowAddcode` | `bigId:path` |

#### `OdsRtSzdnSnapshotFlowProvcaptureAddcodeController` — `/base/provcapture`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/provcapture/list` | `list` | `TableDataInfo` | `odsRtSzdnSnapshotFlowProvcaptureAddcode:model` |
| GET | `/base/provcapture/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |

#### `OdsRtSzdnSnapshotFlowStationcaptureAddcodeController` — `/base/stationcapture`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/stationcapture/list` | `list` | `TableDataInfo` | `odsRtSzdnSnapshotFlowStationcaptureAddcode:model` |
| GET | `/base/stationcapture/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |

#### `OdsSzdnGantryController` — `/base/gantry`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/gantry/list` | `list` | `TableDataInfo` | `odsSzdnGantry:model` |
| GET | `/base/gantry/{id}` | `getInfo` | `AjaxResult` | `id:path` |
| GET | `/base/gantry/listAll` | `getListAll` | `List<OdsSzdnGantry>` | —— |

#### `OdsSzdnGantryIpController` — `/base/gantryIp`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/gantryIp/list` | `list` | `TableDataInfo` | `odsSzdnGantryIp:model` |
| GET | `/base/gantryIp/{id}` | `getInfo` | `AjaxResult` | `id:path` |

#### `OdsSzdnProvinceBorderVehicleWeightNewstructureController` — `/base/vehicleweight`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/vehicleweight/list` | `list` | `TableDataInfo` | `odsSzdnProvinceBorderVehicleWeightNewstructure:model` |
| GET | `/base/vehicleweight/{dataSource}` | `getInfo` | `AjaxResult` | `dataSource:path` |
| GET | `/base/vehicleweight/map` | `map` | `AjaxResult` | —— |

> 注意顺序：`/map` 与 `/{dataSource}` 同为两段路径。Spring 的 `AntPathMatcher` 让**字面量**优先于变量，`app/routes/registry.py` 用 `_specificity()`（`(URI 变量个数, -路径长度)`）重排后注册，因此**无论注解顺序如何**，`/map` 都不会被 `{dataSource}` 吃掉。

#### `OdsSzdnSectionController` — `/base/section`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/section/list` | `list` | `TableDataInfo` | `odsSzdnSection:model` |
| GET | `/base/section/{id}` | `getInfo` | `AjaxResult` | `id:path` |
| GET | `/base/section/listAll` | `getListAll` | `List<OdsSzdnSection>` | —— |

#### `OdsSzdnTollController` — `/base/toll`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/toll/list` | `list` | `TableDataInfo` | `odsSzdnToll:model` |
| GET | `/base/toll/{id}` | `getInfo` | `AjaxResult` | `id:path` |
| GET | `/base/toll/listAll` | `getListAll` | `List<OdsSzdnToll>` | —— |

#### `OdsSzdnTollStationIpController` — `/base/tollStationIp`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/tollStationIp/list` | `list` | `TableDataInfo` | `odsSzdnTollStationIp:model` |
| GET | `/base/tollStationIp/{id}` | `getInfo` | `AjaxResult` | `id:path` |

#### `OdsYhglVBaseOrgController` — `/base/org`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/org/list` | `list` | `TableDataInfo` | `odsYhglVBaseOrg:model` |
| GET | `/base/org/{bigId}` | `getInfo` | `AjaxResult` | `bigId:path` |
| GET | `/base/org/listAll` | `getListAll` | `List<OdsYhglVBaseOrg>` | —— |

#### `ZdataTrailTracksController` — `/base/trailtracks`（2）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/trailtracks/list` | `list` | `TableDataInfo` | `zdataTrailTracks:model` |
| GET | `/base/trailtracks/{uuid}` | `getInfo` | `AjaxResult` | `uuid:path` |

#### `SysUtilController` — `/base/sysutil`（5）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/base/sysutil/saveRedis` | `saveRedis` | `AjaxResult` | `sysUtil:model` |
| GET | `/base/sysutil/carTrackQueryByCarNo` | `carTrackQueryByCarNo` | `TableDataInfo` | `carParaVO:model` |
| GET | `/base/sysutil/carTrackQueryByTime` | `carTrackQueryByTime` | `TableDataInfo` | `carParaVO:model` |
| POST | `/base/sysutil/changeTrailInfo` | `changeTrailInfo` | `TrailInfo` | `trailInfo:body` |
| GET | `/base/sysutil/getByTrailBo` | `getByTrailBo` | `TrailBo` | `trailBo:model` |

#### `SysTestController` — `/base/sysutilTest`（15）
全部返回 `void`（Spring 语义：响应体为空、状态 200），全部无参数；处理函数名与路径末段同名。

| 方法 | 路径 | 处理函数 | 返回 |
|---|---|---|---|
| GET | `/base/sysutilTest/syncCurrentTrack` | `syncCurrentTrack` | `void` |
| GET | `/base/sysutilTest/syncBaseInfo` | `syncBaseInfo` | `void` |
| GET | `/base/sysutilTest/syncHistroyTrack` | `syncHistroyTrack` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar1` | `syncSuspiciousCar1` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar2` | `syncSuspiciousCar2` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar3` | `syncSuspiciousCar3` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar4` | `syncSuspiciousCar4` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar5` | `syncSuspiciousCar5` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar6` | `syncSuspiciousCar6` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar7` | `syncSuspiciousCar7` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar8` | `syncSuspiciousCar8` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar9` | `syncSuspiciousCar9` | `void` |
| GET | `/base/sysutilTest/syncSuspiciousCar10` | `syncSuspiciousCar10` | `void` |
| GET | `/base/sysutilTest/syncOdsSzdnGantry` | `syncOdsSzdnGantry` | `void` |
| GET | `/base/sysutilTest/separateSnapshotFlowTimeList` | `separateSnapshotFlowTimeList` | `void` |

> 这 15 个 GET 会**触发数据写入**（同步门架/轨迹）。Spring 不做方法级副作用检查，Python 侧照搬；生产误触发风险与原系统一致。

#### `LargeScaleQueryController` — `/api/v1/large`（10）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/api/v1/large/snapshot` | `querySnapshotFlow` | `Map<String,Object>` | `startTime`、`endTime`、`fuzzyFields:param_map`、`pageNum`、`pageSize` |
| GET | `/api/v1/large/fee` | `queryFeeRecords` | `Map<String,Object>` | 同上 |
| GET | `/api/v1/large/trail` | `queryTrail` | `Map<String,Object>` | 同上 |
| GET | `/api/v1/large/carTrackQueryByCarNo` | `queryCarTrackByCarNo` | `Map<String,Object>` | `carNo`、`startTime`、`endTime`、`pageNum`、`pageSize` |
| GET | `/api/v1/large/stats/group` | `groupByStats` | `Map<String,Object>` | `type`、`startTime`、`endTime`、`groupBy`、`countField`、`fuzzyFields:param_map`、`topN` |
| POST | `/api/v1/large/export/submit` | `submitExport` | `Map<String,Object>` | `type`、`startTime`、`endTime`（query）+ `fuzzyFields:body` |
| GET | `/api/v1/large/export/status/{taskId}` | `getExportStatus` | `Map<String,Object>` | `taskId:path` |
| POST | `/api/v1/large/sync/full` | `triggerFullSync` | `Map<String,Object>` | —— |
| POST | `/api/v1/large/sync/incremental` | `triggerIncrementalSync` | `Map<String,Object>` | —— |
| POST | `/api/v1/large/sync/repair` | `triggerRepairSync` | `Map<String,Object>` | `type`、`startTime`、`endTime` |

#### `UnifiedQueryController` — `/api/v1/unified`（3）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/api/v1/unified/{ds}/list` | `list` | `Map<String,Object>` | `ds:path`、`startTime`、`endTime`、`fuzzyFields:param_map`、`pageNum`、`pageSize` |
| POST | `/api/v1/unified/{ds}/export/submit` | `submitExport` | `Map<String,Object>` | `ds:path`、`startTime`、`endTime`、`fuzzyFields:body` |
| GET | `/api/v1/unified/export/status/{taskId}` | `getExportStatus` | `Map<String,Object>` | `taskId:path` |

#### `ProgressiveQueryController` — `/progressive`（4）
| 方法 | 路径 | 处理函数 | 返回 | 参数 |
|---|---|---|---|---|
| GET | `/progressive/snapshotflow/list` | `snapshotFlowList` | `TableDataInfo` | 10 个（见下） |
| GET | `/progressive/feerecords/list` | `feeRecordsList` | `TableDataInfo` | 10 个 |
| GET | `/progressive/trailfitting/list` | `trailFittingList` | `TableDataInfo` | 10 个 |
| GET | `/progressive/scale-level` | `scaleLevel` | `AjaxResult` | —— |

三条 list 的参数完全一致：`startTime`、`endTime`、`platenumber`、`gantryname`、`roadname`、`sectionname`、`orgname`、`tollname`、`cursor`、`pageSize`（游标分页，**不走** PageHelper）。

### 3.4 响应契约

| Java 返回类型 | JSON 形态 | 实现 |
|---|---|---|
| `AjaxResult`（`extends HashMap`） | `{"code":200,"msg":"操作成功","data":...}`，`data` 为 null 时**不出现该键** | `AjaxResult(dict)` |
| `TableDataInfo` | `{"total":n,"rows":[...],"code":200,"msg":"查询成功"}`（由 `BaseController.getDataTable` 填充） | `TableDataInfo` |
| `R<T>` | `{"code":..,"msg":..,"data":..}` 泛型体 | `R` |
| `Map<String,Object>` | 直接序列化 | `JacksonResponse` |
| 实体 / VO | 字段名转回 **camelCase**；缩写名（`gantryCaptureBO`）从 `app/compat/java_meta.py` 读精确名 | `app/web/serializer.py`（175 行） |
| `void` | 空 body，200 | `Response(status_code=200)` |

序列化差异（`app/web/responses.py`）：

```python
# Jackson writes {"1": ...} for non-string map keys; orjson needs OPT_NON_STR_KEYS.
# Jackson rejects NaN/Infinity by default -- orjson does too, so no option needed.
orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)
```

- **无 `charset=utf-8`**：Spring 的 `MappingJackson2HttpMessageConverter` 对 `application/json` 不加 charset，Python 侧刻意保持一致（`media_type = "application/json"`）。
- **null 字段照常输出**：Jackson 默认 `Include.ALWAYS`，所以 `"createTime": null` 会出现在响应里；这也是 MyBatis 侧必须 `call-setters-on-nulls: true` 的原因。
- **字段名是 camelCase**：Python 类里的 `car_no` 输出前由 `snake_to_camel` 转成 `carNo`；`gantryCaptureBO` 这类缩写无法从 snake_case 反推，由 `tools/gen_java_meta.py` 生成映射表 `app/compat/java_meta.py`（1,229 行）。
- **时区偏移是原行为**：`application.yml` 没有 `spring.jackson.time-zone`，Jackson 默认 UTC；而 JDBC 会话是 `serverTimezone=Asia/Shanghai`。因此 GaussDB 读出的 naive `datetime` 会**先当上海时间再转 UTC** 输出（比本地时间少 8 小时）。这看起来像 bug，但 Java 侧一直如此，已原样复刻；可用 `CAR_MONIT_DB_TIMEZONE` / `CAR_MONIT_JSON_TIMEZONE` 覆盖。
- **`@JsonFormat(pattern=...)`** 由 `java_pattern_to_strftime` 转成 strftime 模板；没有 pattern 的日期输出 ISO-8601（带毫秒与偏移）。
- **异常体**：项目没有 `@ControllerAdvice`，所有未捕获异常走 Spring Boot `BasicErrorController` → `{"timestamp","status","error","path"}`，且 `server.error.include-message=never` 使 `message` 键**缺失**。`app/web/errors.py` 逐字段复刻（含 `+00:00` 时区写法）。
- **HTTP 状态码**：业务错误一律 `200` + `code=500`（RuoYi 惯例），只有未捕获异常才是 5xx。

### 3.5 被刻意保留的缺陷

| 缺陷 | 位置 | 复刻方式 |
|---|---|---|
| `@RequestParam Map<String,String>` 拿到的是**全部**请求参数（含 `pageNum/pageSize`），而非“业务筛选字段” | `LargeScaleQueryController` 3 处、`UnifiedQueryController` 1 处 + `ProgressiveQueryController` | `param_map` 源如实收集**全部** query；`fuzzyFields` 里的分页键也会被当成模糊匹配字段 —— 与 Spring 完全一致 |
| `listAll` 与 `{id}` 路径同为两段，注解里 `listAll` 在后 | 7 个控制器 | 由 `_specificity()` 重排（字面量优先），与 Spring 一致 |
| `SysTestController` 用 GET 做写操作 | 15 条路由 | 原样保留 |
| `separateSnapshotFlowTimeList` 里 `SimpleDateFormat` 非线程安全 | `SysUtilServiceImpl` | 每次调用新建实例（Java 侧是局部变量，同样非共享） |

---

## 4. ORM / 表映射

### 4.1 三条数据通路

```text
                    ┌─────────────────────────────────────────────┐
业务代码            │ serviceImpl.mapper.selectXxx(...)            │  写法与 Java 一致
                    └───────────────┬─────────────────────────────┘
                                    │
        ┌───────────────────────────┼──────────────────────────────┐
        │                           │                              │
  [A] 内存 BaseMapper        [B] XML 动态 SQL 引擎          [C] SQLAlchemy + psycopg
  (无数据库 / 测试)          (app/db/xml_mapper.py)          (app/db/engine.py)
  进程内 list/dict 表         <if>/<foreach>/<where>           GaussDB 连接池
```

**选择逻辑**：`app/main.py` 启动时若 `app.db.enabled`（默认跟随 `spring.datasource` 可用性）则执行 `_install_persistence()`，用 XML statement 覆盖 Mapper 接口方法；否则保持 [A] 内存实现。**同一份业务代码在两种模式下都能跑**，这是路由冒烟（85/85 不连库）与联调（连 GaussDB）能共用一套代码的原因。

| 通路 | 对应 Java | 位置 |
|---|---|---|
| [A] | MyBatis-Plus `BaseMapper` 的 CRUD 子集 | `com/baomidou/mybatisplus/core/mapper/BaseMapper.py`、`app/db/base_mapper.py` |
| [B] | `org.apache.ibatis.session.Configuration` + `XMLMapperBuilder` | `app/db/xml_mapper.py`（703 行）、`app/db/expr.py`（OGNL `test` 表达式，349 行）、`app/db/registry.py`（291 行） |
| [C] | Druid + `dynamic-datasource` 单 `master` | `app/db/engine.py`（231 行） |
| 分页 | PageHelper 1.4.7 + `PageInfo` | `app/db/pagination.py`（160 行） |
| 主键 | MyBatis-Plus `ASSIGN_ID` / `ASSIGN_UUID` | `app/db/snowflake.py`（109 行） |

### 4.2 表映射（22 张表 / 30 个 domain 类）

| 实体（Python = Java 同名） | `@TableName` | 主键策略 | Mapper |
|---|---|---|---|
| `DwdLcztFwqjcxx` | `dwd_lczt_fwqjcxx` | 见 `@TableId` 元信息 | ✔ |
| `DwdLcztSfsjcxx` | `dwd_lczt_sfsjcxx` | 同上 | ✔ |
| `DwdLcztSfzjcxx` | `dwd_lczt_sfzjcxx` | 同上 | ✔ |
| `OdsCxztFwqclls` | `ods_cxzt_fwqclls` | 同上 | ✔ |
| `OdsLwzxsfsjFeeGantryFusion01` | `ods_lwzxsfsj_fee_gantry_fusion_01` | 同上 | ✔ |
| `OdsLwzxsfsjFeeRecords01` | `ods_lwzxsfsj_fee_records_01` | 同上 | ✔ |
| `OdsLwzxsfsjFeeStationEnter01` | `ods_lwzxsfsj_fee_station_enter_01` | 同上 | ✔ |
| `OdsLwzxsfsjFeeStationExit01` | `ods_lwzxsfsj_fee_station_exit_01` | 同上 | ✔ |
| `OdsRtSzdnSnapshotFlowAddcode` | `ods_rt_szdn_snapshot_flow_addcode` | 同上 | ✔ |
| `OdsRtSzdnSnapshotFlowProvcaptureAddcode` | `ods_rt_szdn_snapshot_flow_provcapture_addcode` | 同上 | ✔ |
| `OdsRtSzdnSnapshotFlowStationcaptureAddcode` | `ods_rt_szdn_snapshot_flow_stationcapture_addcode` | 同上 | ✔ |
| `OdsSzdnGantry` | `ods_szdn_gantry` | 同上 | ✔ |
| `OdsSzdnGantryIp` | `ods_szdn_gantry_ip` | 同上 | ✔ |
| `OdsSzdnProvinceBorderVehicleWeightNewstructure` | `ods_szdn_province_border_vehicle_weight_newstructure` | 同上 | ✔ |
| `OdsSzdnSection` | `ods_szdn_section` | 同上 | ✔ |
| `OdsSzdnToll` | `ods_szdn_toll` | `id` / `ASSIGN_UUID` | ✔ |
| `OdsSzdnTollStationIp` | `ods_szdn_toll_station_ip` | 同上 | ✔ |
| `OdsYhglVBaseOrg` | `ods_yhgl_v_base_org` | 同上 | ✔ |
| `ZdataLocationDict` | `zdata_location_dict` | 同上 | ✔ |
| `ZdataTrailFitting` | `zdata_trail_fitting` | 同上 | ✔ |
| `ZdataTrailTracks` | `zdata_trail_tracks` | 同上 | ✔ |
| `KafkaMessageRecord` | `kafka_message_record` | 同上 | ✔ |

非表对象（8 个，纯 VO/DTO，**没有** `TABLE_NAME`）：`CarVO`、`CarParaVO`、`SuspiciousCarVO`、`TrailBo`、`TrailInfo`、`TrailTracksVo`、`SysUtil`、`PulsarMessageRecord`。

> `PulsarMessageRecord` 没有 `@TableName` 是 Java 原样：它不走 MyBatis-Plus 的 CRUD，三个方法全部用 `@Select`/`@Update` 手写 SQL，表名带 schema 前缀硬编码在语句里（`jl_data01.pulsar_message_record`），所以 Java 与 Python 两侧都不需要表名元信息。

### 4.3 Mapper 映射

`tools/check_mappers.py` 实测：

```text
mapper XML files : 22
statements       : 54
sql fragments    : 19
bound methods    : 58
without XML      : 6
```

| 项 | 数量 | 说明 |
|---|---|---|
| Mapper 接口 | 23 | `pro-business-api/.../base/mapper/*.py` |
| Mapper XML | 22 | **位于 `src/main/java/com/ruoyi/base/mapper/xml/`**（不是 `resources`，原项目就这样） |
| `<select>` 语句 | 54 | 其中 **52 个 select + 2 个 update**（`KafkaMessageRecordMapper` 的 `incrementRetryCount` / `updateStatusById`） |
| `<sql>` 片段 | 19 | `registry.py` 把片段同时按 `id` 和 `namespace.id` 编入索引 |
| 绑定到 XML 的方法 | 58 | 运行时用生成的函数**替换**接口方法 |
| 只有内存实现的方法 | 6 | 见下 |

**XML 不复制**：`app/db/registry.py` 直接读原 Java 目录，理由是 XML 是唯一事实来源，复制会产生两份需要同步的 SQL：

```python
# The mapper XMLs are *not* duplicated into the Python tree: the migration keeps
# the original files as the single source of truth, so the classpath is the Java
# project itself (``car-monit-api-python/`` sits inside it).
_JAVA_ROOT = _PROJECT_ROOT.parent
_CLASSPATH_ROOTS = tuple(
    base / module / "src" / "main" / source_set
    for base in (_JAVA_ROOT, _PROJECT_ROOT)
    for module in _MODULE_ROOTS
    for source_set in ("java", "resources")
)
_DEFAULT_LOCATIONS = "classpath*:com/ruoyi/base/**/xml/*Mapper.xml"
```

6 个“没有 XML/注解”的方法（`check_mappers.py` 会告警，调用时按 MyBatis 语义抛异常）：

```text
OdsLwzxsfsjFeeRecords01Mapper#selectGantryNum
OdsLwzxsfsjFeeRecords01Mapper#selectOdsLwzxsfsjFeeRecords01ById
OdsLwzxsfsjFeeRecords01Mapper#selectOdsLwzxsfsjFeeRecords01List
OdsLwzxsfsjFeeRecords01Mapper#selectOdsLwzxsfsjFeeRecords01ListNew
ZdataTrailFittingMapper#selectZdataTrailFittingById
ZdataTrailFittingMapper#selectZdataTrailFittingList
```

这 6 个方法在 Java 侧同样没有 XML 对应（`OdsLwzxsfsjFeeRecords01Mapper.xml` 只有 `selectByCursorShard`），**是原项目的历史遗留**。区别在于：Java 里调用会抛 `BindingException`，Python 侧当前走内存实现（不抛）。这是第 8 章“已知偏差”里唯一功能性的一条。

**注解 SQL**：`PulsarMessageRecordMapper` 用 `@Select`/`@Update` 而非 XML。Python 侧把原 SQL **逐字保留在 docstring**，实现改为 `selectWhere`/`updateWhere` 的等价过滤：

```python
# Java (verbatim, kept for diff):
#   @Update("UPDATE jl_data01.pulsar_message_record " +
#           "SET status = 2, retry_count = retry_count + 1, error_msg = #{errorMsg} " +
#           "WHERE id = #{id}")
return self.updateWhere(lambda r: r.id == id, lambda r: {"status": 2, ...})
```

### 4.4 类型映射

| Java | Python | 边界说明 |
|---|---|---|
| `Long` / `Integer` / `int` | `int` | 无装箱；`null` → `None`（Java 的 `Integer` 可以是 null，`int` 不行） |
| `BigDecimal` | `Decimal` | `java/math/BigDecimal.py` 提供 `add/subtract/multiply/divide/setScale/compareTo`；**除法必须显式 `setScale`**，否则与 Java 一样抛 `ArithmeticException` |
| `Double` / `Float` | `float` | —— |
| `String` | `str` | 实例方法用 Python 原生写法（`trim()`→`strip()`、`substring(a,b)`→`s[a:b]`、`equalsIgnoreCase`→`casefold()`）；`java/lang/String.py` 只提供 Java 静态方法：`String.format/valueOf/join/hashCode`。业务侧的判空/拼接方法仍在 `com/ruoyi/common/utils/StringUtils.py`（1:1 移植） |
| `Date` / `Timestamp` | `datetime` | 时区沿用 `application.yml` 的 `serverTimezone` |
| `LocalDateTime` / `LocalDate` | `datetime.date/datetime` | `java/time/*` 替身 |
| `boolean` / `Boolean` | `bool` | —— |
| `Map<String,Object>` | `dict[str, Any]` | 键保持插入顺序（Java `HashMap` 无序，但 Jackson 输出顺序不稳定，此处反而更稳定——已在注释标注） |
| `List<T>` / `Set<T>` | `list[T]` / `set[T]` | —— |
| 枚举 | `enum.Enum` | 序列化时输出 `name`（与 Jackson 默认一致） |

### 4.5 分页

`PageHelper.startPage(pageNum, pageSize)` 的三个副作用在 `app/db/pagination.py` 中复刻：

```text
1. 先跑 SELECT count(0) FROM ( <去掉 ORDER BY 的原语句> ) tmp_count
2. reasonable=true 时把 pageNum 夹到 [1, pages]     <- 越界不报错，返回最后一页
3. 原语句追加 LIMIT ? OFFSET ?
4. 计数通过 PageUtils.set_page_total 交给 new PageInfo(list).getTotal()
```

`TableSupport` 的默认值与原项目一致：`pageNum` 缺省 1，`pageSize` 缺省 10，`orderBy` 由 `PageDomain` 的 `orderByColumn` + `isAsc` 拼接，并经 `SqlUtil.escapeOrderBySql` 过滤。

---

## 5. 逐子系统「差异与原因」

> 每个小节固定三段：**Java 怎么做的 → Python 怎么做 → 为什么必须不一样（或为什么可以不一样）**。
> 判断标准：*能逐行等价的一律逐行等价；只有 JVM/容器免费提供的能力才允许换实现。*

### 5.1 配置：`application.yml` + `@Value`

**Java**：Spring Boot 启动时用 SnakeYAML 解析 `application.yml`，把 `@Value("${a.b:默认}")` 的占位符在 Bean 初始化阶段解析；优先级为「环境变量 > yml > 占位符内联默认值」。

**Python**：`org/springframework/core/env/Environment.py`（195 行）+ `app/settings.py`（287 行）。

```text
Environment.getProperty(key, default)
  ├── os.environ[key 的 SCREAMING_SNAKE 形式]     <- RelaxedBinding 子集
  ├── 扁平化的 application.yml
  └── default
```

三个必须知道的差异：

1. **不用 PyYAML，自己写了一个"缩进嵌套 → 点号 key"的最小解析器**（`_load_yaml_flat`）。它只处理 `key: scalar`，**跳过列表项（`- `）和块标量**，遇到 `---` 只取第一个文档。原因：本项目 `@Value` 只引用标量，引入 PyYAML 会把"解析失败的静默降级"变成"启动崩溃"，反而偏离原行为。代价见第 8 章（`PyYAML` 依赖实际未使用）。
2. **占位符正则要求"整串就是一个占位符"**：`^\$\{([^:}]+)(?::(.*))?\}$`。所以 `"${k:60}000"` 这种「占位符 + 字面量后缀」**不走** `Environment.value`，而是由 `Scheduled._resolveMillis` 单独处理（见 5.11.4）。
3. **类型转换显式**：Java 靠 `ConversionService` 推断目标类型；Python 必须写 `settings.int("sync.batch-size", 1000)`、`settings.boolean(...)`、`settings.text(...)`。

**没有 `@ConfigurationProperties`**：原项目一个都没有，所以 Python 侧也没有对应的绑定类，`app/settings.py` 只是 `Environment` 的类型化门面。

### 5.2 Web 层：Spring MVC → FastAPI

| 关注点 | Java | Python | 差异原因 |
|---|---|---|---|
| 路由注册 | 注解 + 组件扫描 | 启动时 `add_api_route` 逐条注册（表由 `gen_routes.py` 生成） | 无注解运行时；生成+校验能防止手写漂移 |
| 参数绑定 | `HandlerMethodArgumentResolver` | `app/web/binding.py` 的 5 种 `source` 分派 | 见 3.2；`model` 分支复刻了 `@ModelAttribute` 的 5 条规则 |
| 绑定失败 | `BindException` → **400** | `BindingError` → 400；同时把 FastAPI 默认的 **422 重写为 400** | 422 是 FastAPI 的语义，Spring 用 400；不改会让前端错误分支走错 |
| JSON 序列化 | Jackson（`ObjectMapper` 可配） | `JacksonResponse` + orjson | 见 3.4；非字符串 key 转字符串、拒绝 NaN/Infinity |
| 日期输出 | `@JsonFormat(pattern = "yyyy-MM-dd")` | `app/web/serializer.py` 按字段 metadata 里的 pattern 格式化 | 元信息在 `field(metadata={"format": ...})` |
| 异常体 | `BasicErrorController` | `app/web/errors.py` | 逐字段复刻，含 `message` 键缺失 |
| 拦截器 | `HandlerInterceptor`（`SecurityInterceptor`） | 业务类保留同名方法；未在 ASGI 层注册全局钩子 | 原拦截器只校验请求头，属于可选链路，见第 8 章 |
| 静态资源 / 视图 | 无（纯 REST） | 无 | —— |

`@ModelAttribute` 风格的 5 条绑定规则（`app/web/binding.py`），与原项目不一致的地方会**直接影响接口行为**，所以逐条列出：

```text
1. 参数名依次匹配：Java 属性名(carNo) -> Python 字段名(car_no) -> 忽略大小写(gantryCaptureBO)
2. 未知请求参数直接忽略（Spring 只对已知字段报绑定错误）
3. 空字符串 -> 非 String 目标映射为 None（对应 StringToNumber/StringToDate 转换器）
4. Date/LocalDate 走 DateUtils.parseDate（对应 BaseController.initBinder）
5. 字段类型是嵌套 dataclass / List<Bean> 时递归绑定（对应 Jackson 反序列化）
```

### 5.3 MyBatis / MyBatis-Plus

见第 4 章。这里只补一条**为什么要有内存通路**：

> Java 的 Mapper 是接口 + 动态代理，**没有数据库就无法启动**。Python 侧如果照搬，`pytest` 和路由冒烟必须依赖 GaussDB 在线，迁移验证会退化成"环境测试"。因此 `BaseMapper` 同时提供内存实现，业务代码一行不改就能在两种模式下运行。这是**唯一为了可验证性增加的能力**，且不改变有库时的行为（XML 语句优先）。

### 5.4 Redis：真实客户端 → 进程内 `RedisCache`

**Java**：`RedisTemplate` + Lettuce 连接池（`spring.redis.*`）。

**Python**：`com/ruoyi/common/core/redis/RedisCache.py`（454 行）用进程内结构实现 `set/get/delete/expire/lRange/sAdd/hGet...`，TTL 用单调时钟判断。

为什么：本项目对 Redis 的用法集中在「门架名称字典缓存」「消息幂等标记」「待确认消息快照」——全部是**单实例、进程内可重建**的缓存；且 `RedisCache` 保持 `TimeUnit` 参数的语义（`TimeUnit.HOURS` 等）。

必须知道的差异：

| 行为 | Java | Python |
|---|---|---|
| 跨进程共享 | 是 | **否**（每个进程一份） |
| `LRANGE` 边界 | 闭区间 | 闭区间（`range(0, 50)` 返回 51 条，注释标注） |
| 过期回收 | Redis 主动 | 读取时惰性判断 |
| 序列化 | JDK 序列化 / JSON | Python 对象直接持有（`copy.deepcopy` 防止外部改内部） |

`tools/check_middleware.py` 显示本机 Redis `127.0.0.1:6379` 是通的——但代码**没有**用它。这是刻意的：一旦改用真 Redis，`pytest` 就依赖外部服务，且原项目里"缓存丢了系统也能跑"的降级语义会消失。

### 5.5 Kafka：`KafkaTemplate` 进程内替身

**Java**：`spring-kafka` 的 `KafkaTemplate.send(topic, key, value)` 返回 `ListenableFuture`，broker ack 由网络线程回调。

**Python**：`org/springframework/kafka/core/KafkaTemplate.py`（102 行）：

```python
# The stub has no broker: send() completes synchronously in the caller thread
# (offset comes from an auto-increment counter) and relies on ListenableFuture's
# "complete-then-register-callback" semantics so addCallback() still fires.
```

| 差异 | 说明 |
|---|---|
| 同步完成 | 真实 Kafka 是异步 ack；替身在 `send()` 内立即完成，`addCallback` 立即收到结果 |
| 无 broker | 消息留在进程内列表，测试可直接断言"发了什么" |
| 失败注入 | `fail_next` / `always_fail` 两个开关，用来覆盖 `onFailure` 分支（相当于 Java 侧注入 `KafkaException`） |
| 单例语义 | `defaultKafkaTemplate()` 模块级单例，还原"所有服务发同一个集群" |
| `flush()` | 空操作（无缓冲区） |

`tools/check_middleware.py` 实测本机 Kafka `localhost:9092` **不通**——所以这个替身不是可选项，是运行前提。生产部署需要换成真客户端（第 8 章）。

### 5.6 Pulsar / Debezium CDC

与 5.5 同构：`PulsarProducerService`（280 行）+ `SnapshotFlowPulsarConsumer`（421 行）+ `DebeziumReadonlyPulsarConsumer`（400 行）跑在进程内 Pulsar 替身上，消费语义（ack / 重投 / retry_count 累加）落在内存表里。配置项 `pulsar.*` 仍从 `application.yml` 读取，地址不对也不会报错——**和 Kafka 一样，连接失败只影响真实收发，不影响启动**。

### 5.7 Elasticsearch：全量现象级替身

这是**影响面最大的一个替身**（`org/elasticsearch` 51 个文件 / 约 4,000 行）。

**Java**：`RestHighLevelClient` 把 `QueryBuilder` 序列化成 DSL 交给 ES 集群，分片并行执行，`search_after`/`scroll` 由服务端维护游标。

**Python**：`RestHighLevelClient` 用**类属性** `_INDICES` 当集群：

```python
# Cluster storage lives on a class attribute: in real ES, DataProcessService's
# writes are visible to EsQueryService even though they hold different client
# instances. The stub keeps that "cross-instance" semantics.
_INDICES: dict[str, list[dict]] = {}
```

| 行为 | 真实 ES | 替身 | 影响 |
|---|---|---|---|
| 查询执行 | 服务端 | 客户端进程内 `query.matches(document)` | 结果集一致，性能特征不同（替身是 O(n)） |
| 排序 | `_score` → `_doc` | 插入顺序 | 无 `sort` 的查询顺序可能与真集群不同 |
| 聚合 | 分片并行 + reduce | 对**全部命中**本地聚合 | 与"聚合只看命中集合、与 from/size 无关"一致，所以 `size(0)` 只取聚合的行为对齐 |
| scroll | 服务端上下文 + keepAlive | 进程内 `_SCROLLS`，**不做过期回收** | 长时间不清理会占内存 |
| 异常 | `IOException` / `ElasticsearchException` | 统一 `ConnectionError` | 让 `EsQueryService` 的 `catch (Exception)` 降级分支可被触发 |
| 一致性对账 | 比对真实集群 | 比对 `_INDICES` | `GaussEsConsistencyService` 的流程可完整跑通 |

`tools/check_middleware.py` 显示本机 ES `localhost:9200` 是**活的**（7.15.2）——但业务代码依然走替身。原因同 5.4：让迁移结果可离线验证。生产切换需替换 `ElasticsearchConfig` 的客户端构造（第 8 章）。

### 5.8 Spark / Hive

`com/ruoyi/common/config/SparkHiveConfig.py`：`SparkSession` **惰性导入**（方法内 `from pyspark.sql import SparkSession`），未安装 `pyspark` 时降级为 warnings 日志，不阻塞启动。Java 侧是 `@Bean` 强依赖，缺 Hive 元数据服务会启动失败——**这里 Python 更宽松，属于有意的偏差**（原项目 Spark 仅用于离线统计，不在请求链路上）。

### 5.9 Flink

`base/flink/VehicleTrackFlinkJob.py`（728 行）完整移植了 DAG：Kafka source → keyBy(车牌) → 键控状态 + 定时器 → 字典广播流富集 → Redis/GaussDB sink。

`org/apache/flink` 的 53 个文件提供 `StreamExecutionEnvironment`、`KeyedProcessFunction`、`ValueState`、`MapStateDescriptor`、`CheckpointConfig` 等替身，**在单进程内按拓扑顺序推数据**。因此：

- 计算逻辑（拼接规则、TTL、定时器触发）可被 pytest 直接验证；
- 但**不是**真正的分布式流处理：没有 watermark、没有 checkpoint 持久化、没有并行度。

### 5.10 大表查询与导出

`base/service/optimization` 13 个类（4,680 → 5,491 行）全部 1:1 移植，差异集中在**外部依赖**而非逻辑：

| 类 | 依赖 | 迁移处理 |
|---|---|---|
| `LargeScaleQueryService` | ES + GaussDB | 查询走 ES 替身；`selectByCursorShard` 走 XML |
| `BillionLevelQueryService` | 分片 + 并行 | `java.util.concurrent` 替身（daemon 线程池） |
| `ProgressiveQueryArchitectureService` | 游标分页 | 游标语义逐行保持（不走 PageHelper） |
| `UnifiedExportService` | 本地文件系统 `/data/export` | `settings.export_dir` 可配；异步任务用 daemon 线程 |
| `GaussEsConsistencyService` | GaussDB ↔ ES 比对 | 见 5.7，可跑通全流程 |
| `CompositeQueryOptimizationService` | `@Value` 大量配置 | `Environment.value` 逐个解析 |

### 5.11 定时任务（Phase 2c）

#### 5.11.1 调用链对照

| Spring | Python | 位置 |
|---|---|---|
| `@EnableScheduling` | `app/scheduler/__init__.py` | 导出 `start_scheduler` |
| `ScheduledAnnotationBeanPostProcessor` | `registerScheduled(bean, registrar)` | `org/springframework/scheduling/annotation/Scheduled.py` |
| `ScheduledTaskRegistrar.afterPropertiesSet` | 同名方法 | `org/springframework/scheduling/config/ScheduledTaskRegistrar.py` |
| `ThreadPoolTaskScheduler` | 同名类（重写） | `org/springframework/scheduling/concurrent/ThreadPoolTaskScheduler.py` |
| `CronExpression` / `CronTrigger` | 同名类（新增） | `org/springframework/scheduling/support/` |
| 容器启动时装配 | `SchedulingConfig()` + `_install_persistence()` 同级调用 | `app/main.py` lifespan |

#### 5.11.2 语义逐条复刻

| Spring 行为 | Python 实现 | 验证用例 |
|---|---|---|
| 六段 cron（秒 分 时 日 月 周） | `CronExpression.parse()` | `test_phase2e.py` 参数化用例覆盖全部项目内表达式 |
| `?` 等价 `*` | 解析时归一化 | `isValidExpression` 用例 |
| 周字段 `0` 与 `7` 都是周日 | `day.isoweekday() % 7` | `test_sunday_zero_and_seven` |
| 日与周**同时**受限时取 **OR** | `_dayMatches()` | 用例锁定 OR 语义 |
| 非法表达式启动即失败（Quartz 的 `W`/`L-`/`#` 不支持） | 抛 `ValueError` | 9 条校验用例 |
| 2 月 31 日永不触发 | 8 年搜索窗口后返回 `None` | `test_feb_31_never_fires` |
| `fixedRate` 以**上次计划时刻**为基准（超时立即补跑） | `_startLoop` 的 `next = last_scheduled + period` | `test_fixed_rate_keeps_running_after_an_exception` |
| `fixedDelay` 以**上次完成时刻**为基准 | `next = completion + delay` | 同上 |
| 任务抛异常**仍继续排期** | `LOG_AND_SUPPRESS_ERROR_HANDLER` 语义 | 同上（原实现会停，已修正） |
| `shutdown()` 取消除进行中的周期任务 | 取消 event + `future.cancel()` | `test_shutdown_leaves_no_threads` |
| `fixedRateString` 先解析占位符再拼字面量 | `_resolveMillis` | 见 5.11.4 |

#### 5.11.3 为什么是 10 个任务，不是 21 个

```text
grep -c '@Scheduled(' 全仓        -> 21
其中 CarTask.java                  -> 11
剩余真实任务                        -> 10
```

`pro-business-api/.../base/task/CarTask.py` 文件头（第 6–22 行）写明了原因：

> Java 源第 1 行是 `/*`、第 231 行是 `*/`，把 package/import/类声明和全部 `@Scheduled` 方法**整体注释掉了**。因此 javac 编译时 `CarTask` **根本不存在**，不会注册任何 Spring 定时任务。

那 11 个被注释的 cron 是 01:00–03:45 每 15 分钟一次（01:00/01:15/01:30/01:45/02:00/02:15/02:30/02:45/03:00/03:15/03:45）。**没有 03:30**，原代码就是这样。若将来要恢复，对应逻辑已由 `SysTestController.syncSuspiciousCar1()` ~ `syncSuspiciousCar10()` 承担（同一段分批同步的已移植版本）。

Python 侧的处理方式是**不定义任何类**（`__all__ = []`），把 Java 全文逐行转成 `#` 注释保留，与"该类不存在"保持一致。`app/scheduler/registry.py` 的 `JOB_CLASSES` 因此显式排除它，并有一条测试用例反向校验：

```python
# tests/test_phase2e.py
_DECORATOR = re.compile(r"^[ \t]*@Scheduled\(", re.MULTILINE)

def test_every_decorator_is_registered_and_nothing_else():
    """扫描全仓所有真实 @Scheduled 装饰器，必须与 JOB_CLASSES 的 10 个任务一一对应。"""
```

#### 5.11.4 `"${...:30}000"` 的毫秒缺陷

```java
// Java: DataLossDetectionService.java
@Scheduled(fixedRateString = "${detection.interval-minutes:30}000")
```

解析过程：`${detection.interval-minutes:30}` → `"30"`，再拼上字面量 `"000"` → `"30000"` → **30,000 ms = 30 秒**。

配置项名字是 `interval-minutes`（检测间隔，**分钟**），yml 里写的是 `30`，意图显然是 **30 分钟**。差 **60 倍**。这是原项目的真实缺陷，迁移时**原样保留**并用断言锁死：

```python
# tests/test_phase2e.py
assert (by_method["scheduledDetection"].kind,
        by_method["scheduledDetection"].trigger) == ("fixedRate", "30000")
assert by_method["scheduledDetection"].java == \
    '@Scheduled(fixedRateString = "${detection.interval-minutes:30}000")'
```

十个任务的实测触发间隔（`tools/smoke_scheduler.py` 输出）：

| Bean | 方法 | 类型 | 表达式 / 解析值 | 实际间隔 | 备注 |
|---|---|---|---|---|---|
| `DataLossDetectionService` | `scheduledDetection` | fixedRate | `${...:30}000` → `30000` | **30 秒** | 见上，60 倍缺陷 |
| `DataReliabilityService` | `checkOfflineDevices` | fixedRate | `300000` | 5 分钟 | 字面量，无缺陷 |
| `DataReliabilityService` | `compensationTask` | fixedRate | `${...:60}000` → `60000` | 1 分钟 | 配置单位是**秒**，正确 |
| `DelayMonitoringService` | `generateStatsReport` | fixedRate | `600000` | 10 分钟 | 字面量 |
| `GaussEsConsistencyService` | `scheduledReconcile` | cron | `0 30 2 * * ?` | 每天 02:30 | **默认 `enabled=false`，方法首行即 return** |
| `DataFlowTask` | `processPendingQueue` | cron | `0 */1 * * * ?` | 每分钟 | —— |
| `DataFlowTask` | `syncGantryCaptureData` | cron | `0 */5 * * * ?` | 每 5 分钟 | —— |
| `TrackTask` | `syncCurrentTrack` | cron | `0 0/3 * * * ?` | 每 3 分钟 | —— |
| `TrackTask` | `syncBaseInfo` | cron | `0 0 0 * * ?` | 每天 00:00 | —— |
| `TrackTask` | `syncHistroyTrack` | cron | `0 0 4 * * ?` | 每天 04:00 | 方法名 `Histroy` 是原代码拼写 |

> 10 个任务里 **9 个真跑**，`scheduledReconcile` 因为 `consistency.reconcile.enabled: false` 每次触发都立即返回。这个开关在原项目里同样是 false —— 也就是说，Java 生产环境的一致性对账其实一直是空转。

#### 5.11.5 daemon 线程：唯一的"必须不一样"

Java 的 `ExecutorService` 默认非守护线程，但 JVM 退出时会执行 shutdown hook 并强制结束线程池。Python 没有等价的"杀线程"能力：`threading.Thread` 一旦进入 `time.sleep(60)` 就无法从外部终止。

如果照搬非守护线程：

```text
pytest 跑完 -> 解释器等待 10 个 sleep 中的调度线程 -> 永不退出
uvicorn Ctrl+C -> 进程挂住，只能 kill -9
```

所以 `ThreadPoolTaskScheduler` 的**全部**线程（`poolSize=10` 的工作线程 + 每个周期任务一个调度线程）都是 `daemon=True`，并配合 `threading.Event` 做取消：

```python
# Java: setWaitForTasksToCompleteOnShutdown(true) + setAwaitTerminationSeconds(60)
# Python: daemon threads + a cancel event -- the interpreter cannot join a thread
# that is blocked in a 10-minute sleep forever.
def shutdown(self) -> None:
    self._stopped.set()
    with self._lock:
        futures, loops = list(self._futures), list(self._loops)
    for future in futures:
        future.cancel(False)
```

保留的等价部分：`poolSize=10`、`threadNamePrefix="scheduler-"`、启动日志 `"[定时任务配置] 线程池初始化完成，线程数: 10"`、`shutdown()` 幂等。

实测：`smoke_scheduler.py` 关机后 `scheduler-*` 线程数为 **0**，`pytest` 3.77 秒正常退出。

#### 5.11.6 关于 `application.yml` 缩进的更正

在本次迁移过程中曾记录过一条"`application.yml` 存在缩进错误（`reconcile:`/`cron:`/`compensation-interval-seconds:`/`interval-minutes:` 顶格）导致配置整体失效"的结论。**该结论不成立，经逐字节比对已更正**：

```bat
fc /n pro-business-api\src\main\resources\application.yml ^
      car-monit-api-python\pro-business-api\src\main\resources\application.yml
:: FC: 找不到差异
```

- `consistency.reconcile.cron`、`reliability.compensation-interval-seconds`、`detection.interval-minutes`、`mybatis-plus.mapper-locations` **全部正确嵌套在父键下**（2 空格缩进）；
- 占位符默认值与 yml 实际值恰好相同（`0 30 2 * * ?`、`60`、`30`），所以即使配置没读到也不会露馅——这正是早期误判的来源；
- 产生误判的直接原因：`grep` 类工具的输出会**去掉行首缩进**，看起来像顶格。

结论：配置解析链路是"yml 优先、默认值兜底"，两条路都通向同一个值，行为与 Java 完全一致。**没有需要修复的 YAML**。

#### 5.11.7 新增的编排代码（Java 侧没有对应文件）

| 文件 | 行数 | 职责 |
|---|---|---|
| `app/scheduler/registry.py` | 252 | `JOB_CLASSES`（6 个 Bean）、`JobSpec`、`plan()`（只做类级扫描，**不实例化**）、`start_scheduler()`（幂等）、`shutdown_scheduler()`、`describe()`（`/health` 探针） |
| `app/scheduler/__init__.py` | 19 | 再导出 |
| `org/springframework/scheduling/support/CronExpression.py` | 274 | 六段 cron 解析 + `next_fire_time` |
| `org/springframework/scheduling/support/CronTrigger.py` | 104 | `TriggerContext` + 锚点（`lastCompletionTime`，首次取 `now`） |
| `tests/test_phase2e.py` | 321 | 36 个用例 |
| `tools/smoke_scheduler.py` | 97 | 端到端冒烟：10 个任务、启动清单、关机无残留线程、可重启 |

`start_scheduler()` 的关键设计：**先把 6 个 Bean 全部注册完，再统一 `afterPropertiesSet()`**。若中途抛异常，会调用 `config.shutdown()` 回收已建线程池，避免"半启动"状态。

---

## 6. 六条「必须知道」的差异

给接手 Java 代码的同事，按重要性排序：

1. **中间件是进程内替身，不是集群。**
   Redis / Kafka / Pulsar / ES 全部在进程内模拟（第 5.4–5.7）。`tools/check_middleware.py` 能连通真实服务，但代码不走。**上生产必须替换客户端构造**，业务逻辑不需要改。

2. **`CarTask` 在两侧都不存在。**
   不要去找那 11 个定时任务——Java 源整个文件是块注释。真正的 10 个任务在 `TrackTask` / `DataFlowTask` / `DataLossDetectionService` / `DataReliabilityService` / `DelayMonitoringService` / `GaussEsConsistencyService`。

3. **`${detection.interval-minutes:30}000` = 30 秒，不是 30 分钟。**
   60 倍缺陷，两侧一致，测试已锁死。要修的话必须两侧同时改，否则行为不等价。

4. **所有线程都是 daemon。**
   Python 无法从外部终止阻塞线程，非守护线程会让进程永远退不出去。这是**唯一**一处主动偏离 Java 运行语义的地方，且只在关机路径可见。

5. **XML 是 SQL 的唯一事实来源，且不复制。**
   `app/db/registry.py` 直接读 `pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/*.xml`。改 SQL 就去改那份 XML，Python 树里没有副本。6 个"没有 XML"的方法在 Java 里同样是 `BindingException` 隐患（4.3）。

6. **错误体跟 Spring Boot 一样"缺 message"。**
   `server.error.include-message` 默认 `never`，所以异常响应只有 `{timestamp,status,error,path}`。前端如果读 `message`，两侧都读不到——不是迁移丢的。

---

## 7. 验证矩阵

最后一次全量执行结果：

| 检查 | 命令 | 结果 |
|---|---|---|
| 单元/集成测试 | `pytest -q` | **82 passed**, 1 warning（starlette/httpx 弃用提示） |
| Phase 2c 专项 | `pytest tests/test_phase2e.py -q` | **36 passed** |
| 路由注册 | `tools/check_routes.py` | 24 控制器 / **85 路由**，`param kinds` 分布见 3.1 |
| 路由冒烟（不连库） | `tools/smoke_all_routes.py` | `200=85`，`defects: none`，`payload: 0 failure(s)` |
| Mapper 绑定 | `tools/check_mappers.py` | 22 XML / 54 statements / 58 bound / 6 without XML |
| 中间件连通 | `tools/check_middleware.py` | GaussDB open、Redis open、Kafka **closed**、ES HTTP 200 |
| 定时任务 | `tools/smoke_scheduler.py` | `10 task(s)`、`scheduler: OK`、关机无残留线程 |
| 专项冒烟 | `largescale` / `progressive` / `unified_export` / `billion` / `consistency` / `scheduler` | 6/6 `EXIT=0` |

**为什么路由冒烟不连库**：`smoke_all_routes.py` 刻意**不进入** FastAPI 的 lifespan（`TestClient` 只有 `with` 块内才触发生命周期），因此 Mapper 保持内存实现。这样 85 条路由的"参数绑定 + 响应序列化 + 状态码"可以在无 GaussDB/Kafka 的机器上验证，而真实的 SQL 行为由 `check_mappers.py` 静态校验 + 联调环境覆盖。

---

## 8. 已知偏差与待办

### 8.1 功能性偏差（会影响行为）

| # | 偏差 | 影响 | 处理建议 |
|---|---|---|---|
| 1 | 中间件为进程内替身（Redis/Kafka/Pulsar/ES） | 多实例部署时缓存/消息不共享 | 生产替换 `RedisConfiguration`/`KafkaProducerConfig`/`ElasticsearchConfig` 的客户端构造，业务代码不动 |
| 2 | 6 个 Mapper 方法无 XML/注解 | **已与 Java 对齐**：两侧调用都抛 `BindingException: Invalid bound statement (not found)` | 无。`app/db/registry.py` 安装抛异常桩，启动时以 WARNING 列出这 6 个方法 |
| 3 | `SecurityInterceptor` 未在 ASGI 层注册为全局钩子 | 请求头校验链路未生效 | 原拦截器只做可选头部校验；需要时在 `app/main.py` 加 `middleware` |
| 4 | `HttpSysUtilApiService`（Forest 声明式客户端）为同步实现 | 超时/重试策略由 urllib 决定 | 原逻辑仅用于 `sysbaseUrl` 拉取组织信息，低频 |

### 8.2 未使用的依赖（已清理）

早期方案选型遗留下来的四个声明均未被任何模块导入，已在 `requirements.txt` / `pyproject.toml` 中移除：

| 包 | 真实替代实现 |
|---|---|
| `APScheduler>=3.10` | `org/springframework/scheduling/*`（自研 `CronExpression` + `ThreadPoolTaskScheduler`，见 5.11） |
| `elasticsearch>=7.17` | `org/elasticsearch/*` 进程内替身（5.7） |
| `PyYAML>=6.0` | `Environment._load_yaml_flat` 手写解析（5.1） |
| `redis>=5.0` | `com/ruoyi/common/core/redis/RedisCache.py` 进程内替身（5.4） |

> 验证方式：`grep -rn "^\s*\(import\|from\) \(redis\|elasticsearch\|yaml\|apscheduler\)"` 无命中。
> 保留的依赖只有 6 个：`fastapi` `uvicorn` `SQLAlchemy` `psycopg` `httpx` `orjson`。

### 8.3 未复制的资源文件（10 个）

`pro-business-api/src/main/resources` 下 Java 14 个文件，Python 4 个（`application.yml` + 3 个 ES 索引模板）。未复制：

| 文件 | 原因 |
|---|---|
| `application-optimization.yml` | 未被任何 `@Value` 引用的独立 profile 片段 |
| `logback-spring.xml` | Python 用 `app/logging_config.py`（63 行）实现同格式 |
| `spy.properties` | p6spy SQL 日志，Python 由 `sqlalchemy` echo 替代 |
| `docs/HIGH_PERFORMANCE_SYNC.md` | 文档 |
| `mapper/xml/PulsarMessageRecordMapper.xml` | **唯一不匹配** `classpath*:com/ruoyi/base/**/xml/*Mapper.xml` 的 XML（位于 `resources/mapper/xml/`）；其 SQL 已在 `PulsarMessageRecordMapper.py` 逐字保留在 docstring（4.3） |
| `sql/*.sql`（5 个） | DDL/索引脚本，由 DBA 执行，不属于运行期资源 |

### 8.4 本阶段（Phase 2c）遗留

`tools/` 下曾用于批量跑冒烟的临时脚本与日志已删除；当前 `tools/` 只保留 16 个长期脚本（`check_*` / `smoke_*` / `gen_*` / `verify_db` / `gen_java_meta`）。

其中 `tools/check_parity.py` 是新增的方法级对照门禁：它对 219 个 Java 文件逐一比较类名/方法名，
输出 `Tier A`（继承或共享，低风险）与 `Tier B`（Python 树里根本不存在，**真实缺口**）两档，
9 条已知等价映射需逐条写明理由才能登记。当前结果：`fully matched 187 / Tier B 0`。

---

## 附录 A：依赖对照

| `pom.xml` | `requirements.txt` | 用途 |
|---|---|---|
| `spring-boot-starter-web` | `fastapi` + `uvicorn[standard]` | HTTP 容器 |
| `mybatis-plus-boot-starter` | 自研 `app/db/*` | ORM（第 4 章） |
| `druid` + `dynamic-datasource` | `SQLAlchemy` + `psycopg[binary]` | GaussDB 连接池 |
| `pagehelper-spring-boot-starter` | 自研 `app/db/pagination.py` | 分页 |
| `spring-boot-starter-data-redis` | 自研 `RedisCache` | 缓存（5.4） |
| `spring-kafka` | 自研 `KafkaTemplate` | 消息（5.5） |
| `pulsar-client` | 自研 Pulsar 替身 | 消息（5.6） |
| `elasticsearch-rest-high-level-client` | 自研 `org.elasticsearch` | 检索（5.7） |
| `flink-streaming-java` + `flink-connector-kafka` | 自研 `org.apache.flink` | 流处理（5.9） |
| `spark-sql` + `hive` | `pyspark`（惰性导入） | 离线统计（5.8） |
| `fastjson2` | 自研 `com.alibaba.fastjson2` | JSON |
| `lombok` | `JavaBean` + `@dataclass` | getter/setter |
| `hutool` / `commons-lang3` | `com/ruoyi/common/utils/*` | 工具类 |
| `orika` | 手写映射 | DTO 转换 |
| Jackson | `orjson`（输出） | 序列化 |
| `logback` | `logging` + `app/logging_config.py` | 日志 |

## 附录 B：排障索引

| 现象 | 先看哪里 |
|---|---|
| 某接口 404 | `app/routes/generated.py` 是否有该 path；`registry.py` 的注册顺序 |
| 某接口 400 | `app/web/binding.py` 的 5 条绑定规则（5.2） |
| 响应少了字段 | `app/web/serializer.py`（`None` 字段是否被 `@JsonInclude` 过滤） |
| 查询报 `has no statement` | `tools/check_mappers.py`；4.3 的 6 个方法 |
| 定时任务没跑 | `/health` 的 `scheduler` 探针 → `plan()` 清单；`app.scheduler.enabled` |
| 进程退不出去 | 是否有绕过替身直接建的 `Thread`（必须 daemon） |
| 配置没生效 | 占位符是否被"整串匹配"限制（5.1 第 2 条）；环境变量是否覆盖 |
| ES 查不到刚写的数据 | 替身是 `_INDICES` 类属性，`resetStore()` 会清空（5.7） |

---

*本手册覆盖 219 个 Java 文件、85 条 REST 路由、22 张表、10 个定时任务。所有数量与路径均由 `tools/` 下的脚本实测生成，可随时复跑校验。*
