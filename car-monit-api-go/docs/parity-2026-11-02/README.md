# Java ↔ Go 全接口对比校验（2026-11-02）

对照对象：`pro-business-api`（Java / Spring Boot，**:9902**）与 `car-monit-api-go`（Go / gin，**:9903**）。
本轮从头重做，不复用 10 月 `_probe` / `_probe_go` 的结论。

## 结论摘要

- **路由层 100% 对齐**：Java 85 个端点，Go 85 个，无缺漏无多余；`{agentPk}`/`{bigId}`/`{ds}`/`{taskId}` 等变量名一致，前端无需改 baseURL。
- **序列化可信**：358 条用例中 **TYPE / 数值精度 / 结构形状差异 0 处**（日期格式、Long 转字符串、空数组、信封都对得上）。
- **实测跑了 11 轮**（含 3 次复跑确认，判定逐条一致），`OK` 从 **208 → 315**（共 361 条），**每一轮都是零回归**：
  初测 208 → 拉平缓存 208（判定不变但归因改变）→ 修分页/过滤 287 → 修工具假差异 310 →
  修请求体契约与日期绑定 314 → 补 sysutil 边界用例后定稿 **315**（+1 OK / +2 新覆盖的 DIFF）。
  DIFF 101→24，STATUS 27→22，NONDET 22→**0**。
- 累计修掉 **16 项**：分页 4（截断 / `pageSize<=0` / 越界回夹 / `orderByColumn` 忽略）、过滤 3
  （`trailtracks` 丢条件、绑定错误静默吞、日期参数绑定按实测矩阵重写）、契约 2（非法请求体 400、结尾斜杠）、
  轨迹链路 4（`captureTime` 恒空、Go 自补 ORDER BY 换行、**历史轨迹少投影 15 列**、相对时间窗缺上界）。
- **剩余 44 条已无一条是"数据算错"**：21 条是 Java 自身 500、6 条是 404/405 响应体形状（待拍板）、
  5 条是 Java 降级 SQL 表名缺 schema（Go 正确）、10 条是 `TrailBo` 空串 vs null（待拍板）、2 条为翻页/排序边角。
- 轨迹富集链路实测已完全一致：`carTrackQueryByTime` 按车牌对齐后 **94/94 行内容零差异**，
  `trailList` 内 114 处差异**全部**是 `Java null ↔ Go ""` 这一类（零"值不同"）。
- **27 条 STATUS 中约 20 条是 Java 侧本身 500/400**（mapper 缺 bound statement、别名当列名），Go 反而能用；
  这类不能简单要求 Go 复刻，需按业务决定。
- **22 条 NONDET 是基准端自身不可复现**（共库 + 调度在写 + 多数 mapper 无 ORDER BY），不计入 Go 缺陷。
- 环境结论：Java 与 Go 的 Redis 分库后**缓存状态并不等价**
  （`sys_config:data_query` 只在 db1、`car_list_jc` 只在 db0），导致 `total=251 vs 900`、
  `carTrackQueryByTime` `112 vs 0` 这类"看起来像代码差异、其实是状态差异"的结果。
  且本机有共驻服务每 30 秒清空 db0 的 `sys_config:*`，**拉平只能动 Go 自己的 db1**。

## 文档导航

| 文件 | 内容 |
|---|---|
| `00_基线环境与校验口径.md` | 端口/进程身份、库与缓存隔离、判定分级标准 |
| `01_路由清单对比.md` | 85↔85 全量路由表、注释态接口处理、信封契约分布 |
| `02_差分实测结果.md` | 差分方法学（为什么不能直接对打）、分组结果、12 类系统性差异带原始证据 |
| `03_代码语义校验.md` | 谓词/排序/序列化/Redis key/定时任务/MQ/配置，含**被实测证伪的审阅结论** |
| `04_问题清单与修复建议.md` | 逐条编号 + 严重级 + 证据 + 修法；含修复状态与待决策项 |
| `05_修复记录与回归验证.md` | 缓存拉平过程与踩坑、Go 侧改动清单、回归数字、导出实测、剩余问题归类 |
| `06_第二轮深挖与逐项归因.md` | 剩余 71 条逐条打穿：工具假差异、Java 侧 8 个缺陷取证、日期绑定矩阵、投影缺列、时区校准、定稿数字 |
| `07_修复总结与闭环审查.md` | **交付总览**：16 项修复的追溯矩阵（代码位置 + 证据类型 + 是否闭环）、闭环审查新抓出的 3 个问题、未闭环清单 |

## 工具（可重跑）

| 文件 | 用途 |
|---|---|
| `tools/parity.py` | 差分主程序：两端对打、按主键对齐、逐字段比、**差异时先验证基准端自稳定性** |
| `tools/suite.py` | 用例表（358 条）：CRUD 的过滤条件由 Java 真实响应自我派生 |
| `tools/suite2.py` | 第二轮补测（29 条）：修正契约坑、打「需实测才能定论」的项 |
| `tools/routes.py` | 扫源码提取两端路由清单并对照 |
| `tools/predicates.py` | 机械对照 Java `<if>` 过滤列 vs Go `tx.Where` 列（19 张表） |
| `tools/redis_equalize.py` | 缓存状态拉平（带备份，可回滚） |
| `tools/export_probe.py` | 导出任务生命周期实测（只跑导出，不跑 `/large/sync/*`） |

```bash
cd car-monit-api-go/docs/parity-2026-11-02/tools
python parity.py --gen && python parity.py --out final --md ../raw/final.md
python suite2.py
python routes.py > ../raw/routes.txt
python predicates.py
python export_probe.py
```

写接口默认不执行（`--allow-write` 才跑），避免在共用库上触发全量同步、覆盖 Java 写入的 ES 文档。

## 原始数据

`raw/` 下每条用例都有 `<用例id>.java.http` / `<用例id>.go.http` 完整报文，
`raw/full-asis.jsonl`（358 条判定）、`raw/probe2.json`（29 条）、`raw/samples.json`（派生用例用的样本快照）。
文档里每个结论都能回溯到具体报文。
