# car-monit-api-rust 全量双端接口校验报告

日期：2026-11-02 ｜ 校验人：hellok ｜ 方式：真实启动 Java 端与 Rust 端，逐接口逐字段对比

## 1. 环境

| 项 | 值 |
|---|---|
| Java | `pro-business-api/target/pro-business-api-1.0.jar`，`-Dserver.port=9902`，JDK 1.8.0_202 |
| Rust | `car-monit-api-rust/target/debug/car-monit-api-rust.exe`，`APP_SERVER_PORT=9911` |
| 数据库 | yml 中的 openGauss/GaussDB：`192.168.56.10:5432/RuoYi`，业务 schema `jl_data01` |
| Redis | Java 用 DB0；Rust 用 `APP_REDIS_DATABASE=15`（避免两端序列化格式互相污染） |
| Kafka | 未启动 → Rust 消息总线为 Noop（与 Java 侧 `localhost:9092` 不可达同状态） |
| ES | 本机 9200 运行中，但无业务索引（此前按 Java mapping 建过并验证空索引路径后删除） |
| 调度/消费 | Rust 侧 `APP_ENABLE_SCHEDULER=false`、`APP_CONSUMER_ENABLED=false`，避免双端定时任务互相干扰 |

## 2. 校验框架

`tools/verify_full.py`，分 7 个阶段，逐项写入 `.run/verify/<stage>.json`，再由 `report` 阶段汇总到本文件：

| 阶段 | 内容 |
|---|---|
| inventory | Rust 路由清单 ↔ Java 控制器注解清点；重复条目；逐条探测 Rust 是否真的注册 |
| base | 19 张基础表 `list / listAll / listToExport / {id}`，含 `pageNum=0`、`pageSize=0/-1`、不存在 ID、非法 ID、深层路径 |
| filters | 以 Mapper XML 的 `<if>` 为字段来源，逐字段过滤矩阵；每个字段再取「真实值 / 不存在值 / 通配符 `%` / 大小写 / 日期多格式」等变体 |
| query | large / unified / progressive / stats / export / 必填参数与非法数据源分支 |
| sysutil | `/base/sysutil/*` 与 `/base/sysutilTest/*`（写副作用端点默认跳过，`--allow-side-effects` 才执行） |
| contract | Content-Type、JSON 键形状（含 null 键是否保留）、数字/日期格式、Spring 错误体 `{timestamp,status,error,message,path}` 的键序与字段值、405/400/深路径 |

判定口径：HTTP 状态码必须一致；响应体做深度比较（数值容差 1e-6；Java 每行随机生成的 `id`/`taskId` 只比存在性与类型；错误体 `timestamp` 不比值）。

## 3. 运行前置

```bash
# Java
cd pro-business-api && java -Xmx1536m -Dserver.port=9902 -jar target/pro-business-api-1.0.jar
# Rust
cd car-monit-api-rust && APP_SERVER_PORT=9911 APP_REDIS_DATABASE=15 \
  APP_ENABLE_SCHEDULER=false APP_CONSUMER_ENABLED=false cargo run
# 校验（脚本会自动备份并临时清空 Redis DB0 的 car_list_jc，跑完恢复）
../car-monit-api-python/.venv/Scripts/python.exe tools/verify_full.py --stage all
```

`car_list_jc` 必须临时清空：该 key 目前被非 Java 服务写成 JSON 数组，Java 的 FastJSON 反序列化后
强转 `CarVO` 会抛 `ClassCastException`，导致 `/base/sysutilTest/syncCurrentTrack`、
`/base/sysutil/carTrackQueryByTime` 等端点 500（属环境数据污染，不是 Java 代码差异）。

## 4. 已完成的历轮结果（本框架之前的实测基线）

| 轮次 | 脚本 | 覆盖 | 结果 |
|---|---|---|---|
| 第 1 轮 | `tools/compare_api.py` | 74 个场景（19 表 list/listAll/详情、listToExport、large/unified/progressive、sysutil/sysutilTest、必填/非法/404） | `ok=74 bad=0` |
| 第 2 轮 | `tools/compare_round2.py` | 93 个场景（分页含 `pageSize=0/-5`、过滤、非法数字主键、POST、405、错误体） | `ok=93 bad=0` |
| 第 3 轮 | `tools/compare_round3.py` | 186 组逐字段过滤矩阵（18 张表 × 每表 ≤12 个真实值，含 ISO 时间值） | `checked=186 bad=0` |
| 单元/集成 | `cargo test` | 19 项（Jackson 日期格式、`TableDataInfo`、分页默认、cron、路由装配、Spring 404、日期白名单、`JavaQuery` 丢弃行为） | `16→19 passed, 0 failed` |

对应修复记录见 `README-MIGRATION.md` 第 10.2、11.2 节。

## 5. 本轮结论与修复清单（2026-11-02 全量校验）

本轮把判定口径从「JSON 语义一致」提高到「状态码 + 响应体深度比较 + 键顺序 + 原始字节」，
并新增逐字段过滤矩阵、重复参数、超长请求行等边界，暴露出 8 类静态复查发现不了的差异，均已修复：

| # | 差异 | Java 行为 | 修复 |
|---|---|---|---|
| 1 | 数据权限过滤没落地 | Redis `sys_config:data_query` 不是 `queryall` 且 `platenumber` 为空时，追加 `orgcode='030000011'`（`/base/snapshotflow/list?applyTime1..` → Java 0 行，Rust 300 行） | `tools/gen_filters.py` 生成 `<if test="flag == 'JiAnDong'">` 的字面量条件；处理器侧读同一个 Redis key |
| 2 | `@PathVariable Long` 的类型契约 | `provcapture/stationcapture/feeStationEnter` 详情传非数字（含 `listAll`、`abc`）→ Spring 400 | 这三张表改用 `entity_repo_numeric!`（与 `gantryIp/tollStationIp/fwqclls` 一致） |
| 3 | 查询参数绑定失败的错误体 | Spring 400 `{timestamp,status,error,message,path}`；Axum 默认是纯文本 `Failed to deserialize query string: …` | 新增 `SpringQueryRejection`，`JavaQuery`/`TrailBo` 绑定失败统一输出 Java 形状 |
| 4 | `zdata_trail_tracks.uuid` 不唯一 | `selectOne()` 命中多行抛 `TooManyResultsException` → 500；0 行 → `AjaxResult.success(null)` | `base::trail_tracks_detail` 按行数三分支（实测同一 uuid 17 行） |
| 5 | `AjaxResult` 键顺序 | Java 是 `HashMap`，稳定输出 `msg → code → data` | `response::envelope()` 改为同序，并加测试锁定 |
| 6 | PageHelper `reasonable` 越界钳位 | `pageNum` 超出总页数时返回**最后一页**（`gantry` total=1526、pageSize=3、pageNum=9999 → 末尾 2 行） | 新增 `PageParams::offset_for(total)`，各 list/listToExport 先 `count` 再取数 |
| 7 | 重复查询参数的绑定 | Spring 把同名参数的值用逗号拼接后再绑定（`platenumber=%&platenumber=%` → `%,%` → 0 行）；`serde_urlencoded` 会当重复字段直接 400 | `JavaQuery` 合并重复键为 `v1,v2` |
| 8 | 容器级请求行长度上限 | Tomcat `maxHttpHeaderSize=8192`，实测 `path?query` 上限 8075 字节（8075→200，8076→400 HTML） | `middleware.rs` 增加 `MAX_URI_BYTES=8075` 闸门；Rust 返回应用的 Spring JSON 错误体，容器 HTML 不复刻 |

`query` 阶段额外暴露并修复了 3 个大数据链路问题：

