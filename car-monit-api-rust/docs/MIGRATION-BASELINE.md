# 阶段一：迁移基线清单（Java → Rust）

> 对象：`D:\work\IdeaProjects\car-monit-api`（`pro-base-common` + `pro-business-api`）
> 目标：`car-monit-api-rust`（本目录）
> 口径：只统计**当前真正会被执行**的代码；Java 源码中处于块注释内的类/方法单独标注。

## 0. 结论摘要

| 维度 | Java 基线 | Rust 目标 |
|---|---|---|
| 源码规模 | **219 个 .java / 33,581 行**（common 53 / 7,343；business 166 / 26,238） | 30 个模型 + 23 个 Repo + 13 个服务文件 + 6 个 handler 文件 |
| HTTP 端点 | **85 个有效端点**（24 个 Controller；`/syncTrack`、`/syncSuspiciousCar` 在块注释内） | **85 条路由**（另有 3 条健康检查） |
| 实体/DTO | 30 个类 / 901 个字段 | 30 个 struct / 字段数逐类相等 |
| 数据表 | 19 张业务表 + `kafka_message_record` | 22 个 Repo（21 只读 + 1 消息记录） |
| Mapper | 23 个接口 + 23 个 XML（另有 23 份 target 副本） | 手写 SQL（sqlx，`$n` 占位符） |
| 定时任务 | 21 个 `@Scheduled`（CarTask 11 个整文件注释） | 21 个登记：9 个默认运行、1 个受开关控制、11 个禁用 |
| 中间件 | Redis / Kafka / Pulsar / RocketMQ / RabbitMQ / Elasticsearch | Redis / Kafka(rdkafka) / ES(reqwest) / Pulsar(接口降级) |
| 鉴权 | 无（`SecurityInterceptor` + `WebConfig` 整文件块注释） | 无（保持一致） |
| 服务端口 | `server.port: 9901`、`context-path: /` | 9901 / `/` |

---

## 1. 项目结构对照表

### 1.1 按包（目录）对照

| Java 路径 | 文件数 | 职责 | Rust 目标 | 类型 |
|---|---|---|---|---|
| `pro-base-common/.../common/core/domain` | 11 | `AjaxResult` / `R` / `BaseEntity` / `TableDataInfo` | `src/response.rs`、`src/models/*` | 框架契约（需惯用法重写） |
| `pro-base-common/.../common/core/page` | 3 | PageDomain / TableSupport / PageUtils | `src/handlers/common.rs`（PageQuery） | 框架契约 |
| `pro-base-common/.../common/core/redis` | 4 | RedisCache / RedisTemplate 配置 | `src/cache.rs` | 框架契约 |
| `pro-base-common/.../common/utils` | 15 | 日期/字符串/SQL/加密等纯函数 | `src/utils.rs` | **纯逻辑（可直接翻译）** |
| `pro-base-common/.../common/config/interceptor` | 2 | `SecurityInterceptor` / `WebConfig` | `src/middleware.rs` | **整文件块注释 → 不实现** |
| `pro-business-api/.../base/controller` | 24 | 24 个 Controller / 85 端点 | `src/handlers/*` + `src/router.rs` | 框架契约 |
| `pro-business-api/.../base/domain` | 30 | 实体 / VO / DTO | `src/models/*` | 纯数据结构 |
| `pro-business-api/.../base/mapper` | 23 + 23 XML | MyBatis 数据访问 | `src/repo/mod.rs` | 框架契约（动态 SQL 需重写） |
| `pro-business-api/.../base/service/impl` | 23 | 业务服务 / MQ 消费 / 可靠性 | `src/services/*` | 混合（见 1.2） |
| `pro-business-api/.../base/service/optimization` | 13 | 大表查询 / 导出 / 同步 / 对账 | `src/services/{query,large,export,progressive,sync,consistency}.rs` | 混合 |
| `pro-business-api/.../base/task` | 3 | TrackTask / DataFlowTask / CarTask | `src/services/track_sync.rs` + `src/scheduler.rs` | 框架契约（`@Scheduled`） |
| `pro-business-api/.../base/config` | 4 | Kafka / Pulsar / Scheduling 配置 | `src/mq.rs`、`src/scheduler.rs` | 框架契约 |
| `pro-business-api/.../mq` | 6 | ES / RabbitMQ / RocketMQ / DataProcess | `src/mq.rs`、`src/es.rs` | 混合 |
| `pro-business-api/.../base/flink` | 1 | `VehicleTrackFlinkJob`（独立 Flink 作业） | **不移植**（见 6.5） | 独立运行时 |
| `pro-business-api/src/main/resources` | — | application.yml / logback / SQL / ES mapping | `config/application.yaml`、`migrations/`、`resources/es/` | 配置 |

### 1.2 关键文件逐项映射

