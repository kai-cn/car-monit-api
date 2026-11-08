#!/usr/bin/env bash
# 上线前置步骤：快照表 ES 索引「带完整 mapping」重建 + 参数化回灌 + 与 DB 对数
#
# 背景：
#   1) 快照表 ES 文档 _id 已统一为 datauuid；旧版本曾用 bigId，同一行会存在两份文档。
#   2) ES 7.15 对 ngram(min=2,max=4) 要求 index.max_ngram_diff>=2；动态映射还会把
#      snapshottime 推断成 text、platenumber 缺少 .ngram，导致 range/sort 400、模糊查询 0 命中。
#      必须先 PUT 完整 mapping（服务内置模板已含 max_ngram_diff），再回灌。
#
# 安全顺序（避免"索引已删但没重建/回灌打不通"）：
#   参数校验 → /readyz 门禁（status/elasticsearch=UP、消费端=DISABLED）→ 回灌接口探针
#   → 预检索引（PUT+校验后删除，失败不动旧索引）→ 删除旧索引 → 重建（最多重试 3 次）
#   → mapping 复核 → 参数化回灌（POST）→ 与 DB 对数
#
# 必填：
#   ES_URL / APP_URL / DATABASE_URL
# 可选：
#   INDEX=snapshot_flow  MAPPING_FILE=resources/es/index/snapshot_flow.json
#   SHARDS=6 REPLICAS=1  ILM_POLICY=car_monit_ilm_policy ATTACH_ILM=false
#   START_TIME/END_TIME（本地时间，yyyy-MM-dd HH:mm:ss；默认最近 365 天本地墙钟）
#   ES_USER/ES_PASS  PGPASSWORD  CONFIRM=yes
#   DB_CLIENT=psql|gsql（GaussDB/openGauss 可用 gsql；默认自动探测 psql → gsql）
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(dirname "${SCRIPT_DIR}")

ES_URL="${ES_URL:?请设置 ES_URL，例如 http://127.0.0.1:9200}"
APP_URL="${APP_URL:?请设置 APP_URL，例如 http://127.0.0.1:9901}"
DATABASE_URL="${DATABASE_URL:?请设置 DATABASE_URL（用于与 DB 对数）}"
INDEX="${INDEX:-snapshot_flow}"
MAPPING_FILE="${MAPPING_FILE:-${ROOT_DIR}/resources/es/index/snapshot_flow.json}"
SHARDS="${SHARDS:-6}"
REPLICAS="${REPLICAS:-1}"
ILM_POLICY="${ILM_POLICY:-car_monit_ilm_policy}"
ATTACH_ILM="${ATTACH_ILM:-false}"
CONFIRM="${CONFIRM:-no}"
# 跨会话/跨主机互斥锁：索引名 + 单文档 + expires_at。
# 改短 TTL + 后台续租：SIGKILL 残留最多阻塞 LOCK_TTL_SECONDS（默认 180s），
# 而不是覆盖 2h 对数窗口的 3h。续租失败（锁被接管）时主动终止主流程。
LOCK_INDEX="${INDEX}__lock"
LOCK_DOC="rebuild"
LOCK_TTL_SECONDS="${LOCK_TTL_SECONDS:-180}"
LOCK_RENEW_SECONDS="${LOCK_RENEW_SECONDS:-30}"
LOCK_HELD="no"
LOCK_RENEW_PID=""
LOCK_OWNER_HOST="$(hostname 2>/dev/null || echo unknown)"
# 随机实例号：仅凭 pid+host 在 PID 复用时可能误判属主。
LOCK_INSTANCE="${LOCK_INSTANCE:-$(date +%s)-$$-$RANDOM}"
# 当前阶段：续租失败/收到 TERM 时打印，便于判断是否落在"已删未建"窗口。
LOCK_STAGE="初始化"
# 锁的 expires_at 使用 ES 服务器时钟（偏移量在获取锁时校准），避免跨机时钟漂移误判。
ES_CLOCK_OFFSET=0

