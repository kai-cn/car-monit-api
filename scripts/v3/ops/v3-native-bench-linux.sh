#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-native-bench-linux.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Measure a Spring Boot native ELF inside WSL: startup time, RSS, CPU.
#   bash v3-native-bench-linux.sh <binary> <port> <label> [sample-sec] [extra-args...]
set -euo pipefail
BIN="${1:-}"; PORT="${2:-19903}"; LABEL="${3:-native-linux}"
SAMPLE="${4:-30}"; shift 4 || true
EXTRA=("$@")

EV="${EVIDENCE_DIR:-/mnt/d/work/runtime-logs/v3-ops/evidence}"
mkdir -p "$EV"
STAMP=$(date +%Y%m%d-%H%M%S)
LOG="$EV/native-run-$LABEL-$STAMP.log"
CSV="$EV/native-bench-$LABEL-$STAMP.csv"

[[ -x "$BIN" ]] || { echo "FATAL: not executable: $BIN"; exit 3; }
echo "s,phase,rss_MB,cpu_seconds,port_open" > "$CSV"
BYTES=$(stat -c %s "$BIN")
echo "==== NATIVE LINUX BENCH $LABEL ===="
echo "binary=$BIN size_bytes=$BYTES size_MB=$(awk -v b=$BYTES 'BEGIN{printf "%.2f",b/1048576}')"
echo "port=$PORT log=$LOG csv=$CSV"
file "$BIN"

T0=$(date +%s%3N)
"$BIN" --server.port="$PORT" "${EXTRA[@]}" > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID"

ready=0; startup_ms=-1; peak_kb=0
for i in $(seq 1 360); do
  R=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ' || true); R=${R:-0}
  if [ "$R" -gt "$peak_kb" ]; then peak_kb=$R; fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "PROCESS EXITED during startup; tail of log:"; tail -25 "$LOG"; break
  fi
  if (echo > "/dev/tcp/127.0.0.1/$PORT") >/dev/null 2>&1; then
    ready=1; startup_ms=$(( $(date +%s%3N) - T0 )); break
  fi
  sleep 0.5
done
echo "port_ready=$ready startup_ms=$startup_ms startup_peak_MB=$(awk -v r=$peak_kb 'BEGIN{printf "%.1f",r/1024}')"

for i in $(seq 0 $((SAMPLE/2))); do
  if ! kill -0 "$PID" 2>/dev/null; then echo "process exited at sample $i"; break; fi
  RSS=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ' || true); RSS=${RSS:-0}
  CPU=$(ps -o time= -p "$PID" 2>/dev/null | tr -d ' ' || true)
  RSSMB=$(awk -v r=$RSS 'BEGIN{printf "%.1f",r/1024}')
  echo "$((i*2)),steady,$RSSMB,$CPU,$ready" | tee -a "$CSV"
  sleep 2
done

echo "==== RESULT ===="
echo "label=$LABEL size_bytes=$BYTES startup_ms=$startup_ms port_ready=$ready"
echo "log_tail:"; tail -20 "$LOG"
if kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; sleep 1; kill -9 "$PID" 2>/dev/null || true; fi
echo "csv=$CSV"