1. **降级查询返回的日期字段全为 null**。`/api/v1/large/snapshot`、`/api/v1/unified/snapshot/list`
   的 DB 降级路径原先是 `SELECT *` → `row_to_json` → `from_value::<实体>`，而 `row_to_json`
   对 `timestamp without time zone` 按 `DateTime<Utc>` 取列会解码失败并静默变 null，
   导致 `snapshottime/receivedtime/loadtime` 与 Java 不一致。
   现改为 `query_as::<_, 实体>`（等价于 Java 用 Mapper 取实体），编码与 `/base/.../list` 完全同源。
2. **`type` 参数不该校验**。Java 的 `resolve(type)`/`resolveDs(type)` 对未知值一律落 `default → SNAPSHOT`；
   Rust 之前返回「type 只能是 snapshot / fee / trail」。`parse_type_lenient` 改为默认 Snapshot。
3. **`carNo` 必填语义**。Java 的 `@RequestParam String carNo` 只在**缺失**时 400，
   传空串正常执行（只是不放模糊条件）；Rust 之前空串也 400。已按存在性判断。

另外：本轮期间 Java 的定时同步任务把 ES 索引 `snapshot_flow`（300 docs）建好了，
所以 large/unified 的路由与 10-31 那轮不同（`fee_records`、`trail_fitting` 仍不存在 →
两端都走降级 → 两端一致）。这也验证了 ES 存在/缺失两种拓扑下的行为都保持一致。

## 6. 跳过项与残留风险

| 项 | 原因 | 风险 |
|---|---|---|
| `/base/sysutilTest/syncHistroyTrack`、`syncSuspiciousCar1..10` | 会遍历上百辆车逐条查询并调用外部系统，单次分钟级且写共享 Redis | 需独立环境验证；已在 10-31 轮验证过 `syncCurrentTrack/syncBaseInfo/saveRedis` 等 |
| `POST /api/v1/large/sync/{full,incremental}` | 会向 ES 回灌数据，本机 D 盘已 99% 满、ES 触发过 flood-stage 只读 | 响应结构已逐字段核对；真实同步链路待独立环境 |
| Kafka 消费链路 | 本机 Kafka 未启动（两端同为不可用状态） | 消息语义只有单测覆盖 |
| 容器级 400 响应体 | Tomcat 返回 HTML 错误页 | 状态码一致；body 形状属容器差异，不复刻 |

## 7. 复现

```bash
# 两端启动后（Java 9902 / Rust 9911），脚本自动备份并临时清空 car_list_jc
../car-monit-api-python/.venv/Scripts/python.exe tools/verify_full.py --stage all
# 单阶段：--stage inventory|base|filters|query|sysutil|contract|report
# 原始结果：.run/verify/<stage>.json（含每条用例的双端状态码与差异明细）
```


<!-- RESULTS -->

## 阶段结果（自动生成于 2026-11-02 14:55）

**合计 548 项：一致 544，不一致 0，容器级差异 1，跳过 3**

