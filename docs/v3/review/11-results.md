# 11-results 云端 native vs JVM / 跨语言 全接口 + 资源性能对比（实测结果）

> 2026-11-17。方法/坑点见 `11-cloud-parity-verification.md`。数字全部来自 GitHub 云 runner 实测。
> 环境：ubuntu-latest（4 vCPU/16GB）或 windows-latest；Mandrel 按分支 pom 的 java.version 自动选择；
> postgres:16 + mysql:8 + redis:7（Docker）；api `jl_data01` 44 表 + 2709 行种子。

## 1. api — native vs JVM（jdk25 / linux，**完整 79 端点**，run 44001213167）

| 指标 | JVM jar | native image | native 优势 |
| --- | --- | --- | --- |
| 启动耗时（到端口就绪） | 6913 ms | **903 ms** | **7.7×** |
| 峰值 RSS（进程树） | 514.5 MB | **309.8 MB** | **1.66×** |
| 平均延迟（79 端点） | 13.58 ms | **2.79 ms** | **4.9×** |
| 状态一致 | — | 78/79 | — |
| 字节级一致（exact） | — | 67/79 | — |
| 语义一致 | — | 67/79 | — |
| 数据非确定性（NONDET） | — | 11 | — |
| **真实差异（DIFF）** | — | **1** | — |

**真实差异**：`GET /base/sysutil/saveRedis` JVM 200 / native 500。
native 日志：`IllegalStateException: No primary or single unique constructor found for class
com.ruoyi.base.domain.SysUtil`（AOT 反射元数据缺失）。属 native 迁移需补
`@RegisterReflectionForBinding` 的真实待办，非误判。

## 2. api — 各 JDK × 平台矩阵

| 分支 | 平台 | JVM 基线 | native | 结论 |
| --- | --- | --- | --- | --- |
| jdk25 | linux | ✅ 79 端点 | ✅ 运行成功 | 完整对比（见 §1） |
| jdk25 | windows | ✅ | ✅ 构建+reachability | Windows 无 DB，仅状态/资源 |
| jdk21 | linux | ✅ 79 端点（7815ms/596.9MB） | ⚠️ 构建成功、**运行 rc=1** | Boot4 native 需 JDK25 |
| jdk21 | windows | ✅ | ⚠️ 同上 | 同上 |
| jdk17 | linux | ✅ 79 端点（8718ms/695.3MB） | ❌ **构建失败**（Mandrel23 无法处理 Boot4） | 同上 |
| jdk17 | windows | ✅ | ❌ 同上 | 同上 |

结论：**Boot4（Spring Boot 4.1.2）的 native 只有 JDK25 能真正构建并运行**；
JDK17/21 的 native 不可用，但 JVM 基线 79 端点全部探针成功，证明工具链与数据准备有效。

## 3. backend — native vs JVM（RuoYi，Linux）

| 分支 | JVM 基线 | native | 说明 |
| --- | --- | --- | --- |
| jdk17 | ✅ 2 端点（12326ms/776.6MB） | ❌ build-only | Boot4 native 需 JDK25 |
| jdk21 | ✅ 2 端点 | ❌ build-only | 同上 |
| jdk25 | 运行中 | 运行中 | 见最终 run |

backend 端点几乎全需认证，仅 `/captchaImage`（随机验证码 → NONDET）与 `/` 可探；
故 backend 对比侧重**启动时间/RSS/延迟/状态**，全接口（79 端点）对比由 api 侧承担。

## 4. 跨语言 — Java8 vs Go / Python / Rust（backend master，run 44006210631）

| 变体 | 启动 | 峰值 RSS | 端点 | 结论 |
| --- | --- | --- | --- | --- |
| **Java8（基线）** | 903 ms | 134.4 MB | 2 | — |
| **Go** | **302 ms** | **15.3 MB** | 2 | 启动快 3×、内存省 8.8× |
| Rust | 启动失败（rc=1，68768ms） | 10.7MB | 0 | 见坑点 |
| Python | 探针/依赖失败 | — | 0 | 见坑点 |
| C# / Kotlin / C++ | — | — | — | **无 HTTP 服务，跳过** |

Go 的 2 个端点判 `MISSING`（/captchaImage、/ 在 Go 侧路径未匹配到基线）——
说明 Go 的 `/captchaImage` 路由前缀与 Java8 不同（或 Go 需 context-path），属需要跑通配置的
真实差异，如实记录（非 native/JVM 问题）。

## 5. 结论

1. **native image 相对 JVM 全面占优**：启动 7.7×、内存 1.66×、延迟 4.9×，适合容器化降本。
2. **接口一致性极好**：79 端点 67 完全一致 + 11 非确定性 + 1 真实回归（saveRedis 反射），
   native 迁移整体可靠，个别反射点需补元数据。
3. **Go 资源最优**（15.3MB RSS），但端点路径需与 Java 对齐才能做接口等价判定。
4. 云上全自动可复现（见 11 号文档复现章节 + 跨语言 workflow）。

## 6. 未完成/受限项（如实记录）
- Rust/Python 跨语言探针未跑通（Rust 启动 rc=1、Python 依赖/配置失败）——需进一步调配配置。
- Windows 单元无 DB 级 body 对比（GitHub Windows runner 无 service containers）。
- JDK17/21 的 native 不可用（Boot4 限制）。
