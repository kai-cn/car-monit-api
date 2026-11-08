# car-monit-api-rust 生产化修复记录

> 日期：2026-11-08
> 依据：`docs/RUST-REVIEW-20261107.md` §9 的 B1–B10 / S1–S9
> 约束：未提交 git、未改动 `../car-monit-api-cpp`、未修改历史文档结论
> 验证基线：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`（构建机需把 `C:\Program Files\CMake\bin` 加入 PATH，rdkafka 走 cmake-build）

---

## B 系列（上线前必做）

### B1 消费端默认关闭 + 幂等顺序修复

| 项 | 内容 |
|---|---|
| 改动文件 | `config/application.yaml`、`src/config.rs`、`src/services/consumer.rs` |
| 为什么 | Java 侧消费者源码全部被注释，Rust 默认开启会与其它消费端双写同一 topic；且原实现先写幂等键再处理，失败时不回删，重投会被误判为"已处理"而静默丢消息 |
| 怎么改 | ① `app.consumer-enabled` 默认改为 false（YAML 与 `AppConfig::default` 同步）；② 幂等键改为"成功保留、失败删除"：`SET NX` 抢占后执行 `process()`，Err 时 `DEL` 幂等键再向 mq 层返回 Err，使重投能真正重试；③ 抽出 `process()` 保持原有 INSERT/UPDATE/DELETE 语义 |
| 如何验证 | `cargo check --all-targets` 通过；代码路径审查（无 DB/Kafka 环境，未做真机重投） |
| 备注 | 缓存未配置时保持"跳过幂等判重"的原有降级行为 |

### B2 时间戳条件绑定修复

| 项 | 内容 |
|---|---|
| 改动文件 | `src/repo/mod.rs` |
| 为什么 | `cursor_query` / `count_between` / `list_big_ids_between` 把 `String` 直接绑定到 timestamp 列，GaussDB 会报类型错误；Java XML 用 `to_timestamp(#{x},'yyyy-mm-dd HH24:MI:SS')` |
| 怎么改 | 起止时间、游标时间、`BETWEEN` 两端统一改为 `to_timestamp($n, 'yyyy-mm-dd HH24:MI:SS')`；复合游标保持 `(time_col, id_col) > (to_timestamp(...), ?)` 的行比较语义 |
| 如何验证 | `cargo check --all-targets` 通过；需真实库回归 `/sync/full`、`/sync/incremental`、丢包检测（未执行） |
| 备注 | 时间入参格式仍要求 `yyyy-MM-dd HH:mm:ss`（与 Java 一致） |

### B3 fuzzyFields 白名单

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/query.rs` |
| 为什么 | DB 降级路径对未知 `fuzzyFields` key 直接当物理列名拼进 SQL，存在注入面 |
| 怎么改 | 只允许 `Meta.logical_to_physical` 白名单内的逻辑字段；未知字段返回 `bad_request`，不再进入 SQL 文本（ES 路径原本已拒绝） |
| 如何验证 | `cargo check --all-targets`；`query()` 对降级路径的 Err 仍按 Java 语义返回空列表（HTTP 200） |
| 备注 | 与 Java 行为有意不同（Java 同样可注入），属安全修复 |

### B4 SIGTERM 优雅停机

| 项 | 内容 |
|---|---|
| 改动文件 | `src/main.rs` |
| 为什么 | 原实现只监听 Ctrl+C，K8s 滚动发布发 SIGTERM 会直接被杀 |
| 怎么改 | 新增 `wait_for_shutdown_signal()`：Unix 同时监听 SIGTERM 与 SIGINT，非 Unix 回退 Ctrl+C；收到信号后停后台任务 → HTTP 排空（axum graceful shutdown）→ 5s 后台收敛窗口 → 导出/大查询 semaphore 收敛 → Redis ping → DB close |
| 如何验证 | `cargo check --all-targets`；Windows 下可用 Ctrl+C 验证日志顺序（Linux SIGTERM 需目标环境验证） |

### B5 探针语义

| 项 | 内容 |
|---|---|
| 改动文件 | `src/router.rs` |
| 为什么 | 原 `/readyz` 只把 DB/Redis ping 失败计为 DOWN；ES 故障不影响状态码，Redis 启动连接失败时（cache=None）静默显示 UP |
| 怎么改 | ES ping 失败 → 503；ES 客户端未初始化 → 503；Redis 未连接 → 503；`mqConsumer` 在 `consumer-enabled=false` 时显示 `DISABLED` 且不影响就绪 |
| 如何验证 | `cargo check --all-targets`；需真实环境停 ES/Redis 验证 503（未执行） |
| 备注 | `/healthz` 仍为纯存活探针，不依赖外部组件 |

### B6 密钥外置 + Redis 密码生效

| 项 | 内容 |
|---|---|
| 改动文件 | `config/application.yaml`、`src/cache.rs` |
| 为什么 | 仓库内 DB/ES 明文密码；`redis.password` 只声明未使用，有密码的 Redis 连不上 |
| 怎么改 | YAML 中 DB/ES 密码改为空串并注明环境变量名（`APP_..._MASTER_PASSWORD` / `APP_ELASTICSEARCH_PASSWORD`）；Redis 连接串改用 `url::Url` 构造，支持 `redis://:password@host:port/db` 并转义特殊字符 |
| 如何验证 | `cargo check --all-targets`；需有密码的 Redis 实例验证（未执行） |
| 备注 | 空密码仍兼容（不设置 password 段） |

### B7 请求体上限 / 全局限时 / 并发上限

| 项 | 内容 |
|---|---|
| 改动文件 | `Cargo.toml`、`src/router.rs` |
| 为什么 | 无 body 上限、无超时、无并发保护，公网可打爆大查询与内存 |
| 怎么改 | 路由层依次加入 `ConcurrencyLimitLayer(256)`、`TimeoutLayer(90s → 408)`、`RequestBodyLimitLayer(20MB → 413)`；`tower` 开启 `limit` feature，`tower-http` 开启 `limit`/`timeout` |
| 如何验证 | `cargo check --all-targets`；压测与超大 body 需真实环境验证（未执行） |
| 备注 | 90s 覆盖统计接口 ES timeout=60s；导出为后台任务不受 HTTP 超时影响 |

### B8 契约补齐

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/sysutil.rs`、`src/services/track_sync.rs`、`src/services/sync.rs`、`src/services/consumer.rs`、`src/services/trail.rs`、`src/handlers/base.rs`、`src/router.rs` |
| 为什么 | 5 处与 Java 契约不一致 |
| 怎么改 | ① `change_data` 结尾按 Java L746-753 清空 `firtStationCode/Name/Time`、`plateColor`、`carType`、`carVehicle`、`carNum`、`passType`；② `sync_history_track` 写入 `Vec<TrailInfo>`（tracks+trailList，过滤空 trailList、按 tracks.uuid 合并），不再写裸 `ZdataTrailTracks`；③ 快照表 ES `_id` 统一为 `datauuid`（`sync.rs` 与消费端 `save_to_es`），消费端 DELETE 先按 bigId 反查 datauuid 再删，兼容历史 bigId 文档；④ `/base/feerecords/{bigId}` 改为 Java 的 500（Mapper 缺 XML 语句）；⑤ 轨迹去重阈值改为毫秒比较 `> 4*60*1000` |
| 如何验证 | `cargo check --all-targets`、`cargo test`（20/20） |
| 风险 | ES `_id` 变更需重建/清理旧索引；`car_history_trail:*` 缓存形状变更需清缓存；`feerecords/{id}` 由 200 变 500 属有意的契约对齐 |

### B9 多副本约束

| 项 | 内容 |
|---|---|
| 改动文件 | `src/cache.rs`、`src/scheduler.rs`、`src/main.rs`、`src/services/export.rs`、`src/services/large.rs`、`tests/router_test.rs` |
| 为什么 | 定时任务在每个副本都跑；导出任务状态在进程内存，轮询可能打到另一副本 |
| 怎么改 | ① `Cache::acquire_lease`：`SET NX EX` 抢占 + GET 校验 owner 后 `EXPIRE` 续期；② 调度器每 10s 竞争 `car_monit:scheduler:leader`（TTL 30s），仅 leader 执行任务，Redis 缺失时退回单副本模式并告警；③ 导出任务状态写 Redis（`car_monit:export:task:{id}`，TTL 24h），提交/状态变更/进度都会镜像，`get_export_status` 本副本未命中时回落到 Redis |
| 如何验证 | `cargo check --all-targets`、`cargo test`（20/20）；两副本与 Leader 切换需真实 Redis/K8s 验证（未执行） |
| 未完成 | 导出文件共享存储仍依赖基础设施（NFS/对象存储）；导出目录未做保留期清理（见 S4 状态） |

### B10 CI 基线

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/gen_filters.py`、`src/repo/filters_gen.rs`（重新生成）、`src/repo/mod.rs`、`src/config.rs`、`src/db.rs`、`src/mq.rs`、`src/scheduler.rs`、`src/handlers/common.rs`、`src/handlers/query.rs`、`src/services/{query,large,delay_monitor,multisource,sysutil}.rs`、`tests/parity_test.rs` |
| 为什么 | 原 clippy 505 warning（466 条来自 `filters_gen.rs`），`-D warnings` 无法进 CI |
| 怎么改 | ① 生成器模板：`JString` 字段不再生成多余的 `.into()`，`JLong` 不再生成 `x as i64`（保留 `JInt` 的 i64 转换），`broken` 分支复用同一 `value_expr`；重新生成后 572 条条件不变；② 手写 `fee_records_filters`/`trail_fitting_filters`/`kafka_record_filters` 去掉无用 `.into()`；③ 机械 lint 直接修（`contains`、`is_multiple_of`、`if let`、`slice::from_ref`、冗余 `&`、测试代码）；④ 结构性 lint 加定点 `#[allow]` 并写明理由（`result_large_err`、`large_enum_variant`、4 处 `too_many_arguments`） |
| 如何验证 | `cargo check --all-targets` 通过；`cargo clippy --all-targets -- -D warnings` **exit 0、0 warning**；`cargo test` **20 passed / 0 failed** |
| 备注 | 未新增 CI 配置文件（仓库当前无 CI 目录），验收命令已可直接用于流水线 |

---

## S 系列（上线后短期，仅做不依赖真实环境且自洽的部分）

### S1 指标暴露（已实现，最小集）

| 项 | 内容 |
|---|---|
| 改动文件 | 新增 `src/metrics.rs`、`src/lib.rs`、`src/middleware.rs`、`src/router.rs` |
| 实现 | `GET /metrics` 输出 Prometheus text 格式：`http_requests_total{method,status}`、`http_request_duration_seconds_sum/count{method}`、`http_requests_in_flight`、`db_pool_connections{state=size|idle}`、`app_consumer_enabled` |
| 为什么不用 `metrics-exporter-prometheus` | 避免为一个端点引入整棵依赖树；原子计数足够覆盖当前最小面板 |
| 如何验证 | `cargo clippy -D warnings` 通过；`cargo test` 20/20；端点内容需启动进程后抓取验证（未执行，因无 DB/Redis 环境时进程会在连接 DB 阶段退出） |
| 未覆盖 | 延迟分位（需直方图桶）、Kafka lag（需 consumer group 查询）、导出队列深度（跨副本）、定时任务成功/耗时 |

### S2 日志/trace 规范化（部分实现）

| 项 | 内容 |
|---|---|
| 改动文件 | `src/middleware.rs` |
| 已做 | 用 `.instrument(span)` 替代 `span.enter()` 跨 await，修复异步任务切换线程时 request_id/path 错位；`/metrics` 采集也在此层完成 |
| 未做 | 解析/透传 `traceparent`、出站（ES/Kafka）注入 trace、采样率配置 —— 需要日志采集侧字段约定与采样策略决策 |
| 如何验证 | `cargo clippy -D warnings` 通过 |

### S4 导出目录治理（部分实现）

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/export.rs`、`src/services/large.rs`、`src/scheduler.rs`、`src/main.rs` |
| 已做 | ① 定时任务 `exportCleanup`（每天 03:45）清理 24h 前的完成/失败任务状态（内存），Redis 侧由 TTL 24h 自动过期；② `clean_expired_files` 按目录 mtime 清理超过 24h 的导出目录（运行中的目录会持续写文件，mtime 被刷新，避免误删在途任务） |
| 未做 | GB 水位告警 —— 需要告警通道与阈值决策 |
| 如何验证 | `cargo check --all-targets`、`cargo clippy -D warnings`、`cargo test` 20/20 |

### S6 调度治理（已实现）

| 项 | 内容 |
|---|---|
| 改动文件 | `src/scheduler.rs` |
| 实现 | 每个任务一个 `AtomicBool` 防重入（上一轮未结束则跳过并告警）；单任务 10 分钟超时（`tokio::time::timeout` 取消本轮并 error 日志）；panic 仍被 `catch_unwind` 捕获 |
| 风险 | 超时取消可能留下半成品，业务任务需可重入（已在代码注释标注） |
| 未做 | 失败告警外发（无告警通道）、执行记录持久化（需 DB 表设计） |
| 如何验证 | `cargo check --all-targets`、`cargo clippy -D warnings`、`cargo test` 20/20 |

### S3 / S5 / S7 / S8 / S9（跳过，附原因）

| ID | 跳过原因 |
|---|---|
| S3 按路由组限流 | B7 已提供全局并发上限（256，排队背压）。按路由组（大查询/导出/管理）限流需要容量测试数据与调用方 SLA 才能定阈值，且需引入 `governor` 等新依赖；阈值拍脑袋会误伤批量调用方，留待容量测试后做 |
| S5 ES 索引/ILM 启动初始化 | 需要真实 ES 集群验证 mapping 与别名/ILM 行为；索引创建涉及运维权限与既有索引归属，必须先与 ES 运维确认，不能在代码里单方面 auto-create |
| S7 时区统一 | 会改变缓存 key、接口展示值与存量数据对账口径，属产品/数据口径决策；需与数据侧确认 UTC/Asia-Shanghai 的最终约定后再动 |
| S8 DB 迁移管理 | `sqlx::migrate!` 需要基线 schema、DDL 权限与发布窗口，且生产为 GaussDB（与 PostgreSQL 语法存在差异）；须并入 DBA 变更流程，不能由应用启动自动执行 |
| S9 链路验证补全 | 依赖独立的 Kafka/ES/GaussDB 环境与数据隔离；本轮环境不具备，未执行任何真机用例 |

---

## 总体验证结果（2026-11-08）

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（exit 0，0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning；生成文件 `filters_gen.rs` 通过修生成器而非 allow 清零） |
| `cargo test` | **20 passed / 0 failed**（14 单元 + 6 集成） |
| 未验证项 | 所有需要真实 GaussDB/Redis/Kafka/ES 的行为（同步/消费/导出/探针/多副本租约），以及 Linux SIGTERM；已在各条目注明 |

## 给复审会话的提示

1. 重点复核语义：B2 的 SQL 文本、B8 的 `change_data` 清空字段与 `datauuid` 作为 ES `_id`、B9 的 leader 续期竞态（GET+EXPIRE 非原子）。
2. `tests/router_test.rs` 因 `ExportService::new` / `LargeScaleQueryService::new` 增加 `store` 参数而改动，其余测试未动。
3. 生成文件 `src/repo/filters_gen.rs` 必须通过 `python tools/gen_filters.py` 重新生成，不应手改。
4. 未提交 git；本次改动均在工作区。

---

# 第二轮：独立审查问题修复（2026-11-08）

> 依据：独立审查结论「2 阻断 / 2 高危 / 若干中危，本批不能上线」。
> 验证：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`（结果见本章末）。

## 阻断项

### 审查-1 ES bulk：`_id` 污染 `_source` + 未检查 items[].error

| 项 | 内容 |
|---|---|
| 改动文件 | `src/es.rs`、`src/services/sync.rs`、`src/services/consumer.rs` |
| 改动 | ① 新增 `BulkOutcome { ok, failed, first_error }`，`bulk_upsert` 返回该结构；② 发送前 clone 文档并移除 `_id`，避免 ES 以 `mapper_parsing_exception` 拒绝；③ 解析响应 `items[]`，逐条检查 `error` 字段计数，`errors=true` 但无明细时也给出错误摘要；④ 同步链路按 `ok/failed` 分别累加 `total_ok/total_err`；⑤ 消费端 `save_to_es` 在 `failed>0` 时返回 `Err`，由 mq 层重投 |
| 对应审查结论 | 阻断 1：同步/消费端静默全量失败 |
| 验证 | `cargo check`、`cargo clippy -D warnings`、`cargo test` 通过；真实 ES 写入未验证 |

### 审查-2 消费端 DELETE 反查 datauuid 必然为空

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/consumer.rs` |
| 改动 | DELETE 分支不再 `delete_by_id` 后 `get_by_id` 反查；直接使用消息里已解析的 `flow.datauuid`，并同时删除 `datauuid` 与消息 key（bigId）两个 `_id`，兼容历史文档 |
| 对应审查结论 | 阻断 2：`_id=datauuid` 的文档永远删不掉 |
| 验证 | `cargo check`、`cargo clippy -D warnings`、`cargo test` 通过；需真实 ES/Kafka 验证删除 |

## 高危项

### 审查-3 生成器时间等值条件仍绑字符串

| 项 | 内容 |
|---|---|
| 改动文件 | `src/repo/mod.rs`、`tools/gen_filters.py`、`src/repo/filters_gen.rs`（重新生成） |
| 改动 | ① `Cond` 新增 `EqTimestamp` / `EqDate`，`push_where` 分别渲染 `to_timestamp($n,'yyyy-mm-dd HH24:MI:SS')` 与 `to_timestamp($n,'yyyy-mm-dd')`；② 生成器对 `JDateTime`/`JIsoDateTime` 的 `=` 输出 `EqTimestamp`，对 `Day` 输出 `EqDate` |
| 验证 | 重新生成后仍为 **572 条条件**；`filters_gen.rs` 中已无对 time/date 列的 `Cond::Eq`（仅剩 4 处 `load_time`，其 Java 实体字段为 `String`，保持字符串绑定才是 1:1）；新增单测 `cond_time_equality_renders_to_timestamp` |
| 备注 | 审查提到的 44 处按"模型时间类型"统计；本次覆盖全部 `Day/JDateTime/JIsoDateTime` 等值条件（32 处 push），其余 `load_time` 属 String 字段，Java 同样绑字符串 |

### 审查-4 `get_history_trail` 的 `limit.max(1)`

| 项 | 内容 |
|---|---|
| 改动文件 | `src/repo/mod.rs` |
| 改动 | `limit>0` 优先；否则取 `vo.page_size`（端点已换算 offset+pageSize）；两者都无（TrackTask）时不加 LIMIT。`ORDER BY cid, extime` 始终保留 |
| 对应审查结论 | 高危 4：`limit<=0` 只取 1 行 |
| 验证 | `cargo check`、`cargo test`；需真实库验证分页 |

## 中危项

| 编号 | 改动文件 | 改动与对应关系 | 验证 |
|---|---|---|---|
| 审查-5 导出失败不持久化 | `src/services/export.rs`、`src/services/large.rs` | 失败分支改为先取快照再 `persist_task`，其它副本不再永久看到 RUNNING | `cargo test` 通过；真实 Redis 未验证 |
| 审查-6 去重索引错位 | `src/services/trail.rs` | `seen` 改为 `SeenPoint { index: Option<usize>, bo }`，严格复刻 Java `map.put(mapKey, trailBo)`；新增单测断言不会误改 S1 | 单测 `dedupe_points_merges_into_stored_point_not_last_output` 通过 |
| 审查-7 syncTrack 缺 trailUuid | `src/services/track_sync.rs` | `change_data` 后补 `info.trail_uuid = car_no`（对齐 Java L377） | 编译/测试通过 |
| 审查-8 关闭可能无限等待 | `src/main.rs`、`src/services/export.rs`、`src/services/large.rs` | 保存每次导出的 `JoinHandle`（提交时清理已完成项），`close(grace)` 用 `tokio::time::timeout + join_all`；main 里 30s 宽限并告警 | 编译通过；真实关闭演练未做 |
| 审查-9 leader 租约竞态 | `src/cache.rs`、`src/scheduler.rs` | `acquire_lease` 改为 Lua 原子脚本（持有者续期/空闲抢占/他人持有失败）；检查间隔 5s、TTL 20s；注释明确「至多额外执行一次」的 at-least-once 语义 | 编译通过；需多副本真机验证 |
| 审查-10 `/metrics` in-flight 泄漏 | `src/router.rs` | 调整 layer 顺序：request_id/metrics 放到最外层，TimeoutLayer 在内层生成 408 时外层 future 仍能完成计数 | 编译/测试通过 |
| 审查-11 消费端状态误报 | `src/mq.rs`、`src/services/consumer.rs`、`src/main.rs` | `consume` 增加 `on_started`，subscribe 成功后才置位；subscribe 失败每 5s 重试；消费循环异常退出后整体重连并复位标志；main 不再提前置位 | 编译通过；需真实 Kafka 验证 |
| 审查-12 ES red / Redis 重连 | `src/es.rs`、`src/cache.rs`、`src/main.rs` | ES `health` 解析 `status`，red 返回 Err；Cache 改为持有 client、按需惰性重连（3s 超时 + 3s 退避），启动失败不再永久降级；main 启动日志区分"已连接/待重连" | 编译通过；需真实 ES/Redis 验证 |
| 审查-13 示例配置 | `.env.example` | `APP_CONSUMER_ENABLED=false`；DB/ES 密码改为空值并注明由 Secret 注入；新增 `APP_ENABLE_SCHEDULER` | 人工核对 |
| 审查-14 存量 bigId 文档 | 新增 `tools/es-rebuild-snapshot-flow.sh` | 可执行的上线前置脚本：检查集群 → 记录文档数 → 删除快照索引 → 调用 `/api/v1/large/sync/full` → 轮询 count 并给出验收清单（抽查 `_id == datauuid`） | 脚本语法人工核对；需在预发执行 |

## 第二轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `cargo test` | **22 passed / 0 failed**（16 单元/一致性 + 6 集成，新增 2 条行为测试） |
| 未验证 | 所有依赖真实 GaussDB/Redis/Kafka/ES 的行为（bulk 写入与失败重投、DELETE、分页 LIMIT、租约切换、探针、关闭排空） |

## 第二轮复审建议关注

1. `sync_history_track` / `sync_track` 仍无 `StartPage` 语义：TrackTask 两条路径与 Java 一致（无 LIMIT），端点路径依赖 `vo.page_size`。
2. ES `_id` 切换的存量数据必须执行 `tools/es-rebuild-snapshot-flow.sh`，否则新旧文档并存。
3. `Cache` 重连是"每操作最多一次尝试 + 3s 退避"，高并发故障时会造成少量请求直接失败（预期降级行为）。

---

# 第三轮：定点复核问题修复（2026-11-08）

> 依据：第三轮复核「1 阻断 / 1 高危 / 3 中危 + 低危」。
> 验证：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`（见本章末）。

## 阻断项

### 审查3-1 ES 索引结构：删索引后先建 mapping 再回灌

| 项 | 内容 |
|---|---|
| 改动文件 | 新增 `resources/es/index/{snapshot_flow,fee_records,trail_fitting}.json`、`src/es.rs`、`src/main.rs`、`src/config.rs`、`config/application.yaml`、`tools/es-rebuild-snapshot-flow.sh` |
| 服务侧 | ① 内置 ES7 结构（去掉 Java 文件的 `_doc` 包装），运行期替换分片/副本占位符；② `EsClient::ensure_indices`：幂等创建 ILM 策略（hot/warm/cold/delete），`auto-create=true` 时对缺失索引 PUT 完整 settings+mappings（已存在则 HEAD 跳过，不改结构）；③ `get_mapping` 供自检/运维抽查；④ main 启动后台执行（15s 超时），失败只告警不影响启动；⑤ `auto-create` 默认改为 true |
| 脚本 | ① 索引名严格校验：`^[a-z0-9][a-z0-9._-]*$`，显式拒绝 `_all`、`*`、逗号、空格，并限定本脚本只处理 `snapshot_flow`；② 交互确认（`CONFIRM=yes` 可跳过）；③ 先 DELETE 再 PUT mapping（shards/replicas 可配，`ATTACH_ILM=true` 时注入 `index.lifecycle.name`），PUT 后校验 `_mapping` 存在 date 与 ngram；④ 时间窗参数化 `START_TIME`/`END_TIME`（默认最近 365 天），调用 `/api/v1/large/sync/repair` 而不是硬编码 12 个月的 `/sync/full`；⑤ 完成判定改为 `psql` 统计 DB 期望条数并与 ES `_count` 对数（≥99% 才结束，2h 超时失败） |
| 对应复核 | 阻断 1：动态映射导致 range/sort 400、模糊查询 0 命中 |
| 验证 | `cargo check`/`clippy -D warnings`/`test` 通过；脚本仅语法与逻辑核对，需在预发真实 ES 7.15 执行 |

### 审查3-2 轨迹分页 LIMIT 溢出

| 项 | 内容 |
|---|---|
| 改动文件 | `src/handlers/common.rs`、`src/handlers/sysutil.rs`、`src/repo/mod.rs` |
| 改动 | ① `page_params`：pageNum 超过 `i32::MAX` 视为非法回退 1（对齐 Java `Convert.toInt`），并钳到 `MAX_PAGE_NUM=10_000_000`；offset/offset_for 全部改 `saturating_mul`；② sysutil 新增 `track_window`：`offset+pageSize` 饱和相加后 `clamp(1, 5000)`，i32 转换不再可能为负；内存切片 offset 用 `usize::try_from` 且 `min(list.len())`；③ 仓储 `get_history_trail` 再加 `MAX_TRACK_LIMIT=5000` 兜底 |
| 对应复核 | 高危 2：大页码 i32 截断成负数 → 钳到 0 → 无 LIMIT 全表读 |
| 验证 | `cargo check`/`clippy`/`test` 通过；真实大页码请求未压测 |

## 中危项

| 编号 | 改动文件 | 改动与对应关系 | 验证 |
|---|---|---|---|
| 审查3-3 Redis 不可用导致调度全停 | `src/config.rs`、`config/application.yaml`、`.env.example`、`src/scheduler.rs` | 新增 `app.scheduler-lease-required`（默认 false，`APP_SCHEDULER_LEASE_REQUIRED`）：true=多副本严格模式，租约错误则暂停并告警；false=单副本降级继续执行并只告警一次。Redis 未配置（cache=None）仍按单副本运行 | 编译/测试通过；需多副本+Redis 故障演练 |
| 审查3-4 停机未覆盖调度任务/DB 关闭挂起 | `src/scheduler.rs`、`src/main.rs` | ① 调度器保存每个任务的 JoinHandle，stop 或宽限期结束时统一 `abort`；② main 保存调度器 JoinHandle，10s 超时后 `abort`；③ `PgPool::close` 加 5s 超时并告警 | 编译通过；需 Linux SIGTERM 演练 |
| 审查3-5 datauuid 为空的两路径不一致 | `src/services/sync.rs` | 统一策略：`_id` 优先 datauuid → 为空回退 bigId（与消费端一致）→ 两者都空则跳过并计入 `total_err`（`SyncRecord.doc: Option`，游标仍用原主键推进）。文档记录该策略 | 编译/测试通过 |
| 审查3-6 bulk errors 无 items / 条数不一致 | `src/es.rs` | `errors=true` 且 items 缺失时整批判失败（failed=docs.len()）；items 数 ≠ docs 数时 `warn`；`errors=true` 但 items 未标记 error 时按缺失条数计失败 | 编译/测试通过 |
| 审查3-7 客户端断连泄漏 in-flight | `src/metrics.rs`、`src/middleware.rs` | 新增 `InFlightGuard`：正常收尾调用 `finish(status,ms)`；future 被取消时 `Drop` 走 `request_aborted`（计数 `client_closed`）并递减 in-flight | 编译/测试通过 |
| 审查3-8 mqConsumer 只看订阅状态 | `src/mq.rs`、`src/state.rs`、`src/router.rs`、`src/main.rs` | `ConsumerState { started, last_recv_ms }` 取代单一 AtomicBool；每次 recv 成功刷新时间；`/readyz` 输出 `UP/STALE(>60s)/DOWN/DISABLED` | 编译/测试通过 |
| 审查3-9 增量失败仍推进水位 | `src/services/sync.rs` | `sync_range` 返回失败条数；增量同步仅 `failed==0` 时推进水位，否则 error 日志并等待下轮/repair | 编译/测试通过 |
| 审查3-10 EqDate 截断时分秒 | `tools/gen_filters.py`、`src/repo/mod.rs`、`src/repo/filters_gen.rs` | 核对 Java：`BaseController.initBinder` 用 `DateUtils.parseDate(text)` 绑定所有 `Date` 字段（`@JsonFormat` 只影响序列化），日期串解析为 00:00:00、带时分秒的入参保留时分秒。因此 `Day` 与 `JDateTime/JIsoDateTime` 统一走 `Cond::EqTimestamp`（`to_timestamp(...,'yyyy-mm-dd HH24:MI:SS')`），移除 `EqDate`；条件数仍为 572 | 单测 `cond_time_equality_renders_to_timestamp` 通过 |

## 第三轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `cargo test` | **22 passed / 0 failed**（16 + 6） |
| 未验证 | ES mapping 创建/ILM/重建脚本（需 ES 7.15）、大页码压测、多副本租约降级、SIGTERM 关闭排空、增量失败水位行为 |

## 环境限制记录（需运维/CI 注意）

- 本轮执行时 **D 盘可用空间为 0 字节**，无法在 D 盘写入编译产物，也无法保存部分工具快照。
- 为释放空间，删除了项目 `.run/java.out`（474MB）与 `.run/java.err`（142MB）——均为历史 Java 运行日志，不属于源码/文档。
- 本次编译使用 `CARGO_TARGET_DIR=C:\Users\abelz\AppData\Local\Temp\car-monit-target-rust`，并设 `CARGO_INCREMENTAL=0`；D 盘的 `target/` 未删除（删除动作被安全策略拒绝）。
- CI 或后续会话建议先清理 D 盘再编译，或显式设置 `CARGO_TARGET_DIR` 到有空间的盘。

---

# 第四轮：复核问题修复（2026-11-08，含中断续做）

> 背景：第四轮修复执行到一半时上游超时中断，改动已落盘但未验证、日志未写。
> 本次先逐项核对落盘内容，再补做剩余项，最后统一验证。
> 依据：第四轮复核「1 阻断 + 若干中危 + 低危」。
> 验证命令：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`
> 编译环境：D 盘仍无可用空间，统一使用 `--target-dir C:\Users\abelz\AppData\Local\Temp\car-monit-target-rust`（未设置 `CARGO_INCREMENTAL=0`，靠独立 target 目录隔离）。

## 一、上一轮已落盘、本次核对确认的部分

| 复核项 | 状态 | 落盘位置 | 本次核对结果 |
|---|---|---|---|
| 1 阻断：`max_ngram_diff` | 已落盘 | `resources/es/index/{snapshot_flow,fee_records,trail_fitting}.json` | 三份模板均含 `"index.max_ngram_diff": 2`；PUT 后 `validate_index_mapping` 用 JSON 结构校验 date 与 `.ngram` |
| 2 脚本：先校验再删除 | 已落盘 | `tools/es-rebuild-snapshot-flow.sh` | 新增"预检索引"：先 PUT `${INDEX}__preflight_$$` 并校验，通过后删除预检索引，再删旧索引；PUT 失败重试 3 次并打印可手工执行的 body；失败信息走 stderr |
| 3 脚本：UTC→本地时间 | 已落盘 | 同上 | 默认窗口改用 `date -d/-v` 本地墙钟，输出显式标注"本地时间" |
| 4 脚本：DB/ES 都为 0 直接成功 | 已落盘 | 同上 | `DB_COUNT==0` 时仅当 `ES_COUNT==0` 立即成功，否则继续等待 |
| 5 脚本：ILM 已存在跳过 | 已落盘 | 同上 | 先查 `_ilm/policy`，200 则跳过，不覆盖运维策略 |
| 6 脚本：JSON 解析校验 mapping | 已落盘 | 同上 | `python3` 解析 `_mapping`，断言 `snapshottime.type=date`、`platenumber.fields.ngram` 存在 |
| 7 脚本：消费端前置校验 + gsql | 已落盘 | 同上 | 解析 `/readyz` 的 `mqConsumer`，非 `DISABLED` 直接拒绝；`DB_CLIENT` 自动探测 `psql`→`gsql`，gsql 使用 `-t -A -c` |
| 8 轨迹分页改 SQL 下推 | 已落盘（本次补 pageSize 上限） | `src/repo/mod.rs`、`src/handlers/sysutil.rs`、`src/services/sysutil.rs`、`src/services/track_sync.rs` | `get_history_trail(vo, limit, offset)` 输出 `LIMIT ? OFFSET ?`；端点只传 `page_size`/`offset`；异常请求拒绝而非截断：`pageSize > 5000` 或 `offset > 50_000_000` 返回 400；TrackTask 传 `(0,0)` 保持无 LIMIT |
| 9 skipped/failed 分离 | 已落盘 | `src/services/sync.rs` | 新增 `SyncStats{failed,skipped}` 与 `total_skipped`；空主键计 skipped 并告警，只有 `failed>0` 才阻断水位 |
| 12 HEAD+PUT 竞态 | 已落盘 | `src/es.rs` | `resource_already_exists_exception` 视为已存在（返回 Ok(false)） |
| 13 bulk 计数补齐/clamp | 已落盘（本次补强） | `src/es.rs` | `items` 少则缺失数一律计入 failed（不再依赖 `errors`），多则 clamp `ok ≤ docs.len()`；`errors=true` 且无可定位明细时整批判失败 |
| 14 索引初始化重试 | 已落盘 | `src/main.rs` | 启动后台任务重试 3 次（5s/15s 退避），最终失败升级为 `error!` 并提示重建脚本 |

**核对中发现并修复的半成品问题**（上一轮未编译验证遗留）：
- `SnapshotFlowConsumer::start` 改为返回 `JoinHandle` 后缺少 `}))`，导致 lib 编译失败；
- `axum::serve(...).with_graceful_shutdown(...)` 不是 `Future`，补充 `IntoFuture::into_future` 后才能被 `tokio::select!` 使用；
- `/readyz` 的 `match` 单分支触发 clippy `single_match`，改为 `if let`。

## 二、本次补做的部分

### 复核 10：协作式停机 + 可配预算

| 项 | 内容 |
|---|---|
| 改动文件 | `src/config.rs`、`config/application.yaml`、`.env.example`、`src/scheduler.rs`、`src/services/consumer.rs`、`src/main.rs` |
| 改动 | ① 新增 `app.shutdown-grace-seconds`（默认 25，`APP_SHUTDOWN_GRACE_SECONDS`，钳 5–300），作为"收到 SIGTERM 起算"的总预算；② HTTP 排空用 `select!` 与"信号后 grace 定时器"竞争，超时放弃剩余连接；③ 消费端返回 JoinHandle，停机时给 ≤3s 自然退出；④ 调度器不再一收到 stop 就 abort：`drain_jobs` 先 `join_all` 等待在途任务，超时才 abort（调度器分得 `min(10s, grace/2)`）；⑤ 导出/大查询/DB 关闭都从动态剩余预算里取，DB 额外封顶 5s；⑥ 文档写明 `terminationGracePeriodSeconds >= shutdown-grace-seconds + 5`（YAML 注释、`.env.example`、启动日志） |
| 对应复核 | "200ms 即 abort 会留半成品；串联超时可达 80s 超出 K8s 默认 30s" |
| 验证 | check/clippy/test 通过；真实 SIGTERM 排空需 Linux 环境演练 |

### 复核 11：严格模式告警限频 + 开关启动日志

| 项 | 内容 |
|---|---|
| 改动文件 | `src/scheduler.rs`、`src/main.rs` |
| 改动 | ① 严格模式租约失败改为 60s 限频（`strict_warned_at`），与降级分支一致，不再每 5s 刷屏；② 启动时打印 `env/consumer_enabled/enable_scheduler/scheduler_lease_required/shutdown_grace_seconds`，调度器启动日志再次打印 `scheduler-lease-required` 与停机预算，便于部署核对 |
| 对应复核 | "严格模式 warn 刷屏；开关取值要在启动日志可见" |
| 验证 | check/clippy/test 通过 |

### 复核 15：`STALE` 区分"topic 安静"与"连接异常"

| 项 | 内容 |
|---|---|
| 改动文件 | `src/mq.rs`、`src/router.rs` |
| 改动 | `ConsumerState` 增加 `last_error_ms`/`last_error`；订阅失败与 `recv` 失败调用 `mark_error`；`/readyz` 判定顺序：未订阅→`DOWN`；最近错误晚于最近成功 recv→`DOWN`（连接异常）；否则 60s 无消息→`STALE`（topic 安静）；有消息→`UP`。响应额外输出 `mqConsumerLastRecvMs` 与 `mqConsumerError` |
| 对应复核 | "STALE 无法区分无消息与连接异常" |
| 验证 | check/clippy/test 通过；真实 broker 断连需环境演练 |

## 三、第四轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（exit 0，0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `cargo test` | **22 passed / 0 failed**（16 单元 + 6 集成） |
| 未验证 | ES 7.15 实际建索引/ILM/脚本全流程、大页码压测、多副本租约与严格模式、Linux SIGTERM 排空、Kafka 断连探针、GaussDB gsql 对数 |

## 四、仍未做 / 需环境或决策

1. 重建脚本采用"预检索引（临时名）+ 删除旧索引 + 重建"，已消除 mapping 非法导致的破坏性窗口；但删除后 ES 立即不可用仍会留下空索引状态（重试 3 次后打印 body 手工恢复）。若要零窗口，需要改为"新索引 + 别名切换"，会牵涉运行期索引寻址方式，建议单独立项。
2. 所有真实环境行为验证（ES/GaussDB/Redis/Kafka、SIGTERM、多副本）仍需预发执行。
3. D 盘空间问题未解决，后续会话仍需使用临时 `--target-dir`。

---

# 第五轮：收口复核修复（2026-11-08）

> 依据：收口复核「无阻断/无高危；2 中危 + 6 低危」。
> 验证：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`（见本章末）。

