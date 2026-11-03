# 10 P-SER-1 与 P-QRY-1 修复（第五轮）

`09` 之后剩下的两条 Go 侧待办，本轮都做掉了，并且**推翻了其中一条的前提**。
数字来自 `raw/r11.jsonl`（361 条）与 `raw/r12.jsonl`（364 条，含本轮新增 3 条用例）。

## 1. 结论

| 项 | 结果 |
|---|---|
| **P-SER-1**（`TrailBo`/`TrailInfo` 的 `null` vs `""`） | **已修**，残余差异从 11 条 → **0 条**，且**没有把 19 处合法空串翻转成 null** |
| **P-QRY-1** 的错误契约部分（非法时间 → Go 报 500、Java 返回空） | **已修**，`large-badtime` 转 OK |
| **P-QRY-1** 的 "ES mapping 是 `text` 导致路径不通" | **前提不成立**（见第 4 节）：range 不失败，失败的是 sort，且**两端逐字等价**，不需要动 ES |
| 定稿 | **r12 = 364 条：OK 329 / DIFF 13 / STATUS 22 / NONDET 0**；r11→r12 共同的 361 条**零迁移** |

累计修复项 17 → **19**。

## 2. P-SER-1：选型与依据

候选原本是 A) 字段改 `*string`；B) 自定义字符串类型，空串编码成 `null`。

**B 被实测否决。** Java 有**合法输出 `""`** 的字段，类型级"空串一律变 null"会把它们做成新差异：

| Java 出处 | 行为 | 实测 |
|---|---|---|
| `SysUtilServiceImpl.java:1198/1205/1213` 显式 `setImagesArry("")`，且 `:1219-1220` 无条件走 `repalacePicUrl(deleteEnd(...))` | `imagesArry` 永远非 null | Java 报文里 `imagesArry` 有 **17 个 `""`**（全在 `getbytrailbo-*`） |
| `SysUtilServiceImpl.java:740` `setDevName(CommonUtil.isNull(code).replaceAll(...))` | code 为空时得到 `""` | **2 个 `""`**（`change-post`、`s2-change-scale`） |

扫全部 Java 侧报文得到的真实分布是：**TrailBo 层 `null` 3907 处 / `""` 19 处**。
> 顺带更正 `07`/`04` 里我写的一句："Java 797 个真实点从不输出 `""`"——方向对、说法错：
> 797 这个数在本语料复现不出来（渲染出的 TrailBo 节点只有 262 个），而且 `""` 确实存在 19 处。

**选 A**，并按 Java 原文把两类赋值分开处理——这是本次改动里唯一真正的语义判断：

| Java 写法 | 语义 | Go 写法 |
|---|---|---|
| `setRoadCode(CommonUtil.isNull(toll.getRoadCode()))`（`SysUtilServiceImpl.java:589/594/599/659/664/669/702/705`） | `isNull` 空值返回**空串** | `model.Str(utils.IsNull(...))` —— 保持 26 处不变 |
| `setDirection(odsSzdnGantry.getDirection())`、`setIsVirtual(...)`、`setDevCode(locationDict.getStandardCode())`、`setDevName(...)`（`:673/676/688/689`） | 裸 getter，**null 要能穿透** | 指针直传 `= g.Direction` —— 改写 35 处 |
| `getString(key)`（fastjson） | 键不存在 / JSON null → **null**；值是 `""` → `""` | 新增 `jsonStrPtr`，`jsonString` 退化成它的 `Val` 包装 |

改动面：`model/trail_bo.go` 27 个字段 + `model/trail_info.go` 的 `TrailUuid` 改为 `*string`；
调用点 **153 处**由编译器逐条指认后改写（含 3 处 `sort` 比较要显式 `model.Val`，
1 处 `prev.SectionCode != curr.SectionCode` 改指针后会变成**比地址**，已一并改成比值）。

## 3. P-QRY-1：错误契约

`GET /api/v1/large/snapshot?endTime=abc`：Java `200 {code:200,data:[],dataSource:…,pageNum:…,pageSize:…,message:"ok"}`，
Go 此前是 `200` 里塞 `code:500`，且另外 4 个键直接消失。

根因不在校验，而在**错误有没有往上冒**：
`UnifiedQueryService.java:126-150` 的两个 catch 都 `return Collections.emptyList()`，
`query()` **永不抛**，控制器因此恒走成功分支。Go 的 `service/query.go` 把降级失败的错误
`return nil, ferr` 上抛，handler 走异常分支提前 return，响应体只剩两个键。

改法：`Query()` 对齐 Java —— 降级也失败时返回**空切片**（不是 nil，nil 会编码成 `null` 而 Java 是 `[]`），
错误照样 `slog.Error`（对应 Java 的 `log.error`）。实测 large 与 unified 两条路径的键集合与取值已逐一对齐。

