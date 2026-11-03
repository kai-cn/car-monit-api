# 09 P-PAGE-8 修复与端到端复验（第四轮）

`08` 的复核把 **P-PAGE-8（轨迹 total 语义）** 列为"仍未闭环、且剩余问题里唯一会让调用方
拿到错数据的一条，优先级应高于 P-SER-1"。本轮就是关掉它，并顺带关掉 `07` 里
P-PAGE-3 一直没闭的 sysutil 那一半。

所有数字来自 `raw/r10.jsonl`（本轮新跑）与当场两端对打，可逐条重放。

## 1. 结论

- **P-PAGE-8 已闭环**：轨迹两个接口的 `total` 现在与 Java 一致（112 / 0 / 0 / 112），
  而且**行身份也逐一对上**——首页 5 条与越界回夹后的末页 2 条，`uuid` 与 Java 完全相同、顺序相同。
- 新增一轮 **r10：361 条 = OK 317 / DIFF 22 / STATUS 22 / NONDET 0**。
  相对 r9 只有 **2 条判定迁移，均为 DIFF→OK**（正是两条 sysutil 边界用例），**零回归**。
- 剩余非 OK 从 46 降到 **44**，且**没有任何一条还归在 P-PAGE-8 名下**（见第 5 节）。
- 累计修复项 16 → **17**。

## 2. 根因（为什么 Go 的 total 一直是错的）

Java 两个轨迹接口都是：

```java
startPage();                                   // PageHelper 起分页
List<ZdataTrailTracks> list = ...carTrackQueryNew(vo);
...
rspData.setTotal(new PageInfo(list).getTotal());   // ← 不是 list.size()
```

`PageInfo(list).getTotal()` 取的是 **PageHelper 用同一套 WHERE 另外跑的一次 count**，
所以 `pageSize=0` 时 Java 仍能给 `total=112` 而 `rows=[]`。
Go 此前把 `len(list)`（本页行数，最多 `pageSize`）当 total，于是：

| 请求 | Java | Go（改前） |
|---|---|---|
| `carTrackQueryByTime?pageNum=1&pageSize=5` | total=112 | total=5 |
| `carTrackQueryByTime?pageNum=1&pageSize=0` | total=112 rows=0 | total=0 rows=0 |
| `carTrackQueryByTime?pageNum=999&pageSize=2` | total=112 rows=2（回夹末页） | total=0 rows=0（没 total 可回夹） |

第三条同时是 `07` 里 **P-PAGE-3 只算"部分闭环"** 的原因：`ClampToLastPage` 需要 total，
而这条路径上当时根本没有人算过 total。

## 3. 改动

| 位置 | 改动 |
|---|---|
| `internal/repo/zdata_trail_tracks.go` | 把 `getHistoryTrail` 的 `<where>` 抽成 `applyHistoryTrailFilters(tx, vo)`；新增 `CountHistoryTrail(ctx, vo)` 走**同一个**谓词函数 |
| `internal/service/sysutil.go` | 新增 `CarTrackCountNew`；`carlist → carNoList` 的拍平从三份收成一份 `flattenCarNoList`，取数与计数共用 |
| `internal/service/track_sync.go` | `CarTrackQuery` 里第三份重复的拍平改为调用同一 helper |
| `internal/handler/sysutil.go` | 两个轨迹接口改成 Java 的顺序：**先 count → `ClampToLastPage(total)` → 再取数**，响应体 `total` 用 count 而不是 `len(list)` |

两个刻意的设计约束，都各有一条测试守着：

1. **count 与取数必须出自同一套谓词。** Java 那边这是天然的（PageHelper 用原 SQL 生成 count），
   Go 一旦让 `CountHistoryTrail` 自己抄一份条件，两边就会各自演化，
   而"total 与数据各说各话"比原来的 `total=页大小` 更难发现。
   这正是 `P-FILT-1` 当年的成因，所以 `TestCountAndRowsSharePredicates` 锁死这一点
   （还顺带禁止 `CountHistoryTrail` 里出现 `LIMIT`——否则 total 又退化成页大小）。
2. **`Carlist` 为空时不能动 `CarNoList`。** count 与取数是对同一个 `vo` 调两次，
   第二次若把车牌列表清空，total 就变成"无车牌条件的全表计数"。
   `TestFlattenCarNoList` / `TestFlattenCarNoListIsIdempotent` 直接测行为（不是测源码文本）。

## 4. 实测证据

### 4.1 两端对打（本轮当场跑的）