| Java 文件 | 职责 | Rust 目标 | 直接翻译 / 框架契约 |
|---|---|---|---|
| `EcBusinessApiApplication.java` | 启动类 | `src/main.rs` | 框架契约（组合根） |
| `BaseController.java` | 分页、`getDataTable` | `src/handlers/common.rs`、`src/response.rs` | 框架契约 |
| `AjaxResult.java` / `TableDataInfo.java` / `R.java` | 统一响应 | `src/response.rs` | 纯逻辑 |
| `RedisCache.java` / `RedisUtil.java` | 缓存操作 | `src/cache.rs` | 框架契约 |
| `CommonUtil.java` / `StringUtils.java` / `DateUtils.java` | 工具函数 | `src/utils.rs` | 纯逻辑 |
| `SecurityInterceptor.java` / `WebConfig.java` | 鉴权拦截器 | `src/middleware.rs`（只做请求 ID/日志） | **整文件注释，不实现** |
| `KafkaProducerConfig.java` | Kafka 生产者 | `src/mq.rs: KafkaBus::new` | 框架契约 |
| `PulsarConsumerConfig.java` | Pulsar 消费语义 | `src/mq.rs: KafkaBus::consume` | 框架契约 |
| `SnapshotFlowPulsarConsumer.java` | 抓拍流水消费 | `src/services/consumer.rs` | 混合 |
| `KafkaProducerService.java` | 生产 + 失败重试 | `src/services/producer.rs` | 混合 |
| `SysUtilServiceImpl.java` | 轨迹查询 / 富集 | `src/services/sysutil.rs` + `track_sync.rs` | 混合（核心逻辑直译） |
| `TrailAggregationService.java` | 轨迹补点 / 质量 | `src/services/trail.rs` | **纯逻辑** |
| `DataReliabilityService.java` | 三重确认 / 死信 | `src/services/reliability.rs` | 混合 |
| `DataLossDetectionService.java` | 丢包检测 | `src/services/loss_detection.rs` | 混合 |
| `DelayMonitoringService.java` | 四段延迟 | `src/services/delay_monitor.rs` | 混合 |
| `MultiSourceDataFlowService.java` | 实时轨迹拼接 | `src/services/multisource.rs` | 混合 |
| `UnifiedQueryService.java` | ES/DB 统一路由 | `src/services/query.rs` | 混合 |
| `LargeScaleQueryService.java` | 模糊查询/统计/导出 | `src/services/large.rs` | 混合 |
| `UnifiedExportService.java` | scroll → CSV | `src/services/export.rs` | 混合 |
| `ProgressiveQueryArchitectureService.java` | 三级查询策略 | `src/services/progressive.rs` | 混合 |
| `LargeScaleDataSyncService.java` | GaussDB → ES 同步 | `src/services/sync.rs` | 混合 |
| `GaussEsConsistencyService.java` | 对账 + 修复 | `src/services/consistency.rs` | 混合 |
| `CarTask.java` | 11 个可疑车辆任务 | `src/scheduler.rs`（登记 + 禁用） | **整文件块注释，Java 从未执行** |
| `TrackTask.java` / `DataFlowTask.java` | 轨迹/流转任务 | `src/services/track_sync.rs` + `src/scheduler.rs` | 框架契约 |
| `VehicleTrackFlinkJob.java` | Flink 流作业 | **不移植**（独立进程） | 独立运行时 |

> “纯逻辑文件”指不依赖 Spring 容器、可直接逐函数翻译的类；“框架契约文件”指依赖注解扫描、AOP、
> 运行时反射或容器生命周期的类，需要用 Rust 的显式组合重写。

---

## 2. 接口清单（85 个有效端点）

生成方式：扫描 24 个 Controller 的 `@RequestMapping` / `@GetMapping` / `@PostMapping`，
先剥离 `/* ... */` 块注释（`SysUtilController` 的 `/syncTrack`、`/syncSuspiciousCar` 因此不计入）。
每一条都已在 `src/router.rs` 注册；测试 `tests/router_test.rs::java_api_inventory_is_85_endpoints` 固化数量。