## 中危

### 审查5-1 mqConsumer 状态机：历史错误永久保留 + STALE 判定顺序

| 项 | 内容 |
|---|---|
| 改动文件 | `src/mq.rs`、`src/router.rs` |
| 改动 | ① `mark_recv` 成功收消息时同时把 `last_error_ms=0`、`last_error=None`，历史错误不再永久保留；② `/readyz` 判定顺序改为：DISABLED → 未订阅 DOWN → **60s 内有消息 UP** → 否则用"错误是否晚于最后 recv"区分 DOWN/STALE；③ `mqConsumerError` 只在当前仍有错误时输出 |
| 对应复核 | 一次历史错误后永远 STALE/DOWN |
| 验证 | check/clippy/test 通过；真实 broker 断连→恢复需环境验证 |

### 审查5-2 HTTP 排空吃满预算导致调度器任务 detach

| 项 | 内容 |
|---|---|
| 改动文件 | `src/main.rs`、`src/scheduler.rs` |
| 改动 | ① HTTP 排空预算改为总 grace 的 **60%**（其余留给消费端/调度器/导出/DB），`timeout(0)` 不再出现；② 新增 `JobHandle` 包装：持有 JoinHandle + AbortHandle，`Drop` 时若 JoinHandle 未被取走（调度器被外部 abort/丢弃）立即 abort 在途 job；`drain_jobs` 取走后按超时逻辑 abort |
| 对应复核 | HTTP 占满 grace → 调度器 abort → 在途 job detach 继续写库 |
| 验证 | check/clippy/test 通过；真实 SIGTERM 需 Linux 演练 |

