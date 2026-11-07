# C++ 迁移工程决策记录（DECISIONS）

本文件记录本轮工程化推进（P0-P7）中的架构与工程取舍。每条包含：决策、备选方案、
理由、影响、可回退性。

---

## D-001 磁盘清理只删可再生构建产物

- **决策**：清理工作区内的 `build*` 目录、`_deps` 缓存、ctest 临时目录；不删源码、
  `.git`、日志中可能含证据的文件。
- **备选**：删除 `logs/`、历史构建产物与第三方源码缓存以腾出更多空间。
- **理由**：源码与 `.git` 不可再生；日志可能仍在排查中。构建产物体积占比最高，
  删除成本最低。
- **影响**：主工作区 4 个 `build*` 目录（约 490 MB）被删除；worktree 保留增量构建
  目录以避免重复下载 librdkafka。
- **可回退性**：完全可回退（重新 configure 即可）。注意：Windows 下删除的文件进入
  回收站，需手动清空回收站才会真正释放磁盘空间。

## D-002 编译告警：/W4 + -Wall -Wextra -Wpedantic，默认开启 -Werror

- **决策**：MSVC 使用 `/W4`，GCC/Clang 使用 `-Wall -Wextra -Wpedantic`；通过
  `CM_WERROR` 选项（默认 ON）把告警升级为错误。
- **备选**：保持 `/W3` / 不启用 `-Werror`，或只在 CI 中启用。
- **理由**：本轮已把本工程代码在 `/W4` 下清零告警，维护成本可控；`-Werror` 能防止
  新代码引入告警回退。保留 `-Wno-unused-parameter`、`-Wno-missing-field-initializers`
  是因为回调签名与聚合初始化在该工程中是有意为之，放开只会产生噪声。
- **影响**：新增告警会直接阻断构建；Linux 平台特有告警未在本机验证，若 CI 首次失败
  可用 `-DCM_WERROR=OFF` 解锁，修完后恢复默认。
- **可回退性**：`-DCM_WERROR=OFF` 即可关闭，无需改代码。

## D-003 第三方头文件使用 SYSTEM 包含

- **决策**：`third_party/{httplib,nlohmann}` 以 `SYSTEM` 方式包含（MSVC 生成
  `-external:W0`），并且告警选项按目标（`target_compile_options`）施加，不使用
  目录级 `add_compile_options`。
- **备选**：目录级统一告警；或对第三方头文件加 `#pragma warning(push, 0)`。
- **理由**：目录级选项会被 FetchContent 拉入的 librdkafka 子目录继承，其 C 代码在
  `/WX` 下会直接失败；`SYSTEM` 包含是 CMake 原生、跨编译器的隔离手段。
- **影响**：第三方头文件告警不参与 `-Werror` 判定；librdkafka 自身告警仍会打印，
  但不影响构建结果。
- **可回退性**：可回退，删除 `SYSTEM` 关键字即可。

## D-004 Sanitizer 选项仅支持 GCC/Clang

- **决策**：新增 `CM_SANITIZE`（取值 `address` / `undefined` / `address,undefined`），
  仅 GCC/Clang 生效；MSVC 下传非空值直接 `FATAL_ERROR`。
- **备选**：在 MSVC 上尝试 `/fsanitize=address`（VS2022 仅部分支持且与 Ninja 组合
  限制多）；或不做 sanitizer。
- **理由**：本机只有 MSVC，且 WSL 被禁用、无 Docker，无法本地验证 ASan/UBSan；
  选项接入 CI 的 Linux job 后在真实 GCC/Clang 下验证，避免“写了但没跑过”。
- **影响**：Windows 本地构建不受影响；Linux CI 增加一个 sanitizer 构建+测试 job。
- **可回退性**：删除选项与 `add_compile_options/add_link_options` 两处即可。

## D-005 `getenv` 统一封装为 `utils::get_env`

- **决策**：新增 `cm::utils::get_env`，MSVC 下使用 `_dupenv_s`，其他平台使用
  `std::getenv`；替换 `config.cpp` 与测试中的直接调用。
- **备选**：全局定义 `_CRT_SECURE_NO_WARNINGS` 压制 C4996。
- **理由**：全局压制会掩盖其他 CRT 安全告警；封装后语义明确（空值等同未设置），
  且不改变现有行为。
- **影响**：`get_env` 返回 `std::optional<std::string>`，调用点需解引用。
- **可回退性**：可回退，纯内部工具函数。