# ---- 0. 索引名/mapping/表范围校验 ----
if [[ ! "${INDEX}" =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
  echo "拒绝执行：非法索引名 '${INDEX}'（只允许小写字母/数字/._-，且不能以 - _ + 开头）" >&2
  exit 2
fi
case "${INDEX}" in
  _all|*'*'*|*','*|*' '*)
    echo "拒绝执行：索引名不能是 _all、不能包含通配符/逗号/空格：'${INDEX}'" >&2
    exit 2
    ;;
esac
if [[ ! -f "${MAPPING_FILE}" ]]; then
  echo "拒绝执行：mapping 文件不存在：${MAPPING_FILE}" >&2
  exit 2
fi
if [[ ! "${LOCK_TTL_SECONDS}" =~ ^[0-9]+$ ]] || (( LOCK_TTL_SECONDS < 60 )); then
  echo "拒绝执行：LOCK_TTL_SECONDS 必须是 ≥60 的整数（当前 ${LOCK_TTL_SECONDS}）" >&2
  exit 2
fi
if [[ ! "${LOCK_RENEW_SECONDS}" =~ ^[0-9]+$ ]] || (( LOCK_RENEW_SECONDS < 10 )); then
  echo "拒绝执行：LOCK_RENEW_SECONDS 必须是 ≥10 的整数（当前 ${LOCK_RENEW_SECONDS}）" >&2
  exit 2
fi
if (( LOCK_RENEW_SECONDS * 2 > LOCK_TTL_SECONDS )); then
  echo "拒绝执行：LOCK_RENEW_SECONDS（${LOCK_RENEW_SECONDS}）必须小于等于 LOCK_TTL_SECONDS（${LOCK_TTL_SECONDS}）的一半，留足续租余量" >&2
  exit 2
fi
# 本脚本的回灌接口与 DB 对数 SQL 均按快照表编写。
if [[ "${INDEX}" != "snapshot_flow" ]]; then
  echo "拒绝执行：本脚本当前仅支持 snapshot_flow（其它索引请单独编写 DB 对数 SQL）" >&2
  exit 2
fi

CURL_TIMEOUT=(--connect-timeout 5 --max-time 60)

# 计划输出只显示 scheme://host:port/path，绝不打印 userinfo/query（ES/DB 都可能带凭据）。
redact_url() {
  python3 - "$1" <<'PY' 2>/dev/null
import sys
from urllib.parse import urlparse

u = urlparse(sys.argv[1])
host = u.hostname or ""
port = f":{u.port}" if u.port else ""
path = (u.path or "").rstrip("/")
scheme = f"{u.scheme}://" if u.scheme else ""
print(f"{scheme}{host}{port}{path}" if host else "<redacted>")
PY
}

curl_es() {
  if [[ -n "${ES_USER:-}" ]]; then
    curl -fsS "${CURL_TIMEOUT[@]}" -u "${ES_USER}:${ES_PASS:-}" "$@"
  else
    curl -fsS "${CURL_TIMEOUT[@]}" "$@"
  fi
}
curl_es_status() {
  if [[ -n "${ES_USER:-}" ]]; then
    curl -s "${CURL_TIMEOUT[@]}" -o /dev/null -w '%{http_code}' -u "${ES_USER}:${ES_PASS:-}" "$@"
  else
    curl -s "${CURL_TIMEOUT[@]}" -o /dev/null -w '%{http_code}' "$@"
  fi
}

# 输出 body + 换行 + HTTP code；传输失败（超时/连接重置）时 body 为空、code=000。
# 用于续租时区分"404/属主不匹配（已确认丢失）"与"传输错误（可重试）"。
curl_es_body_code() {
  local out
  if [[ -n "${ES_USER:-}" ]]; then
    out=$(curl -s "${CURL_TIMEOUT[@]}" -w '\n%{http_code}' -u "${ES_USER}:${ES_PASS:-}" "$@") || out=$'\n000'
  else
    out=$(curl -s "${CURL_TIMEOUT[@]}" -w '\n%{http_code}' "$@") || out=$'\n000'
  fi
  echo "${out}"
}

# ---- 1. 时间窗：使用本地墙钟（DB 按 Asia/Shanghai 解释），避免 UTC 偏移 8h ----
if [[ -z "${START_TIME:-}" ]]; then
  START_TIME=$(date -d '365 days ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -v-365d '+%Y-%m-%d %H:%M:%S')
fi
END_TIME="${END_TIME:-$(date '+%Y-%m-%d %H:%M:%S')}"

# ---- 1.1 时间窗严格校验（先于任何删除动作）----
# 仅靠正则只能保证位数（2026-02-30、25:61:99 都能通过），这里用 strptime 校验真实日期
# 与时分秒范围，并确认 START < END；失败时尚未对 ES 做任何修改。
if ! python3 - "${START_TIME}" "${END_TIME}" <<'PY'
import sys
from datetime import datetime

fmt = "%Y-%m-%d %H:%M:%S"
try:
    start = datetime.strptime(sys.argv[1], fmt)
    end = datetime.strptime(sys.argv[2], fmt)
except ValueError as ex:
    print(f"时间窗非法：{ex}", file=sys.stderr)
    sys.exit(2)
if start >= end:
    print("时间窗非法：START_TIME 必须早于 END_TIME", file=sys.stderr)
    sys.exit(2)
PY
then
  echo "拒绝执行：时间窗校验失败（要求 yyyy-MM-dd HH:mm:ss 且 START_TIME < END_TIME）" >&2
  exit 2
fi
echo "==> 时间窗校验通过：${START_TIME} ~ ${END_TIME}（本地时间）"

# 供测试/流水线只跑参数校验：此时不访问 ES/APP/DB。
if [[ "${CHECK_ONLY:-0}" == "1" ]]; then
  echo "CHECK_ONLY=1：参数校验通过，退出。"
  exit 0
fi

# ---- 2. 回灌前门禁：/readyz（整体 + ES 必须 UP，消费端必须 DISABLED）----
# 这些校验都发生在任何删除动作之前：探针/依赖不健康时直接退出，旧索引分毫不动。
READY=$(curl -s "${CURL_TIMEOUT[@]}" "${APP_URL}/readyz" || true)
READY_FIELDS=$(READY="${READY}" python3 -c '
import json, os
d = json.loads(os.environ["READY"])
print(d.get("status", ""), d.get("elasticsearch", ""),
      d.get("elasticsearchIndex", ""), d.get("mqConsumer", ""), sep="\t")
' 2>/dev/null) || READY_FIELDS=""
if [[ -z "${READY_FIELDS}" ]]; then
  echo "拒绝执行：无法解析 /readyz 响应（${APP_URL}/readyz）" >&2
  exit 2
fi
IFS=$'\t' read -r READY_STATUS READY_ES READY_INDEX MQ <<< "${READY_FIELDS}"
if [[ "${READY_STATUS}" != "UP" ]]; then
  echo "拒绝执行：服务未就绪（/readyz status=${READY_STATUS}）。请先修复 DB/Redis/ES。" >&2
  exit 2
fi
if [[ "${READY_ES}" != "UP" ]]; then
  echo "拒绝执行：Elasticsearch 未就绪（/readyz elasticsearch=${READY_ES}）。" >&2
  echo "          删除旧索引前必须确保 ES 可用，否则会留下空壳索引。" >&2
  exit 2
fi
if [[ "${READY_INDEX}" != "${INDEX}" ]]; then
  echo "拒绝执行：APP 侧快照索引名与脚本 INDEX 不一致（/readyz elasticsearchIndex=${READY_INDEX}，脚本 INDEX=${INDEX}）。" >&2
  echo "          若通过 APP_ELASTICSEARCH_INDEX_SNAPSHOT 覆盖了索引名，脚本会重建另一个索引；请先对齐再执行。" >&2
  exit 2
fi
if [[ "${MQ}" != "DISABLED" ]]; then
  echo "拒绝执行：消费端未关闭（mqConsumer=${MQ}）。请设置 APP_CONSUMER_ENABLED=false 并重启后再执行。" >&2
  exit 2
fi
echo "==> 探针状态：status=UP, elasticsearch=UP, index=${READY_INDEX}, mqConsumer=DISABLED"

# ---- 2.1 回灌接口可达性探针（必须在删除旧索引之前）----
# 用非法时间参数调用 repair：strict_time_range 在 HTTP 阶段必然返回 400，不会真正调度后台任务。
# 判据必须精确等于 400，不能接受"任意 4xx"：401/403/407/429 同样会挡住真实回灌，
# 却会被宽判据误认为"协议正常"，删完索引后照样留下空壳。
# 依据：src/router.rs 只把 /api/v1/large/sync/repair 注册为 POST；src/handlers/query.rs
# 的 strict_time_range 对非法格式返回 400。
REPAIR_PROBE_CODE=$(curl -s "${CURL_TIMEOUT[@]}" -o /dev/null -w '%{http_code}' \
  -G -X POST "${APP_URL}/api/v1/large/sync/repair" \
  --data-urlencode "type=snapshot" \
  --data-urlencode "startTime=probe-invalid-format" \
  --data-urlencode "endTime=probe-invalid-format") || REPAIR_PROBE_CODE="000"
if [[ "${REPAIR_PROBE_CODE}" != "400" ]]; then
  echo "拒绝执行：回灌接口探针失败（HTTP ${REPAIR_PROBE_CODE}，期望精确 400）。" >&2
  echo "          401/403/407/429 等拒绝同样会让真实回灌失败；请确认 APP_URL、鉴权与" >&2
  echo "          /api/v1/large/sync/repair 的 POST 注册/参数校验链路。" >&2
  exit 2
fi
echo "==> 回灌接口探针通过（非法参数精确返回 HTTP 400，路径/方法/鉴权链路正确）"

# ---- 3. 计划确认 ----
# ES/DB 连接串都可能带账号密码：统一只打印 scheme://host:port/path，避免日志/工单泄露凭据。
DB_DISPLAY=$(redact_url "${DATABASE_URL}") || DB_DISPLAY='<redacted>'
ES_DISPLAY=$(redact_url "${ES_URL}") || ES_DISPLAY='<redacted>'
echo "==> 计划重建"
echo "    ES_URL      = ${ES_DISPLAY}"
echo "    INDEX       = ${INDEX}"
echo "    MAPPING     = ${MAPPING_FILE}"
echo "    SHARDS/REPL = ${SHARDS}/${REPLICAS}"
echo "    ILM         = ${ILM_POLICY} (attach=${ATTACH_ILM})"
echo "    TIME RANGE  = ${START_TIME} ~ ${END_TIME}（本地时间）"
echo "    DB          = ${DB_DISPLAY}"
echo
echo "该操作会删除索引 ${INDEX} 并重建；期间快照查询走 DB 降级路径。"
if [[ "${CONFIRM}" != "yes" ]]; then
  read -r -p "确认继续？输入 yes 继续：" ans
  [[ "${ans}" == "yes" ]] || { echo "已取消"; exit 1; }
fi

BODY=$(sed -e "s/__NUMBER_OF_SHARDS__/${SHARDS}/g" -e "s/__NUMBER_OF_REPLICAS__/${REPLICAS}/g" "${MAPPING_FILE}")

# ---- 3.1 ES 侧重建锁：跨主机/跨会话互斥，防止两个流程同时删建主索引 ----
# 锁 = `${INDEX}__lock/rebuild` 单文档，op_type=create 原子抢占 + expires_at 容忍 SIGKILL 残留。
# 预检索引前缀清扫只能防"同机残留"，不能防两台机器同时跑；主索引删建必须靠这把锁。
# 用 ES 响应头的 Date 校准时钟：锁的 expires_at 与过期判定都用 ES 服务器时间，
# 避免 A/B 两台机器时钟漂移导致误判过期（网络延迟在秒级 TTL 下可忽略）。
sync_es_clock() {
  local date_hdr es_epoch
  date_hdr=$(curl_es -D - -o /dev/null "${ES_URL}/" 2>/dev/null \
    | tr -d '\r' | sed -n 's/^[Dd]ate: *//p' | head -1)
  [[ -n "${date_hdr}" ]] || return 1
  es_epoch=$(DATE_HDR="${date_hdr}" python3 -c '
import os, email.utils
print(int(email.utils.parsedate_to_datetime(os.environ["DATE_HDR"]).timestamp()))
' 2>/dev/null) || return 1
  ES_CLOCK_OFFSET=$(( es_epoch - $(date +%s) ))
}
es_now() { echo $(( $(date +%s) + ES_CLOCK_OFFSET )); }

lock_doc_body() {
  echo "{\"owner_pid\":$$,\"host\":\"${LOCK_OWNER_HOST}\",\"instance\":\"${LOCK_INSTANCE}\",\"expires_at\":$1}"
}

# 输出：expires_at host owner_pid instance seq_no primary_term
get_lock_meta() {
  curl_es "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    src = d["_source"]
    print(src.get("expires_at", 0), src.get("host", "?"), src.get("owner_pid", "?"),
          src.get("instance", "?"), d.get("_seq_no", "?"), d.get("_primary_term", "?"))
except Exception:
    sys.exit(1)
'
}

lock_manual_hint() {
  echo "          确认是残留后可手工删除 ${LOCK_INDEX}/${LOCK_DOC}：" >&2
  echo "          curl -X DELETE '${ES_DISPLAY}/${LOCK_INDEX}/_doc/${LOCK_DOC}'" >&2
  echo "          （若集群启用鉴权，请附带与 ES_USER/ES_PASS 相同的 -u 参数，否则会 401）" >&2
}

try_create_lock_doc() {
  local body="$1" code
  # 必须走带 ES_USER/ES_PASS 的 curl_es_status，否则开启 basic-auth 的集群会 401。
  code=$(curl_es_status -X PUT "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}?op_type=create&refresh=true" \
    -H 'Content-Type: application/json' -d "${body}") || code="000"
  echo "${code}"
}

acquire_rebuild_lock() {
  local index_code body now expires code meta expired holder_host holder_pid holder_instance seq primary del_code
  index_code=$(curl_es_status -X PUT "${ES_URL}/${LOCK_INDEX}" \
    -H 'Content-Type: application/json' \
    -d '{"mappings":{"properties":{"expires_at":{"type":"long"},"owner_pid":{"type":"long"},"instance":{"type":"keyword"},"host":{"type":"keyword"}}}}') || index_code="000"
  # 200=新建；400=已存在（锁索引被上个流程创建过）。
  if [[ "${index_code}" != "200" && "${index_code}" != "400" ]]; then
    echo "拒绝执行：无法创建/确认重建锁索引 ${LOCK_INDEX}（HTTP ${index_code}）。" >&2
    exit 2
  fi
  if ! sync_es_clock; then
    echo "警告：读取 ES Date 头失败，锁过期判定回退本机时钟（跨机时钟漂移可能误判）" >&2
  fi
  now=$(es_now)
  expires=$(( now + LOCK_TTL_SECONDS ))
  body=$(lock_doc_body "${expires}")
  code=$(try_create_lock_doc "${body}")
  if [[ "${code}" == "200" || "${code}" == "201" ]]; then
    LOCK_HELD="yes"
    echo "==> 已获取重建锁 ${LOCK_INDEX}/${LOCK_DOC}（TTL ${LOCK_TTL_SECONDS}s，pid=$$）"
    return 0
  fi
  if [[ "${code}" == "409" ]]; then
    meta=$(get_lock_meta) || meta=""
    if [[ -n "${meta}" ]]; then
      read -r expired holder_host holder_pid holder_instance seq primary <<< "${meta}"
      if [[ "${expired}" =~ ^[0-9]+$ ]] && (( expired < now )); then
        echo "==> 发现过期重建锁（pid=${holder_pid} host=${holder_host}），尝试条件接管" >&2
        # 条件删除：只有版本仍是刚读到的版本才删，避免把别人刚接管的新锁删掉。
        if [[ "${seq}" =~ ^[0-9]+$ && "${primary}" =~ ^[0-9]+$ ]]; then
          del_code=$(curl_es_status -X DELETE \
            "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}?if_seq_no=${seq}&if_primary_term=${primary}&refresh=true") || del_code="000"
          if [[ "${del_code}" != "200" && "${del_code}" != "404" ]]; then
            echo "拒绝执行：过期锁在接管期间被其他流程变更（DELETE HTTP ${del_code}），放弃接管。" >&2
            exit 2
          fi
          code=$(try_create_lock_doc "${body}")
          if [[ "${code}" == "200" || "${code}" == "201" ]]; then
            LOCK_HELD="yes"
            echo "==> 已接管重建锁 ${LOCK_INDEX}/${LOCK_DOC}（pid=$$）"
            return 0
          fi
          echo "拒绝执行：另一个流程已接管重建锁（HTTP ${code}）。" >&2
          exit 2
        fi
        echo "拒绝执行：过期锁缺少版本号，无法安全接管（请手工确认后删除）。" >&2
        lock_manual_hint
        exit 2
      fi
      echo "拒绝执行：另一个重建流程持有锁 ${LOCK_INDEX}/${LOCK_DOC}（pid=${holder_pid} host=${holder_host} expires_at=${expired}）。" >&2
      echo "          请等待其结束（锁每 ${LOCK_RENEW_SECONDS}s 续租一次）。" >&2
      lock_manual_hint
      exit 2
    fi
  fi
  echo "拒绝执行：获取重建锁失败（HTTP ${code}），为避免并发删建索引已终止。" >&2
  exit 2
}

# 续租一次。返回码：
#   0 = 续租成功
#   1 = 锁已确认丢失（404 / 属主(instance)不匹配 / 版本冲突）
#   2 = 传输或 ES 错误（超时/5xx/解析失败），可等待下一周期重试
renew_lock_once() {
  local resp code body meta expired holder_host holder_pid holder_instance seq primary expires new_body put_code
  resp=$(curl_es_body_code "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}")
  code=${resp##*$'\n'}
  body=${resp%$'\n'*}
  case "${code}" in
    200)
      meta=$(BODY="${body}" python3 -c '
import json, os, sys
try:
    d = json.loads(os.environ["BODY"])
    src = d["_source"]
    print(src.get("expires_at", 0), src.get("host", "?"), src.get("owner_pid", "?"),
          src.get("instance", "?"), d.get("_seq_no", "?"), d.get("_primary_term", "?"))
except Exception:
    sys.exit(1)
' 2>/dev/null) || return 2
      read -r expired holder_host holder_pid holder_instance seq primary <<< "${meta}"
      if [[ "${holder_instance}" != "${LOCK_INSTANCE}" ]]; then
        return 1
      fi
      if [[ ! "${seq}" =~ ^[0-9]+$ || ! "${primary}" =~ ^[0-9]+$ ]]; then
        return 2
      fi
      expires=$(( $(es_now) + LOCK_TTL_SECONDS ))
      new_body=$(lock_doc_body "${expires}")
      put_code=$(curl_es_status -X PUT \
        "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}?if_seq_no=${seq}&if_primary_term=${primary}&refresh=true" \
        -H 'Content-Type: application/json' -d "${new_body}") || put_code="000"
      case "${put_code}" in
        200|201) return 0 ;;
        409) return 1 ;; # 版本冲突 = 已被其他流程接管
        *) return 2 ;;
      esac
      ;;
    404) return 1 ;; # 锁文档不存在 = 已释放/被接管
    *) return 2 ;;
  esac
}

