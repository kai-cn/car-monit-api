> 文件用途：给 Java 基准项目（`car-monit-api`，RuoYi 结构）提 Issue 的**描述草稿**。
> 取证脚本与数据都在 `car-monit-api-rust` 侧，路径见文末。

---

# Issue 草稿

**标题**：`startPage()` 后 MyBatis 查询未执行时 PageHelper 的 ThreadLocal 不被清理，导致**无关接口**的查询结果被静默截断

**类型**：Bug（数据正确性）
**严重级别**：High —— 会让接口返回不完整数据集而响应看起来完全正常（`total` 仍然正确）
**影响组件**：`pro-base-common`（`BaseController` / `PageUtils`）+ `pro-business-api`（`OdsLwzxsfsjFeeRecords01Controller` 三条路由）
**影响接口**：所有「查询走 MyBatis 但自己不调 `startPage()`」的读接口，已确认的有
`/progressive/snapshotflow/list`、`/progressive/feerecords/list`、`/progressive/trailfitting/list`

---

## 1. 现象

`/base/feerecords/list` 与 `/base/feerecords/listToExport` 稳定返回 500（`BindingException:
Invalid bound statement (not found): ...selectOdsLwzxsfsjFeeRecords01List`，缺 Mapper XML）。

这两个请求在抛错之前已经调用过 `startPage()`，分页参数被放进 PageHelper 的 `ThreadLocal`，
而**没有任何代码清理它**。Tomcat 的工作线程是池化的，于是这条残留会一直留在该线程上，
直到该线程执行下一个 MyBatis 查询 —— 那个查询属于**别人的请求**，会被这条残留的
`pageSize` 加上 `LIMIT`，并且额外跑一次 count 查询。

复现后的实测数据（本机，双端同库同表）：

```
受害者基线（全新连接，30 次）        : {900: 30}          ← /progressive/snapshotflow/list?pageSize=
铺 30 个 /base/feerecords/list?pageSize=2（全部 500）
紧接着测受害者（30 次）              : {2: 10, 900: 20}   ← 10 次被截成 2 行（= plant 的 pageSize）
被截断响应样例                       : (200, rows=2, total=900)
再测一轮（30 次）                    : {900: 30}          ← 残留已被逐个消费掉，故障「时有时无」
```

关键点：**HTTP 状态码 200、`total` 正确、只有 `rows` 变少**，客户端和监控都看不出异常。
这也是为什么它一直没被发现 —— 它不是稳定失败，而是概率性丢数据。

## 2. 复现步骤

前置：Java 服务在 `127.0.0.1:9902`（`-Dserver.port=9902 -jar pro-business-api-1.0.jar`），
共享 GaussDB 里 `ods_rt_szdn_snapshot_flow_addcode` 有 900 行、`zdata_trail_tracks` 有 1379 行。

```bash
# ① 确认受害者正常
curl -s 'http://127.0.0.1:9902/progressive/snapshotflow/list?pageSize=' | jq '.rows|length'
# → 900

# ② 制造残留（同一线程；需要多试几次让线程池里多个线程被污染）
for i in $(seq 1 30); do curl -s -o /dev/null 'http://127.0.0.1:9902/base/feerecords/list?pageSize=2'; done

# ③ 立刻再测受害者：约 1/3 的请求返回 2 行，但 total 仍是 900
for i in $(seq 1 30); do curl -s 'http://127.0.0.1:9902/progressive/snapshotflow/list?pageSize=' \
  | jq -c '[.rows|length, .total]'; done | sort | uniq -c
# 期望：全部 [900,900]；实际：出现若干 [2,900]
```

现成脚本（含计数与衰减观察）：`car-monit-api-rust/tools/v2/pagehelper_leak_repro.py`

同一形状的其它泄漏源（同样第一行就 `startPage()`、同样缺 statement）：
`/base/feerecords/listToExport?pageSize=2`。

> 注意：`/base/feerecords/{bigId}` **不是**泄漏源（`getInfo` 里没有 `startPage()`，见
> `OdsLwzxsfsjFeeRecords01Controller.java:201-203`），它只是另一个会失败的接口，
> 同样可能成为被污染的受害者。

