#!/usr/bin/env bash
# 增量格式检查（clang-format）。
#
# 背景：仓库尚未整体格式化，一次性全仓格式化会产生巨大的、与功能无关的 diff。
# 因此本脚本只检查“相对基线发生变更的 C++ 文件”。CI 中当前为建议阶段
# （continue-on-error），逐批格式化后再切换为阻断。
#
# 用法：
#   ./scripts/format-check.sh                 # 基线自动推断（origin/main → origin/master → HEAD~1）
#   ./scripts/format-check.sh origin/main     # 显式指定基线
#   BASE_REF=origin/main ./scripts/format-check.sh
#
# 依赖：clang-format（版本建议 15+，与 CI 的 apt 包一致）。
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v clang-format >/dev/null 2>&1; then
  echo "未找到 clang-format，跳过格式检查" >&2
  exit 0
fi

base="${1:-${BASE_REF:-}}"
if [ -z "${base}" ]; then
  for candidate in origin/main origin/master HEAD~1; do
    if git rev-parse --verify --quiet "${candidate}" >/dev/null; then
      base="${candidate}"
      break
    fi
  done
fi

if [ -n "${base}" ]; then
  # --relative：输出相对于当前目录（工程根）的路径。
  mapfile -t files < <(git diff --relative --name-only --diff-filter=ACMR "${base}"...HEAD -- '*.cpp' '*.h' '*.hpp' | grep -v '^third_party/' || true)
else
  echo "找不到基线，改为检查全部已跟踪 C++ 文件" >&2
  mapfile -t files < <(git ls-files '*.cpp' '*.h' '*.hpp' | grep -v '^third_party/' || true)
fi

if [ ${#files[@]} -eq 0 ]; then
  echo "无变更的 C++ 文件，跳过格式检查"
  exit 0
fi

echo "检查 ${#files[@]} 个文件（基线：${base:-全量}）"
bad=0
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  if ! clang-format --dry-run --Werror "$f" >/dev/null 2>&1; then
    echo "格式不合规：$f"
    bad=1
  fi
done

if [ "${bad}" -ne 0 ]; then
  echo "存在格式不合规文件。可执行：clang-format -i <文件>"
  exit 1
fi
echo "格式检查通过"
