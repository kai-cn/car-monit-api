# car-monit-api V3 架构落地决策记录

> 版本：V3 阶段一（对应 `architecture-traffic-query-design.md` v1.3 §6.1/§6.2 api 侧职责）
> 工作树：`d:/work/IdeaProjects/car-monit-api-java-V3`
> 约束：不改动原工作树；提交仅限 `car-monit-api-java-V3` 分支，不 push、不动其他分支。

## 1. 本次实现清单（api 侧阶段一）

| # | 交付物 | 落地位置 | 验证方式 |
|---:|---|---|---|
| 1 | 三表月分区迁移/回滚脚本（幂等、蓝绿切换、NOT NULL、`(time DESC, pk)` 索引） | `pro-business-api/src/main/resources/sql/v3/` | openGauss 3.0 真实实例完整演练：000→001→002→006→003→回滚，见 §7.12 |
| 2 | 收费车牌派生列与 Outbox/DLQ/对账表 | 同上 | 004/007 已执行；索引、Outbox、对账、DWS 表均存在 |
| 3 | ES 月索引模板、mapping、ILM、索引创建/回灌脚本 | `pro-business-api/src/main/resources/es/v3/`、`scripts/v3/es-init.ps1` | JSON 语法校验 + 模板字段与设计文档逐项比对 |
| 4 | 车牌解析器 `赣B21E85_0` | `com.ruoyi.base.service.v3.plate` | 样例单测（临时 harness，不落仓库） |
| 5 | ES 月索引/别名/Template 管理 + 文档构建器 | `com.ruoyi.base.service.v3.es` | 编译 + 代码审阅 |
| 6 | ES 组合查询（时间范围 + 维度 term + 车牌 ngram，PIT/search_after） | `com.ruoyi.base.service.v3.query` | 真实 ES 7.15.2 HTTP E2E 通过（§7.4/§7.5） |
| 7 | 三个查询接口改造 | `OdsRtSzdnSnapshotFlowAddcodeController`、`OdsLwzxsfsjFeeRecords01Controller`、`SysUtilController` | 编译 + 契约审阅 |
| 8 | CDC/Outbox + 幂等 `_id` + 对账补偿骨架 | `com.ruoyi.base.service.v3.sync` | 编译 + 代码审阅 |
| 9 | 导出任务模型与接口（展示字段 ES PIT / 全字段 GaussDB 游标） | `com.ruoyi.base.service.v3.export`、`controller/v3` | 编译 + 代码审阅 |
| 10 | backend 契约：大屏预聚合 4 个端点 + `dws_*` DDL | `controller/v3/BigScreenStatsV3Controller`、`service/v3/bigscreen`、`sql/v3/007_dws_tables.sql` | 编译 + 契约字段比对 |
| 11 | backend 契约：`/api/v1/large/export/submit|status|download` | `LargeScaleQueryController`、`ExportTaskService` | 编译 + 契约字段比对 |
| 12 | backend 契约：`/api/v1/bigscreen/warning/list` + `car-warning` 模板/索引/回灌 | `BigScreenWarningV3Controller`、`CarWarningSearchService`、`car_warning_template.json` | 真实 ES 回灌 1627 行；captureType/多值已实测（§7.14） |

## 2. 决策记录（决策 / 备选 / 理由 / 影响）

### D1 数据库迁移采用“影子分区表 + 窗口切换”，不原地破坏性 DDL
- 决策：迁移脚本创建 `*_v3` 影子分区表，按源表动态列定义（读取 `information_schema`）克隆全部列，回填数据后再由 `cutover` 脚本原子重命名；回滚脚本按状态反向重命名。
- 备选：原地 `ALTER TABLE ... PARTITION BY`；直接 `TRUNCATE + INSERT`。
- 理由：设计文档 §7.2 待确认项 13 明确指出维护窗口/在线重建需确认；GaussDB/openGauss 不支持原地把普通表转分区表，且会锁表。影子表可在低峰期逐步回填，失败可随时丢弃。
- 影响：迁移期间源表继续写入，切换窗口内需短暂停写；脚本不自动执行，必须运维在测试 schema 演练后手动运行。

### D2 分区粒度与预建范围
- 决策：统一按月 RANGE 分区；默认从源表最小时间所在月建到“当前月 + 3 个月”；13 个月热保留，历史分区归档。
- 备选：按周（轨迹表备选）；按天（明确不做）。
- 理由：设计文档 §2.5/§5.2 已给出量化结论。
- 影响：轨道表单分区约 35GB，超过 80GB 时再切周分区。
- **openGauss 3.0 修正**：不支持 `DETACH PARTITION`；归档采用“按范围 COPY 到独立归档表 + `DROP PARTITION`”（见 D15、005 脚本），不直接 DELETE。

### D3 主键与 NOT NULL
- 决策：抓拍/收费 `PRIMARY KEY (pk, time)`，轨迹 `PRIMARY KEY (cid, extime)`；`big_id`/`cid`、时间字段 NOT NULL。
- 备选：保留单列 `big_id` 主键（分区表下不能全局唯一）。
- 理由：设计文档 §4.2.3/§5.2。
- 影响：迁移前置校验源数据时间列/主键列 NULL 数，非 0 时脚本 `RAISE EXCEPTION`，需先清洗。

### D4 收费车牌派生列落在明细表
- 决策：收费表新增 `plate_core varchar(32)`、`plate_color_code smallint NOT NULL DEFAULT -1`、`plate_color_raw varchar(16)`、`plate_raw varchar(100)`、`plate_parse_status varchar(16)`；由 Flink/ETL 写入，API 侧解析器作为同一契约实现。
- 备选：旁路映射表 join。
- 理由：设计文档 §5.1.6；旁路 join 会影响列表性能。
- 影响：ETL 需同步改造；迁移只搬原始列，派生列由后续 ETL/回灌按同一解析器补齐（不在 SQL 内做颜色码兜底）。

### D5 ES 索引命名、分片与别名
- 决策：月索引 `snapshot-flow-YYYYMM`、`fee-records-YYYYMM`、`trail-fitting-YYYYMM`；写别名 `*-write` 指向当月，读别名 `*-read` 指向保留期全部月索引；1 主分片、1 副本、refresh 5s、`best_compression`、`max_result_window=10000`。
- 备选：沿用现状固定索引 `snapshot_flow` / 6 分片。
- 理由：设计文档 §2.4/§5.3.1/§5.3.3；写入约 8 条/秒/表，6 分片无收益。
- 影响：旧索引不删除、不改动；新查询默认读 `*-read` 别名，需先执行初始化脚本。旧路径可通过配置开关回退。

### D6 Mapping 字段口径
- 决策：`dynamic: strict`；维度编码 `keyword`；维度名称 `keyword + index:false`（仅展示/导出）；车牌 `plate_norm`（`keyword` + `.ngram`）且 `.ngram` 仅 2–3 字符；收费 `plate_color_code` 为 `keyword`（值 `"0"`…，未知 `"-1"`）；轨迹只由 `envehicleid` 生成 `plate_norm`，`exvehicleid` 仅 `index:false` 兼容；ES 不存 `trailpoints` 与收费 text 大字段。
- 备选：延续现状对 5 个名称字段全 ngram（已否决）。
- 理由：设计文档 §5.1.4/§5.1.6/§5.3.2。
- 影响：为保持既有接口响应字段，mapping 额外保留 `platenumber`/`vehicleplate`/`envehicleid` 等展示字段（`index:false`），查询只走 `plate_norm`。
- **实测修正**：`.ngram` 必须保留位置数据（使用默认 `index_options`），不能设 `index_options: docs`；
  否则 `match_phrase` 报 `field was indexed without position data`。该问题已在真实 ES 7.15.2 复现并修复。

### D7 车牌颜色字典（单一事实源：MySQL carmonitdb）
- 决策：颜色码表**只从 MySQL 3307 `carmonitdb.sys_dict_type` + `sys_dict_data`（dict_type=plate_color）读取**；
  API 启动加载 + 每 5 分钟定时刷新 + 内存原子快照；MySQL 不可用时保留上一次成功快照；
  代码内不再维护 `0..9` 或任何颜色词兜底映射。