start_lock_renewal() {
  (
    failures=0
    # 允许连续失败 TTL/2（至少 1 个周期）后才终止：单次 503/超时不应直接 TERM，
    # 否则 TERM 若落在"旧索引已删、新索引未建"窗口会留下无索引状态。
    max_fail=$(( (LOCK_TTL_SECONDS / 2 + LOCK_RENEW_SECONDS - 1) / LOCK_RENEW_SECONDS ))
    (( max_fail < 1 )) && max_fail=1
    while sleep "${LOCK_RENEW_SECONDS}"; do
      renew_lock_once
      rc=$?
      if [[ ${rc} -eq 0 ]]; then
        failures=0
        continue
      fi
      if [[ ${rc} -eq 1 ]]; then
        echo "严重：重建锁已丢失（404/属主不匹配/版本冲突），当前阶段：${LOCK_STAGE}，终止主流程" >&2
        kill -TERM $$ 2>/dev/null || true
        break
      fi
      failures=$((failures + 1))
      echo "警告：重建锁续租传输失败（第 ${failures}/${max_fail} 次，当前阶段：${LOCK_STAGE}）" >&2
      if (( failures >= max_fail )); then
        echo "严重：续租连续失败达到 TTL/2（${failures} 次），锁可能已过期被接管，终止主流程（当前阶段：${LOCK_STAGE}）" >&2
        kill -TERM $$ 2>/dev/null || true
        break
      fi
    done
  ) &
  LOCK_RENEW_PID=$!
}