## D-006 CI 平台：GitHub Actions，Windows + Linux 双矩阵

- **决策**：使用 GitHub Actions（而非自建 Jenkins/GitLab CI），矩阵覆盖
  Windows(MSVC)、Ubuntu(GCC)、Ubuntu(Clang)，另加一个 Clang ASan/UBSan job 与
  一个静态分析 job。
- **备选**：仅保留本地 PowerShell 脚本；或引入 GitLab CI（当前仓库托管形态未确认）。
- **理由**：仓库已托管在 Git 平台且无既有 CI 配置，Actions 零基础设施成本；Linux
  矩阵能把此前“已修但未验证”的 POSIX 分支变成真实验证。本机 WSL 被禁用、无 Docker，
  Actions 是唯一可执行的 Linux 验证手段。
- **影响**：首次 push 前无法在本地执行 workflow，只能本地静态检查 YAML；若 Linux
  出现平台特有编译告警，`CM_WERROR` 可临时置 OFF 解锁。
- **可回退性**：删除 `.github/workflows/cpp-ci.yml` 即可，不影响构建。

## D-007 静态分析与格式检查的落地方式

- **决策**：
  - 静态分析用 **cppcheck**（`--enable=warning,performance,portability`），排除
    `third_party`，`--error-exitcode=1` 阻断；
  - 同时提供 `.clang-tidy` 配置供 IDE/本地使用，但暂不接入 CI（本机无 clang-tidy，
    全量接入无法先行验证，避免红叉）；
  - clang-format 只提供**基线配置** `.clang-format`，CI 只检查“相对基线变更的文件”，
    且当前为 `continue-on-error` 建议阶段。
- **备选**：一次性 `clang-format -i` 全仓格式化；或完全不引入格式检查。
- **理由**：全仓格式化会让本轮工程化 diff 与历史代码风格变更混在一起，难以审阅；
  增量检查能在新增代码上逐步收敛，不阻塞现有工作。
- **影响**：老文件不受格式约束；新改动文件会被提示。待全仓逐批格式化后，把
  `continue-on-error` 移除即可转为阻断。
- **可回退性**：删除配置与 job 即可。

## D-008 Linux 验证路径

- **决策**：Linux 构建/测试统一走 `scripts/ci-linux.sh`，CI 矩阵与 sanitizer job
  均调用同一脚本；本地无法验证时以 CI 结果为准。
- **备选**：在 Windows 上尝试 MinGW/Clang-cl 交叉验证。
- **理由**：MinGW 与目标 Linux 运行时差异大（POSIX socket、信号、文件系统语义），
  会给出虚假的安全感；MinGW 也不在本轮工具链假设内。
- **影响**：Linux 相关问题（socket 阻塞模式、`<fcntl.h>` 等）的最终确认依赖 CI
  首次运行；若 CI 不可用，则相关结论标注为“代码已修、待 Linux 实测”。
- **可回退性**：无代码耦合，仅流程约定。

## D-009 PG 客户端改用 libpqxx，Windows 侧引入 PostgreSQL 官方二进制包

- **决策**：用 libpqxx 7.10.0（FetchContent 源码）+ libpq 替换自研 wire v3。
  - Linux：系统 `libpq-dev`；
  - Windows：FetchContent 下载 PostgreSQL 官方（EDB 构建）17.2 Windows 二进制包
    （约 311 MB，SHA256 固定），只使用 `include/lib/bin`；运行时把 `libpq.dll`、
    `libssl-3-x64.dll`、`libcrypto-3-x64.dll`、`libintl-9.dll`、`libiconv-2.dll`、
    `libwinpthread-1.dll` 复制到可执行文件目录。
- **备选**：
  1. 从 PostgreSQL 源码自行构建静态 libpq：Windows 上需 Perl/NASM/OpenSSL，
     且 CMake 构建工程量大、无法启用 TLS，验证成本远高于收益；
  2. 仅 Linux 接入 libpqxx、Windows 保留自研实现：双实现长期维护，行为易漂移；
  3. 提供 `CM_PG_BACKEND=native` 回退开关：会把“已删除的自研认证/协议”重新拖回仓库。
- **理由**：官方二进制包来源可信、版本固定；Windows 与 Linux 行为一致；TLS 由
  包内 OpenSSL 3 提供。源码构建在无 Perl/NASM 的 Windows 环境下不可复现。
