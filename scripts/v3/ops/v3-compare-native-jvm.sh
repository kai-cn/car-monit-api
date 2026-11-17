#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-compare-native-jvm.sh
# 用途：性能对比：native 与 JVM 的启动时间/RSS/延迟 A/B 测试
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# A/B measurement: Spring Boot native ELF vs. ordinary fat jar on the SAME host.
#
#   bash v3-compare-native-jvm.sh \
#      --native /path/to/pro-business-api \
#      --jar    /path/to/pro-business-api-1.0.jar \
#      --java   /home/dev/tools/mandrel-25/bin/java \
#      --duration 180 --interval 5 [--jvm-opts "-Xmx768m"] [--probe /doc.html]
#
# Produces (in $EVIDENCE_DIR):
#   compare-<label>-<stamp>.csv        samples for both variants
#   compare-<label>-<stamp>.json       aggregated metrics
#   compare-run-<variant>-<label>-<stamp>.log   application stdout/stderr
#
# Design notes:
#   * Both variants get identical Spring arguments and the same database/redis.
#   * Readiness = TCP port accepts a connection (web server bound).
#   * HTTP liveness = GET on --probe; any HTTP response counts as "alive"
#     (404/401/302 are fine; we measure the process, not authorisation).
#   * Stability phase runs ONLY on the native variant after the A/B comparison.
#   * `set -o pipefail` + process teardown: every ps/awk/curl pipe is protected
#     with `|| true`, otherwise a dead child aborts the whole script.
set -euo pipefail

NATIVE=""; JAR=""; JAVA=""; DURATION=180; INTERVAL=5
PORT_N=19902; PORT_J=19903; PROBE="/doc.html"; JVM_OPTS=""; LABEL="api-jdk25"
DB_URL="jdbc:postgresql://127.0.0.1:5432/RuoYi?useSSL=false"
REDIS_HOST="127.0.0.1"
EV="${EVIDENCE_DIR:-/mnt/d/work/runtime-logs/v3-ops/evidence}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --native)   NATIVE="$2"; shift 2 ;;
    --jar)      JAR="$2"; shift 2 ;;
    --java)     JAVA="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --port-native) PORT_N="$2"; shift 2 ;;
    --port-jvm)    PORT_J="$2"; shift 2 ;;
    --probe)    PROBE="$2"; shift 2 ;;
    --jvm-opts) JVM_OPTS="$2"; shift 2 ;;
    --label)    LABEL="$2"; shift 2 ;;
    --db-url)   DB_URL="$2"; shift 2 ;;
    --redis)    REDIS_HOST="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

for f in "$NATIVE" "$JAR" "$JAVA"; do
  [[ -n "$f" && -e "$f" ]] || { echo "FATAL missing: $f" >&2; exit 3; }
done
command -v curl >/dev/null 2>&1 || { echo "FATAL: curl required" >&2; exit 3; }

# Both datasources must be authenticated. PlateColorDictionary reads MySQL 3307
# via CARMONIT_MYSQL_* ; the master datasource reads openGauss via SPRING_*.
# Values are read from container environments at runtime, never persisted.
GS_PASS=$(docker exec opengauss env 2>/dev/null | sed -n 's/^[^=]*GS_PASSWORD=//p' | tr -d '\r' | head -n 1)
MYSQL_PASS=$(docker exec mysql_wsl env 2>/dev/null | sed -n 's/^[^=]*MYSQL_ROOT_PASSWORD=//p' | tr -d '\r' | head -n 1)
[[ -n "$GS_PASS" && -n "$MYSQL_PASS" ]] || { echo "FATAL: cannot read DB credentials from containers" >&2; exit 4; }
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME=gaussdb
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD="$GS_PASS"
export CARMONIT_MYSQL_USERNAME=root
export CARMONIT_MYSQL_PASSWORD="$MYSQL_PASS"

for P in "$PORT_N" "$PORT_J"; do
  if (echo > "/dev/tcp/127.0.0.1/$P") >/dev/null 2>&1; then
    echo "FATAL: port $P already bound; refusing false-positive readiness" >&2; exit 5
  fi
done