release_rebuild_lock() {
  if [[ "${LOCK_HELD}" != "yes" ]]; then
    return 0
  fi
  LOCK_HELD="no"
  if [[ -n "${LOCK_RENEW_PID}" ]]; then
    kill "${LOCK_RENEW_PID}" 2>/dev/null || true
    wait "${LOCK_RENEW_PID}" 2>/dev/null || true
    LOCK_RENEW_PID=""
  fi
  local meta expired holder_host holder_pid holder_instance seq primary code
  meta=$(get_lock_meta) || meta=""
  if [[ -z "${meta}" ]]; then
    echo "警告：重建锁读取失败（ES 不可用或锁已丢失），TTL ${LOCK_TTL_SECONDS}s 后自动失效" >&2
    return 0
  fi
  read -r expired holder_host holder_pid holder_instance seq primary <<< "${meta}"
  if [[ "${holder_instance}" != "${LOCK_INSTANCE}" ]]; then
    echo "警告：重建锁已被其他流程接管（pid=${holder_pid} host=${holder_host}），不执行删除" >&2
    return 0
  fi
  if [[ ! "${seq}" =~ ^[0-9]+$ || ! "${primary}" =~ ^[0-9]+$ ]]; then
    echo "警告：无法读取锁版本号，跳过删除（TTL ${LOCK_TTL_SECONDS}s 后自动失效）" >&2
    return 0
  fi
  code=$(curl_es_status -X DELETE \
    "${ES_URL}/${LOCK_INDEX}/_doc/${LOCK_DOC}?if_seq_no=${seq}&if_primary_term=${primary}&refresh=true") || code="000"
  if [[ "${code}" == "200" || "${code}" == "404" ]]; then
    echo "==> 重建锁已释放"
  else
    echo "警告：重建锁释放失败（HTTP ${code}；可能已被接管），TTL ${LOCK_TTL_SECONDS}s 后自动失效" >&2
  fi
}