## 4. "ES mapping 是 text 所以路径不通"——前提需要更正

只连 ES 做了只读核查（7.15.2，`snapshot_flow` 300 篇 / `fee_records` 369 篇 / `trail_fitting` 1 篇）：

- `snapshottime` / `transtime` / `extime` 确实是 **`text`**（只有 `.keyword` 子字段，**没有 `.ngram`**）；
  `loadtime`、`receivedtime`、`entime` 是 `date`。
- **但 range 不失败**：`{"range":{"snapshottime":{"gte":"2025-10-01","lte":"abc"}}}` → `failed: 0`、266 命中
  （按词项字典序比，**语义错但不报错**——这比报错更糟，两端都在默默返回错数据）。
- 失败的是 **sort**：`{"sort":[{"snapshottime":{"order":"desc"}}]}` → 400 `all shards failed`
  / `Text fields are not optimised for operations such as sorting`。
- 两端都**无条件附加同一个 sort**（Go `service/query.go:281`、`service/large.go:151`；
  Java `UnifiedQueryService.java:245`），所以路由决策与失败点**已经等价**，
  不存在"Go 需要修才通"的差异。

结论：**不该在这台机器上建模板 / reindex**（那会动共享 ES、并同时改变两端行为，
把已经等价的差异重新搅开）。真要修，是把 mapping 改成 `date` 之后**重新设计路由与排序**，
属独立排期事项，且要先确认那 266 条"字典序 range"的历史结果是否被人当过真。

顺带两处记账更正：
- Java 的三个实体里**只有 SNAPSHOT 带 schema**（`OdsRtSzdnSnapshotFlowAddcode.java:25`），
  FEE/TRAIL 是裸名（`:25`、`ZdataTrailFitting.java:20`）→ 降级路径只有 FEE/TRAIL 会 42P01。
  Go 的注释原先写"三个都没 schema"，已更正（代码本身是对的，三个都带 schema）。
- `04` 里"Java 只吃 `yyyy-MM-dd[ HH:mm:ss]`"这句需要补一条实测（见第 5 节）。

## 5. 本轮新增覆盖：时间格式宽度差异（3 条，仍是差异，但已进主表）

`04` 的 P-QRY-1 一直记着这条宽度差异，但证据只在 `suite2.py` 的 29 条补测里
（`s2-large-dateonly` 等），**主用例表 361 条里没有**，所以 r10/r11 的归因表里它只剩 1 条
`large-badtime`。本轮把它提进主表，变成可跟踪的 3 条：

| 用例 | 请求 | Java | Go |
|---|---|---|---|
| `large-plaindate` | `startTime=2025-10-01&endTime=2025-10-02` | `data=[]` | 5 条 |
| `large-tformattime` | `startTime=2025-10-01T00:00:00…` | `data=[]` | 5 条 |
| `unified-plaindate` | 同上打 unified | `data=[]` | 5 条 |

机制：Java 降级到库时用 `java.sql.Timestamp.valueOf(...)`，**只认 `yyyy-MM-dd HH:mm:ss`**；
纯日期与带 `T` 的串抛异常 → 被 `query()` 的 catch 吞掉 → 空集。Go 解析更宽，真查出了数据。

这与 P-JAVA-9 那 4 条是**同一类**（Java 因自身限制静默返回空、Go 给出正确数据），
所以我**没有让 Go 去复刻"拒绝合法时间格式"**，只把它测出来、登记着。
要复刻的话就是让 Go 也拒绝 `2025-10-01`——这是业务决定，不是技术问题，等你拍板。

## 6. r12 的 35 条非 OK 全部归因

| 归属 | 条数 | 是 Go 缺陷吗 |
|---|---|---|
| P-JAVA-1..8（Java 端点自身 500） | 22 | 否 |
| P-ERR-1（404/405 响应体形状） | 6 | 是（待决策） |
| P-JAVA-9（Java 降级 SQL 表名缺 schema → 恒空，Go 有值） | 4 | 否（Go 正确） |
| P-QRY-1（时间格式宽度：Java `Timestamp.valueOf` 只认完整格式） | 3 | 待决策（本轮新增覆盖） |
| **合计** | **35** | **无一条无归属；NULLISH 类残余已归零** |

对照 `09` 的 44 条：**P-SER-1 的 11 条清零**，P-QRY-1 从 1 条变成 3 条（新增覆盖，不是新差异）。

## 7. 测试

**35 个测试函数 / 8 个文件**（`09` 记的 32/7 → 本轮 +3），`go build`、`go vet`、
`gofmt -l`（空）、6 包 `go test -count=1` 全绿。