mkdir -p "$EV"
STAMP=$(date +%Y%m%d-%H%M%S)
CSV="$EV/compare-$LABEL-$STAMP.csv"
JSON="$EV/compare-$LABEL-$STAMP.json"
echo "variant,phase,elapsed_s,rss_MB,cpu_seconds,port_open,http_code,http_ms" > "$CSV"
echo "==== NATIVE vs JVM COMPARE label=$LABEL ===="
echo "native=$NATIVE ($(stat -c %s "$NATIVE") bytes)"
echo "jar=$JAR ($(stat -c %s "$JAR") bytes)"
echo "java=$JAVA jvm_opts='${JVM_OPTS:-<default>}'"
echo "duration=${DURATION}s interval=${INTERVAL}s probe=$PROBE"
echo "csv=$CSV json=$JSON"

SPRING_ARGS=(--spring.datasource.dynamic.datasource.master.url="$DB_URL"
             --spring.data.redis.host="$REDIS_HOST")

port_open() { (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }
rss_mb() {
  local r
  r=$(ps -o rss= -p "$1" 2>/dev/null | tr -d ' ' || true)
  if [[ -n "$r" ]]; then awk -v k="$r" 'BEGIN{printf "%.1f", k/1024}'; else echo "0"; fi
}
cpu_sec() {
  local t
  t=$(ps -o time= -p "$1" 2>/dev/null | tr -d ' ' || true)
  [[ -z "$t" ]] && { echo 0; return 0; }
  echo "$t" | awk -F: '{ n=NF; s=$n; if(n>1) s+=$(n-1)*60; if(n>2) s+=$(n-2)*3600; printf "%d", s }' || echo 0
}
http_probe() {
  # prints "<code> <ms>" ; never fails the script
  local out code sec
  out=$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 4 \
        "http://127.0.0.1:$1$2" 2>/dev/null || echo "000 0")
  read -r code sec <<< "$out"
  awk -v c="$code" -v s="$sec" 'BEGIN{printf "%s %.1f", c, s*1000}'
}

declare -A STARTUP_MS STARTUP_PEAK PORT_READY

run_variant() {
  local V="$1" PORT="$2"
  local LOG="$EV/compare-run-$V-$LABEL-$STAMP.log"
  local -a CMD
  if [[ "$V" == "jvm" ]]; then
    if [[ -n "$JVM_OPTS" ]]; then
      read -r -a OPTS <<< "$JVM_OPTS"
      CMD=("$JAVA" "${OPTS[@]}" -jar "$JAR")
    else
      CMD=("$JAVA" -jar "$JAR")
    fi
  else
    CMD=("$NATIVE")
  fi
  echo "---- starting $V on port $PORT ----"
  "${CMD[@]}" --server.port="$PORT" "${SPRING_ARGS[@]}" > "$LOG" 2>&1 &
  local PID=$!
  local T0; T0=$(date +%s%3N)
  local ready=0 startup_ms=-1 peak=0 elapsed=0 r c
  for i in $(seq 1 600); do
    if ! kill -0 "$PID" 2>/dev/null; then
      echo "PROCESS EXITED ($V) -- last 30 log lines:"; tail -30 "$LOG" || true; break
    fi
    r=$(rss_mb "$PID"); c=$(cpu_sec "$PID")
    if awk -v a="$r" -v b="$peak" 'BEGIN{exit !(a>b)}'; then peak="$r"; fi
    if port_open "$PORT"; then
      ready=1; startup_ms=$(( $(date +%s%3N) - T0 )); break
    fi
    elapsed=$(( ($(date +%s%3N) - T0) / 1000 ))
    printf '%s,startup,%s,%s,%s,0,,,\n' "$V" "$elapsed" "$r" "$c" >> "$CSV"
    sleep 0.5
  done
  PORT_READY[$V]=$ready
  STARTUP_MS[$V]=$startup_ms
  STARTUP_PEAK[$V]=$peak
  echo "$V: port_ready=$ready startup_ms=$startup_ms startup_peak_MB=$peak"
  if [[ "$ready" == "1" ]]; then
    local i code ms
    for i in $(seq 1 20); do
      r=$(rss_mb "$PID"); c=$(cpu_sec "$PID")
      read -r code ms <<< "$(http_probe "$PORT" "$PROBE")"
      printf '%s,steady,%s,%s,%s,1,%s,%s\n' "$V" "$((i*INTERVAL))" "$r" "$c" "$code" "$ms" >> "$CSV"
      sleep "$INTERVAL"
    done
  fi
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
  sleep 1
}