acquire_rebuild_lock
LOCK_STAGE="预检索引"
start_lock_renewal
trap release_rebuild_lock EXIT
trap 'echo "收到 TERM（当前阶段：${LOCK_STAGE}），退出" >&2; exit 143' TERM

# ---- 4. 预检索引：先验证 mapping 能被 ES 接受，失败时旧索引分毫未动 ----
# SIGKILL/断电时 trap 不会执行，先清扫历史残留的预检索引（固定前缀 + pid 后缀）。
sweep_preflight() {
  local idxs i pid owner
  idxs=$(curl_es "${ES_URL}/_cat/indices/${INDEX}__preflight_*?h=index" 2>/dev/null || true)
  for i in ${idxs}; do
    pid="${i#"${INDEX}__preflight_"}"
    # 并发执行保护：索引后缀是创建者的 PID。
    # 注意 `kill -0` 对其他用户的进程会因 EPERM 返回非零，与"进程不存在"无法区分；
    # 必须先看属主：属主是本机其他用户时保守跳过；只有本用户且存活才跳过，其余视为残留。
    owner=$(ps -o user= -p "${pid}" 2>/dev/null | tr -d '[:space:]') || owner=""
    if [[ -n "${owner}" && "${owner}" != "$(id -un)" ]]; then
      echo "==> 跳过预检索引 ${i}（PID ${pid} 属于用户 ${owner}，无法安全判断存活）" >&2
      continue
    fi
    if [[ -n "${owner}" ]] && kill -0 "${pid}" 2>/dev/null; then
      echo "==> 跳过仍在使用中的预检索引 ${i}（进程 ${pid} 存活）" >&2
      continue
    fi
    echo "==> 清理历史预检索引 ${i}" >&2
    if ! curl_es -X DELETE "${ES_URL}/${i}?ignore_unavailable=true" >/dev/null; then
      echo "警告：历史预检索引 ${i} 清理失败，请手工删除" >&2
    fi
  done
}
sweep_preflight

