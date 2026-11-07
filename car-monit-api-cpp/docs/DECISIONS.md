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