- 实测字典（按 dict_sort）：
  | dict_value | dict_label |
  |---:|---|
  | 0 | 蓝色 |
  | 1 | 黄色 |
  | 3 | 黑色 |
  | 6 | 白色 |
  | 5 | 绿色 |
  | 7 | 临时 |
  | 93 | 黄绿双拼底黑字 |
  | 4 | 渐变绿底黑字 |
  | 9 | 其他 |
- **有效码**：`0,1,3,4,5,6,7,9,93`；`0` 是合法码（蓝色）。
- 旧格式颜色词从 dict_label 派生别名（去“底黑字”、去尾部“色”、`黄绿双拼底黑字` 额外兼容“黄绿”），
  不再硬编码词表；最长匹配优先。
- 未知/异常行为：
  - 码值不在字典（如 `_99`）：`plate_color_code=-1`、`plate_parse_status=color_unparsed`、`plate_color_name=未知(99)`；
  - 无颜色后缀：`-1`、`no_color`、`plate_color_name=未知`；
  - 畸形/无法解析：`-1`、`unparsed`、`plate_color_name=未知(<原颜色段>)`；
  - 过滤：ES `plate_color_code` 使用 `"-1"` 表示未知，合法码直接 term；名称只用于展示，不参与过滤。
- 导出：`plate_color_name` 为派生展示字段；display 路径由 `plate_color_code + plate_color_raw` 生成，
  full 路径在 CSV 末尾追加该列；不写入 ES mapping。
- 配置：`traffic.plate.color.dict.*`（url/username/password/dict-type/refresh-interval-ms），
  口令用 `CARMONIT_MYSQL_USERNAME` / `CARMONIT_MYSQL_PASSWORD` 覆盖；联调环境已切换为只读账号
  `carmonit_ro`（仅 SELECT `sys_dict_type/sys_dict_data/car_warning_info/car_info/car_except_record/car_confim_free/car_aduit_free`），
  口令只写入 `D:\work\runtime-logs\start-api-v3.ps1`（仓库外），不提交。
- 理由：业务已确认原则上以字典表为唯一事实源，避免代码与字典双维护；`dict_plate_color`（GaussDB）实测不存在，废弃。
- 影响：MySQL 字典不可用时颜色码会暂记为未知（不阻塞车牌入库）；恢复后定时刷新自动生效。
  上线前仍建议业务导出字典快照做一次人工核对。

### D8 查询路由与降级（安全默认：legacy）
- 决策：三个既有接口**默认 `legacy`**，避免 ES 未初始化时默认部署直接 503。
  显式配置 `traffic.query.engine=es` 后，启动阶段做就绪检测（ES 可 ping + 三表 `*-read` 别名 + 三表当月索引）；
  任一缺失则自动回退 `legacy` 并打 WARN（不阻断启动）。运行期 ES 故障仍返回 503，**不回退 GaussDB `LIKE`**；
  运维可 `POST /api/v3/es/activate?engine=es|legacy` 临时切换，持久化切换用 `TRAFFIC_QUERY_ENGINE` 或 `application.yml`。
- 备选：默认 es + 每请求回退 legacy；ES 故障回退 GaussDB 全模糊（设计明确否决）。
- 理由：默认值必须保证“未初始化 ES 也能正常出数”；启动检测把“配置错误/初始化遗漏”在启动日志里暴露；运行期禁止模糊回退。
- 影响：默认部署行为与旧实现一致；ES 初始化+回灌完成后需显式切 `es`。切换前需 `GET /api/v3/es/readiness` 确认 `ready=true`。

### D9 深分页与计数
- 决策：既有接口保留 `pageNum/pageSize` 契约，`pageSize≤100`、`from+size≤10000`；超窗返回 400 并提示使用 V3 `search_after` 接口。V3 接口返回 `pitId`、`searchAfter`、`hasMore`。总数使用 `track_total_hits=10000` 封顶。
- 备选：沿用 `from+size` 无上限；使用 scroll 做用户分页（明确否决）。
- 理由：设计文档 §4.3/§5.3.5。
- 影响：前端深分页需改造；`total` 为封顶值，UI 展示“约 1 万+”。

### D10 同步链路
- 决策：新增 `jl_data01.search_sync_outbox`（与事实行同事务写入，由 Flink/ETL 或触发器写入）、`search_sync_dlq`、`search_sync_reconcile`；API 侧提供 Outbox relay（轮询→Kafka `search-sync`）、Kafka 消费者（bulk 幂等 `_id`）、失败重试与 DLQ。CDC（Debezium）为首选，Outbox 为当前可运行兜底；**业务代码不写 ES**。
- 备选：应用双写 ES；Flink 内直接写 ES（均否决）。
- 理由：设计文档 §5.6.2/§8.3。
- 影响：需 Kafka 与 outbox 表；同步延迟 P99 目标 ≤30s。

### D11 对账与补偿
- 决策：按分钟桶比对 GaussDB 行数与 ES `_count`，偏差超过 `0.1%` 记录并触发按桶回灌；小时级/周级抽样作为后续增强。
- 备选：只做全量重建。
- 理由：设计文档 §5.6.3。
- 影响：需要 `search_sync_reconcile` 表与只读查询权限；对账默认关闭，需显式开启。
- **实测修复**：
  1. openGauss 3.0 不支持 `ON CONFLICT`，结果落库改为 `UPDATE + INSERT`（否则异常被 debug 日志吞掉，表里看不到结果）；
  2. 原逻辑先写 DRIFT 再判断 `alreadyDrift`，导致永远不触发补偿；改为先查旧状态、再写结果、再提交回灌；
  3. 新增 `POST /api/v3/sync/reconcile?startTime&endTime&bucketMinutes`，可对历史区间跑分钟桶对账并返回 `totalBuckets/driftBuckets/repairBuckets`。
- 实测（2025-10-01 08:00~09:00，bucket=1）：180 桶，1 个 DRIFT（人为删除 1 条 ES 文档），提交 1 个桶回灌；
  回灌后 ES 文档恢复（该小时 11 条），再次对账 180 桶全部 OK、0 补偿。详见 §7.13。

### D12 导出
- 决策：任务模型 `pending/running/paused/failed/done`；展示字段走 ES PIT + `search_after`；全字段走 GaussDB 分区游标 + `setFetchSize` 流式 CSV/GZIP；全局 2 worker；本期输出到本地目录，对象存储与签名下载作为接口字段预留。
- 备选：同步导出；全字段入 ES（均否决）。
- 理由：设计文档 §5.5。
- 影响：对象存储/审批/审计未实现，接口返回本地文件路径，生产接入前需补齐。
- **能力补齐（backend 契约）**：
  - display 路径 fee 表固定补齐 `plate_color_name`（即使 backend 请求字段未包含），旧同步 Excel 有该列；
  - 全字段路径支持维度过滤：`snapshot` 直连列，`fee` 经 `LEFT JOIN ods_szdn_gantry`（`org_code/section_code/road_code/toll_code`）下推，`trail` 无维度；
  - 维度值支持逗号多值，SQL 使用 `IN (?,...)`（terms 语义）；
  - 新增 `GET /api/v3/export/capabilities`，返回 `modes/tables/dimensionFilters/displayFields/displayAliases/plateColorNameField`，backend 不再硬编码探测。

### D13 轨迹接口
- 决策：`/base/sysutil/carTrackQueryByCarNo` 先由 ES 取轨迹元数据（`plate_norm` + `extime` 范围），再按 `(cid, extime)` 批量回查 GaussDB `trailpoints`，保持既有 `TrailInfo` 响应结构；不在线 `UNNEST`。
- 备选：列表直接返回 GaussDB 全字段；ES 存轨迹点（均否决）。
- 理由：设计文档 §5.8.4/§9。
- 影响：详情页有第二次 DB 查询；列表页不回传轨迹点。

### D14 默认端口 9902
- 决策：`server.port` 默认改为 `9902`，与 backend `vehicleMonitor.baseUrl` 默认值及本机联调端口一致；
  `scripts/v3/es-init.ps1` 默认 `ApiBaseUrl` 同步改为 9902。
- 备选：继续 9901 + 启动参数 `-Dserver.port=9902` 覆盖。
- 理由：避免每次部署依赖启动参数；端口不一致会导致 backend 调用超时/连接失败。
- 影响：若历史脚本显式传 9901，需要同步调整；Python 版仍为 9901，互不冲突。

