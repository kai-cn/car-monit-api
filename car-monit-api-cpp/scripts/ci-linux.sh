#!/usr/bin/env bash
# Linux 构建与单测脚本（对应 Windows 侧 MSVC+Ninja 流程，见 README_CPP.md §3）。
#
# 用法：
#   ./scripts/ci-linux.sh                 # 默认 build-linux 目录，Release
#   ./scripts/ci-linux.sh -DCM_WITH_KAFKA=OFF    # 离线/无 Kafka 场景（透传任意 CMake 参数）
#
# 依赖：cmake >= 3.20、ninja、g++ >= 10（C++20）、libpq-dev（libpq 头/库）。
# 首次 configure 需要联网下载 librdkafka 2.6.1 与 libpqxx 7.10.0（FetchContent）；
# 离线环境：
#   -DFETCHCONTENT_SOURCE_DIR_LIBRDKAFKA=<本地 librdkafka 源码目录>
#   -DFETCHCONTENT_SOURCE_DIR_LIBPQXX=<本地 libpqxx 源码目录>
#   -DFETCHCONTENT_SOURCE_DIR_POSTGRES_WINDOWS=<仅 Windows 需要>
# 或 -DCM_WITH_KAFKA=OFF 退回 Redis 队列降级路径。
set -euo pipefail
cd "$(dirname "$0")/.."

BUILD_DIR="${BUILD_DIR:-build-linux}"
echo "==> 配置：cmake -S . -B ${BUILD_DIR} -G Ninja -DCMAKE_BUILD_TYPE=Release $*"
cmake -S . -B "${BUILD_DIR}" -G Ninja -DCMAKE_BUILD_TYPE=Release "$@"
echo "==> 构建"
cmake --build "${BUILD_DIR}" --parallel
echo "==> 测试"
ctest --test-dir "${BUILD_DIR}" --output-on-failure
echo "==> Linux 构建与单测通过"