## 低危

| 编号 | 改动文件 | 改动与取舍 | 验证 |
|---|---|---|---|
| 5-3 pageSize 5000 分支不可达 | `src/handlers/sysutil.rs`、`src/handlers/common.rs` | 保留 `page_params` 的统一上限并提为 `MAX_PAGE_SIZE=1000`（与 Go 版一致，避免影响全部列表接口），删除不可达的 5000 分支；`check_track_page` 只校验 offset，注释明确"单页最多 1000 行" | 编译/测试通过 |
| 5-4 预检索引残留 | `tools/es-rebuild-snapshot-flow.sh` | 增加 `trap cleanup_preflight EXIT`，任何退出路径（校验失败/Ctrl+C）都清理 `${INDEX}__preflight_<pid>`；正常通过后 `trap - EXIT` | `bash -n` 通过 |
| 5-5 `_id` 缺失静默随机 UUID | `src/es.rs` | 改为返回 Err（"缺少非空主键字段，拒绝写入"），消除每次重跑生成新文档的非幂等行为 | 编译/测试通过 |
| 5-6 bulk items>docs 计数溢出 | `src/es.rs` | `items` 多于请求数时同时 clamp `ok` 与 `failed`，保证 `ok+failed <= docs.len()` | 编译/测试通过 |
| 5-7 脚本时间窗预检 | `tools/es-rebuild-snapshot-flow.sh` | 在任何删除动作前校验 `yyyy-MM-dd HH:mm:ss` 格式且 `START < END`（字典序等价时间序）；用独立 bash 用例验证 reversed/normal/非法月份/相等四种输入 | 逻辑用例 4/4 符合预期 |
| 5-8 psql 探测失败不回退 | `tools/es-rebuild-snapshot-flow.sh` | 显式 `DB_CLIENT` 仅接受 psql/gsql 且失败即报错（不回退）；自动探测时 psql 连接失败则回退 gsql；计数必须为纯数字，否则拒绝继续 | `bash -n` 通过 |