PREFLIGHT="${INDEX}__preflight_$$"
# 任何退出路径（含 Ctrl+C / 校验失败）都清理预检索引，避免残留；清理失败要出声。
cleanup_preflight() {
  if ! curl_es -X DELETE "${ES_URL}/${PREFLIGHT}?ignore_unavailable=true" >/dev/null 2>&1; then
    echo "警告：预检索引 ${PREFLIGHT} 清理失败，请手工执行：curl -X DELETE '${ES_DISPLAY}/${PREFLIGHT}'" >&2
  fi
}
trap 'cleanup_preflight; release_rebuild_lock' EXIT
if ! curl_es -X PUT "${ES_URL}/${PREFLIGHT}" -H 'Content-Type: application/json' -d "${BODY}" >/dev/null; then
  echo "预检失败：mapping 被 ES 拒绝，旧索引 ${INDEX} 未做任何修改。" >&2
  exit 3
fi
validate_mapping() {
  IDX="$1" MAPPING_JSON="$2" python3 -c '
import json, os
idx = os.environ["IDX"]
doc = json.loads(os.environ["MAPPING_JSON"])
props = doc[idx]["mappings"]["properties"]
assert props["snapshottime"]["type"] == "date", "snapshottime 不是 date"
assert "ngram" in props["platenumber"].get("fields", {}), "platenumber 缺少 ngram 子字段"
print("OK")
'
}
if ! validate_mapping "${PREFLIGHT}" "$(curl_es "${ES_URL}/${PREFLIGHT}/_mapping")"; then
  curl_es -X DELETE "${ES_URL}/${PREFLIGHT}?ignore_unavailable=true" >/dev/null
  echo "预检失败：mapping 校验不通过，旧索引 ${INDEX} 未做任何修改。" >&2
  exit 3