| 用例 | Java :9902 | Go :9903 | 一致 |
|---|---|---|---|
| `carTrackQueryByTime?pageNum=1&pageSize=5` | 200 total=112 rows=5 | 200 total=112 rows=5 | ✅ |
| `carTrackQueryByTime?pageNum=1&pageSize=0` | 200 total=112 rows=0 | 200 total=112 rows=0 | ✅ |
| `carTrackQueryByTime?pageNum=1&pageSize=-1` | 200 total=112 rows=0 | 200 total=112 rows=0 | ✅ |
| `carTrackQueryByTime?pageNum=999&pageSize=2` | 200 total=112 rows=2 | 200 total=112 rows=2 | ✅ |
| `carTrackQueryByCarNo?carNo=粤DZW906&pageNum=1&pageSize=0` | 200 total=0 rows=0 | 200 total=0 rows=0 | ✅ |

行身份（不只是数量）：

```
pageNum=999&pageSize=2   两端都是 赣AEH8138  两条 uuid
                         4880c22b…、24d9ebdf…  —— 完全相同且同序
pageNum=1&pageSize=5     两端 5 条 uuid
                         ea025d4d… 3eb3aa48… cc89de21… 993d289c… 1e454394… —— 完全相同且同序
```

这一点值得单独记：`getHistoryTrail` 的 SQL **没有 ORDER BY**（Java 也没有，见 `06`），
所以"回夹到末页"本来完全可能选到不同的行。实测两端同序同记录，
是因为该表这批数据的物理顺序此刻对两端一致 —— **不是可依赖的保证**，
Java 同样如此，属既有的 P-PAGE-5/无排序翻页问题，本轮没有引入也没有消除。

### 4.2 只读交叉验证（不经过 HTTP，直查库）

用一个临时程序按 handler 的谓词直查（跑完即删，未入库）：

```
redis db1 car_list_jc: ok=true carlist=185
carNoList 去空后: 185 个
CountHistoryTrail   = 112          ← 与 Java 的 total 相同
裸 SQL 等价 count   = 112          ← 两条独立路径互相印证
GetHistoryTrail(5)  = 5 行
bannian(赣AK7388):   count=0 rows=0   ← 半年窗口内确实无数据，解释了 ByCarNo 的 total=0
```

（注意 `car_list_jc` 现在是 185 个车牌，与 r9 当时的 94 个不同——缓存被运维任务覆盖过。
`total=112` 仍然吻合，说明这 112 行只与"命中的那批车牌"有关，与列表总长无关。）

### 4.3 全量复跑 r10

| 轮次 | 条数 | OK | DIFF | STATUS | NONDET |
|---|---|---|---|---|---|
| r9（`07` 定稿） | 361 | 315 | 24 | 22 | 0 |
| **r10（本轮）** | 361 | **317** | **22** | 22 | **0** |

判定迁移逐条：

| 用例 | r9 | r10 |
|---|---|---|
| `cartrack-by-time-size0` | DIFF（total 112 vs 0） | **OK** |
| `cartrack-by-time-size-1` | DIFF（total 112 vs 0） | **OK** |

**OK→非OK 的回归：0 条。** `cartrack-by-time` 与 `cartrack-by-time-far` 仍是 DIFF，
但内容变了：`total` 那条 VALUE 差异已消失，剩下的只有 `null` vs `""`
（前者 256 处 NULLISH + 1 处 `sectionCode` 空串键；后者 28 处 NULLISH、已无任何其他类型）。

## 5. r10 的 44 条非 OK 全部归因

> **本节是 r10 口径**，第五轮（`10`）又关掉两条：P-SER-1 的 11 条全部转 OK、
> P-QRY-1 的错误契约 1 条转 OK 并把宽度差异补成 3 条用例。定稿看 `10` §6（r12，35 条）。

| 归属 | 条数 | 是 Go 缺陷吗 |
|---|---|---|
| P-JAVA-1..8（Java 端点自身 500，Go 反而能用） | 22 | 否 |
| P-JAVA-9（Java 降级 SQL 缺 schema，恒空 / Go 有值） | 4 | 否 |
| **P-SER-1**（`TrailBo`/`TrailInfo` 的 `null` vs `""`，含上面两条残留 DIFF） | 11 | 是（契约类，待你选 A/B） |
| **P-ERR-1**（404/405 响应体形状） | 6 | 是（待决策） |
| **P-QRY-1**（ES/DB 路由；本环境 mapping 为 `text`，无法有效实测） | 1 | 是（待决策） |
| **合计** | **44** | 无一条无归属 |

对照 `07` §7 的 46 条：**P-PAGE-8 的 3 条已清零**（其中 2 条转 OK，
第 3 条 `cartrack-by-time-far` 的 total 差异同步消失、只剩 P-SER-1，故并入 P-SER-1 计数，
11 = 原 10 + 1）。

## 6. 测试

