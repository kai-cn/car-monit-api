#!/usr/bin/env bash
# 重建脚本的离线测试：
#   1) 时间窗参数校验（CHECK_ONLY=1，不访问 ES/APP/DB），断言具体退出码与关键 stderr 文案；
#   2) 静态断言：脚本调用 repair 的 HTTP 方法必须与 src/router.rs 的注册方法一致，
#      防止「脚本 GET / 路由 POST」的阻断复发。
# 运行：bash tools/test-es-rebuild-snapshot-flow.sh
set -u

# 脚本的时间窗校验依赖 python3。Git Bash 等环境缺少 python3 时，负例可能因
# "参数校验失败"文案相同而误判 PASS；必须在运行前显式失败，不能给出误导结果。
if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: 当前环境缺少 python3，无法运行参数校验/时间窗测试（请用 WSL 或安装 python3）"
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="${SCRIPT_DIR}/es-rebuild-snapshot-flow.sh"
ROUTER="${SCRIPT_DIR}/../src/router.rs"

# 必填变量给占位值；CHECK_ONLY 会在参数校验后直接退出。
export ES_URL="http://127.0.0.1:1"
export APP_URL="http://127.0.0.1:1"
export DATABASE_URL="postgres://user:secret@127.0.0.1:1/db"
export CHECK_ONLY=1
export INDEX=snapshot_flow

fail=0
run_case() {
  local name="$1" start="$2" end="$3" expect="$4" want_rc="${5:-0}" want_msg="${6:-}"
  local out rc ok=1
  # 只捕获 stderr（脚本的拒绝原因都写 stderr）；stdout 丢弃避免 PASS 日志干扰判断。
  out=$(START_TIME="$start" END_TIME="$end" bash "${SCRIPT}" 2>&1 >/dev/null)
  rc=$?
  if [[ "${expect}" == "ok" ]]; then
    if [[ ${rc} -ne 0 ]]; then
      echo "FAIL: ${name} 期望接受，实际 rc=${rc}"
      fail=1
    else
      echo "PASS: ${name} (rc=0)"
    fi
    return
  fi
  if [[ ${rc} -ne ${want_rc} ]]; then
    echo "FAIL: ${name} 期望 rc=${want_rc}，实际 rc=${rc}"
    ok=0
  fi
  if [[ -n "${want_msg}" ]] && ! grep -Fq "${want_msg}" <<< "${out}"; then
    echo "FAIL: ${name} stderr 缺少关键文案 '${want_msg}'"
    ok=0
  fi
  if [[ ${ok} -eq 1 ]]; then
    echo "PASS: ${name} (rc=${rc}, stderr 文案匹配)"
  else
    fail=1
  fi
}

run_case "normal"        "2026-01-01 00:00:00" "2026-01-02 00:00:00" ok
run_case "reversed"      "2026-01-02 00:00:00" "2026-01-01 00:00:00" reject 2 "时间窗校验失败"
run_case "same"          "2026-01-01 00:00:00" "2026-01-01 00:00:00" reject 2 "时间窗校验失败"
run_case "invalid-date"  "2026-02-30 10:00:00" "2026-03-01 00:00:00" reject 2 "时间窗校验失败"
run_case "invalid-time"  "2026-01-01 25:61:99" "2026-01-02 00:00:00" reject 2 "时间窗校验失败"
run_case "bad-format"    "2026/01/01 00:00:00" "2026-01-02 00:00:00" reject 2 "时间窗校验失败"

# ---- 静态断言：脚本的 repair 调用方法必须与 router.rs 的注册方法一致 ----
# 上一次阻断正是脚本用 GET、路由只注册 POST，且脚本无任何检查。
# 同时要求 repair URL 至少出现两次：删掉正式回灌只留探针时，也必须让测试失败。
curl_block() {
  local line="$1" start end total prev cur
  total=$(wc -l < "${SCRIPT}")
  start="${line}"
  # 向前扩展反斜杠续行（例如 $(curl ... \ 换行  -X POST "${APP_URL}/...")
  while (( start > 1 )); do
    prev=$(sed -n "$((start - 1))p" "${SCRIPT}")
    [[ "${prev}" == *\\ ]] || break
    start=$((start - 1))
  done
  end="${line}"
  while (( end < total )); do
    cur=$(sed -n "${end}p" "${SCRIPT}")
    [[ "${cur}" == *\\ ]] || break
    end=$((end + 1))
  done
  sed -n "${start},${end}p" "${SCRIPT}"
}