### D15 openGauss 3.0 分区 DDL 的实际约束（实测）
- 事实（openGauss 3.0.0，2022-04-01 build）：
  1. `CREATE TABLE ... PARTITION BY RANGE (col)` 不能没有分区定义，报 `syntax error at end of input`；
  2. 不支持 `CREATE TABLE ... PARTITION OF ... FOR VALUES FROM (...) TO (...)`；
  3. 不支持 `CREATE INDEX IF NOT EXISTS`（普通表和分区表都不行）；
  4. 分区父表索引必须显式 `LOCAL`，否则与主键全局索引冲突：
     `Global and local partition index should not be on same column`；
  5. 不支持分区表 partial index（`LOCAL WHERE` / `WHERE LOCAL` 均语法错误）；
  6. 不支持 `ALTER TABLE ... DETACH PARTITION`；支持 `DROP PARTITION`、`RENAME PARTITION`；
  7. 支持 `ALTER TABLE ... ADD PARTITION <name> VALUES LESS THAN (...)`，但新上界必须大于最后分区的上界；
  8. 父表 `relkind='r'`，分区信息在 `pg_partition`（`parttype='r'` 父表，`'p'` 分区，`boundaries` 为上界数组）；
  9. 分区不是独立 `pg_class` 关系，不能按 `parent_pYYYYMM` 直接 SELECT。
- 决策：迁移脚本按上述限制改写：
  - `001` 在 CREATE 内一次性生成“历史月 ~ 预建月”分区列表，且不使用 MAXVALUE/default 分区；
  - `005` 用 `ALTER TABLE ... ADD PARTITION` 预建，用 `pg_partition` 判断存在/上界；归档为“按范围 COPY 到 `*_archive_YYYYMM` + DROP PARTITION”；
  - `006` 用 `pg_class` 存在性检查替代 `IF NOT EXISTS`，索引统一 `LOCAL` 且去掉 partial predicate；
  - `002/004` 的 upsert 改为 `UPDATE + INSERT`（`ON CONFLICT` 不支持）。
- 影响：脚本已按 openGauss 3.0 实测语法执行通过（见 §7.12）；若后续升级 openGauss/PG 版本，可再切回原生 `PARTITION OF` 语法，但当前脚本保持兼容 3.0。

### D16 DWS 预聚合表不按月分区
- 决策：`dws_escape_daily` / `dws_income_daily` / `dws_warning_section_daily` 使用普通表 + 主键/查询索引，不按月分区。
- 备选：沿用设计稿的 `PARTITION BY RANGE (stat_date)`。
- 理由：DWS 为按日聚合小表（每年约 3.6 万行/表），分区收益有限；openGauss 3.0 分区 DDL 限制（D15）会显著增加建表/维护复杂度。
- 影响：`007_dws_tables.sql` 与实际库一致；DWS ETL 幂等重算按 `stat_date` 范围 DELETE+INSERT；如后续数据量增长再评估分区。

### D17 导出能力契约（`/api/v3/export/capabilities`）
- 响应（裸 JSON，与现有字段兼容并扩展）：
  - `modes=["display","full"]`、`tables=["snapshot","fee","trail"]`；
  - `fullDimensionFilters=true`、`multiValueDimensionFilters=true`、`plateColorName=true`、`plateColorNameField=plate_color_name`；
  - `dimensionFilters={snapshot:[orgcode,sectioncode,roadcode,tollcode,gantrycode], fee:[...], trail:[]}`；
  - `nameFilters=[orgname,sectionname,roadname,gantryname,tollname]`；
  - `displayFields={snapshot:[...],fee:[...],trail:[...]}`、`displayAliases={camelCase→snake_case}`、`fullFields=all_columns`。
- 决策：display 路径 fee 表始终输出 `plate_color_name`；full 路径维度过滤多值走 `IN`；`trail` 不支持维度过滤（无对应列）。
- 影响：backend 可直接读取该元数据放开 `full-dimension-filters` 与字段白名单，删除硬编码判断；backend `application.yml` 已改为 `full-dimension-filters: true`（backend 分支单独提交）。

### D18 warning/list 的 captureType 与多值维度
- 决策：
  - ES `car-warning` 模板新增 `capture_type`（keyword），由 `CarWarningDocumentBuilder` 派生：
    优先取 `track_names` 首段 `Type:code` 的类型（`StationCapture/GantryCapture/ServiceAreaCapture`）；
    缺失时按 `in_station_id → StationCapture`、`gantry_station_id/gantry_code → GantryCapture`、`fwqbm → ServiceAreaCapture` 推断。
  - `warning/list` 支持显式 `captureType`（逗号多值，terms）；
    同时兼容旧位置哨兵：`tollCode=StationCapture`、`gantryCode=GantryCapture`、`fwqbm=ServiceAreaCapture`
    会被提取为 `capture_type` 过滤，不再当作真实编码。
  - 所有维度参数（roadCode/sectionCode/tollCode/gantryCode/fwqbm/escapedType/captureType）支持逗号多值 terms；
    出现 `all` 视为取消该维度过滤；`gantryCode` 同时匹配 `gantry_code`/`gantry_station_id`；
    `carNo` 支持逗号多值，完整车牌 term、片段 ngram，任一命中。
- 影响：backend 可删除 `CAPTURE_TYPE_UNSUPPORTED` / `MULTI_VALUE_UNSUPPORTED` 的 Redis 兜底分支；
  本次已回灌 1627 条 car-warning 文档以补齐 `capture_type`（分布 1200/402/25）。契约变化已记录于 §6.3。

### D19 MySQL 只读账号与口令注入
- 决策：联调/生产使用 `carmonit_ro` 只读账号（仅 SELECT 7 张源表），口令通过 `CARMONIT_MYSQL_USERNAME/PASSWORD`
  环境变量注入，由仓库外 launcher 设置；仓库与文档不写明文口令。
- 备选：继续使用 MySQL 超级用户（已否决）。
- 影响：字典刷新、DWS ETL、car-warning CDC 已验证在只读账号下正常；DDL/写入 MySQL 的运维操作需另用管理账号。

## 3. 接口兼容与错误码

- 既有三个接口的 URL、请求参数名、响应结构保持；`rows` 元素仍为原 domain 序列化结果。
- 轨迹接口的实际路径为 `/base/sysutil/carTrackQueryByCarNo`（backend `HttpSysUtilApiService` 调用的路径）；
  设计文档中简写为 `/carTrackQueryByCarNo`，本次未新增根路径别名，避免与 backend 契约漂移。
- 仅当引擎已切换为 `es` 且运行期 ES 故障时：返回 `code=503`、`msg` 指明“模糊查询已禁用回退，请恢复 ES 或切回 legacy 引擎”。
- 默认 `legacy` 下由旧 GaussDB Mapper 提供服务，不会因 ES 未初始化而 503。
- 参数非法（模糊 1 字符、超 365 天、深页超窗）：返回 `code=400`。
- 未传时间范围时默认最近 7 天（设计 §4.3 强制时间范围），不再等价于旧实现的“全时间范围”。
- V3 新增接口统一前缀 `/api/v3/traffic` 与 `/api/v3/export`，不影响旧接口。

## 4. 验证与已知缺口

- 已执行：`mvn -DskipTests compile` 全量编译通过；`mvn -DskipTests package` 打包通过
  （产物 `pro-business-api/target/pro-business-api-1.0.jar`）。
- 配置绑定自检：用临时 harness 加载 `application.yml` 并绑定 `TrafficV3Properties`，通过；
  期间发现 YAML 中文 Map key 无法被 Spring Boot 绑定，已改为 `"颜色词=码值"` 列表并在启动时解析。
- 引擎安全默认：`traffic.query.engine` 默认为 `legacy`；`TrafficQueryEngineService` 在应用就绪后
  对显式 `es` 配置做就绪检测并自动回退；真实 ES 7.15.2 启动检测/HTTP E2E 已通过（§7）。