`go build` / `go vet` / `gofmt -l`（空输出）/ `go test -count=1 ./internal/...` 6 包全绿。

规模从 `08` 记的 **29 个函数 / 6 个文件** 变为 **32 个函数 / 7 个文件**
（新增 `internal/service/sysutil_flatten_test.go`）：

| 新增 | 作用 |
|---|---|
| `TestCountAndRowsSharePredicates` | `GetHistoryTrail` 与 `CountHistoryTrail` 必须共用 `applyHistoryTrailFilters`；count 里不得出现 `LIMIT` |
| `TestFlattenCarNoList` | 空车牌要丢、`Carlist` 为空时不得清掉 `CarNoList` |
| `TestFlattenCarNoListIsIdempotent` | 同一 `vo` 连调两次结果不变（count 与取数共用它） |

同时把 `08` §3.1/§3.2 修好的两条断言随重构改了锁定点：
`TestCarNoAndCarNoListAreIndependentAnds` 现在锁 **`applyHistoryTrailFilters`** 函数体
（谓词已从 `GetHistoryTrail` 上移），`mustSource()` 的 CRLF 归一化保留。

### 变异验证（本轮重新做过）

| 注入的退化 | 结果 |
|---|---|
| `carNo` / `carNoList` 退回 `} else if len(vo.CarNoList) > 0 {` | **被抓** |
| `bannian` 分支删掉 `extime <= now()`（LF 与 CRLF 两种检出） | **被抓** |
| 投影常量删掉 `"enaxlecount, ` | **被抓** |
| `historyTrailRow` 删掉 `column:enaxlecount` 字段 | **被抓**（编译期：`toModel()` 引用不到该字段，`[build failed]`） |
| `CountHistoryTrail` 不走共享谓词、自己抄一份 `IN` | **被抓** |
| `CountHistoryTrail` 里加 `LIMIT` | **被抓** |
| snapshotflow 把 `ApplyOrder` 挪到自身 `Order` 之后 | **被抓**（已锁进 `List()` 函数体） |

> 更正一处记账：`08` §3.5 与本轮早先一次跑批里，"删结构体字段"被记成 *逃逸*。
> 那是分类器的错——它只匹配 `--- FAIL`，而编译失败的输出是 `[build failed]`。
> 实际两种情况都被抓到了。**测试逃逸 0 条。**

## 7. 与 `08` 需要对账的三点

1. `08` §5 写"测试函数个数不变（仍 29）"——本轮加了 3 个，现在 **32 / 7 文件**。
2. `08` §3.1 写"已重写为：把断言锁进 `GetHistoryTrail` 函数体"——谓词上移后锁定点是
   `applyHistoryTrailFilters`，语义不变。
3. `08` §4 把 P-PAGE-8 列为"仍未闭环、建议提到第一位"——本轮已关闭；
   未闭环清单见下面第 8 节。

## 8. 本轮之后仍未闭环

| 编号 | 内容 | 卡在哪 |
|---|---|---|
| P-SER-1 | `TrailBo` 28 个未赋值字符串 `null` vs `""`（≈106 处） | 需要你选：改 `*string` 还是加 `model.Nstr` |
| P-ERR-1 | 404/405 响应体形状（Spring 默认体 vs `AjaxResult`） | 全局兜底，改动面大，待决策 |
| P-ERR-2 | 未捕获异常 Go 200 / Java 500 | 同上 |
| P-QRY-1 | 时间格式决定走 ES 还是走库 | 本环境索引时间列被动态映射成 `text`，两端都跑不通该路径 |
| P-PAGE-5 | Go 取 `offset+size` 行再内存切片 | 与 Java 结果一致，属性能/翻页稳定性问题；改要动 19 个 repo 签名 |
| P-ENV-3 | `configs/config.yaml` 仍是 9901 + db0 | 配置/运维决策，`00` 已标红线 |

## 9. 复现

```bash
# 1) 单测（无需外部依赖）
cd car-monit-api-go && go test -count=1 ./internal/...     # 32 函数 / 6 包全绿

# 2) 端到端对打（需要 Java:9902 与 Go:9903 都在跑，Go 用 configs/config.verify.yaml）
cd car-monit-api-go/docs/parity-2026-11-02/tools
python parity.py --out r10 --md ../raw/r10.md              # 361 条判定
# 只看轨迹这几条：
python parity.py --case cartrack-by-time-size0 --out probe --md ../raw/probe.md
```

`raw/r10.jsonl` / `raw/r10.md` / `raw/run-r10.log` 是本轮产物；
`raw/*.http` 报文已随 r10 刷新（r9 的报文在 git 历史里，`git show 4fccd50:...` 可取）。