| # | Method | Path | Java Controller#method | Rust handler | 鉴权 |
|---|---|---|---|---|---|
| 1 | GET | `/base/fwqjcxx/list` | `DwdLcztFwqjcxxController#list` | `crud::fwqjcxx_list` | 无（SecurityInterceptor 整文件被注释） |
| 2 | GET | `/base/fwqjcxx/{agentPk}` | `DwdLcztFwqjcxxController#getInfo` | `crud::fwqjcxx_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 3 | GET | `/base/fwqjcxx/listAll` | `DwdLcztFwqjcxxController#getListAll` | `crud::fwqjcxx_all` | 无（SecurityInterceptor 整文件被注释） |
| 4 | GET | `/base/sfsjcxx/list` | `DwdLcztSfsjcxxController#list` | `crud::sfsjcxx_list` | 无（SecurityInterceptor 整文件被注释） |
| 5 | GET | `/base/sfsjcxx/{agentPk}` | `DwdLcztSfsjcxxController#getInfo` | `crud::sfsjcxx_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 6 | GET | `/base/sfsjcxx/listAll` | `DwdLcztSfsjcxxController#getListAll` | `crud::sfsjcxx_all` | 无（SecurityInterceptor 整文件被注释） |
| 7 | GET | `/base/sfzjcxx/list` | `DwdLcztSfzjcxxController#list` | `crud::sfzjcxx_list` | 无（SecurityInterceptor 整文件被注释） |
| 8 | GET | `/base/sfzjcxx/{agentPk}` | `DwdLcztSfzjcxxController#getInfo` | `crud::sfzjcxx_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 9 | GET | `/base/sfzjcxx/listAll` | `DwdLcztSfzjcxxController#getListAll` | `crud::sfzjcxx_all` | 无（SecurityInterceptor 整文件被注释） |
| 10 | GET | `/api/v1/large/snapshot` | `LargeScaleQueryController#querySnapshotFlow` | `query::large_query (DsSnapshot)` | 无（SecurityInterceptor 整文件被注释） |
| 11 | GET | `/api/v1/large/fee` | `LargeScaleQueryController#queryFeeRecords` | `query::large_query (DsFee)` | 无（SecurityInterceptor 整文件被注释） |
| 12 | GET | `/api/v1/large/trail` | `LargeScaleQueryController#queryTrail` | `query::large_query (DsTrail)` | 无（SecurityInterceptor 整文件被注释） |
| 13 | GET | `/api/v1/large/carTrackQueryByCarNo` | `LargeScaleQueryController#queryCarTrackByCarNo` | `query::car_track_by_car_no` | 无（SecurityInterceptor 整文件被注释） |
| 14 | GET | `/api/v1/large/stats/group` | `LargeScaleQueryController#groupByStats` | `query::group_stats` | 无（SecurityInterceptor 整文件被注释） |
| 15 | POST | `/api/v1/large/export/submit` | `LargeScaleQueryController#submitExport` | `query::large_export_submit` | 无（SecurityInterceptor 整文件被注释） |
| 16 | GET | `/api/v1/large/export/status/{taskId}` | `LargeScaleQueryController#getExportStatus` | `query::large_export_status` | 无（SecurityInterceptor 整文件被注释） |
| 17 | POST | `/api/v1/large/sync/full` | `LargeScaleQueryController#triggerFullSync` | `query::sync_full` | 无（SecurityInterceptor 整文件被注释） |
| 18 | POST | `/api/v1/large/sync/incremental` | `LargeScaleQueryController#triggerIncrementalSync` | `query::sync_incremental` | 无（SecurityInterceptor 整文件被注释） |
| 19 | POST | `/api/v1/large/sync/repair` | `LargeScaleQueryController#triggerRepairSync` | `query::sync_repair` | 无（SecurityInterceptor 整文件被注释） |
| 20 | GET | `/manager/fwqclls/list` | `OdsCxztFwqcllsController#list` | `crud::fwqclls_list` | 无（SecurityInterceptor 整文件被注释） |
| 21 | GET | `/manager/fwqclls/{bigId}` | `OdsCxztFwqcllsController#getInfo` | `crud::fwqclls_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 22 | GET | `/base/feeGantry/list` | `OdsLwzxsfsjFeeGantryFusion01Controller#list` | `crud::fee_gantry_list` | 无（SecurityInterceptor 整文件被注释） |
| 23 | GET | `/base/feeGantry/{bigId}` | `OdsLwzxsfsjFeeGantryFusion01Controller#getInfo` | `crud::fee_gantry_flat` | 无（SecurityInterceptor 整文件被注释） |
| 24 | GET | `/base/feerecords/list` | `OdsLwzxsfsjFeeRecords01Controller#list` | `base::fee_records_list` | 无（SecurityInterceptor 整文件被注释） |
| 25 | GET | `/base/feerecords/listToExport` | `OdsLwzxsfsjFeeRecords01Controller#listToExport` | `base::fee_records_export` | 无（SecurityInterceptor 整文件被注释） |
| 26 | GET | `/base/feerecords/{bigId}` | `OdsLwzxsfsjFeeRecords01Controller#getInfo` | `crud::fee_records_flat` | 无（SecurityInterceptor 整文件被注释） |
| 27 | GET | `/base/feeStationEnter/list` | `OdsLwzxsfsjFeeStationEnter01Controller#list` | `crud::fee_enter_list` | 无（SecurityInterceptor 整文件被注释） |
| 28 | GET | `/base/feeStationEnter/{bigId}` | `OdsLwzxsfsjFeeStationEnter01Controller#getInfo` | `crud::fee_enter_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 29 | GET | `/base/feestationexit/list` | `OdsLwzxsfsjFeeStationExit01Controller#list` | `crud::fee_exit_list` | 无（SecurityInterceptor 整文件被注释） |
| 30 | GET | `/base/feestationexit/{bigId}` | `OdsLwzxsfsjFeeStationExit01Controller#getInfo` | `crud::fee_exit_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 31 | GET | `/base/snapshotflow/list` | `OdsRtSzdnSnapshotFlowAddcodeController#list` | `base::snapshot_flow_list` | 无（SecurityInterceptor 整文件被注释） |
| 32 | GET | `/base/snapshotflow/listToExport` | `OdsRtSzdnSnapshotFlowAddcodeController#listToExport` | `base::snapshot_flow_export` | 无（SecurityInterceptor 整文件被注释） |
| 33 | GET | `/base/snapshotflow/{bigId}` | `OdsRtSzdnSnapshotFlowAddcodeController#getInfo` | `crud::snapshot_flow_flat` | 无（SecurityInterceptor 整文件被注释） |
| 34 | GET | `/base/provcapture/list` | `OdsRtSzdnSnapshotFlowProvcaptureAddcodeController#list` | `crud::prov_capture_list` | 无（SecurityInterceptor 整文件被注释） |
| 35 | GET | `/base/provcapture/{bigId}` | `OdsRtSzdnSnapshotFlowProvcaptureAddcodeController#getInfo` | `crud::prov_capture_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 36 | GET | `/base/stationcapture/list` | `OdsRtSzdnSnapshotFlowStationcaptureAddcodeController#list` | `crud::station_capture_list` | 无（SecurityInterceptor 整文件被注释） |
| 37 | GET | `/base/stationcapture/{bigId}` | `OdsRtSzdnSnapshotFlowStationcaptureAddcodeController#getInfo` | `crud::station_capture_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 38 | GET | `/base/gantry/list` | `OdsSzdnGantryController#list` | `crud::gantry_list` | 无（SecurityInterceptor 整文件被注释） |
| 39 | GET | `/base/gantry/{id}` | `OdsSzdnGantryController#getInfo` | `crud::gantry_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 40 | GET | `/base/gantry/listAll` | `OdsSzdnGantryController#getListAll` | `crud::gantry_all` | 无（SecurityInterceptor 整文件被注释） |
| 41 | GET | `/base/gantryIp/list` | `OdsSzdnGantryIpController#list` | `crud::gantry_ip_list` | 无（SecurityInterceptor 整文件被注释） |
| 42 | GET | `/base/gantryIp/{id}` | `OdsSzdnGantryIpController#getInfo` | `crud::gantry_ip_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 43 | GET | `/base/vehicleweight/list` | `OdsSzdnProvinceBorderVehicleWeightNewstructureController#list` | `crud::vehicle_weight_list` | 无（SecurityInterceptor 整文件被注释） |
| 44 | GET | `/base/vehicleweight/{dataSource}` | `OdsSzdnProvinceBorderVehicleWeightNewstructureController#getInfo` | `crud::vehicle_weight_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 45 | GET | `/base/vehicleweight/map` | `OdsSzdnProvinceBorderVehicleWeightNewstructureController#map` | `crud::vehicle_weight_map` | 无（SecurityInterceptor 整文件被注释） |
| 46 | GET | `/base/section/list` | `OdsSzdnSectionController#list` | `crud::section_list` | 无（SecurityInterceptor 整文件被注释） |
| 47 | GET | `/base/section/{id}` | `OdsSzdnSectionController#getInfo` | `crud::section_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 48 | GET | `/base/section/listAll` | `OdsSzdnSectionController#getListAll` | `crud::section_all` | 无（SecurityInterceptor 整文件被注释） |
| 49 | GET | `/base/toll/list` | `OdsSzdnTollController#list` | `crud::toll_list` | 无（SecurityInterceptor 整文件被注释） |
| 50 | GET | `/base/toll/{id}` | `OdsSzdnTollController#getInfo` | `crud::toll_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 51 | GET | `/base/toll/listAll` | `OdsSzdnTollController#getListAll` | `crud::toll_all` | 无（SecurityInterceptor 整文件被注释） |
| 52 | GET | `/base/tollStationIp/list` | `OdsSzdnTollStationIpController#list` | `crud::toll_station_ip_list` | 无（SecurityInterceptor 整文件被注释） |
| 53 | GET | `/base/tollStationIp/{id}` | `OdsSzdnTollStationIpController#getInfo` | `crud::toll_station_ip_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 54 | GET | `/base/org/list` | `OdsYhglVBaseOrgController#list` | `crud::org_list` | 无（SecurityInterceptor 整文件被注释） |
| 55 | GET | `/base/org/{bigId}` | `OdsYhglVBaseOrgController#getInfo` | `crud::org_ajax` | 无（SecurityInterceptor 整文件被注释） |
| 56 | GET | `/base/org/listAll` | `OdsYhglVBaseOrgController#getListAll` | `crud::org_all` | 无（SecurityInterceptor 整文件被注释） |
| 57 | GET | `/progressive/snapshotflow/list` | `ProgressiveQueryController#snapshotFlowList` | `query::progressive_list (snapshotflow)` | 无（SecurityInterceptor 整文件被注释） |
| 58 | GET | `/progressive/feerecords/list` | `ProgressiveQueryController#feeRecordsList` | `query::progressive_list (feerecords)` | 无（SecurityInterceptor 整文件被注释） |
| 59 | GET | `/progressive/trailfitting/list` | `ProgressiveQueryController#trailFittingList` | `query::progressive_list (trailfitting)` | 无（SecurityInterceptor 整文件被注释） |
| 60 | GET | `/progressive/scale-level` | `ProgressiveQueryController#scaleLevel` | `query::scale_level` | 无（SecurityInterceptor 整文件被注释） |
| 61 | GET | `/base/sysutilTest/syncCurrentTrack` | `SysTestController#syncCurrentTrack` | `selftest::sync_current_track` | 无（SecurityInterceptor 整文件被注释） |
| 62 | GET | `/base/sysutilTest/syncBaseInfo` | `SysTestController#syncBaseInfo` | `selftest::sync_base_info` | 无（SecurityInterceptor 整文件被注释） |
| 63 | GET | `/base/sysutilTest/syncHistroyTrack` | `SysTestController#syncHistroyTrack` | `selftest::sync_histroy_track` | 无（SecurityInterceptor 整文件被注释） |
| 64 | GET | `/base/sysutilTest/syncSuspiciousCar1` | `SysTestController#syncSuspiciousCar1` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 65 | GET | `/base/sysutilTest/syncSuspiciousCar2` | `SysTestController#syncSuspiciousCar2` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 66 | GET | `/base/sysutilTest/syncSuspiciousCar3` | `SysTestController#syncSuspiciousCar3` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 67 | GET | `/base/sysutilTest/syncSuspiciousCar4` | `SysTestController#syncSuspiciousCar4` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 68 | GET | `/base/sysutilTest/syncSuspiciousCar5` | `SysTestController#syncSuspiciousCar5` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 69 | GET | `/base/sysutilTest/syncSuspiciousCar6` | `SysTestController#syncSuspiciousCar6` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 70 | GET | `/base/sysutilTest/syncSuspiciousCar7` | `SysTestController#syncSuspiciousCar7` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 71 | GET | `/base/sysutilTest/syncSuspiciousCar8` | `SysTestController#syncSuspiciousCar8` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 72 | GET | `/base/sysutilTest/syncSuspiciousCar9` | `SysTestController#syncSuspiciousCar9` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 73 | GET | `/base/sysutilTest/syncSuspiciousCar10` | `SysTestController#syncSuspiciousCar10` | `router::blocked_sync_suspicious` | 无（SecurityInterceptor 整文件被注释） |
| 74 | GET | `/base/sysutilTest/syncOdsSzdnGantry` | `SysTestController#syncOdsSzdnGantry` | `router::blocked_gantry` | 无（SecurityInterceptor 整文件被注释） |
| 75 | GET | `/base/sysutilTest/separateSnapshotFlowTimeList` | `SysTestController#separateSnapshotFlowTimeList` | `router::blocked_separate` | 无（SecurityInterceptor 整文件被注释） |
| 76 | GET | `/base/sysutil/saveRedis` | `SysUtilController#saveRedis` | `sysutil::save_redis` | 无（SecurityInterceptor 整文件被注释） |
| 77 | GET | `/base/sysutil/carTrackQueryByCarNo` | `SysUtilController#carTrackQueryByCarNo` | `sysutil::car_track_by_car_no` | 无（SecurityInterceptor 整文件被注释） |
| 78 | GET | `/base/sysutil/carTrackQueryByTime` | `SysUtilController#carTrackQueryByTime` | `sysutil::car_track_by_time` | 无（SecurityInterceptor 整文件被注释） |
| 79 | POST | `/base/sysutil/changeTrailInfo` | `SysUtilController#changeTrailInfo` | `sysutil::change_trail_info` | 无（SecurityInterceptor 整文件被注释） |
| 80 | GET | `/base/sysutil/getByTrailBo` | `SysUtilController#getByTrailBo` | `sysutil::get_by_trail_bo` | 无（SecurityInterceptor 整文件被注释） |
| 81 | GET | `/api/v1/unified/{ds}/list` | `UnifiedQueryController#list` | `query::unified_list` | 无（SecurityInterceptor 整文件被注释） |
| 82 | POST | `/api/v1/unified/{ds}/export/submit` | `UnifiedQueryController#submitExport` | `query::unified_export_submit` | 无（SecurityInterceptor 整文件被注释） |
| 83 | GET | `/api/v1/unified/export/status/{taskId}` | `UnifiedQueryController#getExportStatus` | `query::unified_export_status` | 无（SecurityInterceptor 整文件被注释） |
| 84 | GET | `/base/trailtracks/list` | `ZdataTrailTracksController#list` | `crud::trail_tracks_list` | 无（SecurityInterceptor 整文件被注释） |
| 85 | GET | `/base/trailtracks/{uuid}` | `ZdataTrailTracksController#getInfo` | `crud::trail_tracks_ajax` | 无（SecurityInterceptor 整文件被注释） |