新增 `internal/service/trailbo_null_test.go`，锁的正是第 2 节那个语义判断：

- `TestJSONStrPtrMatchesFastjsonGetString`：键不存在 / JSON null → nil；`""` → 装箱非 nil；数字 → 字面量串。
- `TestTrailBoJSONKeepsThreeStates`：`nil`→`null`、`Str("")`→`""`、有值→原值，三种必须分得开。
- `TestTrailInfoJSONAcceptsNullAndEmpty`：`TrailInfo` 同时是入参，`null` 与 `""` 都要能吃进且不塌缩。

## 8. 仍未闭环

| 编号 | 内容 | 卡在哪 |
|---|---|---|
| P-ERR-1 | 404/405 响应体形状（Spring 错误体 vs `AjaxResult`） | 全局兜底，改动面大，待决策 |
| P-ERR-2 | 未捕获异常的 HTTP 码 | 同上 |
| P-QRY-1（新覆盖的 3 条） | Go 接受的时间格式比 Java 宽 | 要不要复刻 Java 的限制，业务决定 |
| ES mapping | 时间列是 `text`：range 静默按字典序、sort 必失败 | 改 mapping 会同时改变两端行为，需独立排期 |
| P-PAGE-5 | Go 取 `offset+size` 行再内存切片 | 与 Java 结果一致，属性能；改要动 19 个 repo 签名 |
| P-ENV-3 | `configs/config.yaml` 仍是 9901 + db0 | 配置/运维决策 |
| P-JAVA-1..9 | Java 侧 22 + 4 条 | 切到 Go 会从 500/空变成 200/有数据，需确认上游没有依赖 500 |

## 9. 复现

```bash
cd car-monit-api-go && go test -count=1 ./internal/...          # 35 函数 / 6 包

cd docs/parity-2026-11-02/tools
python parity.py --gen                                          # 改了 suite.py 必须重新生成用例表
python parity.py --out r12 --md ../raw/r12.md                   # 364 条
```

> 踩坑记录：只改 `suite.py` 不跑 `--gen`，`parity.py` 会读缓存的 `cases.json`，
> 新用例**静默不生效**（我第一次跑 r12 就是 361 条）。凡加用例，`--gen` 在前。

## 10. 覆盖率与证据链复核（本轮收尾做的三件机械核对）

改完 `TrailBo` 这类底层类型后，光看差分通过不够，把之前几轮"引用过但没重算"的
机械结论也一并重跑了一遍：

| 核对项 | 怎么做的 | 结果 |
|---|---|---|
| **端点覆盖率** | 拿 `routes.py` 的 Java 端点清单逐条匹配 `cases.json` 的路径（`{var}` 转正则） | 85 个端点里**主表直接命中 83**；剩 2 个是 `POST /api/v1/large/export/submit` 与 `POST /api/v1/unified/{ds}/export/submit`，由导出探针覆盖 → **实际 85/85** |
| **谓词覆盖** | 重跑 `predicates.py`（结果存 `raw/predicates-r12.txt`） | 19 张表**缺 0 的仍 17 张**；两张有缺的都不是 Go 问题（`feerecords` 缺 1 = Java XML 没有 list 语句、`fwqjcxx` 缺 28 = Java 把 SELECT 别名当列名，实测 500）。`trailtracks` 在新增 `CountHistoryTrail` 之后仍是 **缺0/多4** —— 共用谓词没有让计数与取数各报一份 |
| **导出证据链** | 复查 `raw/export-probe*.json` | **发现一处引用错误**：被当作"导出实测"引用的 `export-probe.json`，其实是两个服务都没监听时的一次非运行（两端都 `WinError 10061`）。真正有结果的是 `export-probe-livedata.json`：两端 submit 200、`RUNNING→FAILED`、失败原因同为 ES `all shards failed`，**状态体键集合两端一致**（`large` 两边都无 `errorMessage`，`unified` 两边都有）。`05` §4 的引用已更正 |

> 换句话说：导出的**提交与状态查询**两端等价，但**成功产出 xlsx 的路径两端都没跑到**
> ——卡在同一个 ES mapping 上（`10` §4）。这条仍是灰度前要确认的事，不是 Go 的差异。

### 本轮结束时环境发生变化

Java `:9902`（PID 92588）与 Go `:9903` 在本轮收尾阶段**都已退出**（`netstat` 无监听、
两个 PID 不存在），所以"用当前构建复跑导出探针"没能完成。
**r11 / r12 两轮跑批是在两端都在线时完成的，已提交的数据不受影响。**
Go 那份是我起的进程，随时可以按 `configs/config.verify.yaml` 重启；
Java 是基准端，重启前要确认（`08` §环境事件里也记过它硬退出过一次）。