run_variant jvm "$PORT_J"
run_variant native "$PORT_N"

# ---------------- native stability phase ----------------
echo "---- native stability: ${DURATION}s ----"
SLOG="$EV/compare-run-native-stability-$LABEL-$STAMP.log"
"$NATIVE" --server.port="$PORT_N" "${SPRING_ARGS[@]}" > "$SLOG" 2>&1 &
SPID=$!
sready=0
for i in $(seq 1 600); do
  if port_open "$PORT_N"; then sready=1; break; fi
  if ! kill -0 "$SPID" 2>/dev/null; then
    echo "native stability process exited"; tail -20 "$SLOG" || true; break
  fi
  sleep 0.5
done
echo "native stability port_ready=$sready"
if [[ "$sready" == "1" ]]; then
  N=$((DURATION / INTERVAL))
  [[ "$N" -lt 1 ]] && N=1
  for i in $(seq 1 "$N"); do
    r=$(rss_mb "$SPID"); c=$(cpu_sec "$SPID")
    read -r code ms <<< "$(http_probe "$PORT_N" "$PROBE")"
    printf 'native,stability,%s,%s,%s,1,%s,%s\n' "$((i*INTERVAL))" "$r" "$c" "$code" "$ms" >> "$CSV"
    sleep "$INTERVAL"
  done
fi
kill "$SPID" 2>/dev/null || true
wait "$SPID" 2>/dev/null || true

# ---------------- aggregate ----------------
python3 - "$CSV" "$JSON" "$LABEL" "$NATIVE" "$JAR" "$DURATION" \
        "${STARTUP_MS[jvm]:-0}" "${STARTUP_MS[native]:-0}" \
        "${STARTUP_PEAK[jvm]:-0}" "${STARTUP_PEAK[native]:-0}" \
        "${PORT_READY[jvm]:-0}" "${PORT_READY[native]:-0}" <<'PY'
import csv, json, os, sys
(csv_p, json_p, label, native, jar, duration,
 jvm_ms, nat_ms, jvm_peak, nat_peak, jvm_ready, nat_ready) = sys.argv[1:13]
rows = list(csv.DictReader(open(csv_p, encoding='utf-8')))
phase = lambda v, p: [r for r in rows if r['variant'] == v and r['phase'] == p]
def stats(v, p):
    rs = phase(v, p)
    rss = [float(r['rss_MB']) for r in rs if r['rss_MB'] not in ('', '0')]
    codes = [r['http_code'] for r in rs if r.get('http_code')]
    lat = [float(r['http_ms']) for r in rs if r.get('http_ms') not in (None, '')]
    return {
        'samples': len(rs),
        'rss_avg_MB': round(sum(rss)/len(rss), 1) if rss else None,
        'rss_min_MB': min(rss) if rss else None,
        'rss_max_MB': max(rss) if rss else None,
        'http_success': sum(1 for c in codes if c != '000'),
        'http_total': len(codes),
        'http_latency_avg_ms': round(sum(lat)/len(lat), 1) if lat else None,
    }
out = {
    'label': label,
    'native_bytes': os.path.getsize(native),
    'jar_bytes': os.path.getsize(jar),
    'stability_duration_s': int(duration),
    'startup_ms': {'jvm': int(jvm_ms), 'native': int(nat_ms)},
    'startup_peak_rss_MB': {'jvm': float(jvm_peak), 'native': float(nat_peak)},
    'port_ready': {'jvm': int(jvm_ready), 'native': int(nat_ready)},
    'steady': {v: stats(v, 'steady') for v in ('jvm', 'native')},
    'native_stability': stats('native', 'stability'),
}
s = out['native_stability']['rss_avg_MB']
rss = [float(r['rss_MB']) for r in phase('native', 'stability') if r['rss_MB'] not in ('', '0')]
out['native_stability']['rss_first_MB'] = rss[0] if rss else None
out['native_stability']['rss_last_MB'] = rss[-1] if rss else None
out['native_stability']['rss_drift_MB'] = round(rss[-1] - rss[0], 1) if len(rss) > 1 else None
json.dump(out, open(json_p, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
PY
echo "COMPARE_OK csv=$CSV json=$JSON"