### 2.1 统一约定

- **鉴权**：无。`SecurityInterceptor` 与 `WebConfig` 在 Java 源码中整段被 `/* ... */` 注释，Spring 不会注册；Rust 侧不新增鉴权。
- **响应壳**：`AjaxResult` = `{code,msg,data?}`；`TableDataInfo` = `{total,rows,code,msg}`；`/api/v1/*` 返回 `Map<String,Object>`（`code/message/...`）。
- **分页参数**：`pageNum`（默认 1）、`pageSize`（默认 10；large/unified/progressive 默认 20）。
- **`{id}` 类型**：`gantryIp`、`tollStationIp`、`fwqclls` 为 `Long`（非法值 400）；其余为 String。
- **`/base/*` 的 `/{id}` 返回**：`feeGantry`、`feerecords`、`snapshotflow` 直接返回实体（null 时 200 空体）；其余包 `AjaxResult`。

### 2.2 Java 侧无法执行的端点（12 个）

| 端点 | Java 出处 | 原因 |
|---|---|---|
| `/base/sysutilTest/syncSuspiciousCar1..10` | `SysTestController.java:175-321` → `SysUtilServiceImpl.syncSuspiciousCarQutaz:1245-1635` | 依赖 `OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew`，该语句在全部 Mapper XML 中缺失 → `Invalid bound statement` |
| `/base/sysutilTest/syncOdsSzdnGantry` | `SysTestController.java:327-354` | 依赖 `selectGantryNum`（同样只有声明），且时间串 `"2025-11-01 00-00-00"` 过不了 `to_timestamp` |
| `/base/sysutilTest/separateSnapshotFlowTimeList` | `SysTestController.java:359-364` | 产出 `car_uspicious:*` 的唯一消费方无调用方，且会向外部 HTTP 推送数据 |