### base（140 项：一致 140，不一致 0，跳过 0）

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| base | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=3` | 200 | 200 | OK | fwqjcxx list |
| base | GET | `/base/fwqjcxx/list?pageNum=2&pageSize=3` | 200 | 200 | OK | fwqjcxx list |
| base | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=0` | 200 | 200 | OK | fwqjcxx list |
| base | GET | `/base/fwqjcxx/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | fwqjcxx list |
| base | GET | `/base/fwqjcxx/listAll` | 200 | 200 | OK | fwqjcxx listAll |
| base | GET | `/base/fwqjcxx/1` | 200 | 200 | OK | fwqjcxx detail(ajax) |
| base | GET | `/base/fwqjcxx/__no_such_id__` | 500 | 500 | OK | fwqjcxx detail-miss |
| base | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=3` | 200 | 200 | OK | sfsjcxx list |
| base | GET | `/base/sfsjcxx/list?pageNum=2&pageSize=3` | 200 | 200 | OK | sfsjcxx list |
| base | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=0` | 200 | 200 | OK | sfsjcxx list |
| base | GET | `/base/sfsjcxx/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | sfsjcxx list |
| base | GET | `/base/sfsjcxx/listAll` | 200 | 200 | OK | sfsjcxx listAll |
| base | GET | `/base/sfsjcxx/d2c6df4afa7ff18d48786d728d3919d2` | 200 | 200 | OK | sfsjcxx detail(flat) |
| base | GET | `/base/sfsjcxx/__no_such_id__` | 200 | 200 | OK | sfsjcxx detail-miss |
| base | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=3` | 200 | 200 | OK | sfzjcxx list |
| base | GET | `/base/sfzjcxx/list?pageNum=2&pageSize=3` | 200 | 200 | OK | sfzjcxx list |
| base | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=0` | 200 | 200 | OK | sfzjcxx list |
| base | GET | `/base/sfzjcxx/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | sfzjcxx list |
| base | GET | `/base/sfzjcxx/listAll` | 200 | 200 | OK | sfzjcxx listAll |
| base | GET | `/base/sfzjcxx/363bc7b76e508c55dcb259cf6a3f007e` | 200 | 200 | OK | sfzjcxx detail(flat) |
| base | GET | `/base/sfzjcxx/__no_such_id__` | 200 | 200 | OK | sfzjcxx detail-miss |
| base | GET | `/manager/fwqclls/list?pageNum=1&pageSize=3` | 200 | 200 | OK | fwqclls list |
| base | GET | `/manager/fwqclls/list?pageNum=2&pageSize=3` | 200 | 200 | OK | fwqclls list |
| base | GET | `/manager/fwqclls/list?pageNum=1&pageSize=0` | 200 | 200 | OK | fwqclls list |
| base | GET | `/manager/fwqclls/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | fwqclls list |
| base | GET | `/manager/fwqclls/listAll` | 400 | 400 | OK | fwqclls listAll |
| base | GET | `/manager/fwqclls/1` | 200 | 200 | OK | fwqclls detail(ajax) |
| base | GET | `/manager/fwqclls/__no_such_id__` | 400 | 400 | OK | fwqclls detail-miss |
| base | GET | `/manager/fwqclls/abc` | 400 | 400 | OK | fwqclls detail-abc |
| base | GET | `/base/feeGantry/list?pageNum=1&pageSize=3` | 200 | 200 | OK | feeGantry list |
| base | GET | `/base/feeGantry/list?pageNum=2&pageSize=3` | 200 | 200 | OK | feeGantry list |
| base | GET | `/base/feeGantry/list?pageNum=1&pageSize=0` | 200 | 200 | OK | feeGantry list |
| base | GET | `/base/feeGantry/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | feeGantry list |
| base | GET | `/base/feeGantry/listAll` | 200 | 200 | OK | feeGantry listAll |
| base | GET | `/base/feeGantry/listToExport?pageNum=1&pageSize=3` | 200 | 200 | OK | feeGantry listToExport |
| base | GET | `/base/feeGantry/59` | 200 | 200 | OK | feeGantry detail(flat) |
| base | GET | `/base/feeGantry/__no_such_id__` | 200 | 200 | OK | feeGantry detail-miss |
| base | GET | `/base/feeGantry/abc` | 200 | 200 | OK | feeGantry detail-abc |
| base | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=3` | 200 | 200 | OK | feeStationEnter list |
| base | GET | `/base/feeStationEnter/list?pageNum=2&pageSize=3` | 200 | 200 | OK | feeStationEnter list |
| base | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=0` | 200 | 200 | OK | feeStationEnter list |
| base | GET | `/base/feeStationEnter/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | feeStationEnter list |
| base | GET | `/base/feeStationEnter/listAll` | 400 | 400 | OK | feeStationEnter listAll |
| base | GET | `/base/feeStationEnter/listToExport?pageNum=1&pageSize=3` | 400 | 400 | OK | feeStationEnter listToExport |
| base | GET | `/base/feeStationEnter/2308` | 200 | 200 | OK | feeStationEnter detail(flat) |
| base | GET | `/base/feeStationEnter/__no_such_id__` | 400 | 400 | OK | feeStationEnter detail-miss |
| base | GET | `/base/feeStationEnter/abc` | 400 | 400 | OK | feeStationEnter detail-abc |
| base | GET | `/base/feestationexit/list?pageNum=1&pageSize=3` | 200 | 200 | OK | feestationexit list |
| base | GET | `/base/feestationexit/list?pageNum=2&pageSize=3` | 200 | 200 | OK | feestationexit list |
| base | GET | `/base/feestationexit/list?pageNum=1&pageSize=0` | 200 | 200 | OK | feestationexit list |
| base | GET | `/base/feestationexit/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | feestationexit list |
| base | GET | `/base/feestationexit/listAll` | 200 | 200 | OK | feestationexit listAll |
| base | GET | `/base/feestationexit/listToExport?pageNum=1&pageSize=3` | 200 | 200 | OK | feestationexit listToExport |
| base | GET | `/base/feestationexit/11150377` | 200 | 200 | OK | feestationexit detail(flat) |
| base | GET | `/base/feestationexit/__no_such_id__` | 200 | 200 | OK | feestationexit detail-miss |
| base | GET | `/base/feestationexit/abc` | 200 | 200 | OK | feestationexit detail-abc |
| base | GET | `/base/snapshotflow/list?pageNum=1&pageSize=3&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow list |
| base | GET | `/base/snapshotflow/list?pageNum=2&pageSize=3&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow list |
| base | GET | `/base/snapshotflow/list?pageNum=1&pageSize=0&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow list |
| base | GET | `/base/snapshotflow/list?pageNum=0&pageSize=-1&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:0` | 200 | 200 | OK | snapshotflow list |
| base | GET | `/base/snapshotflow/listAll` | 200 | 200 | OK | snapshotflow listAll |
| base | GET | `/base/snapshotflow/listToExport?pageNum=1&pageSize=3&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%20` | 200 | 200 | OK | snapshotflow listToExport |
| base | GET | `/base/provcapture/list?pageNum=1&pageSize=3` | 200 | 200 | OK | provcapture list |
| base | GET | `/base/provcapture/list?pageNum=2&pageSize=3` | 200 | 200 | OK | provcapture list |
| base | GET | `/base/provcapture/list?pageNum=1&pageSize=0` | 200 | 200 | OK | provcapture list |
| base | GET | `/base/provcapture/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | provcapture list |
| base | GET | `/base/provcapture/listAll` | 400 | 400 | OK | provcapture listAll |
| base | GET | `/base/provcapture/312748` | 200 | 200 | OK | provcapture detail(ajax) |
| base | GET | `/base/provcapture/__no_such_id__` | 400 | 400 | OK | provcapture detail-miss |
| base | GET | `/base/provcapture/abc` | 400 | 400 | OK | provcapture detail-abc |
| base | GET | `/base/stationcapture/list?pageNum=1&pageSize=3` | 200 | 200 | OK | stationcapture list |
| base | GET | `/base/stationcapture/list?pageNum=2&pageSize=3` | 200 | 200 | OK | stationcapture list |
| base | GET | `/base/stationcapture/list?pageNum=1&pageSize=0` | 200 | 200 | OK | stationcapture list |
| base | GET | `/base/stationcapture/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | stationcapture list |
| base | GET | `/base/stationcapture/listAll` | 400 | 400 | OK | stationcapture listAll |
| base | GET | `/base/stationcapture/20113483` | 200 | 200 | OK | stationcapture detail(ajax) |
| base | GET | `/base/stationcapture/__no_such_id__` | 400 | 400 | OK | stationcapture detail-miss |
| base | GET | `/base/stationcapture/abc` | 400 | 400 | OK | stationcapture detail-abc |
| base | GET | `/base/gantry/list?pageNum=1&pageSize=3` | 200 | 200 | OK | gantry list |
| base | GET | `/base/gantry/list?pageNum=2&pageSize=3` | 200 | 200 | OK | gantry list |
| base | GET | `/base/gantry/list?pageNum=1&pageSize=0` | 200 | 200 | OK | gantry list |
| base | GET | `/base/gantry/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | gantry list |
| base | GET | `/base/gantry/listAll` | 200 | 200 | OK | gantry listAll |
| base | GET | `/base/gantry/18` | 200 | 200 | OK | gantry detail(ajax) |
| base | GET | `/base/gantry/__no_such_id__` | 200 | 200 | OK | gantry detail-miss |
| base | GET | `/base/gantry/abc` | 200 | 200 | OK | gantry detail-abc |
| base | GET | `/base/gantryIp/list?pageNum=1&pageSize=3` | 200 | 200 | OK | gantryIp list |
| base | GET | `/base/gantryIp/list?pageNum=2&pageSize=3` | 200 | 200 | OK | gantryIp list |
| base | GET | `/base/gantryIp/list?pageNum=1&pageSize=0` | 200 | 200 | OK | gantryIp list |
| base | GET | `/base/gantryIp/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | gantryIp list |
| base | GET | `/base/gantryIp/listAll` | 400 | 400 | OK | gantryIp listAll |
| base | GET | `/base/gantryIp/1` | 200 | 200 | OK | gantryIp detail(ajax) |
| base | GET | `/base/gantryIp/__no_such_id__` | 400 | 400 | OK | gantryIp detail-miss |
| base | GET | `/base/gantryIp/abc` | 400 | 400 | OK | gantryIp detail-abc |
| base | GET | `/base/vehicleweight/list?pageNum=1&pageSize=3` | 200 | 200 | OK | vehicleweight list |
| base | GET | `/base/vehicleweight/list?pageNum=2&pageSize=3` | 200 | 200 | OK | vehicleweight list |
| base | GET | `/base/vehicleweight/list?pageNum=1&pageSize=0` | 200 | 200 | OK | vehicleweight list |
| base | GET | `/base/vehicleweight/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | vehicleweight list |
| base | GET | `/base/vehicleweight/listAll` | 500 | 500 | OK | vehicleweight listAll |
| base | GET | `/base/vehicleweight/18f8e2af-6ebe-4b33-8f37-a688f441de37` | 500 | 500 | OK | vehicleweight detail(ajax) |
| base | GET | `/base/vehicleweight/__no_such_id__` | 500 | 500 | OK | vehicleweight detail-miss |
| base | GET | `/base/section/list?pageNum=1&pageSize=3` | 200 | 200 | OK | section list |
| base | GET | `/base/section/list?pageNum=2&pageSize=3` | 200 | 200 | OK | section list |
| base | GET | `/base/section/list?pageNum=1&pageSize=0` | 200 | 200 | OK | section list |
| base | GET | `/base/section/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | section list |
| base | GET | `/base/section/listAll` | 200 | 200 | OK | section listAll |
| base | GET | `/base/section/18` | 200 | 200 | OK | section detail(ajax) |
| base | GET | `/base/section/__no_such_id__` | 200 | 200 | OK | section detail-miss |
| base | GET | `/base/section/abc` | 200 | 200 | OK | section detail-abc |
| base | GET | `/base/toll/list?pageNum=1&pageSize=3` | 200 | 200 | OK | toll list |
| base | GET | `/base/toll/list?pageNum=2&pageSize=3` | 200 | 200 | OK | toll list |
| base | GET | `/base/toll/list?pageNum=1&pageSize=0` | 200 | 200 | OK | toll list |
| base | GET | `/base/toll/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | toll list |
| base | GET | `/base/toll/listAll` | 200 | 200 | OK | toll listAll |
| base | GET | `/base/toll/1` | 200 | 200 | OK | toll detail(ajax) |
| base | GET | `/base/toll/__no_such_id__` | 200 | 200 | OK | toll detail-miss |
| base | GET | `/base/toll/abc` | 200 | 200 | OK | toll detail-abc |
| base | GET | `/base/tollStationIp/list?pageNum=1&pageSize=3` | 200 | 200 | OK | tollStationIp list |
| base | GET | `/base/tollStationIp/list?pageNum=2&pageSize=3` | 200 | 200 | OK | tollStationIp list |
| base | GET | `/base/tollStationIp/list?pageNum=1&pageSize=0` | 200 | 200 | OK | tollStationIp list |
| base | GET | `/base/tollStationIp/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | tollStationIp list |
| base | GET | `/base/tollStationIp/listAll` | 400 | 400 | OK | tollStationIp listAll |
| base | GET | `/base/tollStationIp/40017` | 200 | 200 | OK | tollStationIp detail(ajax) |
| base | GET | `/base/tollStationIp/__no_such_id__` | 400 | 400 | OK | tollStationIp detail-miss |
| base | GET | `/base/tollStationIp/abc` | 400 | 400 | OK | tollStationIp detail-abc |
| base | GET | `/base/org/list?pageNum=1&pageSize=3` | 200 | 200 | OK | org list |
| base | GET | `/base/org/list?pageNum=2&pageSize=3` | 200 | 200 | OK | org list |
| base | GET | `/base/org/list?pageNum=1&pageSize=0` | 200 | 200 | OK | org list |
| base | GET | `/base/org/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | org list |
| base | GET | `/base/org/listAll` | 200 | 200 | OK | org listAll |
| base | GET | `/base/org/24945` | 200 | 200 | OK | org detail(ajax) |
| base | GET | `/base/org/__no_such_id__` | 200 | 200 | OK | org detail-miss |
| base | GET | `/base/org/abc` | 200 | 200 | OK | org detail-abc |
| base | GET | `/base/trailtracks/list?pageNum=1&pageSize=3` | 200 | 200 | OK | trailtracks list |
| base | GET | `/base/trailtracks/list?pageNum=2&pageSize=3` | 200 | 200 | OK | trailtracks list |
| base | GET | `/base/trailtracks/list?pageNum=1&pageSize=0` | 200 | 200 | OK | trailtracks list |
| base | GET | `/base/trailtracks/list?pageNum=0&pageSize=-1` | 200 | 200 | OK | trailtracks list |
| base | GET | `/base/trailtracks/listAll` | 200 | 200 | OK | trailtracks listAll |
| base | GET | `/base/trailtracks/e0e22490-fb40-4795-947b-68565d864aa7` | 500 | 500 | OK | trailtracks detail(flat) |
| base | GET | `/base/trailtracks/__no_such_id__` | 200 | 200 | OK | trailtracks detail-miss |

### contract（19 项：一致 19，不一致 0，跳过 0）

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| contract | GET | `/base/gantry/list?pageNum=1&pageSize=2` | 200 | 200 | OK | contract |
| contract | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | contract |
| contract | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2` | 200 | 200 | OK | contract |
| contract | GET | `/base/trailtracks/list?pageNum=1&pageSize=2` | 200 | 200 | OK | contract |
| contract | GET | `/not-exist` | 404 | 404 | OK | contract |
| contract | GET | `/api/v1/large/snapshot` | 400 | 400 | OK | contract |
| contract | POST | `/base/gantry/list` | 405 | 405 | OK | 405 |
| contract | GET | `/base/gantry/list?pageNum=abc&pageSize=xyz` | 200 | 200 | OK | lenient-page |
| contract | GET | `/base/gantry/list?pageNum=%E9%9D%9E%E6%B3%95` | 200 | 200 | OK | nonnum-page |
| contract | GET | `/base/gantry/1/2` | 404 | 404 | OK | deep-path |
| contract | GET | `/base/gantry/list?pageNum=1&pageSize=1&gantryName=%25` | 200 | 200 | OK | like-escape |
| contract | GET | `/base/gantry/list?pageNum=1&pageSize=1&gantryName=G00` | 200 | 200 | OK | ascii-like |
| contract | GET | `/base/snapshotflow/list?applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00&platenumber=%25&plat` | 200 | 200 | OK | duplicate-param |
| contract | GET | `/base/snapshotflow/list?applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00&platenumber=ZZZQ&pla` | 200 | 200 | OK | duplicate-param |
| contract | GET | `/base/gantry/list?pageNum=1&pageNum=2&pageSize=1` | 200 | 200 | OK | duplicate-param |
| contract | GET | `/base/gantry/list?direction=1&direction=2&pageSize=1` | 200 | 200 | OK | duplicate-param |
| contract | GET | `/nope` | 404 | 404 | OK | error-shape |
| contract | GET | `/base/nope/list` | 404 | 404 | OK | error-shape |
| contract | GET | `/api/v1/large/nope?startTime=1&endTime=2` | 404 | 404 | OK | error-shape |