- 车牌解析：已用临时 harness 验证设计 §5.1.6 六类样例，结果与设计一致：
  - `赣B21E85_0` -> core=赣B21E85、color=0、status=ok；
  - `赣B21E85_1` -> ok；`赣B21E85` -> no_color/-1；
  - `赣B21E85_99` -> color_unparsed/-1；`赣B21E85蓝` -> ok/0；
  - `赣B21E85_0_extra` -> unparsed/-1；空值/null -> unparsed/-1；
  - 全角/空格/小写混写 `" 赣 b21e85 ＿0 "` -> 正确归一化为 `赣B21E85`。
- ES 模板：5 个 JSON 文件（三张月索引 + ILM + car-warning）已通过 `ConvertFrom-Json` 语法校验；
  字段与设计 §8.2/§5.4.4 对齐。
- 默认端口：`server.port=9902`，与 backend `vehicleMonitor.baseUrl` 默认值一致；
  `es-init.ps1` 默认 `ApiBaseUrl` 同步为 9902。
- backend 契约：已逐字段对照 `backend-java-V3` 的 `TrafficApiEndpoints` 与
  `CarStatisticsVO/CarAuditVO/incomeStatisticVO/TopTenVO/CarWarningInfo`，路径、字段名、错误语义记录在 §6。
- **真实联调已执行**（ES 7.15.2 + openGauss `192.168.56.10/RuoYi`）：见 §7 实际请求/耗时/命中数/失败点。
- 运行中的 9902 已是 V3 实例（最终 PID 50672，`-Xms512m -Xmx1g`，`TRAFFIC_QUERY_ENGINE=es`），
  当前 `activeEngine=es`、readiness 全 true；迁移演练与全部 HTTP E2E 均在该实例上完成。
- `car_warning_info` 位于 `carmonitdb` schema（1627 行），`jl_data01.car_warning_info` 不存在；
  `car-warning` 回灌已按 `carmonitdb` 优先、`jl_data01` 兜底处理。
- **未实现**（阶段一骨架范围外，已保留接口/字段）：对象存储上传与签名下载、审批流、多租户权限 scope 下推、GaussDB 精确短窗路由、小时级/周级对账抽样。
  `dws_*` DDL 与 MySQL→GaussDB 批量 ETL/回填已落地并实测；生产最终由 Flink 承担实时 ETL，本服务 ETL 作为初始化/补偿。

## 5. 上线/回滚操作顺序

### 5.1 数据库（测试 schema 或副本演练后再上生产）

```bash
# 0) 时间列 NULL 备份 + 显式排除（本次实测 36 行 snapshottime IS NULL）
psql "$PGURL" -f pro-business-api/src/main/resources/sql/v3/000_null_time_exclusion.sql

# 1) 建影子分区表（不碰在用表；预检会输出 NULL/已排除/未处理报告）
psql "$PGURL" -f pro-business-api/src/main/resources/sql/v3/001_shadow_schema.sql

# 2) 按月搬运（逐月执行，可中断续跑；月份范围按源表 min/max 决定）
psql "$PGURL" -v month=2025-11 -f .../002_copy_data.sql
psql "$PGURL" -v month=2025-12 -f .../002_copy_data.sql
# ...直到最近一个月

# 3) 同步基础表（Outbox/DLQ/对账/位点）
psql "$PGURL" -f .../004_sync_tables.sql

# 4. 数据搬完后统一建索引 + ANALYZE（openGauss 3.0：索引必须 LOCAL，见 D15）
psql "$PGURL" -f .../006_post_copy_indexes.sql

# 4.1) 大屏预聚合表（dws_*；非分区，见 D16；数据由 ETL 回填）
psql "$PGURL" -f .../007_dws_tables.sql

# 4.2) 分区维护函数（预建未来分区 / 归档历史分区；归档需 confirm=YES）
psql "$PGURL" -f .../005_partition_maintenance.sql
psql "$PGURL" -c "SELECT jl_data01.v3_create_future_partitions(3);"

# 5) 停写窗口内切换（源表 -> *_legacy_<ts>，影子表 -> 源表）
psql "$PGURL" -v confirm=YES -f .../003_cutover.sql
```

回滚：

```bash
psql "$PGURL" -v confirm=YES -f .../003_cutover_rollback.sql
```

### 5.2 Elasticsearch

```powershell
$env:ES_URL = "http://<es-host>:9200"
.\scripts\v3\es-init.ps1 -Months 13 -ForwardMonths 1
```

初始化后可触发回灌（API 异步任务）：

```bash
curl -X POST "http://<api-host>:9902/api/v3/sync/backfill?table=snapshot&startTime=2025-11-01%2000:00:00&endTime=2026-12-01%2000:00:00"
curl "http://<api-host>:9902/api/v3/sync/backfill/status/<taskId>"
```

> 注意：ILM 的 warm/cold 阶段通过 `allocate.require.data=warm|cold` 做节点分层。
> 若集群未给节点打 `data: warm` / `data: cold` 属性（单机测试环境常见），
> 需先移除对应 `allocate` 动作或补节点属性，否则索引到 40 天/365 天后会分配失败。
> 单机环境可把副本数改为 0，避免长期 yellow。

### 5.3 应用开关与灰度

1. 默认配置即为 `traffic.query.engine=legacy`，可直接启动、与旧实现行为一致；
2. 完成 `es-init.ps1` 建索引/别名与回灌，轮询回灌任务确认完成；
3. `GET /api/v3/es/readiness` 确认 `ready=true`（ES 可达、三表读别名、当月索引齐全）；
4. 临时切换 `POST /api/v3/es/activate?engine=es`，或持久化设置 `TRAFFIC_QUERY_ENGINE=es`
   （/`application.yml`）后重启；启动时会再次就绪检测，不通过自动回退 legacy 并 WARN；
5. 观察列表 P99、503 率、ES 拒绝率；
6. 开启 `traffic.sync.enabled=true`（Outbox relay + `search-sync` 消费）；
   `traffic.sync.car-warning-enabled=true`（MySQL `update_time` → outbox → Kafka → car-warning ES）；
7. 开启 `traffic.reconcile.enabled=true`（分钟桶对账 + 按桶回灌）；手动跑历史窗口：
   `POST /api/v3/sync/reconcile?startTime=...&endTime=...&bucketMinutes=1`；
8. 回滚：`POST /api/v3/es/activate?engine=legacy` 或配置改回 `legacy`；GaussDB SoR 不受影响。

### 5.4 验证命令（联调）

```bash
# V3 组合查询（浅分页）
curl -X POST http://<api-host>:9902/api/v3/traffic/list -H "Content-Type: application/json" \
  -d '{"table":"fee","startTime":"2026-01-01 00:00:00","endTime":"2026-01-31 23:59:59","plate":"赣B21E85","pageSize":20}'

# 展示字段导出
curl -X POST http://<api-host>:9902/api/v3/export/display -H "Content-Type: application/json" \
  -d '{"table":"snapshot","startTime":"2026-01-01 00:00:00","endTime":"2026-01-07 23:59:59"}'

# 全字段导出
curl -X POST http://<api-host>:9902/api/v3/export/full -H "Content-Type: application/json" \
  -d '{"table":"fee","startTime":"2026-01-01 00:00:00","endTime":"2026-01-07 23:59:59"}'

# backend 契约：导出提交（mode=display）
curl -X POST "http://<api-host>:9902/api/v1/large/export/submit?type=fee&startTime=2026-01-01%2000:00:00&endTime=2026-01-31%2023:59:59&mode=display" \
  -H "Content-Type: application/json" \
  -d '{"fuzzyFields.platenumber":"赣B21E85","fields":["bigId","transtime","vehicleplate","fee"],"purpose":"联调"}'

# backend 契约：状态与下载
curl "http://<api-host>:9902/api/v1/large/export/status/<taskId>"
curl -OJ "http://<api-host>:9902/api/v1/large/export/download/<taskId>"

# backend 契约：大屏预聚合（stats-enabled=true 且 dws_* 已回填后）
curl "http://<api-host>:9902/api/v1/bigscreen/stats/escape?startDate=2026-01-01&endDate=2026-01-31"
curl "http://<api-host>:9902/api/v1/bigscreen/stats/audit?startDate=2026-01-01&endDate=2026-01-31"
curl "http://<api-host>:9902/api/v1/bigscreen/stats/income?queryDateType=suo&startDate=2026-01-01"
curl "http://<api-host>:9902/api/v1/bigscreen/stats/warning-top?startTime=2026-01-01&endTime=2026-01-31&topN=10"

# 实时预警列表 + car-warning 索引创建/回灌
curl "http://<api-host>:9902/api/v1/bigscreen/warning/list?limit=100"
curl -X POST "http://<api-host>:9902/api/v3/es/car-warning/bootstrap"
curl -X POST "http://<api-host>:9902/api/v3/sync/car-warning/backfill?startTime=2026-01-01%2000:00:00&endTime=2026-01-31%2023:59:59&limit=1000"
```