真实双端实测后，Rust 按 Java 的实际 HTTP 行为复刻：
- `syncSuspiciousCar1..10`：Java 方法返回 void，异步任务内部失败 → **HTTP 200 + 空体**；
- `syncOdsSzdnGantry`：同步执行并抛 `Invalid bound statement` → **HTTP 500**；
- `separateSnapshotFlowTimeList`：方法返回 void → **HTTP 200 + 空体**。

---

## 3. 数据层清单

### 3.1 数据库

- 类型：**GaussDB（openGauss）/ PostgreSQL**，JDBC：`postgresql://192.168.56.10:5432/RuoYi`
- 驱动：`org.postgresql.Driver`；连接池 Druid：`initial-size=5`、`maxActive=20`、`maxWait=60000ms`
- Schema：业务表全部在 **`jl_data01`**（`zdata_trail_tracks` 的 `@TableName` 未写 schema，但 Mapper 手写 SQL 使用 `jl_data01.` 前缀）
- Rust：`sqlx` + `PgPoolOptions`（max 20 / min 5 / acquire 60s）

### 3.2 表 / 主键 / Repo 对照

| 表 | Schema | 主键 | Rust Repo | SQL 来源 |
|---|---|---|---|---|
| `ods_szdn_service`（Java 类名 DwdLcztFwqjcxx） | jl_data01 | `id` | `FwqjcxxRepo` | XML `DwdLcztFwqjcxxMapper.xml`（25 列别名） |
| `dwd_lczt_sfsjcxx` | jl_data01 | `agent_pk` | `SfsjcxxRepo` | XML |
| `dwd_lczt_sfzjcxx` | jl_data01 | `agent_pk` | `SfzjcxxRepo` | XML |
| `ods_cxzt_fwqclls` | jl_data01 | `big_id` | `FwqcllsRepo` | XML |
| `ods_lwzxsfsj_fee_gantry_fusion_01` | jl_data01 | `big_id` | `FeeGantryRepo` | XML |
| `ods_lwzxsfsj_fee_records_01` | jl_data01 | `big_id` | `FeeRecordsRepo` | **XML 缺失**，按字段语义重建 |
| `ods_lwzxsfsj_fee_station_enter_01` | jl_data01 | `cardid` | `FeeStationEnterRepo` | XML |
| `ods_lwzxsfsj_fee_station_exit_01` | jl_data01 | `big_id` | `FeeStationExitRepo` | XML |
| `ods_rt_szdn_snapshot_flow_addcode` | jl_data01 | `big_id` | `SnapshotFlowRepo` | **XML 缺失**，按字段语义重建 + 3 个 `@Select` |
| `ods_rt_szdn_snapshot_flow_provcapture_addcode` | jl_data01 | `guid` | `ProvCaptureRepo` | XML |
| `ods_rt_szdn_snapshot_flow_stationcapture_addcode` | jl_data01 | `deviceid` | `StationCaptureRepo` | XML |
| `ods_szdn_gantry` | jl_data01 | `id` | `GantryRepo` | XML |
| `ods_szdn_gantry_ip` | jl_data01 | `id` (bigint) | `GantryIpRepo` | XML |
| `ods_szdn_province_border_vehicle_weight_newstructure` | jl_data01 | `datauuid` | `VehicleWeightRepo` | XML |
| `ods_szdn_section` | jl_data01 | `id` | `SectionRepo` | XML |
| `ods_szdn_toll` | jl_data01 | `id` | `TollRepo` | XML |
| `ods_szdn_toll_station_ip` | jl_data01 | `id` (bigint) | `TollStationIpRepo` | XML |
| `ods_yhgl_v_base_org` | jl_data01 | `big_id` | `OrgRepo` | XML |
| `zdata_trail_tracks` | jl_data01 | `uuid` | `TrailTracksRepo` | XML + `getHistoryTrail` |
| `zdata_location_dict` | jl_data01 | `big_id` | `LocationDictRepo` | XML |
| `zdata_trail_fitting` | jl_data01 | `big_id` / 游标键 `cid` | `TrailFittingRepo` | XML + `selectByCursorShard` |
| `kafka_message_record` | jl_data01 | `id` | `KafkaMessageRecordRepo` | XML + DDL |