## 第五轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `cargo test` | **22 passed / 0 failed**（16 单元 + 6 集成） |
| 脚本 | `bash -n` 通过；时间窗校验逻辑用 4 组输入验证通过 |
| 环境 | D 盘仍无空间，使用 `--target-dir C:\Users\abelz\AppData\Local\Temp\car-monit-target-rust` |

## 仍未做（需预发/环境）

1. ES 7.15 实际建索引、ILM 创建、重建脚本全流程（需 ES + psql/gsql + python3 + bash）。
2. Kafka 断连→恢复时 `/readyz` 的 UP/DOWN/STALE 切换观测。
3. Linux SIGTERM 停机演练：确认 HTTP 60% 排空、调度器 drain、job 不 detach、总耗时 ≤ `terminationGracePeriodSeconds`。
4. 多副本租约切换与严格模式告警限频。
5. 零窗口重建（别名切换）未实现，仍建议单独立项。

---

# 第六轮：独立审阅问题修复（2026-11-08）

> 依据：独立审阅「无阻断；3 中危 + 6 低危」，核心问题为"日志声称修了、实际没完全生效"。
> 验证：`cargo check --all-targets`、`cargo clippy --all-targets -- -D warnings`、`cargo test`（见本章末）。

## 中危

### 审查6-1 时间窗预检只校验形状 → 删索引后新索引空壳

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh`、`src/handlers/query.rs` |
| 改动 | ① 脚本预检改用 `python3 datetime.strptime("%Y-%m-%d %H:%M:%S")`，同时校验真实年月日（拒绝 `2026-02-30`）与时分秒范围（拒绝 `25:61:99`），并要求 `START < END`；校验发生在任何 ES 删除动作之前；新增 `CHECK_ONLY=1` 让 CI 只跑参数校验。② repair 接口改用 `strict_time_range`：`time_range`（非空）→ `utils::parse_time`（与后台 `repair_sync` 同一个解析器）→ 严格 `s >= e` 拒绝，非法直接 400，不再出现"HTTP 200 + 后台 parse 失败" |
| 对应复核 | 旧索引已删、新索引空壳 |
| 验证 | 脚本 6 组用例全部通过；`/sync/repair` 的 400 语义需真实 HTTP 请求复核 |

### 审查6-2 `mq.rs` 状态机永久误报

| 项 | 内容 |
|---|---|
| 改动文件 | `src/mq.rs`、`src/services/consumer.rs` |
| 改动 | ① `mark_started` 同时清 `last_error_ms=0` 与 `last_error=None`："订阅失败→恢复→topic 安静"最终落到 STALE，不再永久 DOWN。② 消费循环整体包 `AssertUnwindSafe(...).catch_unwind()`：任务 panic 后仍执行 `mark_error("消费循环 panic 退出")` + `mark_stopped()`，`is_started` 不会永久为 true 被误判 STALE |
| 对应复核 | 已解决的错误仍持续输出；panic 后任务死亡却显示存活 |
| 验证 | readyz 状态机 6 个单测覆盖"恢复后无消息"与"任务死亡"边界 |

### 审查6-3 重建脚本打印含密码的 `DATABASE_URL`

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh` |
| 改动 | 计划输出不再用 `${DATABASE_URL%%\?*}`，改用 `urllib.parse` 只打印 `host:port/db`；解析失败回退 `<redacted>`。密码、用户名、query 参数一律不进日志 |
| 对应复核 | 日志/工单泄露数据库凭据 |
| 验证 | 脚本用例执行通过（脱敏分支不访问 DB） |

## 低危