### 5.5 启动说明（安全默认与引擎切换）

- **默认安全**：`application.yml` 的 `traffic.query.engine` 为 `legacy`，服务可直接启动，
  默认端口 `9902`（与 backend `vehicleMonitor.baseUrl` 对齐），三个既有查询接口走旧 GaussDB Mapper，
  不依赖 ES 初始化。
- **显式启用 ES**：
  - 持久化：设置环境变量 `TRAFFIC_QUERY_ENGINE=es`，或修改 `application.yml` 后重启；
  - 启动检测：ES 可 ping + 三表 `*-read` 别名 + 三表当月索引全部存在才启用 `es`；
    任一缺失自动回退 `legacy`，启动日志输出 `[V3引擎] ... 已自动回退 legacy` 的 WARN。
- **运行期切换**：
  - `GET /api/v3/es/readiness`：查看 `configuredEngine/activeEngine/ready/readAliases/currentIndices`；
  - `POST /api/v3/es/activate?engine=es`：就绪则立即启用，否则保持 legacy 并返回 409；
  - `POST /api/v3/es/activate?engine=legacy`：立即降级。
  运行期切换不修改配置文件，重启后按配置重新检测。
- **es-init.ps1**：初始化索引/别名后可用 `-Activate` 调用 activate；脚本会先查询 readiness，
  并明确打印“持久化切换 / 临时切换 / 回滚”三种操作。回灌任务为异步，必须在回灌完成后再切换。
- **运行期 ES 故障**：不回退 GaussDB 全模糊，接口返回 503；运维应恢复 ES 或立即 activate legacy。

### 5.6 生产配置项清单与启动/回滚手册

**配置项（环境变量优先，密钥不落仓库）**

| 配置 | 默认 | 生产建议 |
|---|---|---|
| `server.port` | `9902` | 与 backend `vehicleMonitor.baseUrl` 一致 |
| `TRAFFIC_QUERY_ENGINE` | `legacy`（yml） | `es`；启动就绪检测失败自动回退 legacy |
| `TRAFFIC_BIGSCREEN_STATS_ENABLED` | `false` | `true`（DWS 回填并核对后） |
| `TRAFFIC_BIGSCREEN_ETL_ENABLED` | `false` | `true`（MySQL→GaussDB DWS 补偿 ETL） |
| `TRAFFIC_SYNC_ENABLED` | `false` | `true`（Outbox relay + `search-sync` 消费） |
| `TRAFFIC_SYNC_CAR_WARNING_ENABLED` | `false` | `true`（car-warning CDC → outbox → Kafka → ES） |
| `TRAFFIC_RECONCILE_ENABLED` | `false` | `true`；`bucket-minutes=1`、`lookback-minutes=60`、`max-repair-buckets` 按容量调整 |
| `CARMONIT_MYSQL_USERNAME/PASSWORD` | 空（无默认口令） | `carmonit_ro` + 只读口令；由部署环境注入 |
| `SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD` | 空 | GaussDB 口令；写入 `api-local.properties` 或密钥管理系统 |
| `ELASTICSEARCH_USERNAME/PASSWORD` | 空 | 按 ES 安全配置注入 |
| `spring.redis.password` / `RABBITMQ_*` | 空 | 按实际中间件注入 |
| `traffic.export.dir` | 系统临时目录 | 独立数据盘目录，限制权限并配置清理 |
| Kafka `spring.kafka.bootstrap-servers` / topic | `localhost:9092` / `search-sync` | 生产 broker 列表；消费组 `search-sync-api` |

**启动（本机联调已验证的脱离终端方式）**

```powershell
# 1) 只允许单实例：先确认 9902 无监听、无 pro-business-api java 进程
Get-NetTCPConnection -LocalPort 9902 -State Listen -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
  Where-Object { $_.CommandLine -like '*pro-business-api*' }

# 2) 通过仓库外 launcher 注入环境变量后启动（WMI 创建，脱离当前终端作业）
$cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\work\runtime-logs\start-api-v3.ps1"'
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd}

# 3) 校验：PID 唯一、readiness、三查询、warning、导出
Invoke-RestMethod http://localhost:9902/api/v3/es/readiness
```

launcher 关键参数：`java -Xms512m -Xmx1g -Dserver.port=9902 -jar pro-business-api-1.0.jar
--spring.config.additional-location=file:D:/work/runtime-logs/api-local.properties`。

**回滚**

1. 查询层：`POST /api/v3/es/activate?engine=legacy` 立即切回旧 GaussDB Mapper（不重启）。
2. 应用：停止当前 V3 实例 → 用备份 jar（如 `D:\work\runtime-logs\api-backup-v3-dict.jar`）
   以同一 launcher/堆参数启动 → 确认 9902 唯一实例与三接口。
3. 数据库：仅当已执行 cutover 且需要回退时，停写窗口内执行
   `psql "$PGURL" -v confirm=YES -f 003_cutover_rollback.sql`；影子表保留为 `*_v3_rollback_<ts>`。
4. ES：V3 索引/别名保留不影响 legacy；如需彻底回退，只需把查询引擎切 legacy；
   回灌/对账/CDC 开关全部置 false 后重启。

## 6. backend 契约对接（2026-11-08 新增）

### 6.1 大屏预聚合查询

| 端点 | 返回 | 数据来源 | 状态 |
|---|---|---|---|
| `GET /api/v1/bigscreen/stats/escape` | `List<CarStatisticsVO>` 裸 JSON | `jl_data01.dws_escape_daily` | 已实现；stats-enabled=true 实测通过 |
| `GET /api/v1/bigscreen/stats/audit` | `CarAuditVO` 裸 JSON | `dws_escape_daily`（应追缴）+ `dws_income_daily`（已完成） | 已实现；实测金额与 legacy 一致 |
| `GET /api/v1/bigscreen/stats/income` | `List<incomeStatisticVO>` 裸 JSON | `dws_income_daily`（`org_name` 来自 DWS，不 join GaussDB `sys_dept`） | 已实现；实测总额一致 |
| `GET /api/v1/bigscreen/stats/warning-top` | `List<TopTenVO>` 裸 JSON | `dws_warning_section_daily` + `ods_szdn_section` | 已实现；实测计数与 MySQL 一致 |
| `GET /api/v1/bigscreen/warning/list` | `List<CarWarningInfo>` | `car-warning` ES 索引 | 已实现（索引缺失返回空；capture_type 已补齐） |

决策：

- 预聚合表 DDL 见 `sql/v3/007_dws_tables.sql`；数据由 Flink/ETL 回填，API 只读，不直连 backend 业务表。
- 开关 `traffic.bigscreen.stats-enabled` 默认 **false**；DWS 回填后已置 **true** 实测，
  金额与 MySQL 一致、`car_cnt` 为按日去重求和（跨日偏大），详见 §7.14。
- `audit` 口径假设：`totalAmount/totalCount` 取 `dws_escape_daily`，
  `finishedAmount/finishedCount` 取 `dws_income_daily`；`car_cnt` 为按日近似去重，
  跨日求和不是精确 distinct（设计允许 HLL 近似，误差 1–2%）。
- `escapedTypeName` 使用实际逃费类型编码 `10/20/30/40/50/60` 的静态映射
  （入口少轴/屏蔽通行介质/货车客标/有入无出/大车小标/假冒其他优免车）；
  若 `sys_dict_data` 文案不同，以字典为准并在 API 配置侧替换，返回字段名不变。
- `warning-top` 与 legacy 展示对齐：`sectionName` 前缀 `roadCode + 空格`，`rate` 为相对 Top1 的整数百分比。
- 错误语义：未启用/表缺失 → HTTP 503；参数非法 → HTTP 400。后端只看 HTTP 状态，不依赖包装结构。
- `warning/list` 已实现，详见 §6.3；索引缺失时返回空列表，ES 不可达时 503 让 backend 回退 Redis。