### 3.3 SQL 语义要点

| 场景 | Java | Rust |
|---|---|---|
| 列表分页 | PageHelper 隐式注入 `LIMIT/OFFSET` | `repo.list(q, limit, offset)` 显式下推 `LIMIT $n OFFSET $m` |
| 时间区间（同步游标） | `>= start AND < end`（**半开区间**） | 同左，`list_by_cursor_shard` |
| 对账计数 | `BETWEEN start AND end`（闭区间） | 同左，`count_between` |
| 模糊匹配 | `LIKE '%x%'`（部分 XML）/ `ILIKE` | `ILIKE $n`（忽略大小写，与 Go 版一致） |
| 占位符 | MyBatis `#{}` → JDBC `?` | PostgreSQL `$1..$n`（注释中标注差异） |
| 车辆轨迹历史 | `to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')` + `now() - 180 / - 3` | 原样保留 SQL 表达式 |
| 服务区 Mapper | 表名与类名不一致，SELECT 25 列别名 | `FWQ_SELECT` 常量逐列复刻 |

### 3.4 事务边界

- Java 侧**没有** `@Transactional` 注解（全仓检索为 0）；MyBatis 单语句自动提交。
- 消费端 `saveOrUpdate` = `selectById` → `insert`/`update` 两次访问，与 Java 一致（非原子）。
- Rust 提供 `Db::begin()`（`sqlx::Transaction`）作为将来需要事务时的显式入口；
  现有链路保持与 Java 相同的单语句/两语句语义。

---

## 4. 中间件与外部依赖

### 4.1 Redis（Lettuce / RedisTemplate）

| Key | 用途 | TTL |
|---|---|---|
| `sys_config:data_query` | 查询范围开关（`queryall` 与否） | 无（配置项） |
| `dev_post` / `gantry_ip` / `station_ip` / `section_road_map` / `station_info` / `gantry_list` | 字典缓存 | 无（`syncBaseInfo` 重建） |
| `car_list_jc` | 重点车辆列表 | 无（运维写入） |
| `trail:{carNo}` → `car_curent_trail:{carNo}` | 实时轨迹 | 无 |
| `car_history_trail:{carNo}` / `car_sync_time:{carNo}` | 历史轨迹 / 同步时间 | 无 |
| `pulsar:msg:processed:{dataId}` | 消费幂等 | 86400s |
| `reliability:msg:status/content:{messageId}` | 三重确认 | 86400s |
| `reliability:timeout:queue` | 超时补偿队列 | 无 |
| `reliability:device:heartbeat:{deviceId}` | 设备心跳 | 300s |
| `detection:reported:{小时}` / `detection:device:count:{dev}:{日}` | 丢包检测 | 48h |
| `monitoring:delay:*` | 延迟样本 | 48h |
| `table:count:{table}` | 渐进式查询数据量级别 | 1h |
| `es:sync:watermark:{snapshot,fee,trail}` | 增量同步水位 | 30 天（Rust 侧设置） |