## 3. 根因（代码位置）

| # | 位置 | 事实 |
|---|---|---|
| 1 | `pro-base-common/.../core/controller/BaseController.java:53-56` | `startPage()` → `PageUtils.startPage()`，在**业务代码之前**把分页参数写入 ThreadLocal |
| 2 | `pro-base-common/.../utils/PageUtils.java:18-26`（关键行 `:25`） | `PageHelper.startPage(pageNum, pageSize, orderBy).setReasonable(reasonable)`；`pageNum`/`pageSize` 缺省为 1/10（`TableSupport.java:44-45`），**不传参数也会分页** |
| 3 | `pro-base-common/.../core/controller/BaseController.java:74-77`、`PageUtils.java:31-34` | 框架其实提供了 `clearPage()`，但**全项目 Java 代码没有任何调用点**，也没有 `try/finally`、Filter、Interceptor 或切面做兜底清理（`grep -rn clearPage` 只命中这两个定义处） |
| 4 | `pro-business-api/.../OdsLwzxsfsjFeeRecords01Controller.java:46-51, :79` | `list()`：`:48 startPage()` → `:51` 读 Redis → 中间还有条件装配与循环 → `:79 selectOdsLwzxsfsjFeeRecords01List(...)` **抛 BindingException**，PageHelper 的拦截器从未被执行，因此它自己的 `finally { clearPage }` 也没机会跑 |
| 5 | 同上 `:123-125, :155` | `listToExport()`：同样 `:125 startPage()` 打头、`:155` 同一个缺失 statement |
| 6 | `pro-business-api/.../mapper/OdsLwzxsfsjFeeRecords01Mapper.java:24,32,39,41` vs `.../mapper/xml/OdsLwzxsfsjFeeRecords01Mapper.xml`（源码与 `target/classes` 两份完全相同，共 41 行） | 接口声明了 5 个方法，XML 里**只有 `selectByCursorShard` 一个** `<select id=...>`；`selectOdsLwzxsfsjFeeRecords01List`、`...ById`、`selectGantryNum`、`...ListNew` 四个 id 全项目无定义。XML 确实被加载（`application.yml:106 mapper-locations: classpath*:com/ruoyi/base/**/xml/*Mapper.xml`），所以是 statement 缺失而非 namespace 未注册 |
| 7 | `pro-base-common/pom.xml:171-176` | `pagehelper-spring-boot-starter:1.4.7`（解析到 pagehelper 5.3.3）；`application*.yml` 里**没有** `pagehelper:` 配置段，`supportMethodsArguments=false` → ThreadLocal 是唯一生效途径，没有自动参数模式兜底 |
| 8 | `pro-business-api/.../ProgressiveQueryController.java:53-86`（`:83 getDataTable(...)`） | 受害者：方法体内**没有** `startPage()`，但走 MyBatis 查询并调用 `getDataTable()`。同文件 `:92/:119`、`:128/:155` 形状相同 |
| 9 | `pro-base-common/.../core/controller/BaseController.java:83-91` | `getDataTable()` 用 `new PageInfo(list).getTotal()` 取总数 —— 被污染时 list 是 PageHelper 的 `Page`，count 查询给出**正确的全量 total**，`rows` 却是被 `LIMIT` 截断的，正好解释了「total 对、数据少」这种最危险的形态 |

一句话根因：**`startPage()` 与「实际执行查询」之间没有事务性的配对**。任何让查询没跑起来的分支
（异常、提前 return、走缓存没走 DB）都会把分页状态泄漏给线程上的下一个请求。

## 4. 影响

1. **静默丢数据**：受影响接口返回 200 + 正确 `total` + 不完整 `rows`。分页组件会显示
   「共 900 条」但只有 2 条，用户表现为「数据缺失/翻页空白」。
2. **随线程调度出现/消失**，与请求本身无关，单请求测试与线上常规回归都抓不到。
3. **额外的 count 查询**：被污染的那次查询会被 PageHelper 强加一次 `SELECT COUNT`，
   在大表上是无谓的 DB 负担（也可能放大慢查询）。
4. **受害面不只 progressive 三个接口**：任何「调 MyBatis 但自己不调 `startPage()`」的读接口
   都可能被污染，包括 `listAll` 这类应当返回全量的端点。
