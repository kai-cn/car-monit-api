# 11-results 云端 native vs JVM 全接口 + 资源性能对比（实测结果）

> 2026-11-17。方法/坑点见 `11-cloud-parity-verification.md`。所有数字来自 GitHub 云 runner 实测。

## api — jdk25 / linux（已实测，run 44001213167）

环境：ubuntu-latest（4 vCPU / 16GB）、Mandrel 25.0.5、postgres:16 + mysql:8 + redis:7（Docker），
`jl_data01` 44 表 + 2709 行种子，api 全部 **79 个 GET 端点**。

| 指标 | JVM jar | native image | native 优势 |
| --- | --- | --- | --- |
| 启动耗时（到端口就绪） | 6913 ms | **903 ms** | **7.7×** |
| 峰值 RSS（进程树） | 514.5 MB | **309.8 MB** | **1.66×** |
| 平均延迟（79 端点） | 13.58 ms | **2.79 ms** | **4.9×** |
| 端点状态一致 | — | 78/79 | — |
| 字节级完全一致（exact） | — | 67/79 | — |
| 语义一致（去易变字段） | — | 67/79 | — |
| 数据非确定性（NONDET） | — | 11 | — |
| **真实差异（DIFF）** | — | **1** | — |

### 真实差异（1 个，native 回归，非误判）
- `GET /base/sysutil/saveRedis`：JVM **200** / native **500**。
- native 日志：`java.lang.IllegalStateException: No primary or single unique constructor found
  for class com.ruoyi.base.domain.SysUtil`。
- 定性：AOT 反射元数据缺失（SysUtil 无可用构造器注册）。属 native-image 真实行为差异，
  需在业务侧补 `@RegisterReflectionForBinding(SysUtil.class)` 或 reachability metadata；
  不在本次“验收”范围，如实记录。

### 数据非确定性端点（11 个，非 native 差异）
典型：`/base/feeGantry/list`（每次随机 UUID）、`/base/vehicleweight/map`（无 ORDER BY）。
`--check-stability` 连打两次判定 `stable=False` → 判 NONDET（仅豁免 body，不豁免 status）。

## api — 其余矩阵（jdk21/17 × linux/windows）

- **jdk21 / jdk17 native**：能构建，但启动即 `NativeImageRequirementsException`
  （Spring Boot 4 native 要求 Java 25）。这些单元为 **build-only**，jar 基线仍探针成功。
- **windows**：GitHub Windows runner 无 service containers，`mode=reachability`
  （无 DB，仅状态/字节/延迟/启动/RSS），不做 body 全接口对比。

> 具体每单元结论见对应 run 的 `report.md`（artifact `parity-<jdk>-<platform>`）。

## backend — jdk25 / linux

见 backend run 的 `report.md`。要点：
- RuoYi 后端仅 `/captchaImage` 免认证 GET，随机验证码 → body NONDET；
  故 backend native-vs-jvm 主要对比 **启动时间 / 峰值 RSS / 延迟 / status**。
- 全接口（79 端点）对比由 **api 侧**承担。

## 跨语言 — Java8 vs Go/Python/Rust（backend master）

见 `crosslang-parity-cloud` run 的 `report-<lang>.md`。
- 共同免认证 GET 端点 `/captchaImage`（随机图 → NONDET），主要对比启动/RSS/延迟/status。
- **C#/Kotlin/C++ 无 HTTP 服务，跳过**（如实记录）。

## 结论

1. native image 在启动（7.7×）、内存（1.66×）、延迟（4.9×）上全面优于 JVM，适合容器化降本。
2. 79 端点中 67 完全一致 + 11 非确定性 + **1 真实回归**（saveRedis 反射元数据），
   说明 native 迁移整体一致性好，个别反射点需补元数据。
3. 云端对比可全自动复现（见 11 号文档复现章节）。