### filters（343 项：一致 342，不一致 0，跳过 0）

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&bigId=59` | 200 | 200 | OK | feeGantry.bigId/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.bigId/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&id=5f21d0510a5c4a5b992f8b8c9a281486` | 200 | 200 | OK | feeGantry.id/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&id=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.id/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&actualfeeclass=1` | 200 | 200 | OK | feeGantry.actualfeeclass/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&actualfeeclass=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.actualfeeclass/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&axlecount=6` | 200 | 200 | OK | feeGantry.axlecount/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&axlecount=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feeGantry.axlecount/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&createtime=2024-11-11T10%3A09%3A21.000%2B00%3A00` | 200 | 200 | OK | feeGantry.createtime/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&createtime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.createtime/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&createtime=2024-11-11%2010%3A09%3A21` | 200 | 200 | OK | feeGantry.createtime/space |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&createtime=2024-11-11` | 200 | 200 | OK | feeGantry.createtime/date-only |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&createtime=2024/11/11%2010%3A09%3A21` | 200 | 200 | OK | feeGantry.createtime/slash |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&discountfee=1388` | 200 | 200 | OK | feeGantry.discountfee/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&discountfee=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feeGantry.discountfee/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&electricalpercentage=0` | 200 | 200 | OK | feeGantry.electricalpercentage/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&electricalpercentage=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%` | 400 | 400 | OK | feeGantry.electricalpercentage/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&enaxlecount=6` | 200 | 200 | OK | feeGantry.enaxlecount/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&enaxlecount=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feeGantry.enaxlecount/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entime=2024-10-26%2008%3A53%3A57` | 200 | 200 | OK | feeGantry.entime/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.entime/absent |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entime=2024-10-26%2008%3A53%3A57` | 200 | 200 | OK | feeGantry.entime/space |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entime=2024-10-26` | 200 | 200 | OK | feeGantry.entime/date-only |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entime=2024/10/26%2008%3A53%3A57` | 200 | 200 | OK | feeGantry.entime/slash |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entolllanehex=33010B3305` | 200 | 200 | OK | feeGantry.entolllanehex/real |
| filters | GET | `/base/feeGantry/list?pageNum=1&pageSize=2&entolllanehex=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeGantry.entolllanehex/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&bigId=2308` | 200 | 200 | OK | feeStationEnter.bigId/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feeStationEnter.bigId/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&cardid=15012312232021029616` | 200 | 200 | OK | feeStationEnter.cardid/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&cardid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeStationEnter.cardid/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&electricalpercentage=100` | 200 | 200 | OK | feeStationEnter.electricalpercentage/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&electricalpercentage=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%` | 400 | 400 | OK | feeStationEnter.electricalpercentage/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&enaxlecount=2` | 200 | 200 | OK | feeStationEnter.enaxlecount/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&enaxlecount=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-` | 400 | 400 | OK | feeStationEnter.enaxlecount/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entime=2024-11-24` | 200 | 200 | OK | feeStationEnter.entime/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feeStationEnter.entime/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entolllanehex=360101FD04` | 200 | 200 | OK | feeStationEnter.entolllanehex/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entolllanehex=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%B` | 200 | 200 | OK | feeStationEnter.entolllanehex/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entolllaneid=G00703600100601010030` | 200 | 200 | OK | feeStationEnter.entolllaneid/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entolllaneid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC` | 200 | 200 | OK | feeStationEnter.entolllaneid/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entollstationid=G0070360010060` | 200 | 200 | OK | feeStationEnter.entollstationid/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&entollstationid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80` | 200 | 200 | OK | feeStationEnter.entollstationid/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&enweight=1500.0` | 200 | 200 | OK | feeStationEnter.enweight/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&enweight=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feeStationEnter.enweight/absent |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&identifyvehicleid=%E8%B5%A3GF66749_4` | 200 | 200 | OK | feeStationEnter.identifyvehicleid/real |
| filters | GET | `/base/feeStationEnter/list?pageNum=1&pageSize=2&identifyvehicleid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%` | 200 | 200 | OK | feeStationEnter.identifyvehicleid/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&bigId=11150377` | 200 | 200 | OK | feestationexit.bigId/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feestationexit.bigId/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&actualfeeclass=0` | 200 | 200 | OK | feestationexit.actualfeeclass/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&actualfeeclass=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%B` | 200 | 200 | OK | feestationexit.actualfeeclass/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&axlecount=2` | 200 | 200 | OK | feestationexit.axlecount/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&axlecount=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | feestationexit.axlecount/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&discountfee=0` | 200 | 200 | OK | feestationexit.discountfee/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&discountfee=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7` | 400 | 400 | OK | feestationexit.discountfee/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&electricalpercentage=0` | 200 | 200 | OK | feestationexit.electricalpercentage/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&electricalpercentage=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E` | 400 | 400 | OK | feestationexit.electricalpercentage/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entime=1970-01-01%2000%3A00%3A00` | 200 | 200 | OK | feestationexit.entime/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | feestationexit.entime/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entime=1970-01-01%2000%3A00%3A00` | 200 | 200 | OK | feestationexit.entime/space |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entime=1970-01-01` | 200 | 200 | OK | feestationexit.entime/date-only |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entime=1970/01/01%2000%3A00%3A00` | 200 | 200 | OK | feestationexit.entime/slash |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entolllanehex=0` | 200 | 200 | OK | feestationexit.entolllanehex/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entolllanehex=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC` | 200 | 200 | OK | feestationexit.entolllanehex/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entolllaneid=-1` | 200 | 200 | OK | feestationexit.entolllaneid/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entolllaneid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-` | 200 | 200 | OK | feestationexit.entolllaneid/absent |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entollstationid=-1` | 200 | 200 | OK | feestationexit.entollstationid/real |
| filters | GET | `/base/feestationexit/list?pageNum=1&pageSize=2&entollstationid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%` | 200 | 200 | OK | feestationexit.entollstationid/absent |
| filters | GET | `/manager/fwqclls/list?pageNum=1&pageSize=2&bigId=1` | 200 | 200 | OK | fwqclls.bigId/real |
| filters | GET | `/manager/fwqclls/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | fwqclls.bigId/absent |
| filters | GET | `/manager/fwqclls/list?pageNum=1&pageSize=2&datauuid=uuid-fwq-20251023001` | 200 | 200 | OK | fwqclls.datauuid/real |
| filters | GET | `/manager/fwqclls/list?pageNum=1&pageSize=2&datauuid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | fwqclls.datauuid/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&agentPk=1` | 500 | 500 | OK | fwqjcxx.agentPk/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&agentPk=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | fwqjcxx.agentPk/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&yxtzj=45L4479928780847000` | 500 | 500 | OK | fwqjcxx.yxtzj/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&yxtzj=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | fwqjcxx.yxtzj/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fwqbm=G0321361123W0010` | 200 | 200 | OK | fwqjcxx.fwqbm/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fwqbm=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | fwqjcxx.fwqbm/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fwqmc=%E4%B8%89%E6%B8%85%E5%B1%B1%E8%A5%BF%E6%9C%8D%E5%8A%A1%E5%8C%BA` | 200 | 200 | OK | fwqjcxx.fwqmc/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fwqmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | fwqjcxx.fwqmc/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&wd=28.78460594859297` | 500 | 500 | OK | fwqjcxx.wd/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&wd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | fwqjcxx.wd/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fxdm=1` | 500 | 500 | OK | fwqjcxx.fxdm/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&fxdm=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | fwqjcxx.fxdm/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&jd=117.99355545361145` | 500 | 500 | OK | fwqjcxx.jd/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&jd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | fwqjcxx.jd/absent |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&sslxbh=G0321` | 200 | 200 | OK | fwqjcxx.sslxbh/real |
| filters | GET | `/base/fwqjcxx/list?pageNum=1&pageSize=2&sslxbh=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | fwqjcxx.sslxbh/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&id=18` | 200 | 200 | OK | gantry.id/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&id=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.id/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryCode=G003536012000720010` | 200 | 200 | OK | gantry.gantryCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.gantryCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryName=%E7%91%9E%E9%87%91%E5%8C%97%E4%BA%92%E9%80%9A-%E5%AE%81%E9%8` | 200 | 200 | OK | gantry.gantryName/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.gantryName/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryName=%25` | 200 | 200 | OK | gantry.gantryName/wildcard |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryName=%E7%91%9E%E9%87%91%E5%8C%97%E4%BA%92%E9%80%9A-%E5%AE%81%E9%8` | 200 | 200 | OK | gantry.gantryName/case |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&gantryName=%E7%91%9E%E9%87%91%E5%8C%97` | 200 | 200 | OK | gantry.gantryName/prefix |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&roadCode=G35` | 200 | 200 | OK | gantry.roadCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&roadCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.roadCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&sectionCode=200R500350729001` | 200 | 200 | OK | gantry.sectionCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&sectionCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.sectionCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&tollCode=G35360730F0020` | 200 | 200 | OK | gantry.tollCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&tollCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.tollCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&orgCode=030000007` | 200 | 200 | OK | gantry.orgCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.orgCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&hexCode=39110A` | 200 | 200 | OK | gantry.hexCode/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&hexCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.hexCode/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&direction=1` | 200 | 200 | OK | gantry.direction/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&direction=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.direction/absent |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&pileNo=ZK1396%2B010` | 200 | 200 | OK | gantry.pileNo/real |
| filters | GET | `/base/gantry/list?pageNum=1&pageSize=2&pileNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantry.pileNo/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&id=1` | 200 | 200 | OK | gantryIp.id/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&id=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | gantryIp.id/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryCode=S003636011000510010` | 200 | 200 | OK | gantryIp.gantryCode/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantryIp.gantryCode/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryName=%E5%8D%97%E5%AE%89%E4%BA%92%E9%80%9A-%E5%B3%A1%E6%B1%9F%E4` | 200 | 200 | OK | gantryIp.gantryName/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantryIp.gantryName/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryName=%25` | 200 | 200 | OK | gantryIp.gantryName/wildcard |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryName=%E5%8D%97%E5%AE%89%E4%BA%92%E9%80%9A-%E5%B3%A1%E6%B1%9F%E4` | 200 | 200 | OK | gantryIp.gantryName/case |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&gantryName=%E5%8D%97%E5%AE%89%E4%BA%92` | 200 | 200 | OK | gantryIp.gantryName/prefix |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&orgCode=020000253` | 200 | 200 | OK | gantryIp.orgCode/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantryIp.orgCode/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&ip=36.121.3.43` | 200 | 200 | OK | gantryIp.ip/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&ip=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantryIp.ip/absent |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&brand=Signalway` | 200 | 200 | OK | gantryIp.brand/real |
| filters | GET | `/base/gantryIp/list?pageNum=1&pageSize=2&brand=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | gantryIp.brand/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&bigId=24945` | 200 | 200 | OK | org.bigId/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.bigId/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgCode=000000936` | 200 | 200 | OK | org.orgCode/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgCode/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgName=%E4%B8%AD%E5%BF%83%E6%9C%BA%E5%85%B3` | 200 | 200 | OK | org.orgName/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgName/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgName=%25` | 200 | 200 | OK | org.orgName/wildcard |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgName=%E4%B8%AD%E5%BF%83%E6%9C%BA%E5%85%B3` | 200 | 200 | OK | org.orgName/case |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgName=%E4%B8%AD%E5%BF%83%E6%9C%BA` | 200 | 200 | OK | org.orgName/prefix |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgShortName=%E4%B8%AD%E5%BF%83%E6%9C%BA%E5%85%B3` | 200 | 200 | OK | org.orgShortName/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgShortName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgShortName/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgShortName=%25` | 200 | 200 | OK | org.orgShortName/wildcard |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgShortName=%E4%B8%AD%E5%BF%83%E6%9C%BA%E5%85%B3` | 200 | 200 | OK | org.orgShortName/case |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgShortName=%E4%B8%AD%E5%BF%83%E6%9C%BA` | 200 | 200 | OK | org.orgShortName/prefix |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgParentId=030000009` | 200 | 200 | OK | org.orgParentId/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgParentId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgParentId/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgLevelCode=00000011005300050001` | 200 | 200 | OK | org.orgLevelCode/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgLevelCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgLevelCode/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgIsVirtual=1` | 200 | 200 | OK | org.orgIsVirtual/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgIsVirtual=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgIsVirtual/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgMaintenance=1` | 200 | 200 | OK | org.orgMaintenance/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgMaintenance=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgMaintenance/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgSequence=1` | 200 | 200 | OK | org.orgSequence/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgSequence=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | org.orgSequence/absent |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgIsManager=0` | 200 | 200 | OK | org.orgIsManager/real |
| filters | GET | `/base/org/list?pageNum=1&pageSize=2&orgIsManager=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | org.orgIsManager/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&bigId=312748` | 200 | 200 | OK | provcapture.bigId/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | provcapture.bigId/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&deviceip=36.101.189.5` | 200 | 200 | OK | provcapture.deviceip/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&deviceip=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | provcapture.deviceip/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetimeunix=-28800` | 200 | 200 | OK | provcapture.tailcapturetimeunix/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetimeunix=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80` | 400 | 400 | OK | provcapture.tailcapturetimeunix/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetime=1969-12-31T16%3A00%3A00.000%2B00%3A00` | 200 | 200 | OK | provcapture.tailcapturetime/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-` | 200 | 200 | OK | provcapture.tailcapturetime/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetime=1969-12-31%2016%3A00%3A00` | 200 | 200 | OK | provcapture.tailcapturetime/space |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetime=1969-12-31` | 200 | 200 | OK | provcapture.tailcapturetime/date-only |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&tailcapturetime=1969/12/31%2016%3A00%3A00` | 200 | 200 | OK | provcapture.tailcapturetime/slash |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&platecolorcode=1` | 200 | 200 | OK | provcapture.platecolorcode/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&platecolorcode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7` | 400 | 400 | OK | provcapture.platecolorcode/absent |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&platecolor=%E8%93%9D%E8%89%B2` | 200 | 200 | OK | provcapture.platecolor/real |
| filters | GET | `/base/provcapture/list?pageNum=1&pageSize=2&platecolor=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | provcapture.platecolor/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&id=18` | 200 | 200 | OK | section.id/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&id=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.id/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadCode=G6021` | 200 | 200 | OK | section.roadCode/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.roadCode/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadName=%E6%9D%AD%E9%95%BF%E9%AB%98%E9%80%9F` | 200 | 200 | OK | section.roadName/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.roadName/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadName=%25` | 200 | 200 | OK | section.roadName/wildcard |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadName=%E6%9D%AD%E9%95%BF%E9%AB%98%E9%80%9F` | 200 | 200 | OK | section.roadName/case |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&roadName=%E6%9D%AD%E9%95%BF%E9%AB%98` | 200 | 200 | OK | section.roadName/prefix |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionCode=200R560210671000` | 200 | 200 | OK | section.sectionCode/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.sectionCode/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionName=%E4%B9%90%E6%B8%A9` | 200 | 200 | OK | section.sectionName/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.sectionName/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionName=%25` | 200 | 200 | OK | section.sectionName/wildcard |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionName=%E4%B9%90%E6%B8%A9` | 200 | 200 | OK | section.sectionName/case |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&sectionName=%E4%B9%90%E6%B8%A9` | 200 | 200 | OK | section.sectionName/prefix |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&startPileNo=379` | 200 | 200 | OK | section.startPileNo/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&startPileNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | section.startPileNo/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&endPileNo=397` | 200 | 200 | OK | section.endPileNo/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&endPileNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | section.endPileNo/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgCode=020110017` | 200 | 200 | OK | section.orgCode/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.orgCode/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgName=%E5%8D%97%E6%98%8C%E4%B8%9C%E7%AE%A1%E7%90%86%E4%B8%AD%E5%BF%8` | 200 | 200 | OK | section.orgName/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.orgName/absent |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgName=%25` | 200 | 200 | OK | section.orgName/wildcard |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgName=%E5%8D%97%E6%98%8C%E4%B8%9C%E7%AE%A1%E7%90%86%E4%B8%AD%E5%BF%8` | 200 | 200 | OK | section.orgName/case |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgName=%E5%8D%97%E6%98%8C%E4%B8%9C` | 200 | 200 | OK | section.orgName/prefix |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgLevelCode=0000001100530011` | 200 | 200 | OK | section.orgLevelCode/real |
| filters | GET | `/base/section/list?pageNum=1&pageSize=2&orgLevelCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | section.orgLevelCode/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&agentPk=d2c6df4afa7ff18d48786d728d3919d2` | 500 | 500 | OK | sfsjcxx.agentPk/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&agentPk=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | sfsjcxx.agentPk/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&yxtzj=1531950771411013633` | 200 | 200 | OK | sfsjcxx.yxtzj/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&yxtzj=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.yxtzj/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sfsmc=%E4%B8%8A%E4%B8%87%E6%94%B6%E8%B4%B9%E6%89%80` | 200 | 200 | OK | sfsjcxx.sfsmc/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sfsmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.sfsmc/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&jd=117.43187400` | 200 | 200 | OK | sfsjcxx.jd/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&jd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.jd/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&wd=28.46829500` | 200 | 200 | OK | sfsjcxx.wd/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&wd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.wd/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sslxbh=S33` | 200 | 200 | OK | sfsjcxx.sslxbh/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sslxbh=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.sslxbh/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sslxmc=%E4%B8%8A%E4%B8%87%E9%AB%98%E9%80%9F%E5%85%AC%E8%B7%AF` | 200 | 200 | OK | sfsjcxx.sslxmc/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&sslxmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.sslxmc/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&ssldbh=200R50033360804000` | 200 | 200 | OK | sfsjcxx.ssldbh/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&ssldbh=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.ssldbh/absent |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&ssldmc=%E4%B8%8A%E4%B8%87%E9%AB%98%E9%80%9F%E4%B8%8A%E4%B8%87%E6%AE%B5` | 200 | 200 | OK | sfsjcxx.ssldmc/real |
| filters | GET | `/base/sfsjcxx/list?pageNum=1&pageSize=2&ssldmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfsjcxx.ssldmc/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&agentPk=363bc7b76e508c55dcb259cf6a3f007e` | 200 | 200 | OK | sfzjcxx.agentPk/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&agentPk=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.agentPk/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&yxtzj=1495673117678645249` | 200 | 200 | OK | sfzjcxx.yxtzj/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&yxtzj=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.yxtzj/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sfzdm=G56360429F0010` | 200 | 200 | OK | sfzjcxx.sfzdm/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sfzdm=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.sfzdm/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sfzmc=%E5%9D%87%E6%A1%A5%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | sfzjcxx.sfzmc/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sfzmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.sfzmc/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&jd=116.29458816` | 200 | 200 | OK | sfzjcxx.jd/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&jd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.jd/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&wd=29.66365882` | 200 | 200 | OK | sfzjcxx.wd/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&wd=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.wd/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sslxbh=S22` | 200 | 200 | OK | sfzjcxx.sslxbh/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sslxbh=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.sslxbh/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sslxmc=%E9%83%BD%E4%B9%9D%E9%AB%98%E9%80%9F%E5%85%AC%E8%B7%AF` | 200 | 200 | OK | sfzjcxx.sslxmc/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&sslxmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.sslxmc/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&ssldbh=200R00223600000611000` | 200 | 200 | OK | sfzjcxx.ssldbh/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&ssldbh=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.ssldbh/absent |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&ssldmc=%E9%83%BD%E4%B9%9D%E9%AB%98%E9%80%9F%E4%B9%9D%E6%99%AF%E6%AE%B5` | 200 | 200 | OK | sfzjcxx.ssldmc/real |
| filters | GET | `/base/sfzjcxx/list?pageNum=1&pageSize=2&ssldmc=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | sfzjcxx.ssldmc/absent |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.gantryname/real |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.gantryname/absent |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.gantryname/wildcard |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.gantryname/case |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.gantryname/prefix |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.roadname/real |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.roadname/absent |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.roadname/wildcard |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.roadname/case |
| filters | GET | `/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00` | 200 | 200 | OK | snapshotflow.roadname/prefix |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&bigId=20113483` | 200 | 200 | OK | stationcapture.bigId/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&bigId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | stationcapture.bigId/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&datasource=ZdTrails%3AStationCapture` | 200 | 200 | OK | stationcapture.datasource/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&datasource=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.datasource/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&cameratype=StationCapture` | 200 | 200 | OK | stationcapture.cameratype/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&cameratype=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.cameratype/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&deviceid=00000000` | 200 | 200 | OK | stationcapture.deviceid/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&deviceid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.deviceid/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&deviceip=36.105.104.121` | 200 | 200 | OK | stationcapture.deviceip/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&deviceip=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.deviceip/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollcode=G60361121F0020` | 200 | 200 | OK | stationcapture.tollcode/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollcode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.tollcode/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollname=%E4%B8%8A%E9%A5%B6%E4%B8%9C%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | stationcapture.tollname/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollname=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | stationcapture.tollname/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollname=%25` | 200 | 200 | OK | stationcapture.tollname/wildcard |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollname=%E4%B8%8A%E9%A5%B6%E4%B8%9C%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | stationcapture.tollname/case |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&tollname=%E4%B8%8A%E9%A5%B6%E4%B8%9C` | 200 | 200 | OK | stationcapture.tollname/prefix |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&orgcode=20110016` | 200 | 200 | OK | stationcapture.orgcode/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&orgcode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | stationcapture.orgcode/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&siteid=10` | 200 | 200 | OK | stationcapture.siteid/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&siteid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | stationcapture.siteid/absent |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&laneid=3` | 200 | 200 | OK | stationcapture.laneid/real |
| filters | GET | `/base/stationcapture/list?pageNum=1&pageSize=2&laneid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | stationcapture.laneid/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&id=1` | 200 | 200 | OK | toll.id/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&id=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.id/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&roadCode=S43` | 200 | 200 | OK | toll.roadCode/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&roadCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.roadCode/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&idCard=44L4464527980850000` | 200 | 200 | OK | toll.idCard/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&idCard=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.idCard/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollCode=S43361002F0020` | 200 | 200 | OK | toll.tollCode/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.tollCode/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollName=%E6%8A%9A%E5%B7%9E%E4%B8%9C%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | toll.tollName/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.tollName/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollName=%25` | 200 | 200 | OK | toll.tollName/wildcard |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollName=%E6%8A%9A%E5%B7%9E%E4%B8%9C%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | toll.tollName/case |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&tollName=%E6%8A%9A%E5%B7%9E%E4%B8%9C` | 200 | 200 | OK | toll.tollName/prefix |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&pileNo=11.725899696350098` | 200 | 200 | OK | toll.pileNo/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&pileNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.pileNo/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgName=%E6%8A%9A%E5%B7%9E%E7%AE%A1%E7%90%86%E4%B8%AD%E5%BF%83` | 200 | 200 | OK | toll.orgName/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.orgName/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgName=%25` | 200 | 200 | OK | toll.orgName/wildcard |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgName=%E6%8A%9A%E5%B7%9E%E7%AE%A1%E7%90%86%E4%B8%AD%E5%BF%83` | 200 | 200 | OK | toll.orgName/case |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgName=%E6%8A%9A%E5%B7%9E%E7%AE%A1` | 200 | 200 | OK | toll.orgName/prefix |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&stateCode=S0043360010020` | 200 | 200 | OK | toll.stateCode/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&stateCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.stateCode/absent |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgCode=030000006` | 200 | 200 | OK | toll.orgCode/real |
| filters | GET | `/base/toll/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | toll.orgCode/absent |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollCode=S0089360020040` | 200 | 200 | OK | tollStationIp.tollCode/real |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | tollStationIp.tollCode/absent |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollName=%E8%8E%B2%E8%8A%B1%E8%A5%BF%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | tollStationIp.tollName/real |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollName=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | tollStationIp.tollName/absent |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollName=%25` | 200 | 200 | OK | tollStationIp.tollName/wildcard |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollName=%E8%8E%B2%E8%8A%B1%E8%A5%BF%E6%94%B6%E8%B4%B9%E7%AB%99` | 200 | 200 | OK | tollStationIp.tollName/case |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&tollName=%E8%8E%B2%E8%8A%B1%E8%A5%BF` | 200 | 200 | OK | tollStationIp.tollName/prefix |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&orgCode=030000008` | 200 | 200 | OK | tollStationIp.orgCode/real |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&orgCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | tollStationIp.orgCode/absent |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&ip=36.106.145.9` | 200 | 200 | OK | tollStationIp.ip/real |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&ip=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | tollStationIp.ip/absent |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&brand=haikang` | 200 | 200 | OK | tollStationIp.brand/real |
| filters | GET | `/base/tollStationIp/list?pageNum=1&pageSize=2&brand=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | tollStationIp.brand/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&uuid=e0e22490-fb40-4795-947b-68565d864aa7` | 200 | 200 | OK | trailtracks.uuid/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&uuid=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | trailtracks.uuid/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&type=0` | 200 | 200 | OK | trailtracks.type/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&type=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | trailtracks.type/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&pointCount=45` | 200 | 200 | OK | trailtracks.pointCount/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&pointCount=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | trailtracks.pointCount/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&plateKey=%E8%B5%A3CEA826` | 200 | 200 | OK | trailtracks.plateKey/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&plateKey=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | trailtracks.plateKey/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&enterTime=2025-09-10%2004%3A39%3A49` | 200 | 200 | OK | trailtracks.enterTime/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&enterTime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | trailtracks.enterTime/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&enterTime=2025-09-10%2004%3A39%3A49` | 200 | 200 | OK | trailtracks.enterTime/space |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&enterTime=2025-09-10` | 200 | 200 | OK | trailtracks.enterTime/date-only |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&enterTime=2025/09/10%2004%3A39%3A49` | 200 | 200 | OK | trailtracks.enterTime/slash |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&exitTime=2025-09-11%2002%3A19%3A01` | 200 | 200 | OK | trailtracks.exitTime/real |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&exitTime=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | trailtracks.exitTime/absent |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&exitTime=2025-09-11%2002%3A19%3A01` | 200 | 200 | OK | trailtracks.exitTime/space |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&exitTime=2025-09-11` | 200 | 200 | OK | trailtracks.exitTime/date-only |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&exitTime=2025/09/11%2002%3A19%3A01` | 200 | 200 | OK | trailtracks.exitTime/slash |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&trailPoints=%5B%7B%22pointUuid%22%3A%22cd58f6fa-a108-45ff-8d5b-458` | 400 | 400 | CONTAINER | raw body differs: '<!doctype html><html lang="en"><head><title>HTTP Status 400 – Bad Request</title><style type="text/css">body {font-famil' != '{"timestamp":"2 |
| filters | GET | `/base/trailtracks/list?pageNum=1&pageSize=2&trailPoints=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | trailtracks.trailPoints/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&dataSource=ZdTrails%3ABorderWeighing` | 500 | 500 | OK | vehicleweight.dataSource/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&dataSource=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.dataSource/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&dataType=weigh` | 500 | 500 | OK | vehicleweight.dataType/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&dataType=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.dataType/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateNo=%E8%BD%A6%E7%89%8C%E5%9B%BE%E7%89%87%E6%9C%AA%E5%8C%B9%E` | 500 | 500 | OK | vehicleweight.plateNo/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.plateNo/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&siteId=4` | 500 | 500 | OK | vehicleweight.siteId/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&siteId=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.siteId/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&location=%E5%AE%9C%E6%98%A5%E7%AE%A1%E7%90%86%E4%B8%AD%E5%BF%83%` | 200 | 200 | OK | vehicleweight.location/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&location=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 200 | 200 | OK | vehicleweight.location/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&driveNo=2` | 500 | 500 | OK | vehicleweight.driveNo/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&driveNo=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 400 | 400 | OK | vehicleweight.driveNo/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateColor=%E5%85%B6%E4%BB%96` | 500 | 500 | OK | vehicleweight.plateColor/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateColor=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.plateColor/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateColorCode=9` | 500 | 500 | OK | vehicleweight.plateColorCode/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateColorCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC` | 500 | 500 | OK | vehicleweight.plateColorCode/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateType=%E5%85%B6%E4%BB%96` | 500 | 500 | OK | vehicleweight.plateType/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateType=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-7Q` | 500 | 500 | OK | vehicleweight.plateType/absent |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateTypeCode=99` | 500 | 500 | OK | vehicleweight.plateTypeCode/real |
| filters | GET | `/base/vehicleweight/list?pageNum=1&pageSize=2&plateTypeCode=ZZZ-%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E5%80%BC-` | 500 | 500 | OK | vehicleweight.plateTypeCode/absent |

### inventory（2 项：一致 2，不一致 0，跳过 0）

元信息：`{"rust_inventory": 85, "java_annotations": 85}`

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| inventory | - | `清单数量` | - | - | OK | rust=85 java=85 unique=85 |
| inventory | GET | `路由注册探测（{param}→1）` | - | - | OK | 共 85 条，无 404 未注册 |

### query（34 项：一致 34，不一致 0，跳过 0）

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| query | GET | `/api/v1/large/snapshot?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNum=1&pageSize=5` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/snapshot?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNum=1&pageSize=5&fuzz` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/snapshot?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNum=1&pageSize=5&fuzz` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/snapshot?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNum=1001&pageSize=20` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/fee?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNum=1&pageSize=2` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/trail?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNum=1&pageSize=2` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/trail?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNum=1&pageSize=2&fuzzyFi` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/carTrackQueryByCarNo?carNo=&startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNu` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/carTrackQueryByCarNo?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 400 | 400 | OK | query |
| query | GET | `/api/v1/large/stats/group?type=snapshot&startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&groupBy=` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/stats/group?type=fee&startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&groupBy=gantr` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/stats/group?type=trail&startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&groupBy=env` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/stats/group?type=bogus&startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&groupBy=x` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/stats/group?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 400 | 400 | OK | query |
| query | GET | `/api/v1/large/export/status/nope` | 200 | 200 | OK | query |
| query | GET | `/api/v1/unified/snapshot/list?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNum=1&pageSize` | 200 | 200 | OK | query |
| query | GET | `/api/v1/unified/fee/list?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNum=1&pageSize=3` | 200 | 200 | OK | query |
| query | GET | `/api/v1/unified/trail/list?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageNum=1&pageSize=3` | 200 | 200 | OK | query |
| query | GET | `/api/v1/unified/bad/list?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 200 | 200 | OK | query |
| query | GET | `/api/v1/unified/snapshot/list?endTime=2025-09-09%2000:00:00` | 400 | 400 | OK | query |
| query | GET | `/api/v1/unified/export/status/nope` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/foo?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 404 | 404 | OK | query |
| query | GET | `/progressive/snapshotflow/list?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageSize=20&plate` | 200 | 200 | OK | query |
| query | GET | `/progressive/feerecords/list?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageSize=2` | 500 | 500 | OK | query |
| query | GET | `/progressive/trailfitting/list?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59&pageSize=2` | 500 | 500 | OK | query |
| query | GET | `/progressive/scale-level` | 200 | 200 | OK | query |
| query | GET | `/api/v1/large/sync/full?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 405 | 405 | OK | query |
| query | GET | `/api/v1/large/fee?startTime=2025-13-45%2000:00:00&endTime=2026-12-31%2023:59:59` | 200 | 200 | OK | query |
| query | POST | `/api/v1/large/export/submit?type=snapshot&startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00` | 200 | 200 | OK | query-post |
| query | POST | `/api/v1/large/export/submit?type=fee&startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 200 | 200 | OK | query-post |
| query | POST | `/api/v1/unified/snapshot/export/submit?startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00` | 200 | 200 | OK | query-post |
| query | POST | `/api/v1/unified/bad/export/submit?startTime=2025-01-01%2000:00:00&endTime=2026-12-31%2023:59:59` | 200 | 200 | OK | query-post |
| query | POST | `/api/v1/large/sync/repair?type=snapshot&startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00` | 200 | 200 | OK | query-post |
| query | POST | `/base/gantry/list` | 405 | 405 | OK | query-post |