fi
curl_es -X DELETE "${ES_URL}/${PREFLIGHT}?ignore_unavailable=true" >/dev/null
trap release_rebuild_lock EXIT
echo "==> 预检通过（mapping 可被 ES 接受且 date/ngram 齐备）"

# ---- 5. ILM：已存在则跳过，不覆盖运维调过的策略 ----
if [[ "${ATTACH_ILM}" == "true" ]]; then
  if [[ "$(curl_es_status "${ES_URL}/_ilm/policy/${ILM_POLICY}")" == "200" ]]; then
    echo "==> ILM 策略已存在，跳过创建：${ILM_POLICY}"
  else
    curl_es -X PUT "${ES_URL}/_ilm/policy/${ILM_POLICY}" -H 'Content-Type: application/json' -d '{
      "policy": {"phases": {
        "hot":    {"min_age": "0ms",  "actions": {"set_priority": {"priority": 100}, "rollover": {"max_age": "30d", "max_primary_shard_size": "50gb"}}},
        "warm":   {"min_age": "30d",  "actions": {"set_priority": {"priority": 50}, "forcemerge": {"max_num_segments": 1}, "shrink": {"number_of_shards": 1}}},
        "cold":   {"min_age": "90d",  "actions": {"set_priority": {"priority": 0}, "freeze": {}}},
        "delete": {"min_age": "365d", "actions": {"delete": {}}}
      }}
    }' >/dev/null
    echo "==> ILM 策略已创建：${ILM_POLICY}"
  fi
  BODY=$(BODY="${BODY}" POLICY="${ILM_POLICY}" python3 -c \
    'import json,os; b=json.loads(os.environ["BODY"]); b.setdefault("settings",{})["index.lifecycle.name"]=os.environ["POLICY"]; print(json.dumps(b))')
fi

# ---- 6. 删除旧索引并重建（最多 3 次；预检已排除 mapping 非法）----
BEFORE=$(curl_es "${ES_URL}/${INDEX}/_count" 2>/dev/null | sed -E 's/.*"count":([0-9]+).*/\1/' || echo 0)
echo "==> 重建前计数：${BEFORE}"
LOCK_STAGE="删除旧索引"
curl_es -X DELETE "${ES_URL}/${INDEX}?ignore_unavailable=true" >/dev/null
LOCK_STAGE="旧索引已删除，创建新索引"
CREATED=no
for attempt in 1 2 3; do
  if curl_es -X PUT "${ES_URL}/${INDEX}" -H 'Content-Type: application/json' -d "${BODY}" >/dev/null; then
    CREATED=yes
    break
  fi
  echo "重建失败（第 ${attempt}/3 次），2 秒后重试…" >&2
  sleep 2
done
if [[ "${CREATED}" != "yes" ]]; then
  echo "严重：旧索引已删除且新索引创建失败。请立即用下面的 body 手工执行：" >&2
  echo "  PUT ${ES_DISPLAY}/${INDEX}" >&2
  echo "${BODY}" >&2
  exit 4
fi
LOCK_STAGE="新索引已创建，复核 mapping"
echo "==> 索引 ${INDEX} 已按 mapping 创建"

# ---- 7. 复核最终 mapping（JSON 解析，不依赖字符串压缩格式）----
if ! validate_mapping "${INDEX}" "$(curl_es "${ES_URL}/${INDEX}/_mapping")"; then
  echo "校验失败：最终索引 mapping 不符合要求。" >&2
  exit 3