### 6.2 导出提交/状态/下载

| 端点 | 行为 |
|---|---|
| `GET /api/v3/export/capabilities` | 返回模式/表/维度过滤字段/展示字段白名单/别名/多值能力；backend 据此放开过滤，不再硬编码 |
| `POST /api/v1/large/export/submit?type&startTime&endTime&mode` | `mode=display` → ES PIT；`mode=full` → GaussDB 游标；**不带 mode** → 旧 `LargeScaleQueryService`，保持向后兼容 |
| `GET /api/v1/large/export/status/{taskId}` | 优先 V3 任务；未命中回落 legacy；返回 `code/status/totalExported/filePartCount/submitTime/endTime/mode/type` |
| `GET /api/v1/large/export/download/{taskId}` | 200 + `application/gzip` + `Content-Disposition`；任务不存在 404；未完成 409 |

决策：

- 响应保持 backend 已编码契约：提交返回 `code=200`、`taskId`；状态返回 `code=200`；不改字段名。
- backend 的下载令牌/HMAC/归属校验仍在 backend 侧完成；api 下载端点不重复鉴权，仅内网可达。
- `fields`（display）支持：backend camelCase 逻辑字段映射到 ES 文档字段（如 `bigId→big_id`、
  `plateColor→plate_color_raw`、`plateColorName→plate_color_name`、`enterTime→entime`）；未知字段输出空列，不报错。
  **fee 表 display 固定补齐 `plate_color_name`**（即使 `fields` 未包含）。
  `full` 路径忽略 `fields`，按 GaussDB `SELECT *` 全字段输出，并在 fee 末尾追加 `plate_color_name`。
- `fuzzyFields.*`：车牌类透传；编码类直接作为过滤（多值逗号拆分为 `IN`）；名称类先经码表解析为编码，
  解析不到直接返回业务码 400，避免“名称被忽略导致导出全量”。
- 全字段维度过滤：`snapshot` 直连 `orgcode/sectioncode/roadcode/tollcode/gantrycode`；
  `fee` 经 `LEFT JOIN ods_szdn_gantry` 使用 `org_code/section_code/road_code/toll_code`，`gantryid` 直连；
  `trail` 无维度列，能力元数据返回空数组。多值统一 `IN (?,...)`。
- 实测（§7.15）：fee 两个 section 多值 full 导出 253 行（=ES 聚合 139+114）；
  snapshot 两个 org 多值 full 导出 383 行（=ES 聚合 251+132）；display 强制补齐列验证通过。
- 对象存储/签名 URL/审批流未接入；当前文件落在 `traffic.export.dir`（默认系统临时目录），
  backend 下载代理可直接拉取。生产接对象存储时只需替换 `ExportTaskService` 的落盘/上传实现。

### 6.3 实时预警列表 `car-warning` 索引

**端点**：`GET /api/v1/bigscreen/warning/list`

| 参数 | 过滤字段 | 说明 |
|---|---|---|
| `roadCode` | `road_code` terms | 支持逗号多值 |
| `sectionCode` | `section_code` terms | 支持逗号多值；`all` 取消过滤 |
| `tollCode` | `toll_code` terms | 支持逗号多值；`StationCapture` 按 capture_type 处理 |
| `gantryCode` | `gantry_code`/`gantry_station_id` terms（任一命中） | 支持逗号多值；`GantryCapture` 按 capture_type 处理 |
| `fwqbm` | `fwqbm` terms | 支持逗号多值；`ServiceAreaCapture` 按 capture_type 处理 |
| `escapedType` | `escaped_type` terms | 支持逗号多值 |
| `captureType` | `capture_type` terms | `StationCapture/GantryCapture/ServiceAreaCapture`，支持逗号多值 |
| `carNo` | 完整车牌 `car_no` term；片段 `car_no.ngram` match_phrase | 支持逗号多值，任一命中；至少 2 字符 |
| `limit` | — | 默认/上限 100 |

- 返回裸 JSON 数组，字段名与 backend `CarWarningInfo` 一致（snake_case → camelCase，日期格式化
  `yyyy-MM-dd HH:mm:ss`）。
- **行为约定**：
  - 索引存在但无数据 → 200 + 空数组；
  - 索引缺失（尚未 `bootstrap`/回灌）→ 200 + 空数组，并 WARN；
  - ES 不可达/查询异常 → 503，backend 回退 Redis 快照（仅故障降级，不再因 captureType/多值而兜底）。
- capture_type 派生规则见 D18；旧位置哨兵会自动提取，不参与真实编码过滤。
- 该端点不依赖 `traffic.query.engine`，始终优先 ES。