5. 只要 `/base/feerecords/list` 被访问（前端菜单、巡检脚本、拨测都会打），
   污染就会持续产生。

## 5. 建议修复

**A. 最小且必须（消除泄漏本身）**：把「`startPage()` → 查询」写成配对结构，异常路径必清理。

```java
// BaseController
protected void startPage() { PageUtils.startPage(); }

// 推荐新增一个受控版本，业务里用它替代裸 startPage()
protected <T> List<T> queryPaged(Supplier<List<T>> query) {
    try {
        PageUtils.startPage();
        return query.get();
    } finally {
        PageUtils.clearPage();   // 现成方法（BaseController.java:74-77），目前全项目无人调用
    }
}
```

调用方示例：

```java
// OdsLwzxsfsjFeeRecords01Controller#list
List<OdsLwzxsfsjFeeRecords01> list = queryPaged(
        () -> odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01List(param));
return getDataTable(list);
```

**B. 全局兜底（推荐同时做，防止其它路由重犯）**：加一个 after-completion 清理，
把「清理」变成框架责任而不是每个 controller 的自觉。

```java
@Component
public class PageHelperCleanupInterceptor implements HandlerInterceptor {
    @Override public void afterCompletion(HttpServletRequest r, HttpServletResponse s,
                                          Object h, Exception ex) {
        PageHelper.clearPage();     // 覆盖异常、提前 return、静态资源等所有出口
    }
}
```

**C. 根治失败路由**：补 `OdsLwzxsfsjFeeRecords01Mapper.xml` 缺失的 4 个 statement
（`selectOdsLwzxsfsjFeeRecords01List`、`...ById`、`selectGantryNum`、`...ListNew`），
或把这 3 条路由摘掉。**注意**：只补 XML 只能让这三个接口不再 500，
其它「`startPage()` 后异常/提前返回」的路径仍然会泄漏，所以 A/B 才是修这个缺陷的关键。

## 6. 验证方法

```bash
# 修复前：阶段2 会出现 rows=2；修复后应当恒为 900
python tools/v2/pagehelper_leak_repro.py
# 期望输出：
#   [java] 阶段0 基线 N=30 行数分布: {900: 30}
#   [java] 阶段2 立刻测受害者: {900: 30}  → 被截断 0/30（0%）
```

补充：并发一致性回归（`tools/v2/concurrency.py --workers 24 --rounds 6`）在修复后应当
不再出现 `pr:presence:09` 的 `rows 2 ↔ 900` 抖动。

## 7. 附：取证数据与工具

| 内容 | 位置（`car-monit-api-rust`） |
|---|---|
| 概率化复现（铺残留 → 测截断 → 看衰减） | `tools/v2/pagehelper_leak_repro.py` |
| 同连接紧邻形状 | `tools/v2/pagehelper_leak_probe.py` |
| A/B：污染范围与持续长度 | `tools/v2/pagehelper_leak_scope.py` |
| 泄漏源候选清单扫描 | `tools/v2/pagehelper_leak_sources.py` |
| 并发一致性（Java 6/924 异常、Rust 0） | `tools/v2/concurrency.py` → `.run/verify2/results/concurrency.jsonl` |
| 结论与讨论 | `docs/verify/12-并发一致性与状态隔离.md`、`docs/verify/09-已知差异与根因.md` §4b（D5） |

对照参考：迁移到 Rust 的实现（每请求从 query 解析分页、直接写 `LIMIT/OFFSET`，无跨请求线程状态）
在同一清单 21 轮中**从未**被截断（受害者恒 1526/900 行），可作为「无泄漏」基线。

---

## 草稿使用说明（不随 Issue 提交）

- 建议正文保留 §1–§6，把 §7 的表折叠成附件；`pagehelper_leak_repro.py` 可改成纯 curl 版本后附到 Issue。
- 若需要更硬的线程证据，可在 §2 步骤③前加一段临时日志打印 `PageHelper.getLocalPage()` 与
  `Thread.currentThread().getName()`（`BaseController.startPage()` 内一行即可），
  能直接看到「A 请求设置的页被 B 请求消费」。
