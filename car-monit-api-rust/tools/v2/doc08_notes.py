# -*- coding: utf-8 -*-
"""给 docs/verify/08-覆盖率审计.md 追加「结论与解释」一节（幂等：重复运行会覆盖该节）。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(ROOT, 'docs', 'verify', '08-覆盖率审计.md')

MARK = '\n## 5. 结论与解释'

BODY = MARK + """

### 5.1 这一轮补上了哪些原本零覆盖的端点

阶段 8 首次审计时，有 3 个端点**完全没被任何用例命中**，现在都已闭环：

| 端点 | 之前为什么漏 | 现在的用例来源 |
|---|---|---|
| `GET /base/{table}/{id}`（226 条 `{id}` 路径） | 生成器只在实体 `/list` 上锚定，`{id}`、`listAll`、`listToExport` 没挂进表结构 | `gen_cases.tables_from_inventory()` 改成两轮锚定（先实体 `/list`，再挂同表的其余读端点） |
| `GET /base/{table}/listAll`（7 条） | 同上 | 同上 |
| `GET /base/{table}/listToExport` | 同上 | 同上 |

另外 `gap` 阶段专门补了此前只用例名出现过、实际没打过的形状：`vehicleweight/map`（含裸路径与
带 `pageSize` 两种）、伪造的导出 taskId、`progressive/stats` 的多参数组合、`orderByColumn` 的
奇异写法（表别名 `t.id`、多列、空格、超长）。

### 5.2 弱覆盖（≤2 例）为什么不再加深

27 条弱覆盖集中在三类，**都不是「没测」而是「按设计只能测一次」**：

1. **`/base/sysutilTest/*`（14 条，1 例）**：Java 侧的同步/回填触发器，每次调用都会真的写
   共享库（`syncHistroyTrack`、`syncSuspiciousCar1..10` 等）。已在阶段 4b 用
   `write_probe.py` 实测过：状态码与响应体 20/20 一致，8 张观测表 total 未变。
   反复调用没有新的契约维度，只会重复写库，所以每个只留 1 例。
2. **`/api/v1/large/sync/*` 与 `unified/{ds}/export/submit`（4 条，1 例）**：同理（有副作用 +
   依赖外部 ES/Kafka，双端都稳定返回同一失败信封）。
3. **`listAll`（7 条，1 例）与 `progressive/scale-level`（2 例）**：无参数端点，参数矩阵对它
   没有意义；1 例足以覆盖全量响应体的逐字段比对（其中 `listAll` 的响应体是整表，
   一次比对就覆盖全部行）。

### 5.3 机读口径

- 端点清单：`inventory.py` 剥掉 Java 块注释/行注释后解析（`syncTrack`、`syncSuspiciousCar`
  这类被注释掉的映射不会被算成端点），Java 85 条 / Rust 84 条路由，差的是 Rust 自查端点
  `/selftest`（Java 无对应，反向差集已核对）。
- 命中判定：按 Spring/Ant 的**具体度**排序匹配（`/base/{table}/{id}` 不会吃掉
  `/base/toll/listAll`），所以「命中」表示该请求真的会落到这个 handler。
- 明细：`.run/verify2/coverage.json`（含每个端点的用例 ID）。
"""


def main():
    src = io.open(P, encoding='utf-8').read()
    i = src.find(MARK.strip())
    if i >= 0:
        src = src[:i]
    src = src.rstrip('\n') + BODY
    io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
    print('已写入 %s' % os.path.relpath(P, ROOT))


if __name__ == '__main__':
    main()