序列化：Java 用 FastJson2/JDK；Rust 统一 JSON 字符串。**切换期两类 key 不能共用**，需先 `DEL`（见 README「升级注意」）。

### 4.2 消息队列

| 组件 | Java | Rust | 结论 |
|---|---|---|---|
| Kafka | `spring-kafka` + `KafkaTemplate` | `rdkafka`（librdkafka 2.12，cmake-build） | 1:1：同步 ack、按 key 分区、手动提交、指数退避、DLQ |
| Pulsar | `pulsar-client` + `@PulsarConsumer` | 无成熟 Rust 客户端 → 复用 Kafka 同语义 | 需架构决策；业务只依赖 `Bus`，接真 Pulsar 只需新增实现 |
| RocketMQ | `rocketmq-spring-boot-starter` | 生态无稳定客户端 | 需架构决策；Java 侧无活跃消费者 |
| RabbitMQ | `spring-boot-starter-amqp` | `lapin` 可用但未接线 | Java 配置存在、消费者未启用；Rust 保持 `enabled: false` |

消息格式：`{operationType, data}`；幂等 key `pulsar:msg:processed:{dataId}`；消费成功提交 offset，失败重投，超过 `pulsar.max-retry-times` 投 `{topic}.DLQ`。

### 4.3 Elasticsearch

- 客户端：Java `RestHighLevelClient`；Rust `reqwest` 直连 REST（search / count / scroll / clear scroll / bulk / delete）。
- 索引：`snapshot_flow`、`fee_records`、`trail_fitting`（配置项原样保留）。
- 映射与 ILM：`resources/es/*.json` 从 Java `resources/es/index` 与 `resources/sql` 原样复制。
- 路由：有模糊条件 / 超 `optimization.query.es-force-days`（30 天）/ FEE、TRAIL 一律走 ES；ES 失败自动降级 GaussDB。

### 4.4 定时任务（21 个 `@Scheduled`）

| 任务 | Cron / fixedRate | 默认状态 | Rust |
|---|---|---|---|
| TrackTask.syncBaseInfo | `0 0 0 * * ?` | 运行 | `scheduler::build` |
| TrackTask.syncCurrentTrack | `0 0/3 * * * ?` | 运行 | 同左 |
| TrackTask.syncHistroyTrack | `0 0 4 * * ?` | 运行 | 同左（拼写保留） |
| DataFlowTask.processPendingQueue | `0 */1 * * * ?` | 运行 | 同左 |
| DataFlowTask.syncGantryCaptureData | `0 */5 * * * ?` | 运行（方法体为空） | 同左（仅日志） |
| DataLossDetectionService | 30 分钟 | 运行 | `Every(30m)` |
| DelayMonitoringService | 10 分钟 | 运行 | `Every(10m)` |
| DataReliabilityService.compensation | 60 秒 | 运行 | `Every(60s)` |
| DataReliabilityService.checkOfflineDevices | 5 分钟 | 运行 | `Every(5m)` |
| GaussEsConsistencyService | `0 30 2 * * ?` | **受 `consistency.reconcile.enabled` 控制（默认 false）** | 同左 |
| CarTask 11 个 | `0 0/15/30/45 ...` | **Java 整文件块注释，从未执行** | 登记 + `Disabled: true` |

### 4.5 其它

| 依赖 | Java | Rust |
|---|---|---|
| 外部 HTTP | Forest（`HttpSysUtilApiService`，60s 超时、2 次重试） | 未接线（Java 调用链路 `syncSuspiciousCarDB` 无调用方） |
| Flink | `VehicleTrackFlinkJob`（独立作业） | **不移植**（见 6.5） |
| 鉴权 | `SecurityInterceptor`（整文件注释） | 不实现 |
| 线程池 | `ThreadPoolTaskExecutor`（core=2×CPU，max=3×，队列 1000，CallerRuns） | `tokio::spawn` + `Semaphore`（导出 2/4 并发） |
| 日志 | Logback + `logging.level` | `tracing` + `RUST_LOG`（text/json） |

---

## 5. 配置项清单

| Java 配置 | Rust 配置 | 默认值 | 说明 |
|---|---|---|---|
| `server.port` | `server.port` | 9901 | 一致 |
| `server.servlet.context-path` | `server.context-path` | `/` | 一致 |
| `spring.datasource.dynamic.datasource.master.url` | 同名 | GaussDB URL | JDBC 前缀会被剥离 |
| `...master.username/password` | 同名 | gaussdb / OpenGauss@123 | 一致 |
| `spring.redis.host/port/database` | `redis.*` | 127.0.0.1 / 6379 / 0 | 一致 |
| `spring.redis.lettuce.pool.max-active` | `redis.pool-size` | 8 → 16 | Rust 侧连接管理器 |
| `spring.kafka.bootstrap-servers` | `kafka.bootstrap-servers` | localhost:9092 | 空值降级为 Noop |
| `spring.kafka.topic.snapshot-flow` | `kafka.topic.snapshot-flow` | ods-rt-szdn-snapshot-flow | 一致 |
| `spring.pulsar.*` | `pulsar.*` | 见 config | 全部保留 |
| `elasticsearch.*` | `elasticsearch.*` | localhost:9200 | 全部保留 |
| `optimization.query.*` | `optimization.query.*` | 30000 / 10000 / 30 | 一致 |
| `optimization.export.*` | `optimization.export.*` | 2000 / 100000 / `/data/export` / 5 | 一致 |
| `sync.*` | `sync.*` | 1000 / true / 60000 | 一致 |
| `consistency.reconcile.*` | 同名 | false / 3 / 0.01 / `0 30 2 * * ?` | 一致 |
| `reliability.*` | 同名 | 30000 / 5 / 60 / 10000 | 一致 |
| `detection.*` | 同名 | 60 / 30 / 5 | 一致 |
| `monitoring.*` | 同名 | 5000 / 3000 / 10000 / 30000 / 10 | 一致 |
| `mybatis-plus.*` | — | — | Rust 无 ORM 配置 |
| `logging.level.root` | `logging.level` | INFO | 一致 |
| `isLocalhost` | `app.env` | local | 语义一致 |
| `sysbaseUrl` | `app.sysbase-url` | 同左 | 一致 |
| （无） | `app.consumer-enabled` | true | **Rust 新增**：消费端开关 |
| （无） | `app.enable-scheduler` | true | **Rust 新增**：调度器开关 |