### sysutil（10 项：一致 7，不一致 0，跳过 3）

| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |
|---|---|---|---|---|---|---|
| sysutil | GET | `/base/sysutil/getByTrailBo` | 200 | 200 | OK | sysutil-get |
| sysutil | GET | `/base/sysutil/changeTrailInfo` | 405 | 405 | OK | sysutil-get |
| sysutil | GET | `/api/v1/large/carTrackQueryByCarNo?carNo=&startTime=2025-09-08%2000:00:00&endTime=2025-09-09%2000:00:00&pageNu` | 200 | 200 | OK | sysutil-track |
| sysutil | GET | `/base/sysutilTest/syncBaseInfo` | 200 | 200 | OK | sysutilTest |
| sysutil | GET | `/base/sysutilTest/syncCurrentTrack` | 200 | 200 | OK | sysutilTest |
| sysutil | GET | `/base/sysutilTest/syncHistroyTrack` | - | - | SKIP | 写副作用/耗时，需 --allow-side-effects |
| sysutil | GET | `/base/sysutilTest/syncSuspiciousCar1` | - | - | SKIP | 写副作用/耗时，需 --allow-side-effects |
| sysutil | GET | `/base/sysutilTest/syncSuspiciousCar2` | - | - | SKIP | 写副作用/耗时，需 --allow-side-effects |
| sysutil | GET | `/base/sysutilTest/syncOdsSzdnGantry` | 500 | 500 | OK | sysutilTest |
| sysutil | GET | `/base/sysutilTest/separateSnapshotFlowTimeList` | 200 | 200 | OK | sysutilTest |
