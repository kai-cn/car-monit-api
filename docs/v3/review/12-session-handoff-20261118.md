# 12. 会话交接（2026-11-18 起，含 11-20 Java POM 升级收口）

## 11-18 基线
- workflow 全量扫描 `BAD=0`；H9 Go/Python 通过；H8 后续已在 11-20 收官。
- 工作记忆与脚本索引位于 `D:/work/runtime-logs/`。

## 2026-11-20 Java POM 升级收口
- api/backend master 升级到 Spring Boot 2 最终版 2.7.18；全部 Java 分支 POM 依赖以 Boot BOM 为版本基准。
- api 所有 Java 分支完成 Jedis → Lettuce（`spring-boot-starter-data-redis` + LettuceClusterClient）。
- 新增 Java-only workflow `java-upgrade-verify.yml`，避免 Boot2 分支被 Python/DB fixture/native clean 等非 Java job 阻断。
- 16/16 Java 分支云 runner run success，证据 `D:/work/runtime-logs/java-upgrade-runs.json`。
- GitHub 认证改为本地 token 缓存 helper，git credential fill/push 不再弹账号选择框。
- 当日工作记忆：`.workbuddy/memory/2026-11-20.md`。


## 2026-11-21 Native/跨语言重跑
- Boot3/Boot4 10 个 Java 分支 native success；Boot2 无 native profile，N/A。
- crosslang-parity-cloud success；11/11 云任务 success，证据 `native-crosslang-status.json`。
- Mandrel25 + Lombok annotationProcessorPaths + LOG_PATH 修复完成。
- 157 个历史脚本补齐注释，复扫 0 缺失。

## 2026-11-22 Java JUnit 与 Java25 跨语言全量验证收官

- Java JUnit 全接口/压测：16/16 run success（backend 7、api 9），证据 `D:\work\runtime-logs\java-junit-results.json`。
- Java25 Boot4 crosslang：backend `44983230639`、api `44983238487`；baseline + python/go/cpp/rust 全部 job success。
- 证据：`D:\work\runtime-logs\crosslang-evidence.json` / `crosslang-evidence.md`；对齐差异如实记录，未用断言掩盖。
- 本地复跑：JUnit 生成/Java8 编译 2/2、workflow YAML 4/4、脚本注释 TOTAL_MISSING 0、stub 驱动 contract/load rc=0/0 errors=0。
- 关键修复：AOT skip、sudo 日志目录、Corretto 8、lazy init/Kafka exclude、artifact 携带 JUnit jar、候选启动命令与环境修正。

## 2026-11-22 最终全量验证报告引用

- 最终报告：`docs/v3/review/13-final-junit-crosslang-20261122.md`
- Java JUnit：16/16 success。
- crosslang workflow：backend `44983230639`、api `44983238487`，baseline + python/go/cpp/rust 全部 job success。
- 对齐差异与压测比值为 artifact 真实记录，未用断言掩盖。