| 编号 | 改动文件 | 改动与取舍 | 验证 |
|---|---|---|---|
| 6-4 drain 期间外部 abort 仍 detach | `src/scheduler.rs` | 新增 `AbortAllOnDrop` guard：`drain_jobs` 把 JoinHandle 移出 `JobHandle` 后，guard 持有全部 `AbortHandle`；drain 被外部 abort 时 guard 的 Drop 中止所有在途 job；正常结束置 `armed=false` | `#[tokio::test] cancelling_drain_aborts_inflight_jobs` |
| 6-5 末段预算为 0 / 日志用未 clamp 值 | `src/main.rs` | ① `shutdown_grace` 只在一处 `clamp(5,300)`，调度器与主流程复用同一值，启动日志打印有效值；② 导出/大查询仅在剩余预算 ≥1s 时等待，否则 `warn` 明确"预算已用尽，跳过等待"（写进日志与注释）；③ DB close 至少尝试 1s 但不超过 5s；④ 消费端超时由 detach 改为 `handle.abort()` 并标 DOWN | check/clippy/test 通过 |
| 6-6 pageSize 上限只覆盖 `/base/*` | `src/handlers/query.rs` | `page_args` 末尾统一 `page_size.min(MAX_PAGE_SIZE)`（覆盖 `/api/v1/large`、`/api/v1/unified`）；`progressive_request` 同样钳制；日志声明与实际行为一致 | 编译通过；上限行为由 `page_params` 既有语义保证 |
| 6-7 消费端 3s 预算到点 detach | `src/main.rs` | 超时分支执行 `handle.abort()`，并 `mark_error` + `mark_stopped`，不再让任务脱离管理继续运行 | check 通过；真实停机需 Linux 演练 |
| 6-8 脚本 trap 覆盖不到 SIGKILL / cleanup 静默 | `tools/es-rebuild-snapshot-flow.sh` | ① 新增 `sweep_preflight`：运行开始时按 `${INDEX}__preflight_*` 清扫历史残留（SIGKILL/断电场景）；② `curl_es`/`curl_es_status` 统一带 `--connect-timeout 5 --max-time 60`；③ `cleanup_preflight` 失败时输出警告与手工清理命令，不再静默吞掉 | `bash -n` 通过 |
| 6-9 改动无测试 | `src/es.rs`、`src/scheduler.rs`、`src/router.rs`、`tools/test-es-rebuild-snapshot-flow.sh` | ① bulk 计数 3 例（缺失 items 计失败、多余 items clamp、`errors=true` 无明细整批失败）；② `JobHandle` Drop 语义 2 例（drop 中止任务、drain 被 abort 时中止在途 job）；③ readyz 状态机 6 例（DISABLED 优先、未启动 DOWN、新消息 UP、安静 STALE、新错误 DOWN、从未收到 STALE）；④ 脚本时间窗 6 例（正常/倒置/相等/非法日期/非法时间/格式错误） | `cargo test` 33 passed；脚本用例 6/6 PASS |

## 第六轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo check --all-targets` | **通过**（exit 0，0 error / 0 warning） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `cargo test` | **33 passed / 0 failed**（11 单元 + 16 parity + 6 router） |
| 脚本 | `bash -n` 两个脚本通过；`tools/test-es-rebuild-snapshot-flow.sh` 6/6 PASS |
| 环境 | D 盘仍无空间，使用 `--target-dir C:\Users\abelz\AppData\Local\Temp\car-monit-target-rust` |

## 仍未做（需预发/真实环境）

1. ES 7.15 实际建索引、ILM、`sweep_preflight` 与完整重建流程（需 ES + psql/gsql + python3 + bash）。
2. `/sync/repair` 非法时间参数的真实 400 响应与合法参数的端到端回灌。
3. Kafka 订阅失败→恢复→topic 安静的 readyz 切换、消费任务 panic 后的 DOWN 观测。
4. Linux SIGTERM 停机演练：消费端 3s 超时 abort、调度器 drain 与 `AbortAllOnDrop`、总耗时 ≤ `terminationGracePeriodSeconds`。
5. 零窗口重建（别名切换）仍未实现，建议单独立项。

---

# 第七轮：第六轮独立审阅问题修复（2026-11-08）

> 依据：第六轮独立审阅「1 阻断 / 1 高危 / 4 中危 + 7 低危」。
> 约束：本目录被仓库根 `.gitignore` 整体忽略、目录内无独立 `.git`，未执行任何 git 命令。
> 验证：`cargo test --all-targets`、`cargo clippy --all-targets -- -D warnings`、`bash -n` 两个脚本、`bash tools/test-es-rebuild-snapshot-flow.sh`（结果见本章末）。

## 阻断

### 审查7-1 重建脚本删完索引后 GET 调 repair（405），回灌从未发出

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh`、`tools/test-es-rebuild-snapshot-flow.sh` |
| 问题 | 脚本用 `curl --get` 调 `/api/v1/large/sync/repair`，而 `src/router.rs` 只注册了 POST。真实顺序是：删旧索引 → 建空索引 → GET 得到 405 → `curl -f` 非零 → `set -e` 中止，回灌一次都没发出去，索引变成空壳。 |
| 改法 | ① 正式回灌改为 `-G -X POST`（`--data-urlencode` 仍拼 query），与 router 注册方法一致；② 在删除旧索引**之前**新增"回灌接口可达性探针"：用非法时间参数（`strict_time_range` 在 HTTP 阶段返回 400，不会调度后台任务）调用同一 POST 端点，断言得到 4xx 且不是 404/405，否则 `exit 2`；③ `/readyz` 门禁从只校验 `mqConsumer=DISABLED` 扩展为 `status==UP` 且 `elasticsearch==UP`（消费端检查保留），全部通过才允许继续；④ APP 侧两处 curl（`/readyz`、repair）补 `--connect-timeout 5 --max-time 60`，避免 APP 假死无限等待。 |
| 依据 | `src/router.rs` 的 `.route("/api/v1/large/sync/repair", post(query::sync_repair))`；`src/handlers/query.rs` 的 `strict_time_range` 对非法格式返回 400 |
| 残余差异 | 探针只验证"路径 + 方法 + 参数校验链路"可达，不验证后台回灌最终能否成功（ES 写入仍可能失败）。真实 HTTP/ES 端到端未执行。 |

## 高危（本轮不重构别名切换，只加术前门禁）

### 审查7-2 删旧索引与回灌之间没有别名切换

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh`（仅门禁） |
| 问题 | 删旧索引后 HTTP 层已返回成功，回灌失败只能靠 `_count` 轮询两小时才发现；期间查询走 DB 降级或空索引。 |
| 本轮改法 | 只做手术前门禁：`/readyz`（status+ES=UP）、repair 可达性探针、预检索引；把"必然留空壳"降为"仅 ES/APP 中途故障才留空壳"。 |
| 不做别名切换的理由 | 需要运行期写/查全部改为按别名寻址，并实现双索引并行写入、原子切换与回滚脚本；涉及 `src/es.rs` 索引解析、`src/services/{sync,consumer,query,large,export,progressive}.rs`、`resources/es/index/*.json` 与整套验收流程，工作量和风险超出本轮范围。 |
| **独立待办（必须单独立项）** | 新索引 `<index>_v2` → 完整回灌 → `_count` 与 DB 对数达标 → `_aliases` 原子切换到新索引 → 旧索引保留 N 天再删除；验收需覆盖切换失败回滚、双写窗口、ILM/别名绑定。 |
| 当前残余风险 | 删除后回灌失败仍会留空壳；恢复手段为重跑 repair 或按脚本打印的 body 手工 PUT；`/readyz` 不感知"索引存在但为空"。 |

## 中危

### 审查7-3 `strict_time_range` 挡不住空白时间

| 项 | 内容 |
|---|---|
| 改动文件 | `src/handlers/common.rs`、`src/handlers/query.rs` |
| 问题 | `parse_time` 对空串返回 epoch 0；`require_time_range` 只判 `is_empty`，`startTime=+` 解码成空格即可通过，随后 repair 从 1970 年按小时分片回灌。 |
| 改法 | ① `require_time_range` 改为 `trim().is_empty()` 拒绝（所有查询/列表端点统一）；② repair 的 `strict_time_range` 不再复用宽容的 `parse_time`，改用 `chrono::NaiveDateTime::parse_from_str("%Y-%m-%d %H:%M:%S")`，只接受单一格式，trim 后返回；仍要求 START < END。 |
| 依据 | 运维入口需要确定输入；`parse_time` 的多格式宽容语义保留给 Java `DateUtils` 兼容路径。 |
| 残余差异 | 其它端点仍接受 `parse_time` 的多格式（有意对齐 Java）；`parse_time("")` 仍返回 epoch 0，但公开 HTTP 入口已被 `require_time_range` 拦截。 |