check_repair_method() {
  local router_method=UNKNOWN line block clean probe=0 formal=0 probe_line=0 probe_window=""
  local -a repair_lines=()
  if grep -Eq '"/api/v1/large/sync/repair"[[:space:]]*,[[:space:]]*post\(' "${ROUTER}"; then
    router_method=POST
  fi
  # 只统计真实调用：URL 以 ${APP_URL} 开头，且排除 shell 注释行。
  mapfile -t repair_lines < <(
    grep -Fn '${APP_URL}/api/v1/large/sync/repair' "${SCRIPT}" \
      | grep -vE '^[0-9]+:[[:space:]]*#' | cut -d: -f1
  )
  # 必须是“1 处探针 + 1 处正式回灌”，复制探针凑数不能通过。
  if (( ${#repair_lines[@]} != 2 )); then
    echo "FAIL: repair 调用应恰好 2 处（1 探针 + 1 正式），实际 ${#repair_lines[@]} 处"
    fail=1
    return
  fi
  for line in "${repair_lines[@]}"; do
    block=$(curl_block "${line}")
    # 剔除块内注释行：注释掉的 -G/-X POST 不能算数。
    clean=$(printf '%s\n' "${block}" | sed -E '/^[[:space:]]*#/d')
    if ! grep -Eq -- '-X[[:space:]]+POST' <<< "${clean}"; then
      echo "FAIL: 脚本第 ${line} 行所在 curl 块（剔除注释后）缺少 -X POST"
      fail=1
      return
    fi
    # -G 必须显式存在：否则 --data-urlencode 会被当成请求体，实际变成非 GET 语义的错误调用。
    if ! grep -Eq -- '(^|[[:space:]])-G([[:space:]]|$)' <<< "${clean}"; then
      echo "FAIL: 脚本第 ${line} 行所在 curl 块（剔除注释后）缺少 -G"
      fail=1
      return
    fi
    if grep -Fq 'probe-invalid-format' <<< "${clean}"; then
      probe=$((probe + 1))
      probe_line="${line}"
    fi
    if grep -Fq 'startTime=${START_TIME}' <<< "${clean}"; then
      formal=$((formal + 1))
    fi
  done
  if (( probe != 1 || formal != 1 )); then
    echo "FAIL: 应恰好 1 处探针 + 1 处正式回灌（probe=${probe}, formal=${formal}）"
    fail=1
    return
  fi
  # 探针判据必须精确 400，且必须写在非注释代码里；改回“任意 4xx”正则时失败。
  # 判据在 curl 语句块结束后的 if 行，窗口取探针 URL 行起 12 行并剔除注释。
  probe_window=$(sed -n "${probe_line},$((probe_line + 12))p" "${SCRIPT}" \
    | sed -E '/^[[:space:]]*#/d')
  if ! grep -Eq 'REPAIR_PROBE_CODE.*!=[[:space:]]*"400"' <<< "${probe_window}"; then
    echo "FAIL: 探针判据不是精确 400（未在探针代码附近找到 REPAIR_PROBE_CODE != \"400\"）"
    fail=1
    return
  fi
  if grep -Eq '4\[0-9\]\[0-9\]' <<< "${probe_window}"; then
    echo "FAIL: 探针附近仍出现 4xx 正则（判据过宽）"
    fail=1
    return
  fi
  if [[ "${router_method}" == "POST" ]]; then
    echo "PASS: repair 断言通过（1 探针 + 1 正式，均 -G/-X POST，精确 400；router=POST）"
  else
    echo "FAIL: router.rs 未把 /api/v1/large/sync/repair 注册为 POST（当前 ${router_method}）"
    fail=1
  fi
}
check_repair_method

exit ${fail}