- **影响**：Windows 首次 configure 需下载约 311 MB（CI 已对 `build/_deps` 做缓存）；
  产物目录多 6 个 DLL（约 7 MB）；`third_party` 仍只保留头文件。
- **可回退性**：删除 CMake 中的 FetchContent/`PostgreSQL::PostgreSQL` 链接与
  `pg.cpp` 实现即可回退（需同时恢复旧实现，属较大回退）。

## D-010 参数绑定：SqlFragment + `$1..$n`，替代字符串拼接

- **决策**：新增 `repo::SqlFragment{sql, params}`、`bind_param`、`bind_in`、
  `append_fragment`（按已有参数数量重编号 `$n`）。DAO 过滤、按 ID 查询、
  导出/降级查询、字典回源、Kafka 落库等所有用户输入值统一走参数绑定；
  标识符仍由 EntityMeta / 白名单校验。
- **备选**：继续用 `quote()` 手工转义；或只在新代码使用参数绑定。
- **理由**：libpqxx 的 `exec(sql, params)` 能真正把值与 SQL 文本分离，
  彻底消除“转义遗漏”类注入面；`append_fragment` 解决多段 SQL 拼接时
  占位符编号冲突。
- **影响**：查询层函数签名由 `std::string where` 变为 `SqlFragment`；
  单测可直接断言 SQL 文本不含用户值、参数顺序正确。
- **可回退性**：`SqlFragment` 只是字符串 + 参数容器，可逐步退回字符串拼接。

## D-011 openGauss 专有 SHA256 认证不再由本工程实现

- **决策**：删除自研 MD5/openGauss SHA256/SCRAM 派生与 `auth-mode` 配置，
  认证完全交给 libpq。stock libpq 不支持 openGauss 的
  `SHA256(SHA256(password)‖salt)` 方案。
- **备选**：保留自研 SASL 分支以兼容 openGauss sha256。
- **理由**：用户明确要求删除派生实现；继续维护两套认证逻辑会持续产生
  “算法不匹配 → 失败登录 → 账号锁定”的风险。
- **影响**：若目标 openGauss 的 `password_encryption_type` 仅允许 sha256/sm3，
  连接会失败（28P01）。部署侧需改为 `password_encryption_type=1`（md5），
  或使用 openGauss 提供的定制 libpq。该限制已写入 COMPATIBILITY/MIGRATION_GUIDE。
- **可回退性**：需重新引入自研认证实现，回退成本高；因此在此显式记录。

## D-012 Redis 客户端改用 hiredis，暂不引入 pipeline

- **决策**：用 hiredis 1.5.0（FetchContent 静态库）+ hiredis_ssl 替换自研 RESP2。
  保持 `cache::Redis` 的对外命令接口；连接超时/命令超时由 `redisOptions`
  的 `connect_timeout` / `command_timeout` 处理；TLS 由 hiredis_ssl（OpenSSL 3）
  提供，默认关闭（与 Java 侧一致）。
- **备选**：
  1. 保留自研 RESP2 并补 TLS/超时：需自行维护 RESP3/RESP2 边界、SSL、重连状态机；
  2. 引入 Redis++ 等 C++ 封装：依赖更重，且会引入连接池/线程模型改动；
  3. 接入 pipeline：当前代码无批量命令调用点，加了也无调用方。
- **理由**：hiredis 是 Redis 官方 C 客户端，协议/超时/TLS 成熟；同步 API 与现有
  “单连接 + 互斥锁”语义完全匹配，改造面最小。hiredis 1.2 的 CMake 最低版本
  低于 CMake 4 的下限，故选用 1.5.0。
- **影响**：并发吞吐仍受单连接 + 互斥限制（与改造前一致，已在 COMPATIBILITY 标注）；
  单连接模型在高并发下是已知瓶颈，后续如需可再引入连接池/pipeline。
- **可回退性**：`Redis` 接口未变，可替换回自研实现；但 TLS/超时能力会随之丢失。

## D-013 查询质量：运行期列展开、字典本地缓存、深翻页标注

- **决策**：
  1. `meta::select_columns` 在运行期把 `select_sql == "*"` 的实体按 `fields` 的物理列
     展开（跳过空列、按列名去重），所有 SELECT 入口统一走该函数；
  2. 字典在 Redis 缓存之上增加进程内缓存（TTL 300s，可显式失效）；
  3. `weight_capture_map` 先查 Redis，再按 100 个 uuid 批量回源；
  4. 深翻页保持 `LIMIT/OFFSET`（与 Java PageHelper 一致），count 查询去掉
     `ORDER BY`，并在 COMPATIBILITY 标注 O(offset) 为已知限制。
