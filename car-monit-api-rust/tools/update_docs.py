import io

p = 'README-MIGRATION.md'
s = io.open(p, encoding='utf-8').read()

s = s.replace('''> **本机未安装 GaussDB，因此“监听 9901 并完成真实业务请求”未在当前环境实测**；
> 已通过 `--check-config`、Router 装配测试、`/healthz` HTTP 集成测试证明装配正确。
> 该项在自检清单中标记为“待环境验证”。''',
'''> **已使用真实 GaussDB/Redis 完成双端实测**：Java（9902）与 Rust（9911）同时连接
> `192.168.56.10:5432/RuoYi`，对 74 个只读/错误场景逐 JSON 对比，结果 **74/74 一致**。
> 详见第 10 节。''')

s = s.replace('| `base.domain.*`（30 个） | `src/models/*`（由 `tools/gen_models.py` 从已核对的 Go 模型生成） |',
              '| `base.domain.*`（30 个） | `src/models/*`（`tools/gen_models.py` 解析 Java 字段类型/@JsonFormat + 真实 DB 类型生成） |')

s = s.replace('| 3 | 状态码/错误码一致 | ✅ | 404/405 fallback 返回 `{code,msg,data}`；501 blocked；`AppError::IntoResponse`；`tests/router_test.rs::unknown_path_returns_ajax_result` |',
              '| 3 | 状态码/错误码一致 | ✅ | 404/405/400/500 均复刻 Spring `{timestamp,status,error,message,path}`；真实双端对比覆盖必填参数、非法数据源、Java 侧异常端点；`tests/router_test.rs::unknown_path_returns_spring_error` |')

s = s.replace('| 9 | 应用可启动并监听相同端口 | ⚠️ 待环境验证 | 端口 9901/上下文 `/` 已装配；本机无 GaussDB，`cargo run` 会在启动 Ping 阶段 fail-fast（与 Go 版一致）。`--check-config` + Router 装配测试 + `/healthz` 集成测试通过 |',
              '| 9 | 应用可启动并监听相同端口 | ✅（实测） | Rust 以 9911 启动并连接真实 GaussDB/Redis；Java 9902 同库运行；74 个接口逐 JSON 一致（见第 10 节） |')

s = s.replace('| 4 | **缺 XML 的两个 selectList 按字段语义重建** | Java 仓库中 `fee_records_01` / `snapshot_flow` 的自定义 list 无 XML，Java 调用会抛 `Invalid bound statement` | Rust 返回的是“按字段语义推断”的结果集，不是 Java 实测行为 | 若前端依赖这些接口，需先补齐 Java XML 并做灰度对比 |',
              '| 4 | **Java 侧缺失 SQL 的端点按 Java 实际 HTTP 行为复刻** | 实测 `feerecords/list|listToExport`、`progressive/feerecords|trailfitting`、`vehicleweight/{id}`、`trailtracks/{id}` 返回 Spring 500；`sysutilTest` 部分端点返回 200/500 | Rust 不再返回 501 或“推断结果”，而是返回与 Java 相同的 200/500 错误体 | 若后续补齐 Java XML，再同步恢复 Rust 的真实查询实现 |')


s = s.replace('| 10 | **启动未实测** | 本机无 GaussDB | 不能证明真实请求链路 | 在有库环境执行 `cargo run` + `curl /readyz` |',
              '| 10 | **启动与业务请求已实测** | 使用 yml 中的 GaussDB/Redis | Java/Rust 双端 74 个接口一致 | 见第 10 节；Kafka/ES 的真实生产链路仍需独立联调 |')

s = s.replace('| 12 | **ES / Kafka 未做真实集成测试** | 本机无服务 | 查询/导出的真实 DSL 行为未验证 | 用 docker-compose 起 ES/Kafka 后跑冒烟脚本 |',
              '| 12 | **ES / Kafka 未做完整数据集成** | 本机 ES 磁盘 97%、触发 flood-stage 只读；Kafka 未启动 | 已按 Java mapping 建索引，但仅验证了空索引路径；消息总线为 Noop | 清理磁盘后执行全量/增量同步，并用 Kafka 联调消费链路 |')

s = s.replace('| `src/models/` | 30 个实体/DTO（`tools/gen_models.py` 生成） |',
              '| `src/models/` | 30 个实体/DTO（Java 注解 + 真实 DB 类型驱动生成） |')
s = s.replace('| `tools/gen_models.py` | 从已核对的 Go 模型生成 Rust 模型（改表结构时重跑） |',
              '| `tools/gen_models.py` | 解析 Java 字段类型/@JsonFormat 与 DB schema，生成 NULL 感知的 Rust 模型（改表/改实体时重跑） |')