**索引/模板**：
- 固定单索引 `car-warning`（不按月），模板
  [car_warning_template.json](file:///d:/work/IdeaProjects/car-monit-api-java-V3/pro-business-api/src/main/resources/es/v3/car_warning_template.json)；
- 1 主分片、1 副本、refresh 5s、`best_compression`、`dynamic:strict`；
- **不挂 ILM**：单索引持续写入，挂 hot/warm 策略会在 40 天后被转 warm/只读；
- `car_no` keyword + `.ngram`（2–3）；`_source.excludes: ["track_josn"]`（列表不返回大字段）；
- `capture_type` keyword（由 track_names/维度列派生，D18）；
- 维度编码 keyword，名称字段 `index:false` 仅展示；日期字段 `date`。

**索引创建**：
- `POST /api/v3/es/bootstrap` 一并创建模板 + `car-warning` 索引；
- 单独创建：`POST /api/v3/es/car-warning/bootstrap`；
- `scripts/v3/es-init.ps1` 会写入 `car-warning-template` 并创建 `car-warning`。

**写入方案（优先级）**：
1. **生产/NOW**：CDC/Outbox 捕获 `car_warning_info` 变更 → Kafka `search-sync`
   → 消费者 `_bulk` 写入 `car-warning`，`_id = id` 幂等；删除 tombstone 按 `_id` 删除。
   本阶段已实现：`CarWarningChangeProducer`（MySQL `update_time` 水位 → GaussDB outbox）
   + `CarWarningIndexWriter`（Kafka `search-sync` 消费 → ES），删除/恢复已实测。
2. **阶段一运维回灌**：`POST /api/v3/sync/car-warning/backfill?startTime&endTime&limit`
   从 `car_warning_info`（可选 join `car_info` 取 `escaped_type/escaped_amount/plate_color`）
   批量写入；用于初始化/对账修复。
3. **不采用**：API 业务代码双写 ES；在线查询直接 `LIKE car_warning_info`。

## 7. 真实联调记录（2026-11-08）

环境：ES 7.15.2 `http://localhost:9200`（单节点 512m，yellow 可接受）；openGauss `192.168.56.10:5432/RuoYi`，
schema `jl_data01`（三张核心表）+ `carmonitdb`（`car_warning_info` 1627 行、`car_info` 248 行）。

### 7.1 ES 初始化

- `scripts/v3/es-init.ps1 -Months 13 -ForwardMonths 1` 成功：
  - ILM `traffic_hot_warm_cold`、4 个索引模板（三表 + car-warning）；
  - 14 个月索引/表 + 读写别名，`car-warning` 固定索引；
  - 联调期间把所有测试索引副本数临时设为 0；本次创建的测试索引均为 green，
    集群仍 yellow 仅因旧的 `snapshot_flow`/`fee_records`/`trail_fitting` 3 个副本未分配（未触碰旧索引）。
- 脚本修复：PowerShell 5 需 UTF-8 BOM；PUT body 需显式 UTF-8 字节，否则 `§`/中文导致 ES 400。

### 7.2 回灌与计数

| 表 | DB 行数 | 回灌行数 | ES `_count` | 差异 | 备注 |
|---|---:|---:|---:|---:|---|
| 抓拍 | 936（非空时间 900） | 900 | 900 | 0（按非空时间） | 36 行 `snapshottime IS NULL` 已备份并显式排除（见 §7.10） |
| 收费 | 1016 | 1016 | 1016 | 0 | 耗时约 5.0s |
| 轨迹 | 682 | 682 | 682 | 0 | 耗时约 2.5s |
| car-warning | 1627 | 1627 | 1627 | 0 | 来源 `carmonitdb.car_warning_info + car_info` |

### 7.3 readiness / activate

- `configured=es, active=es`；readiness 全部 `true`：
  `readAliases={snapshot=true, fee=true, trail=true}`、`currentIndices={snapshot=true, fee=true, trail=true}`。
- `activate(es)=success`、`activate(legacy)=success`、再次 `activate(es)=success`。

### 7.4 三表查询（时间范围 + 维度 + 车牌模糊）

| 场景 | 命中 | 耗时 | 结果 |
|---|---:|---:|---|
| 抓拍 维度 section + 车牌片段 `6P069` | 1 | 49ms | `big_id=154288684` |
| 抓拍 完整车牌 `赣H6P069` | 1 | 6ms | term 命中 |
| 收费 维度 section + 完整车牌 `赣BGE801` | 1 | 5ms | `big_id=1029053238`（section 由 gantry join 回填） |
| 收费 车牌片段 `GE801`（直接 ES 验证） | 1 | — | `match_phrase` 生效 |
| 轨迹 完整车牌 `赣AN7012` | 2 | 6ms | `envehicleid` term 命中 |
| 不存在车牌 `赣A00000` | 0 | — | 空结果正常 |

### 7.5 深分页

- `pageNum=101,pageSize=100`：被拒绝 `code=400`，提示使用 search_after。
- PIT + `search_after`：第 1 页 100 行、第 2 页 100 行，重复 0，`hasMore=true`，PIT 正常关闭。

### 7.6 warning/list

- 无过滤：`rows=100`，36ms；
- Controller 方法：HTTP 语义 `200`，`rows=100`；
- `carNo=赣DH2468`：18 行；字段与 backend `CarWarningInfo` 对齐，日期为 `yyyy-MM-dd HH:mm:ss`。
- `carNo` 片段 `H2468`（直接 ES 验证）：18 行，`car_no.ngram` 生效。

### 7.7 导出 submit/status/download

| 路径 | 任务 | 耗时 | 结果 |
|---|---|---:|---|
| display（抓拍） | `f97b107c...` | 503ms | 900 行，CSV.GZ 12,924B |
| 状态 | — | — | `code=200,status=done,totalExported=900,filePartCount=1` |
| 下载 | — | — | `200 application/gzip`，12,924B，gzip magic 正确 |
| full（收费） | `46d2333f...` | 502ms | 1016 行，CSV.GZ 228,761B，状态 `done` |

### 7.8 失败点与修复

| 问题 | 影响 | 处理 |
|---|---|---|
| `.ngram` 设 `index_options: docs` | `match_phrase` 报 `indexed without position data`，模糊车牌不可用 | 模板改为默认 positions，重建索引后复测通过 |
| 收费表无 `sectioncode` 列 | 收费维度过滤无数据 | 回灌/按主键回查 SQL 增加 `LEFT JOIN ods_szdn_gantry` 回填 `sectioncode` |
| `es-init.ps1` 中文/`§` 编码 | ES 400 `Invalid UTF-8 start byte 0xa7` | 脚本加 UTF-8 BOM + 显式 UTF-8 body |
| 抓拍 36 行 `snapshottime NULL` | 无法进入时间索引；迁移脚本预检会中止 | 已备份到 `ods_rt_szdn_snapshot_flow_addcode_null_time_backup`，并写入 `v3_migration_excluded_rows` 显式排除（36/36，未处理 0）；业务复核见 §7.10 |
| `jl_data01.dict_plate_color` 不存在 | 颜色码表无来源 | 已改为 MySQL `carmonitdb.sys_dict_type/sys_dict_data` 单一事实源（D7），不再使用 GaussDB 码表或代码兜底 |
| ES 对 text 字段 `doc_values:false` 警告 | 无功能影响 | 模板已移除该无效参数 |

### 7.9 仍需处理

1. 36 行抓拍 `snapshottime IS NULL` 已备份 + 显式排除，**未删除源数据**；需业务复核后决定清洗/补时间/永久排除（见 §7.10）。
2. 真实 HTTP E2E 已完成（V3 实例替换后验证）；生产替换仍需按灰度窗口执行。
3. `car-warning` CDC/Outbox 消费者已补齐（§6.3 方案 1），更新/删除/恢复已实测。
4. MySQL 字典已切换只读账号 `carmonit_ro`，口令由仓库外 launcher 注入（D19/§7.16）。

### 7.10 snapshottime NULL 处置记录

- 备份表：`jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup`，36 行，原样全列。
- 排除表：`jl_data01.v3_migration_excluded_rows`，36 行，
  reason=`snapshottime IS NULL; backed up ...; requires business review`。
- 预检报告：NULL 总数 36、已备份并显式排除 36、未处理 0；`001` 会继续建影子表，
  `002` 搬运时按排除表过滤，不会静默丢弃。
- **未修改源表**；业务确认后可选择：补时间回填、清洗删除或维持永久排除。

### 7.11 HTTP E2E 与受控服务替换（2026-11-08）

**替换记录**
- 旧实例：PID 2656，`D:\work\IdeaProjects\car-monit-api\pro-business-api\target\pro-business-api-1.0.jar`，
  `--spring.config.additional-location=file:D:/work/runtime-logs/api-local.properties`，`-Xms512m -Xmx1g`。
- 新实例：PID 39948，V3 jar，同堆参数与同配置文件；通过 WMI 脱离终端作业启动，
  启动期间 9902 始终只有一个 Java 实例。
- 备份：旧 jar 原位保留；替换前 V3 jar 备份在 `D:\work\runtime-logs\api-backup-v3-predict.jar`。
- 最终保留 **V3 实例**：全部 HTTP E2E 通过、字典加载正常、readiness/activate 正常；
  未回滚。`SnapshotFlowSyncService.fullSync` 的 `Integer cannot be cast to String` 已修复
  （Redis 历史水位为 Integer，改为 `String.valueOf` 兼容；增量时间兼容 Date/Number/String）。
- 后续因发布新能力/对账修复又做过两次受控替换；当前最终实例见 §7.16。

**HTTP 实测（服务 9902，V3 jar）**

| 请求 | 耗时 | 结果 |
|---|---:|---|
| `GET /api/v3/es/readiness`（legacy） | 108ms | ready=true，et aliases true |
| `POST /api/v3/es/activate?engine=es` | 49ms | active=es |
| 抓拍 section + 车牌片段 `6P069` | 1107ms（首次冷 PIT）/ 后续 28ms | total=1 |
| 抓拍完整车牌 `赣H6P069` | 28ms | total=1 |
| 收费 section + `赣BGE801` + `plateColor=蓝色` | 58ms | total=1，字典颜色过滤生效 |
| 轨迹 `赣AN7012` | 342ms | total=2 |
| 空车牌 `赣A00000` | — | total=0，rows=0 |
| 旧接口深页 `pageNum=101` | — | `code=400`，提示 search_after |
| V3 searchAfter 第 1/2 页 | 146ms / 87ms | 各 100 行，重复 0，hasMore=true |
| `GET /api/v1/bigscreen/warning/list?limit=100` | 56ms | 100 行 |
| warning `carNo=赣DH2468` | 18ms | 18 行 |
| display export 提交/状态/下载 | 12ms / 514ms / 18ms | 900 行，12,924B，gzip 正确 |
| full export（收费）提交/状态/下载 | 7ms / 513ms / 14ms | 1016 行，229,692B，`plate_color_name` 列存在且含“蓝色” |
| fee display export（`fields=[vehicleplate,plateColor,plateColorName]`） | 6ms / 510ms / 8ms | 3,158B，表头 `vehicleplate,plateColor,plateColorName`，值含“黄色” |

**字典验证**
- 服务启动日志：`plate_color 字典已加载: entries=9, codeToName={0=蓝色,1=黄色,3=黑色,6=白色,5=绿色,7=临时,93=黄绿双拼底黑字,4=渐变绿底黑字,9=其他}`。
- 收费 ES 文档重新回灌 1016 行后，`plate_color_code` 聚合为 `0/1/4/7/-1`，不再出现旧兜底的 `2/8`，
  证明新解析器已按 MySQL 字典生效；`-1` 为未知/无颜色/畸形，按设计保留。
- 解析样例：`_0`→蓝色、`_1`→黄色、`_6`→白色、`_4`→渐变绿底黑字、`_93`→黄绿双拼底黑字、
  `_99`→未知(99)、`蓝色`→0、`渐变绿`→4。

**空值处置**
- 36 行 `snapshottime IS NULL` 已备份到
  `jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup`，并写入
  `jl_data01.v3_migration_excluded_rows`（36/36，未处理 0）；源表未修改。
- `000_null_time_exclusion.sql` 可重复执行；`001` 预检输出“NULL 总数/已排除/未处理”，
  `002` 搬运按排除表过滤，不会静默丢弃。

### 7.12 分区迁移完整演练（openGauss 3.0，2026-11-09）

环境：`192.168.56.10:5432/RuoYi`，schema `jl_data01`；源表快照 936（含 36 NULL 时间）/收费 1016/轨迹 682。

| 步骤 | 首次耗时 | 幂等重跑 | 结果/校验 |
|---|---:|---:|---|
| 000 空值备份+排除 | 41ms | 18-28ms | NULL 36、备份 36、排除 36、未处理 0 |
| 001 影子分区表 | **1592ms** | 47-81ms | 分区数 snapshot 18 / fee 27 / trail 17；影子行数 0 |
| 002 按月搬运（12 个月） | 247ms | 45-78ms | snapshot 900、fee 1016、trail 682；单月 3-41ms |
| 006 分区索引 + ANALYZE | 684ms | 177ms | 8 个 LOCAL 索引：time/plate ×3 + snapshot org + fee gantry |
| 003 cutover | 18ms | — | 源表重命名为 `*_legacy_<ts>`、影子表接管；行数 900/1016/682 |
| 003 rollback | 10ms | — | 源表恢复（936/1016/682，含 36 NULL 行）；分区表保留为 `*_v3_rollback_<ts>` |
| 004 同步基础表 | 38ms | — | Outbox/DLQ/对账/位点及索引 |
| 007 DWS 表 | 31ms | — | 3 张非分区 DWS 表 + 3 个索引 |

- 演练后状态：三张源表为普通表（业务未受影响）；回滚产生的
  `*_v3_rollback_20261109_003355` 已重命名回 `*_v3`，影子表保持 18/27/17 个分区，
  可直接用于下一次切换演练或正式 cutover。
- `005_partition_maintenance.sql` 已成功创建函数；`v3_create_future_partitions(3)` 幂等跳过已有分区；
  归档分支未对测试数据执行破坏性演练（会 DROP 分区，需业务确认）。
- 演练期间 9902 服务保持单实例；cutover/rollback 仅秒级重命名，V3 查询链路（ES）不受影响。

### 7.13 分钟桶对账与补偿演练

- 初始对账（2025-10-01 08:00~09:00，bucket=1）：180 桶，0 漂移。
- 人为删除 ES 文档 `326306944`（08:02 桶）后再对账：
  `totalBuckets=180, driftBuckets=1, repairBuckets=1`；该桶 Gauss=1 / ES=0。
- 回灌任务自动执行后：文档 `_id=326306944` 恢复，该小时 ES 计数 11；
  再次对账 180 桶全部 OK、`driftBuckets=0, repairBuckets=0`。
- `search_sync_reconcile` 表落库验证：snapshot-flow 1 DRIFT + 59 OK，fee-records 60 OK，trail-fitting 60 OK；
  修复后再次对账全部 OK。
- 修复点见 D11（`ON CONFLICT`、补偿顺序、历史区间参数）。

### 7.14 DWS 四统计端点与 legacy 对比

DWS 回填（只读账号）：`escapeRows=82, incomeRows=76, warningRows=63, costMs=357`；
DWS 覆盖：escape 2025-07-04~2026-02-05、income 2025-10-22~2026-02-03、warning 2025-10-01~2026-02-04。

| 端点 | V3/DWS 结果 | MySQL legacy | 结论 |
|---|---|---|---|
| `stats/escape` | 6 类型金额 17294.28/84882.23/3420.88/1704.33/906.36/7508.67，number 合计 126 | 金额逐类型完全一致；`COUNT(DISTINCT car_no)` 合计 73 | **金额一致**；count 因按日去重求和偏大 |
| `stats/audit` | totalAmount=115716.75、finishedAmount=22388.32；count 126/92 | 同金额 115716.75/22388.32；distinct 73/37 | **金额一致**；count 为近似口径 |
| `stats/income` | 10 个 orgName 行，金额合计 22388.32 | 按 org_id 22 行，金额合计 22388.32 | **总额一致**；DWS 按 `org_name` 聚合，未知名称合并、行数更少 |
| `stats/warning-top` | 总数 1627；Top1 G1517=727、G6011=180、S47=162、G76=105、G35=68 | 按 section 计数 727/180/105/90+72/68 | **计数一致**；Top 展示按“路线+路段名称”合并，符合 legacy 展示口径 |

- 已知近似：`car_cnt/finishedCount` 为“按日去重后跨日求和”，不是跨日精确 distinct；
  本次样本 escape 126 vs 73、audit finished 92 vs 37，偏差来源于多日重复车牌。
  生产若需精确值，应由 Flink/HLL 或查询层做跨日去重；当前保留近似并在响应/文档标注。
- `stats-enabled=true` 已真实开启并验证，不再走 503。

### 7.15 导出能力与 warning 多值/captureType 实测

- `GET /api/v3/export/capabilities` 返回：`modes=[display,full]`、`tables=[snapshot,fee,trail]`、
  `fullDimensionFilters=true`、`multiValueDimensionFilters=true`、`plateColorName=true`、
  `plateColorNameField=plate_color_name`、`dimensionFilters`、`displayFields`、`displayAliases`。
- display（fee）仅请求 `fields=[vehicleplate,transtime]`：CSV 表头变为
  `vehicleplate,transtime,plate_color_name`，1016 行，强制补齐列生效。
- full（fee）`dimensionCodes.sectioncode=[200R500450649000,200R515170829000]`：导出 253 行
  （= ES 聚合 139+114），`status=done`，无 SQL 错误。
- full（snapshot）`dimensionCodes.orgcode=[030000011,030000006]`：导出 383 行（= ES 聚合 251+132）。
- warning/list：
  - `captureType=ServiceAreaCapture` → 25 行（索引中该类型共 25）；
  - `tollCode=StationCapture`（位置哨兵）→ 100 行（上限）；
  - `captureType=StationCapture,GantryCapture` → 100 行（多值）；
  - `sectionCode=200R515170829000,200R560110793001` → 100 行（多值 terms）。
- `capture_type` 回灌后聚合：StationCapture 1200、GantryCapture 402、ServiceAreaCapture 25（合计 1627）。

### 7.16 MySQL 只读账号与最终服务状态

- 账号 `carmonit_ro`：仅 `SELECT` 7 张表（`sys_dict_type/sys_dict_data/car_warning_info/car_info/
  car_except_record/car_confim_free/car_aduit_free`）；验证 `sys_user` 被拒绝（`SELECT command denied`）。
- 只读账号下验证：字典加载 9 条、DWS ETL 82/76/63（357ms）、car-warning CDC
  `fetched=1/outboxInserted=1/watermark saved`（水位更新已改为 `UPDATE+INSERT`）。
- 最终服务：PID **50672**，`9902` 唯一 Java 实例，命令
  `java -Xms512m -Xmx1g -Dserver.port=9902 -jar pro-business-api-1.0.jar
   --spring.config.additional-location=file:D:/work/runtime-logs/api-local.properties`；
  `readiness ready=true, activeEngine=es`；snapshot total=1、fee total=1、trail total=2、warning 行数正常。
- launcher 环境：`TRAFFIC_QUERY_ENGINE=es`、`TRAFFIC_BIGSCREEN_STATS_ENABLED=true`、
  `TRAFFIC_BIGSCREEN_ETL_ENABLED=true`、`TRAFFIC_SYNC_ENABLED=true`、
  `TRAFFIC_SYNC_CAR_WARNING_ENABLED=true`、`TRAFFIC_RECONCILE_ENABLED=true`、
  `CARMONIT_MYSQL_USERNAME=carmonit_ro`（口令在仓库外 launcher，不提交）。
- 服务曾被外部停止十几分钟；本次按同一 launcher/WMI 方式恢复并完成上述能力发布。

