# 阶段7 · BigDecimal 过滤参数绑定专项回归

针对 `06` §6 遗留项 2（「`filters_gen.rs` 的数字列过滤仍按 f64 绑定」）做的专项验证与修复。

- 生成器：`tools/v2/gen_decimal.py` → `.run/verify2/cases/decimal.json`（**85 例**）
- 结果：`.run/verify2/results/decimal.jsonl` → 修复前 **82 通过 / 3 不一致**，修复后 **85 / 85 通过**
- 命令：`python tools/v2/gen_decimal.py && python tools/v2/run.py --stage decimal --workers 4`

## 1. 为什么要单独测

Java 侧 MyBatis 对 `BigDecimal` 属性用 `setBigDecimal`，GaussDB/PostgreSQL 走 `numeric = numeric` 的**精确**比较。
Rust 侧原来是：

```rust
if let Some(x) = q.enweight.get() {          // JDecimal → f64
    v.push(Cond::EqF64("enweight", x));      // 绑定 double precision
}
```

参数一旦是 float8，PG 会把列隐式转成 float8 再比（`numeric → float8` 是 PG 的首选方向），
于是**超过 double 分辨率的值会被折成同一个数**。这不是格式差异，是**错结果**。

## 2. 用例设计（5 个 decimal 绑定点 × 17 变体）

覆盖点位（即 `filters_gen.rs` 里全部 5 个 `Cond::EqF64`）：
`/base/snapshotflow` 的 `lon`、`lat`；`/base/feeStationEnter` 的 `enweight`、`transfee`；`/base/feestationexit` 的 `feerate`。

| 变体 | 取值 | 意图 |
|---|---|---|
| `exact` | 真实值原样 | 对照：证明该字段确有命中行（用例非空转） |
| `eps_tail` | 真实值 + 15 个 0 + `1`（差值 1e-15 绝对量级） | ★ 低于 double 分辨率：一旦经过 double 就会「等于」真实值 |
| `tail` / `trunc` / `ulp` | 尾位加 `0001` / 去掉末位 / 末位减一 | numeric 域与 double 域是否同判 |
| `wide` / `wide2` | `9007199254740993` / `…992`（2^53±1） | double 无法分辨相邻整数 |
| `huge` / `tiny` | 30 位大数 / 1e-21 | 精度与量程边界 |
| `overflow` / `underflow` | `1e400` / `1e-400` | ★ 超出 double 量程：上溢 inf、下溢 0 |
| `sci` / `space` | `1.16038e2`、前后空格 | Java `BigDecimal(String)` 的宽松度 |
| `empty` / `junk` / `nan` / `inf` | 空串、`abc`、`NaN`、`Infinity` | Spring 绑定失败 → 400 的一致性 |

## 3. 修复前实测到的错结果（3 例）

| 用例 | Java | Rust（f64 绑定） | 判定 |
|---|---|---|---|
| `enweight=1e-400` | `total=0` | `total=10`（返回了 Java 不返回的行） | 错结果 |
| `transfee=1e-400` | `total=0` | `total=317` | 错结果 |
| `feerate=1e-400` | `total=0` | `total=210` | 错结果 |

机制：`1e-400` 转成 f64 直接**下溢成 0.0**，于是查询变成 `列 = 0`，把所有 0 值行都捞了出来。

## 4. 修复

| 位置 | 改动 |
|---|---|
| `src/repo/filters_gen.rs` | 5 个点位改为 `q.<col>.dec()` + `Cond::EqDecimal("col", x.clone())`（`EqDecimal` 绑定 `BigDecimal` → PG numeric） |
| `src/models/mod.rs` | `JDecimal` 的词法校验：只接受 Java `BigDecimal(String)` 允许的字符（数字/`+`/`-`/`.`/`e`），显式拒绝 `NaN`/`Infinity`——否则 bigdecimal 会接受它们，最后在 numeric 绑定处炸成 500，而 Java 是 400 |

## 5. 修复后专项结果（非空转证明）

| 字段 | `exact` 命中行 | `eps_tail` 命中行（双端） | 结论 |
|---|---|---|---|
| `feeStationEnter.enweight` | 116 | 0 / 0 | 有效：改前 `eps_tail` 会被折成 116 |
| `feeStationEnter.transfee` | 317 | 0 / 0 | 有效 |
| `feestationexit.feerate` | 210 | 0 / 0 | 有效 |
| `snapshotflow.lon` | 0 | 0 / 0 | **在本机数据集上空转**（该列在这几行里与过滤值不同域，Java 也 0 行），保留但不作为证据 |
| `snapshotflow.lat` | 0 | 0 / 0 | 同上 |

专项 85 例全通过；`underflow`、`overflow`、`nan`、`inf`、`junk`、`empty` 六个边界变体在 5 个字段上双端状态码与 total 全部一致。

## 6. 连带回归（确认无副作用）

改动了 SQL 参数类型与 `JDecimal` 的词法校验，因此重跑了全量只读矩阵：

| 阶段 | 用例 | 通过 | 可接受 | 不一致 |
|---|---|---|---|---|
| base | 1024 | 1024 | 0 | 0 |
| filters | 2349 | 2348 | 1 | 0 |
| query | 112 | 111 | 1 | 0 |
| contract | 134 | 126 | 8 | 0 |
| sysutil | 59 | 59 | 0 | 0 |
| decimal（新） | 85 | 85 | 0 | 0 |
| **合计** | **3763** | **3753** | **10** | **0** |

`cargo test`：`parity_test` 15 项 + `router_test` 6 项全绿。

## 7. 仍待观察

- `filters_gen.rs` 里其余数字列（JInt/JLong 走的 `Cond::EqI64`、JString 走的 `Cond::Eq`）未受本次影响：
  前者与 Java 的整数域一致；后者绑成 text，PG 会把未知字面量按 numeric 解析，与 Java 同域。
- `lon`/`lat` 两个点位希望在**有真实经度数据**的环境里再跑一遍 `eps_tail`，
  目前本机数据下该组用例是空转（表里对应行的 lon 与过滤值不同列/不同精度）。
- 结论：`Cond::EqF64` 现在只剩「列本身就是 float8」时才该用；当前 5 处已全部转走，
  `EqF64` 变为未使用变体（保留，未删，避免动 300+ 处生成代码的注释口径）。