s = s.rstrip() + '''

---

## 10. 真实环境双端实测记录（2026-10-31）

### 10.1 环境与方式

| 项 | 值 |
|---|---|
| Java | `pro-business-api-1.0.jar`，`-Dserver.port=9902`，今日构建 |
| Rust | `target/debug/car-monit-api-rust.exe`，`APP_SERVER_PORT=9911` |
| 数据库 | yml 中的 GaussDB：`192.168.56.10:5432/RuoYi`（schema `jl_data01`） |
| Redis | Java 用 DB0；Rust 用 `APP_REDIS_DATABASE=15` 隔离，避免序列化格式互相污染 |
| 调度/消费者 | Rust 侧 `APP_CONSUMER_ENABLED=false`、`APP_ENABLE_SCHEDULER=false`，避免双端任务互相干扰 |
| 对比脚本 | `tools/compare_api.py`：逐接口请求 Java/Rust，解析 JSON 后深度比较（数值允许 1e-9 相对误差；忽略随机行 key 与错误时间戳） |
| 覆盖 | 74 个场景：19 张表 list/listAll/详情、listToExport、导出状态、large/unified/progressive、sysutil、sysutilTest、必填参数/非法数据源/404 |

复现：

```bash
# 终端 1：Java（已有构建产物）
java -Dserver.port=9902 -jar pro-business-api/target/pro-business-api-1.0.jar
# 终端 2：Rust
cd car-monit-api-rust
APP_SERVER_PORT=9911 APP_REDIS_DATABASE=15 APP_CONSUMER_ENABLED=false \\
  APP_ENABLE_SCHEDULER=false APP_KAFKA_BOOTSTRAP_SERVERS= \\
  cargo run -- --config config/application.yaml
# 终端 3：对比
python tools/compare_api.py
# SUMMARY ok=74 bad=0
```

### 10.2 实测中发现并修正的差异

1. **可空列解码**：467 个 DB 可空列被当作非空 `String`/`i32`，真实数据一遇到 NULL 就 500。
   改为 NULL 感知标量：`JString / JInt / JLong / JFloat / JBool / Day / JDateTime / JIsoDateTime / JList`，
   JSON 为 null 时与 Jackson 一致。
2. **跨类型兼容**：GaussDB 实际列类型与 Java 实体类型不一致（VARCHAR↔TEXT、INT2↔INT4↔INT8、
   FLOAT8↔INT4、TIMESTAMP↔TIMESTAMPTZ、`TEXT[]`、`tinyint`），SQLx 默认 `Option<T>` 会拒绝。
   为标量类型实现 `compatible()` 与按实际 SQL 类型解码。
3. **时区**：JDBC `serverTimezone=Asia/Shanghai` + Jackson UTC 输出；`Date` 字段需要 -8h，
   而 Java String 字段走 `getString` 返回墙钟时间、不能偏移。两类分别处理。
4. **快照列表 SQL**：按 `OdsRtSzdnSnapshotFlowAddcodeMapper.xml` 只选 17 列并 `ORDER BY snapshottime DESC`；
   实测 `flag == 'JiAnDong'` 的 OGNL 条件未生效，Rust 同步忽略。
5. **渐进式查询不分页**：Java phase1 直接 `selectList`（无 PageHelper），pageSize 被忽略；
   Rust 改为无 LIMIT 的 `list_unbounded`。
6. **feeGantry 列表 id**：Java 每行临时生成 UUID，Rust 同步。
7. **Spring 错误体**：404/405/400/500 统一输出 `{timestamp,status,error,message,path}`；
   Java 侧因缺失 Mapper SQL 的 12 个端点，Rust 返回相同的 200/500，而不是 501。
8. **缓存污染**：Redis DB0 中 `DATE_BorderWeighingCapture:*` 被 Python/Go 迁移写入不兼容 JSON，
   会让 Java `/base/vehicleweight/map` 500；清理后两端一致（切换版本前必须清缓存）。

### 10.3 结论

- 74 / 74 场景 JSON 一致（状态码 + 响应体）。
- 未纳入自动对比的是会产生副作用的 POST（导出提交、全量/增量同步）与消息消费链路；
  这些接口的启动参数/校验分支已在代码层对齐，但仍需在独立测试环境验证。
- ES 索引已按 Java mapping 创建，但本机磁盘 97% 触发 flood-stage 只读，仅验证了空索引路径；
  Kafka 未启动，消息总线为 Noop。
'''

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

p = 'docs/MIGRATION-BASELINE.md'
s = io.open(p, encoding='utf-8').read()
s = s.replace('### 2.2 501 端点（12 个，Java 侧同样跑不通）', '### 2.2 Java 侧无法执行的端点（12 个）')
s = s.replace('''Rust 侧返回 **HTTP 501 + `{code,msg,data,porting:"blocked",javaRef,reason}`**，避免调用方误以为同步成功。''',
'''真实双端实测后，Rust 按 Java 的实际 HTTP 行为复刻：
- `syncSuspiciousCar1..10`：Java 方法返回 void，异步任务内部失败 → **HTTP 200 + 空体**；
- `syncOdsSzdnGantry`：同步执行并抛 `Invalid bound statement` → **HTTP 500**；
- `separateSnapshotFlowTimeList`：方法返回 void → **HTTP 200 + 空体**。''')
s = s.replace('| 2 | `SysUtilServiceImpl.syncSuspiciousCarQutaz` | 依赖不存在的 Mapper 语句 | 12 个端点返回 501 + 证据 |',
              '| 2 | `SysUtilServiceImpl.syncSuspiciousCarQutaz` | 依赖不存在的 Mapper 语句 | 按 Java 实际返回复刻：10 个 200 空体 + `syncOdsSzdnGantry` 500 |')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('docs updated')