优先级：**命令行 `--config` > `CAR_MONIT_CONFIG` > `config/application.yaml` > 代码默认值**。

---

## 6. “不可 1:1 直接翻译”的阻塞点与 Rust 方案

| # | Java 机制 | 为什么不能照搬 | Rust 方案 |
|---|---|---|---|
| 6.1 | `@RestController` + 注解扫描 | Rust 没有运行时注解扫描 | 显式 `Router::route`；`tests/router_test.rs` 固化 85 条端点 |
| 6.2 | `@Autowired` / `@Service` / `@Bean` | 无 DI 容器、无反射 | `main.rs` 组合根 + `Arc<AppState>` + 编译期依赖检查 |
| 6.3 | MyBatis 动态 SQL（`<if>` / `<foreach>`） | XML 运行时解析 | `Cond` 枚举 + `QueryBuilder` 生成 `$n` 参数；列名全部是 `&'static str` 白名单 |
| 6.4 | PageHelper ThreadLocal | Rust 无隐式上下文 | 显式 `PageParams` → `LIMIT/OFFSET` |
| 6.5 | Flink `VehicleTrackFlinkJob` | 独立流处理运行时/Checkpoint 状态 | **不移植**：它是独立部署的 Flink 作业，不是 Spring Web 服务的一部分；如需迁移应单独立项 |
| 6.6 | Pulsar 客户端 | Rust 生态无生产级官方客户端 | `Bus` 接口 + Kafka 同语义实现（手动 ack、DLQ、幂等 key 相同）；接真 Pulsar 时新增 `PulsarBus` |
| 6.7 | RocketMQ starter | Rust 客户端生态不成熟 | 不接线；Java 侧无活跃消费者 |
| 6.8 | `@Transactional` AOP | Rust 无代理/自调用陷阱 | 显式 `Db::begin()`；现有链路无事务注解，保持同语义 |
| 6.9 | Lombok `@Data` / `@Accessors(chain)` | 编译期代码生成 | `serde` + 公开字段；setter 链式调用改为结构体更新 |
| 6.10 | Jackson/Fastjson 多态与动态 `Map` | Rust 静态类型 | 固定结构体 + `serde_json::Value`（仅三表合并/ES 文档等确需动态之处） |
| 6.11 | 继承（`BaseController` / `BaseEntity`） | Rust 无类继承 | 组合（`PageParams` / `AppState`）+ trait（`ReadRepo<T>`） |
| 6.12 | 异常 + `@ControllerAdvice` | Rust 无异常 | `AppError` + `Result` + `IntoResponse`；`?` 传播 |
| 6.13 | Druid / p6spy / SQL 日志 | 连接池与代理是 starter 能力 | `sqlx::PgPool`；`log-sql` 开关保留，SQL 日志用 `tracing` |
| 6.14 | 运行时 `SecurityInterceptor` | 整文件被注释 | 保持“无鉴权”；若恢复，应在 `middleware.rs` 增加 tower layer |

---

## 7. 迁移中发现的 Java 侧既有问题（Rust 原样保留或显式标注）

| # | 位置 | 问题 | Rust 处理 |
|---|---|---|---|
| 1 | `CarTask.java` | 整文件处于块注释，11 个 `@Scheduled` 从未执行 | 登记但 `Disabled: true` |
| 2 | `SysUtilServiceImpl.syncSuspiciousCarQutaz` | 依赖不存在的 Mapper 语句 | 按 Java 实际返回复刻：10 个 200 空体 + `syncOdsSzdnGantry` 500 |
| 3 | `changeData` L481-482 | `lat` 被赋成 `lon` | **照抄**（注释标注） |
| 4 | `changeData` L471 | `indexType` 在循环外声明，未命中时沿用上一点 | **照抄** |
| 5 | `getTrailBoList` L2054 | 仅当 `captureTime` 含 `T` 才赋值 | **照抄** |
| 6 | `mapTrailBoList` | 注释写 3 分钟，实际阈值 4 分钟 | 按 4 分钟实现 |
| 7 | `SecurityInterceptor` / `WebConfig` | 整文件块注释 | 不实现 |
| 8 | `PulsarMessageRecordMapper.xml` | 只有一行未闭合的 XML 声明 | 不移植（`PulsarProducerService` 非 Bean） |
| 9 | `OdsLwzxsfsjFeeRecords01Mapper` / `OdsRtSzdnSnapshotFlowAddcodeMapper` | 自定义 `selectList` 无 XML | 按字段语义重建（与 Go 版一致） |
| 10 | `feerecords` 数据权限 | `flag="JiAnDong"` 无对应列 | 记 WARN 后不过滤（注释标注） |