- **备选**：
  1. 直接改 `entities_generated.h` 里 20 处 `*`：文件为自动生成，手改会破坏
     “可重新生成”的约束；
  2. 不加入本地缓存，只做批量回源：track 处理每个点位时仍会重复 Redis GET +
     JSON 解析 + map 重建；
  3. 引入 keyset pagination：会改变 API 分页语义，与 Java 行为不一致。
- **理由**：运行期展开不触碰生成文件，且测试能直接断言映射列齐全；本地缓存
  在保持 Redis 共享缓存的前提下把高频字典读取降为进程内操作。
- **影响**：`select_columns` 每次调用会拼接字符串（对每请求一次可忽略）；本地字典
  缓存最多滞后 5 分钟（已在 COMPATIBILITY 标注）。
- **可回退性**：三处均可独立回退（恢复 `select_sql` 直接用、去掉 memo_map、
  改回逐条回源）。

## D-014 契约测试：路由黄金基线 + 只读采集/diff 脚本

- **决策**：
  1. `contracts/endpoints.golden.json` 固化为 87 条路由（85 业务 + `/health`、
     `/metrics`）的 method/path/响应形态，由 `carmonit_tests` 生成与校验；
     更新基线需显式设置 `CM_UPDATE_CONTRACT_GOLDEN=1`；
  2. `scripts/contract-collect.ps1` 只发 GET（跳过写方法），按端点保存
     status/contentType/body，Java 与 C++ 用同一脚本采集；
  3. `scripts/contract-diff.ps1` 做 JSON 结构 diff，忽略时间戳/自增 id/分页 total
     等易变字段，数组按元素排序后比较。
- **备选**：
  1. 立刻生成 85 份请求/响应样本文件：没有真实响应时只能凭空构造，校准价值低；
  2. 用 Postman/Newman 集合：引入额外运行时依赖，且与本仓库脚本化流程不一致。
- **理由**：先把“路由与响应形态”固化为可阻断的基线，等 DB 解锁后一条命令采集
  Java 真实响应再 diff；采集结果不入库（避免生产数据/凭据进版本库）。
- **影响**：当前基线只覆盖 method/path/kind，精确 body 契约待采集；
  **Java 9902 在 2026-11-08 探测为不可达（连接被拒绝），标记为待采集**。
- **可回退性**：删除脚本与基线文件即可，不影响构建与测试。

## D-015 可观测性与运维：双格式指标、JSON 日志、停机超时、不做热重载

- **决策**：
  1. `/metrics` 默认 JSON（保持既有契约），`?format=prometheus` 输出 Prometheus
     文本；指标含请求量、错误率、延迟 P50/P95/P99、状态码分类、依赖状态/延迟、
     后台线程池队列深度；
  2. 依赖探活 5s 缓存；DB/Redis 只在已有连接上做轻量探测，**绝不新建连接**；
     ES/Kafka 为被动状态（不主动探测/无同步探测接口）；
  3. 结构化日志为可选开关（`logging.json`/`CM_LOG_JSON`），每行携带 requestId；
     HTTP 层生成/透传 `X-Request-Id` 并回写响应头；
  4. 优雅停机增加硬超时 `server.shutdown-timeout-ms`（默认 30s），超时强制退出；
  5. **不支持 SIGHUP/配置热重载**：改配置需重启，避免半热更状态。
- **备选**：
  1. 把 `/metrics` 直接改成 Prometheus 文本：会破坏已有 JSON 消费方；
  2. 每次 scrape 主动连 DB/ES 做真实探活：可能在 DB 未就绪时制造失败登录/慢请求；
  3. 实现 SIGHUP 重载：涉及线程池、连接池、调度器的重建，收益低且风险高。
- **理由**：保持契约兼容的同时满足 Prometheus 采集；探活不制造副作用；JSON 日志
  可按需开启，默认文本日志不改变现有排障习惯。
- **影响**：依赖延迟为“探活耗时”，不是业务调用耗时；ES/Kafka 延迟固定为 0。
- **可回退性**：各项独立可回退（删除 query 分支/开关/超时逻辑）。