fi
echo "==> mapping 校验通过（snapshottime=date，platenumber.ngram 存在）"
LOCK_STAGE="回灌中"

# ---- 8. 参数化回灌（必须 POST：router.rs 中该路由只注册了 POST；GET 会得到 405）----
curl -fsS "${CURL_TIMEOUT[@]}" -G -X POST "${APP_URL}/api/v1/large/sync/repair" \
  --data-urlencode "type=snapshot" \
  --data-urlencode "startTime=${START_TIME}" \
  --data-urlencode "endTime=${END_TIME}"
echo
LOCK_STAGE="等待 ES/DB 对数"

# ---- 9. 与 DB 对数（psql 优先；探测/认证失败时自动回退 gsql）----
COUNT_SQL="SELECT count(*) FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode \
WHERE snapshottime >= to_timestamp('${START_TIME}','yyyy-mm-dd HH24:MI:SS') \
  AND snapshottime <  to_timestamp('${END_TIME}','yyyy-mm-dd HH24:MI:SS')"

run_count() {
  local client="$1"
  if [[ "${client}" == "gsql" ]]; then
    gsql "${DATABASE_URL}" -t -A -c "${COUNT_SQL}"
  else
    psql "${DATABASE_URL}" -tAc "${COUNT_SQL}"
  fi
}

CLIENT_USED=""
if [[ -n "${DB_CLIENT:-}" ]]; then
  case "${DB_CLIENT}" in
    psql|gsql) ;;
    *)
      echo "拒绝执行：DB_CLIENT 只支持 psql 或 gsql（当前 ${DB_CLIENT}）" >&2
      exit 2
      ;;
  esac
  # 显式指定时不回退：失败直接报错，避免运维以为用了 A 实际用了 B。
  if ! DB_COUNT=$(run_count "${DB_CLIENT}" 2>/dev/null); then
    echo "拒绝执行：DB_CLIENT=${DB_CLIENT} 连接或查询失败（认证/驱动/网络）。请修正连接串或改用另一种客户端。" >&2
    exit 2
  fi
  CLIENT_USED="${DB_CLIENT}"
else
  # 自动探测：psql 优先；psql 探测/认证失败且存在 gsql 时回退。
  if command -v psql >/dev/null 2>&1; then
    if DB_COUNT=$(run_count psql 2>/dev/null); then
      CLIENT_USED=psql
    elif command -v gsql >/dev/null 2>&1; then
      echo "提示：psql 不可用（认证/驱动/网络失败），回退 gsql 重试…" >&2
      if DB_COUNT=$(run_count gsql 2>/dev/null); then
        CLIENT_USED=gsql
      fi
    fi
  elif command -v gsql >/dev/null 2>&1; then
    if DB_COUNT=$(run_count gsql 2>/dev/null); then
      CLIENT_USED=gsql
    fi
  fi
  if [[ -z "${CLIENT_USED}" ]]; then
    echo "拒绝执行：psql/gsql 均不可用或连接失败，无法与 DB 对数。请设置 DB_CLIENT 或修正 DATABASE_URL。" >&2
    exit 2
  fi
fi

DB_COUNT=$(echo "${DB_COUNT}" | tr -d '[:space:]')
if [[ ! "${DB_COUNT}" =~ ^[0-9]+$ ]]; then
  echo "拒绝执行：DB 返回非数字计数 '${DB_COUNT}'（client=${CLIENT_USED}）" >&2
  exit 2
fi
echo "==> DB 期望条数：${DB_COUNT}（client=${CLIENT_USED}）"

deadline=$(( $(date +%s) + 7200 ))
while :; do
  ES_COUNT=$(curl_es "${ES_URL}/${INDEX}/_count" 2>/dev/null | sed -E 's/.*"count":([0-9]+).*/\1/' || echo 0)
  echo "    ES count=${ES_COUNT} / DB=${DB_COUNT}"
  if [[ "${DB_COUNT}" == "0" ]]; then
    # 窗口内本就没有数据：只要索引为空即成功，不做无意义等待。
    if [[ "${ES_COUNT}" == "0" ]]; then
      echo "==> 窗口内 DB 无数据，ES 为空，重建完成"
      break
    fi
  elif (( ES_COUNT * 100 >= DB_COUNT * 99 )); then
    echo "==> 回灌完成（允许 1% refresh/写入误差）"
    break
  fi
  if (( $(date +%s) > deadline )); then
    echo "回灌超时（2h）：ES=${ES_COUNT} DB=${DB_COUNT}，请检查服务日志后重试 repair" >&2
    exit 5
  fi
  sleep 60
done

echo
echo "验收："
echo "  1) curl '${ES_DISPLAY}/${INDEX}/_search?size=1' 抽查 _id == _source.datauuid；"
echo "  2) 日志出现 '[同步] 完成' 且 failed=0；"
echo "  3) /readyz 持续 200。"