### 审查7-4 消费端 panic 后永久 `break`，任务停摆但探针 200

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/consumer.rs`、`src/router.rs`（仅测试） |
| 问题 | panic 分支只 `mark_error` + `mark_stopped` 后退出任务，`/readyz` 只体现在 JSON 里、HTTP 仍 200，K8s 不摘流也不重启。 |
| 选型 | 选择"panic 后带退避重连"，**不选**"readyz 503（限 DOWN）"。 |
| 理由 | Kafka 消费是旁路写链路，Kafka 故障不应把整个 HTTP 服务从流量里摘掉（503 会连带打掉查询流量，放大故障面）；进程内 panic 可通过重连自愈，退避 5s→60s 上限避免 panic 空转刷日志。 |
| 改法 | `start()` 改为外层循环：每次 `bus.consume` 独立 `catch_unwind`，异常/panic 后 `mark_stopped` 并按退避重连，退避等待可被 stop 中断；一次运行 ≥120s 后失败则退避重置；新增 `mark_panic_exit(state)` 统一 panic 接线（`mark_error` + `mark_stopped`），供单测直接覆盖。 |
| 依据 | `mq.consume` 收到 stop 时返回 `Ok(())`，可与异常退出区分。 |
| 残余差异 | 若 panic 由"每条消息必现"的 bug 引起，会持续重连循环（最长 60s 退避）而无法真正恢复；`/readyz` 仍返回 200（JSON 中 `mqConsumer=DOWN`），这是选型的直接代价。 |

### 审查7-5 `shutdown_grace` 总预算契约不成立

| 项 | 内容 |
|---|---|
| 改动文件 | `src/main.rs` |
| 问题 | 调度器与 DB 关闭各有 `max(...,1s)` 硬下限，极端情况下总耗时可比 grace 多约 2s；最终日志用 `grace.saturating_sub(remaining)` 会把超支低报成"恰好等于 grace"；注释宣称"保证总时长不超过 grace"与实现不符。 |
| 改法 | 保留 1s 最低尝试窗口（保证清理动作有机会执行），但：① 最终日志改用 `signal_at` 的真实 elapsed，并同时输出 `grace_ms` 便于对比；② 重写预算注释，明确"可超出约 2s"；③ 消费任务 `abort()` 后 `await` JoinHandle，确保任务真正结束再进入后续关闭阶段。 |
| 依据 | 硬下限是必要的清理机会；日志必须如实反映实测耗时。 |
| 残余差异 | 合同仍不是严格硬上限（最坏约 +2s）；部署侧 `terminationGracePeriodSeconds` 仍需 ≥ `shutdown-grace-seconds + 5`。 |

### 审查7-6 6-6 只钳了 `pageSize`

| 项 | 内容 |
|---|---|
| 改动文件 | `src/handlers/query.rs`、`src/handlers/common.rs`、`src/services/query.rs`、`src/services/large.rs` |
| 问题 | `page_args` 只钳 `pageSize`，`pageNum` 无上限：`pageNum=9223372036854775807&pageSize=20` 时 `(pageNum-1)*pageSize` 在 debug 下 panic → 500，release 下回绕成负数 → `.max(0)` → 静默返回第 1 页错误数据。 |
| 改法 | ① `MAX_PAGE_NUM` 改为 `pub` 并在 `page_args` 中钳制（与 `/base/*` 复用同一上限）；② `query_from_es` 的 `from`、`page_in_memory` 的 `from/to`、`large.rs` 的 ES `from` 全部改 `saturating_sub` / `saturating_mul` / `saturating_add`；③ 新增极值单测。 |
| 依据 | 复用第三轮为 `/base/*` 做的 `MAX_PAGE_NUM` + 饱和运算策略。 |
| 残余差异 | `page_in_memory` 对超大页码返回空列表（而非 PageHelper `reasonable` 钳到最后一页）；仅影响 DB 降级分支的异常输入。 |

## 低危

| 编号 | 改动文件 | 改动与依据 | 残余差异 |
|---|---|---|---|
| 7-7 `ES_URL` 明文进日志 | `tools/es-rebuild-snapshot-flow.sh` | 新增 `redact_url()`（`urllib.parse`），计划输出只打印 `scheme://host:port/path`；`ES_URL` 与 `DATABASE_URL` 共用 | 用户名也一并隐藏（更保守）；URL 解析失败回退 `<redacted>` |
| 7-8 APP 侧 curl 无超时 | 同上 | `/readyz` 与 repair 调用统一带 `CURL_TIMEOUT`（connect 5s / max 60s） | APP 处理超过 60s 会判失败，符合运维预期 |
| 7-9 `abort()` 后未 join | `src/main.rs` | abort 后 `let _ = handle.await;`，等待任务真正结束 | 已被 abort 的任务不会返回业务结果，join 只保证生命周期收敛 |
| 7-10 panic 时幂等 key 不清理 | `src/services/consumer.rs` | 新增 `IdempotencyGuard`：成功 `keep()`；`Err` 仍同步 await 删除；panic 时 Drop 里 `tokio::spawn` 删除（尽力而为） | Drop 内不能 await，删除是异步尽力而为；运行时已关闭时 spawn 会被丢弃（进程退出场景可接受） |
| 7-11 `parse_bulk_response` 把失败钳成 0 | `src/es.rs` | items 多于 docs 时只钳 `ok`，若原始 items 有 error 且钳后 `failed==0` 则强制置 1；保证"多出来的失败"不会被静默吞掉 | 该异常场景下 `ok + failed` 可能比 `docs_len` 多 1；宁可多报失败也不谎报成功 |
| 7-12 `sweep_preflight` 并发误删 | `tools/es-rebuild-snapshot-flow.sh` | 索引名后缀即创建者 PID：`kill -0` 存活的跳过，仅清理已死进程/非数字后缀的残留 | 跨主机 PID 可能与本机同名进程碰撞，属尽力而为；固定前缀 + PID 已使碰撞概率很低 |
| 7-13 脚本测试只断言"非 0" | `tools/test-es-rebuild-snapshot-flow.sh` | 拒绝类用例改为断言具体 `rc=2` 且 stderr 含"时间窗校验失败"；新增静态断言：脚本中每处 `${APP_URL}/api/v1/large/sync/repair` 调用附近必须显式 `-X POST`，且 `router.rs` 注册必须是 `post(` | 静态断言靠文本匹配，若脚本改用变量拼接 URL 需同步调整检查 |

## 测试补强

| 项 | 改动 | 说明 |
|---|---|---|
| readyz 状态机 | `src/router.rs` 测试改为驱动 `ConsumerState::mark_started/mark_recv/mark_error/mark_stopped`，再用 getter 组装 `consumer_status` 入参 | 若回退 `mark_started` 清 `last_error` 的逻辑，`mark_started_clears_previous_error_then_stale` 会变 DOWN 而失败；覆盖 panic 前 `mark_stopped` 语义 |
| panic 接线 | `src/services/consumer.rs` 新增 `mark_panic_exit` 单测 | 直接断言 panic 后 `is_started=false`、`last_error` 非空、状态 DOWN |
| 正常 drain 不 abort | `src/scheduler.rs` 新增 `normal_drain_lets_jobs_finish_without_abort` 与 `disarmed_abort_guard_does_not_abort` | 直接覆盖 `AbortAllOnDrop` 的 `armed=false`：disarm 后 Drop 不得中止任务 |
| bulk `errors=true` 分支 | `src/es.rs` 用例改为 items 数 == docs_len、全部无 `error` 且 `errors=true` | 真正执行 `errors_flag && failed==0` 分支，不再依赖"items 缺失"分支 |
| 脚本静态断言 | `tools/test-es-rebuild-snapshot-flow.sh` | 防止"脚本 GET / 路由 POST"的阻断复发 |

## 第七轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo test --all-targets` | **47 passed / 0 failed**（25 单元 + 16 parity + 6 router） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `bash -n tools/es-rebuild-snapshot-flow.sh` | 通过 |
| `bash -n tools/test-es-rebuild-snapshot-flow.sh` | 通过 |
| `bash tools/test-es-rebuild-snapshot-flow.sh` | **7/7 PASS**（6 组时间窗用例 + 1 组 repair 方法静态断言） |
| 编译环境 | D 盘仅剩 0.01 GB、C 盘约 1.08 GB；继续使用 `--target-dir C:\Users\abelz\AppData\Local\Temp\car-monit-target-rust` + `CARGO_INCREMENTAL=0`，未删除任何用户数据 |

## 仍未做（需预发/真实环境）

1. 真实 ES 7.15 + APP + psql/gsql 端到端：`/readyz` 门禁、repair 探针（期望 400）、POST 回灌、`_count` 对数。
2. 消费端 panic → 退避重连 → 恢复的真实观测（需 Kafka 与可触发 panic 的故障注入）。
3. Linux SIGTERM 演练：实测 `total_elapsed_ms` 与 grace 的关系、abort 后 join、调度器 drain。
4. 别名切换（7-2 独立待办）未实现。
5. `/sync/repair` 严格格式 400 的真实 HTTP 响应复核（单测已覆盖函数层）。

---

# 第八轮：第七轮独立审阅问题修复（2026-11-08）

> 依据：第七轮独立审阅「1 条本轮引入的中危 + 1 条测试缺口 + 9 条未闭环低危」。
> 约束：本目录被仓库根 `.gitignore` 整体忽略、目录内无独立 `.git`，未执行任何 git 命令。
> 验证：`cargo test --all-targets`、`cargo clippy --all-targets -- -D warnings`、`bash -n` 两个脚本、`bash tools/test-es-rebuild-snapshot-flow.sh`（结果见本章末）。

## 中危

### 审查8-1 回灌探针判据过宽（任意 4xx 即通过）

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh` |
| 问题 | 旧判据只要求 `4xx` 且非 404/405；401/403/407/429 同样会挡住真实回灌，却会被当作"探针通过"，删除旧索引后仍留空壳。 |
| 改法 | 判据收紧为 **HTTP 必须精确等于 400**。探针参数是故意非法的 `startTime/endTime`，`strict_time_range` 必然在 HTTP 阶段返回 400；401/403/407/429 或任何其它状态都在删除前 `exit 2`。错误信息明确列出鉴权/限流类误判风险。 |
| 依据 | `src/handlers/query.rs` 的 `strict_time_range` 对非法格式返回 400；`src/router.rs` 只注册 POST。 |
| 残余差异 | 探针仍只证明"HTTP 校验链路可达且鉴权通过"，不证明后台修数最终成功；真实 400 响应需预发复核。 |

### 审查8-2 panic 接线测试是假覆盖

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/consumer.rs` |
| 问题 | 旧用例直接调用 `mark_panic_exit()` 再断言，循环里真正调用它的那行删掉仍全绿，无法发现接线缺失。 |
| 改法 | 把重连循环抽成泛型 `supervise_consume(stop, state, backoff 参数, run)`：`run` 每调用一次代表一次 consume 尝试，结果分 `Result<(), AppError>`（Ok=停机正常退出、Err=异常）与 panic（`catch_unwind`）。单测注入假 consume：第一次 panic/Err，第二次在"重连入口"断言 `is_started=false`、`last_error` 非空、状态 DOWN，再模拟订阅成功 `mark_started()`；同时断言调用次数=2、最终已恢复。删掉循环里的 `mark_panic_exit` 或 Err 分支的 `mark_error`，第二次断言必失败。 |
| 依据 | `mq::consume` 收到停机返回 `Ok(())`，异常返回 `Err(AppError)`，panic 可被 `catch_unwind` 捕获。 |
| 残余差异 | 假 consume 不覆盖真实 Kafka subscribe/recv 行为；真实 panic→重连需故障注入验证。 |

## 低危

| 编号 | 改动文件 | 改法与依据 | 验证 / 残余 |
|---|---|---|---|
| 8-3 `ES_URL` 三处明文 | `tools/es-rebuild-snapshot-flow.sh` | 预检清理失败的手工命令、旧索引已删重建失败的手工 PUT、验收提示全部改用 `${ES_DISPLAY}`（`redact_url` 输出，无 userinfo/query）；实际 curl 仍用真实 `ES_URL` | `bash -n` 通过；日志脱敏分支不需访问 ES |
| 8-4 主索引删建无互斥 + `kill -0` EPERM 误判 | 同上 | ① 新增 ES 侧锁 `${INDEX}__lock/rebuild`：显式建锁索引（`expires_at/owner_pid/host` mapping），`op_type=create` 原子抢占，`expires_at` 容忍 SIGKILL 残留（过期后删除重抢）；`LOCK_TTL_SECONDS` 默认 10800s，覆盖 2h 对数窗口；EXIT trap 释放；TTL 过期接管、409 时打印持有者并提供手工删除命令。② `sweep_preflight` 先 `ps -o user=` 取属主：属主是其他用户则保守跳过（`kill -0` 的 EPERM 与"进程不存在"不可区分）；属主是本用户且存活才跳过，其余视为残留 | `bash -n` 与脚本测试通过；锁的并发竞争需真实 ES 双会话演练 |
| 8-5 `Ok(Err)` 只 mark_stopped 不 mark_error | `src/services/consumer.rs` | `supervise_consume` 的 Err 分支先 `mark_error("消费循环异常退出: {e}")` 再 `mark_stopped`，`/readyz` 能看到 DOWN 原因 | 新增 `error_in_consume_records_reason_then_reconnects` 断言 `last_error` 含原因 |
| 8-6 停机 abort 路径可能丢消息 | `src/services/consumer.rs` | 改两段式幂等：`done_key` 沿用旧前缀（跨版本兼容，TTL=完整幂等窗口）；`processing_key = 旧前缀+processing:`，短 TTL=10s。命中 done→ack；命中 processing 但无 done→返回 Err 触发重投（宁可进 DLQ 也不静默丢）；成功先写 done 再删 processing；失败删 processing；panic 由 Drop 异步删，最坏 10s 后自动失效 | 编译/测试通过；真实 Redis 幂等行为与停机红投需环境验证。残余：跨版本滚动升级时旧单 key 会被新代码当作 done，属兼容取舍 |
| 8-7 `disabled_wins` 未验证优先级 | `src/router.rs` | 用例改为 default 状态 + `enabled=false`（不 `mark_started`）断言 DISABLED；另补 `enabled=true + started=false → DOWN` | `cargo test` 通过 |
| 8-8 静态断言只要求"至少一处" | `tools/test-es-rebuild-snapshot-flow.sh` | repair URL 出现次数必须 ≥2（探针 + 正式回灌）；`-X POST` 检测改为按反斜杠续行展开整个 curl 语句块，不再只看行窗口 | 脚本测试 8/8 PASS（含 "script=POST x2"） |
| 8-9 脚本 INDEX 与 APP 索引名无一致性校验 | `src/router.rs`、`tools/es-rebuild-snapshot-flow.sh` | `/readyz` 新增 `elasticsearchIndex`（`cfg.elasticsearch.index.snapshot`）；脚本解析该字段并断言 `== ${INDEX}`，不一致在删除前退出，提示检查 `APP_ELASTICSEARCH_INDEX_SNAPSHOT` | 编译通过；脚本离线测试不覆盖该分支，需真实 /readyz 验证 |
| 8-10 导出超时后 detach 而非 abort | `src/services/export.rs`、`src/services/large.rs`、`src/main.rs` | 两个 `close()` 在 join 超时后对全部 `AbortHandle` 显式 `abort()`，日志改为"已中止剩余任务"；main 不再在预算 <1s 时跳过 close，而是始终调用（`timeout(0)` 立即 abort），注释同步改为如实描述 | 编译/测试通过；真实导出超时停机需环境演练 |
| 8-11 `stop.changed()` 返回 Err 时忙循环 | `src/mq.rs`（2 处）、`src/scheduler.rs`、`src/services/producer.rs`、`src/services/consumer.rs`（supervisor） | 所有 `stop.changed()` 分支改为 `if r.is_err() \|\| *stop.borrow() { ...停机... }`；Sender 提前 drop 时不再以 0 延迟重复循环 | 编译/测试通过；进程停机时序需 Linux 演练 |

## 第八轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo test --all-targets` | **49 passed / 0 failed**（27 单元 + 16 parity + 6 router） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `bash -n tools/es-rebuild-snapshot-flow.sh` | 通过 |
| `bash -n tools/test-es-rebuild-snapshot-flow.sh` | 通过 |
| `bash tools/test-es-rebuild-snapshot-flow.sh` | **7 PASS**（6 时间窗用例 + 1 静态断言；脚本输出共 7 行，第八轮误写为 8/8，已订正） |
| 构建产物清理 | 使用仓库内 `target` 构建；删除前 D 可用 31,603,990,528 B，`.NET Directory.Delete` 后目录消失但可用降为 31,554,686,976 B（**-49,303,552 B**），判定为"搬家进回收站"，**实际释放 0 B**。已验证绕过：64 MB 文件 `SetLength(0)` 截断立即释放 67,108,864 B，空壳删除进回收站仅占元数据；该方式已写入项目记忆供后续使用 |
| 未验证 | 真实 ES 双会话锁竞争/过期接管、真实 /readyz 索引名门禁、repair 精确 400、Kafka panic 重连与 Redis 两段式幂等、导出超时 abort、Linux SIGTERM |

---

# 第九轮：第八轮独立审阅问题修复（2026-11-08）

> 依据：第八轮独立审阅「1 条中高危（本轮引入）+ 2 条中危 + 7 条低危」。
> 约束：本目录被仓库根 `.gitignore` 整体忽略、目录内无独立 `.git`，未执行任何 git 命令。
> 验证：`cargo test --all-targets`、`cargo clippy --all-targets -- -D warnings`、`bash -n` 两个脚本、`bash tools/test-es-rebuild-snapshot-flow.sh`（结果见本章末）。

## 中高危

### 审查9-1 消费端 panic 把毒消息变成永久停摆，且永不进 DLQ

| 项 | 内容 |
|---|---|
| 改动文件 | `src/mq.rs`、`src/services/consumer.rs` |
| 问题 | `catch_unwind` 只包在 `bus.consume` 外层，handler panic 会冒泡到重连循环；`Message.attempt` 在 `handle_with_retry` 内部维护、重连后归零。确定性 panic 的消息形成 `panic → 未提交 offset → 重连 → 重投 → 再 panic` 的死循环，永不进入重试耗尽/DLQ，分区被永久卡住，且 readyz 在 DOWN/STALE 间反复跳，故障不可见。 |
| 改法 | `mq.rs` 新增 `call_handler`：在 `handle_with_retry` 每次尝试内对 `handler(m)` 做 `AssertUnwindSafe(...).catch_unwind()`，panic 转成 `Err(AppError::biz("消息处理 panic: ..."))`。该 Err 与普通业务失败走同一路径：计入 attempt、指数退避重试、耗尽后投 DLQ、随后提交 offset。`consumer.rs` 外层 `catch_unwind` 仅保留为"consume 内部非消息级 panic"的安全网，不再承担毒消息兜底。 |
| 依据 | Kafka 分区内 panic 必须按单条失败处理，才能让 offset 前移；外层重连无法区分"毒消息"和"连接故障"。 |
| 验证 | 新增 `handler_panic_becomes_err` / `handler_error_is_not_marked_as_panic` / `handler_ok_passes_through` 三个单测，直接驱动 `call_handler`；`cargo test` 通过。真实 Kafka 毒消息故障注入未跑。 |
| 残余差异 | 若 panic 发生在 `handler` 之外的 consume 内部（rdkafka 封装层），仍走重连；这类 panic 不属于单条消息。 |

## 中危

### 审查9-2 两段式幂等的 TTL 大于自身重试预算

| 项 | 内容 |
|---|---|
| 改动文件 | `src/services/consumer.rs` |
| 问题 | `PROCESSING_TTL_SECONDS=10s`，而 `max-retry-times=3` + 200ms 指数退避 ⇒ 4 次尝试总窗口约 1.4s。任何落在 10s 残留窗口内的重投（跨副本 rebalance、10s 内重启、Drop 异步删除失败）都会在 1.4s 内耗尽重试并被投 DLQ，而实际上再等 8.6s 就能正常处理。 |
| 改法 | 看到 `processing` 且无 `done` 时不立即返回 Err，而是在**本次 handler 内等待**：每 200ms 检查（1）done 是否出现 → ack；（2）processing 是否消失 → 重新 `SET NX` 抢占并继续处理；最多等 `TTL + 1s` 才返回 Err。这样"处理中"不再消耗 mq 重试次数，也不再受 1.4s 预算限制。注释同步改写，删除"跨进程并发由分区语义避免"的错误假设。 |
| 依据 | 重投可能来自 rebalance/快速重启，分区语义并不能阻止同一消息落到另一副本。 |
| 验证 | 编译/测试通过；Go/Redis 等待分支需真实 Redis + 双副本演练。 |
| 残余差异 | 单线程顺序消费，等待期最长 11s 会阻塞**所有分区**的消费进度（同一 key 有序性要求如此）；若原处理者超过 TTL 仍存活，仍可能短暂双处理（依赖 upsert 幂等）。 |

### 审查9-3 ES 锁接管/释放不校验属主、TTL 与续租

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh` |
| 问题 | ① 过期接管是"读 expires_at → 无条件 DELETE → create"，A 可能在 B 接管后删掉 B 的新锁；② `release_rebuild_lock` 无条件 DELETE，超 TTL 被接管的旧流程退出时会删新持有者的锁；③ `LOCK_TTL_SECONDS` 下限 300s，而脚本轮询窗口 2h 且无续租，设 300–7000s 会中途被抢；④ 手工删除命令用脱敏 URL，开 basic-auth 的集群照抄会 401；⑤ `expires_at` 依赖本机时钟，跨机漂移误判。 |
| 改法 | ① 接管改为**条件删除**：GET 同时取 `_seq_no`/`_primary_term`，DELETE 带 `if_seq_no`/`if_primary_term`；版本冲突（409）则放弃接管；删除后再 create，create 409 说明别人先接管，退出。② 释放前 GET 比对 `owner_pid/host`，再用条件 DELETE；属主不匹配只告警不删。③ 改短 TTL（默认 180s）+ 后台每 30s 续租（`if_seq_no` 条件更新）；续租失败说明锁已丢失，向主进程发 TERM 终止，避免无锁继续删建。校验 `LOCK_TTL_SECONDS≥60`、`LOCK_RENEW_SECONDS≥10` 且续租≤TTL/2。④ 手工命令改用 `${ES_DISPLAY}` 并明确提示"启用鉴权时附带与 ES_USER/ES_PASS 相同的 -u 参数"。⑤ 用 ES 响应 `Date` 头计算时钟偏移，`expires_at` 与过期判定都用 ES 服务器时间。 |
| 依据 | `if_seq_no`/`if_primary_term` 是 ES 7 的乐观并发控制；短 TTL + 续租兼顾"崩溃后快速恢复"与"运行中不被抢"。 |
| 验证 | `bash -n`、脚本离线测试通过；真实双会话竞争/接管/续租需 ES 环境演练。 |
| 残余差异 | ES `Date` 头读取失败时回退本机时钟并告警（跨机漂移仍可能误判）；锁索引/文档保留（不删除锁索引本身）。 |

## 低危

| 编号 | 改动文件 | 改法与依据 | 验证 / 残余 |
|---|---|---|---|
| 9-4 探针精确 400 无自动化验证 | `tools/test-es-rebuild-snapshot-flow.sh` | 新增静态断言：脚本必须包含 `[[ "${REPAIR_PROBE_CODE}" != "400" ]]`，改回"任意 4xx"即失败。**不为合法参数增加探针**：合法调用会真实启动 repair 后台任务，在删除旧索引前触发一次全量回灌，副作用不可接受；合法格式由 `repair_accepts_only_exact_datetime_format` 单测覆盖 | 静态断言通过；"合法参数返回 200"仍属预发端到端项 |
| 9-5 静态断言可被复制探针满足 | 同上 | 统计真实 repair 调用（排除注释行）必须**恰好 2 处**；每处 curl 语句块必须同时含 `-G` 和 `-X POST`；按块内容要求**恰好 1 处探针**（含 `probe-invalid-format`）+**1 处正式回灌**（含 `startTime=${START_TIME}`） | 脚本测试通过（7 行 PASS） |
| 9-6 `close()` abort 后未 join | `src/services/export.rs`、`src/services/large.rs` | 改为持有 `JoinHandle` 并顺序 await（任务本身已并发运行）；超时后先 `abort()`，再用 500ms 上限 await 全部 handle，确保返回时任务已停在 await 点；若仍超 500ms（同步 I/O 阻塞）告警后继续 | 编译/测试通过；真实导出任务同步写 CSV 的取消延迟需演练 |
| 9-7 锁残留/TTL/手工命令/时钟 | `tools/es-rebuild-snapshot-flow.sh` | 见 9-3：短 TTL 180s + 30s 续租；手工命令说明 `-u`；ES `Date` 校准 | 同上；时钟回退属残余 |
| 9-8 8-7 只覆盖 default + enabled=false | `src/router.rs` | 新增 `disabled_wins_even_with_fresh_message`：构造 `started + 新鲜 recv`（enabled=true 时必为 UP），断言 `enabled=false` 仍为 DISABLED；把 enabled 判定下移到 UP 之后该用例会失败 | `cargo test` 通过 |
| 9-9 关键分支无单测 | `src/services/consumer.rs`、`src/mq.rs` | 新增 `dropped_stop_sender_is_treated_as_shutdown`（Sender drop → changed() 返 Err → 监督器退出且不再发起第 2 次尝试）、`dropped_guard_runs_cleanup_with_processing_key` / `kept_guard_does_not_run_cleanup`（Drop 清理语义）、`mq::tests` 三个（panic→Err/Err/Ok） | 通过；跨进程 DLQ 窗口与真实 Redis 等待分支仍需环境 |
| 9-10 文档订正 | `docs/RUST-FIX-LOG-20261108.md` | 第八轮验证表由"8/8 PASS"改为"7 PASS（6 时间窗 + 1 静态断言）"；本轮不再引用漂移行号，改用函数/文件描述 | 人工核对 |

## 第九轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo test --all-targets` | **56 passed / 0 failed**（34 单元 + 16 parity + 6 router） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `bash -n tools/es-rebuild-snapshot-flow.sh` / `test-...sh` | 通过 |
| `bash tools/test-es-rebuild-snapshot-flow.sh` | **7 PASS**（6 时间窗 + 1 静态断言：1 探针 + 1 正式、均 `-G`/`-X POST`、精确 400） |
| 构建产物清理 | target 共 5,809 个文件 / 4,058,998,867 B。逐文件 `SetLength(0)` 后删除：截断即释放 **3,716,648,960 B**；最终删除后合计释放 **3,667,304,448 B（约 3.50 GB）**，`Test-Path=False` |
| 未验证 | 真实 ES 锁竞争/条件接管/续租、Kafka 毒消息 DLQ 路径、Redis processing 等待与 rebalance、导出取消延迟、Linux SIGTERM |

---

# 第十轮：第九轮独立审阅问题修复（2026-11-08）

> 依据：第九轮独立审阅「2 条中危 + 7 条低危」。审阅同时确认：单条消息最坏约 45s，不会触发 rebalance（此前把 `PROCESSING_TTL_SECONDS=10` 与脚本 `LOCK_TTL_SECONDS=180` 混淆）。
> 约束：本目录被仓库根 `.gitignore` 整体忽略、目录内无独立 `.git`，未执行任何 git 命令。
> 验证：`cargo test --all-targets`、`cargo clippy --all-targets -- -D warnings`、`bash -n` 两个脚本、`bash tools/test-es-rebuild-snapshot-flow.sh`（结果见本章末）。

## 中危

### 10-1 等待预算与 poll 预算之间没有约束

| 项 | 内容 |
|---|---|
| 改动文件 | `src/config.rs`、`src/mq.rs`、`src/services/consumer.rs`、`config/application.yaml`、`.env.example` |
| 问题 | 全仓未配置 `max.poll.interval.ms`，也没有校验 `(max_retry+1)×(TTL+1)+退避+DLQ超时 < poll预算`；默认安全纯属常数凑巧。把 TTL 调到 ≥75s 或 max-retry-times 调到 ≥27 会静默越过预算。另：等待期会阻塞单线程消费的所有分区；等待循环也不响应停机。 |
| 改法 | ① 新增 `kafka.max-poll-interval-ms`（默认 600000，YAML + `APP_KAFKA_MAX_POLL_INTERVAL_MS`），`KafkaBus` 显式 `set("max.poll.interval.ms")`。librdkafka 默认 **300000ms（300s）**（第十一轮已用依赖源码核实；此前误写 5000ms，实为相邻的 `auto.commit.interval.ms` 默认值）。② `PROCESSING_TTL_SECONDS` / `RETRY_BACKOFF_MS` / `DLQ_SEND_TIMEOUT_SECONDS` 提到 `config.rs` 公共常量，`Config::validate` 按 `attempts×(TTL+1s)+Σ指数退避+DLQ 发送超时 < poll` 校验，不合规启动失败。③ `handle()` 增加 `stop` 参数，等待循环 `select!` 响应停机；`mq::consume` 在 stop 置位时跳过 offset 提交，避免"停机 → Err → 提交"导致消息丢失。④ 日志改为"单线程顺序消费，等待期间阻塞所有分区（最长 TTL+1s）"。 |
| 依据 | 消费端在 handler 内同步处理/等待，两次 `recv()` 之间的间隔就是 handler 耗时；必须由配置显式放大并校验。 |
| 验证 | 新增 3 个 config 单测：默认配置通过、60s poll 被拒、30 次重试被拒；`cargo test` 通过。 |
| 残余差异 | 真实 librdkafka 的 `max.poll.interval.ms` 行为与配置值需联调确认；停机时依赖 mq 的"不提交 offset"保证不丢消息（已实现，但需真机 SIGTERM 演练）。 |

### 10-2 ES 锁续租单次失败即 TERM

| 项 | 内容 |
|---|---|
| 改动文件 | `tools/es-rebuild-snapshot-flow.sh` |
| 问题 | `renew_lock_once` 只要 `get_lock_meta` 失败一次（503/超时/连接重置/404）就 `kill -TERM $$`，无连续失败判据、不区分传输错误与 404 被接管；TERM 若落在"删完旧索引、未建新索引"之间，EXIT trap 只释放锁不重建索引，留下无索引状态。 |
| 改法 | ① `renew_lock_once` 改为返回码：0=成功；1=确认丢失（404 / instance 不匹配 / 条件更新 409）；2=传输或 ES 错误（超时/5xx/解析失败）。② 续租循环：返回 1 立即 TERM；返回 2 连续 `ceil(TTL/2/renew)` 次（默认 3 次≈90s）才 TERM；每次告警与 TERM 都打印 `LOCK_STAGE`。③ `LOCK_STAGE` 在"预检/删除旧索引/旧索引已删创建中/新索引已创建/回灌中/等待对数"逐点更新。 |
| 依据 | 单次 503 不应等同于锁丢失；连续失败超过 TTL/2 才说明锁可能过期被接管。 |
| 验证 | `bash -n`、脚本离线测试通过；真实 503/404/接管场景需 ES 演练。 |
| 残余差异 | TERM 落在"删除后、创建前"仍可能留无索引（概率已降至"锁真正丢失或 ES 长时间不可用"）；不自动重建，交由运维按脚本打印信息处理。 |

## 低危

| 编号 | 改动文件 | 改法与依据 | 验证 / 残余 |
|---|---|---|---|
| 10-3 done→processing 双检竞态 | `src/services/consumer.rs` | `SET NX` 抢占成功后**再查一次** done：若原处理者已在两次检查之间写完 done，则删除本次抢占的 processing 并 ack，避免重复处理一次 | 编译/测试通过；Redis 竞态需真实环境 |
| 10-4 `close()` 500ms 只是放弃等待 | `src/services/export.rs`、`src/services/large.rs` | 注释改为"abort 已发出，但 500ms 内可能仍停在同步 I/O，最长再延后一次写盘"，不再声称"确保停止" | 注释订正 |
| 10-5 `call_handler` 未包同步求值 | `src/mq.rs` | 先 `catch_unwind(|| handler(msg))` 包住同步调用阶段，再包 future polling；两阶段 panic 都转 Err | `handler_panic_becomes_err` 等单测通过 |
| 10-6 重试循环测试缺失 | `src/mq.rs` | 抽出 `run_with_retries(max_retry, backoff, msg, handler) -> (结果, Option<DLQ>)`，`handle_with_retry` 只负责发布；新增用例断言 panic 时调用次数=`max_retry+1`、恰好 1 条 DLQ、最终 Err；成功时无 DLQ | `retry_loop_counts_panic_and_returns_one_dlq` / `retry_loop_success_produces_no_dlq` 通过；改回裸 `handler(m).await` 会失败 |
| 10-7 静态断言可被注释满足 | `tools/test-es-rebuild-snapshot-flow.sh` | 剔除块内注释后再校验 `-G`/`-X POST`；精确 400 判据改为探针 URL 起 12 行、剔注释后的窗口内匹配 `REPAIR_PROBE_CODE != "400"`，并禁止该窗口出现 `4[0-9][0-9]` 正则 | 脚本测试 7 PASS |
| 10-8 锁属主 pid+host 可复用 | `tools/es-rebuild-snapshot-flow.sh` | 增加随机 `LOCK_INSTANCE`（时间-pid-random），写入锁文档与 mapping；续租/释放按 instance 比对 | `bash -n` / 离线测试通过 |
| 10-9 测试脚本在无 python3 环境误判 | `tools/test-es-rebuild-snapshot-flow.sh` | 运行前 `command -v python3` 检查，缺失直接 `exit 2` 并输出明确失败，避免负例因文案相同而误 PASS | 本机（有 python3）7 PASS；Git Bash 无 python3 时会明确失败 |

## 第十轮验证结果

| 命令 | 结果 |
|---|---|
| `cargo test --all-targets` | **61 passed / 0 failed**（39 单元 + 16 parity + 6 router） |
| `cargo clippy --all-targets -- -D warnings` | **通过**（exit 0，0 warning） |
| `bash -n tools/es-rebuild-snapshot-flow.sh` / `test-...sh` | 通过 |
| `bash tools/test-es-rebuild-snapshot-flow.sh` | **7 PASS**（6 时间窗 + 1 静态断言） |
| 构建产物清理 | target 共 5,817 个文件 / 4,082,871,103 B。逐文件 `SetLength(0)` 后删除：截断即释放 **3,766,583,296 B**；最终合计释放 **3,759,120,384 B（约 3.50 GB）**，`Test-Path=False` |
| 未验证 | 真实 librdkafka `max.poll.interval.ms`/停机不提交 offset、ES 锁 503/404/接管与 TERM 阶段、Redis done/processing 竞态、导出同步 I/O 取消延迟 |

---

# 第十一轮：max.poll.interval.ms 默认值核实与最终收口（2026-11-08）

## 11-1 事实核实：librdkafka 默认值是 300000ms（300s）

| 项 | 内容 |
|---|---|
| 核实文件 1 | `D:\rust\cargo\registry\src\index.crates.io-1949cf8c6b5b557f\rdkafka-sys-4.10.0+2.12.1\librdkafka\CONFIGURATION.md` |
| 原文行（第 136 行） | `max.poll.interval.ms | C | 1 .. 86400000 | 300000 | high | Maximum allowed time between calls to consume messages ...` |
| 核实文件 2 | 同目录 `librdkafka\src\rdkafka_conf.c` |
| 原文行（第 1364-1379 行） | `{_RK_GLOBAL \| _RK_CONSUMER \| _RK_HIGH, "max.poll.interval.ms", _RK_C_INT, _RK(max_poll_interval_ms), ... 1, 86400 * 1000, 300000},`（第三个数值即默认值，单位 ms） |
| 结论 | **默认 300000ms（300s）**。第十轮"默认仅 5000ms"的说法错误。5000ms 实为紧邻的 `auto.commit.interval.ms` 默认值（CONFIGURATION.md 第 138 行：`auto.commit.interval.ms ... 5000`），属邻行混淆。 |
| 对既有结论的影响 | "默认 300s，因此原设计在最坏约 45~75s 时不会触发 rebalance"的推算**成立**；但该安全性只是"默认值恰好够用"，代码未约束，所以第十轮新增的显式配置 + 启动预算校验仍然必要，不是"更必要"，而是"把隐式安全变为显式契约"。第十轮"更必要"的措辞已按此订正。 |
| 代码现状（安全性核对） | ① `KafkaBus::new` 的 `max.poll.interval.ms` **走配置**（`kafka.max-poll-interval-ms`，默认 600000、YAML 600000、`APP_KAFKA_MAX_POLL_INTERVAL_MS` 可覆盖），不是调用点硬编码。② `Config::validate` 的不等式使用与运行期相同的来源：`pulsar.max_retry_times`（mq 的 `max_retry`）、`RETRY_BACKOFF_MS`（mq 退避基数）、`DLQ_SEND_TIMEOUT_SECONDS`（publish 发送超时）、`PROCESSING_TTL_SECONDS`（consumer 等待 TTL）。上述四个可调大来源都被覆盖。③ 未纳入不等式的是单次 handler 的业务处理耗时（DB/ES），它不是本轮新增可调项，且受 ES/DB 客户端超时约束；作为残余风险记录。 |

## 最终状态

| 项 | 内容 |
|---|---|
| 累计轮次 | **10 轮修复**：第一轮上线前 B1–B10/S 系列 + 第二至第十轮独立审阅修复；本轮（第十一轮）仅为事实核实与注释/文档订正，无逻辑改动。 |
| 当前门禁结果 | `cargo test --all-targets`：**61 passed / 0 failed**（39 单元 + 16 parity + 6 router）；`cargo clippy --all-targets -- -D warnings`：**0 warning**；`bash -n` 两个脚本通过；`bash tools/test-es-rebuild-snapshot-flow.sh`：**7 PASS**。本轮订正未改变可执行代码，故沿用该结果。 |
| 未实跑验证项（不得视为已通过） | 1. 真实 ES 双会话抢锁、过期接管与续租；2. librdkafka 停机时不提交 offset；3. Redis done/processing 竞态；4. 导出同步 I/O 的取消延迟；5. Linux SIGTERM 停机演练。 |
| 声明 | **以上结论只来自静态推演与单测，未经真实环境验证。** |





