#!/usr/bin/env bash
# Start a Linux native-image build against the WSL openGauss instance, measure
# startup, RSS and HTTP readiness, then stop it.
#
# Usage: v3-run-native-linux.sh <binary> <label> [sample-seconds] [port]
#
# The datasource password is read from the openGauss container environment
# (GS_PASSWORD) and never written to disk.
#
# The app listens on server.port from application.yml (9902 for car-monit-api),
# NOT the Spring default 8080 -- pass it explicitly when it differs.
set -u

BIN=${1:?usage: v3-run-native-linux.sh <binary> <label> [sample-seconds] [port]}
LABEL=${2:?label required}
SAMPLE=${3:-25}
PORT=${4:-9902}

EVID=/mnt/d/work/runtime-logs/v3-ops/evidence
LOG="$EVID/native-run-linux-$LABEL.log"
SUM="$EVID/native-run-linux-$LABEL.summary.txt"
CONTAINER=opengauss

if [ ! -x "$BIN" ]; then
  echo "FATAL: not executable: $BIN" >&2
  exit 3
fi

# The container env may carry a BOM before the variable name, so strip anything
# up to and including "GS_PASSWORD=" instead of matching the key exactly.
PASS=$(docker exec "$CONTAINER" env 2>/dev/null | sed -n 's/^[^=]*GS_PASSWORD=//p' | tr -d '\r' | head -n 1)
if [ -z "${PASS:-}" ]; then
  echo "FATAL: cannot read GS_PASSWORD from container $CONTAINER" >&2
  exit 4
fi

export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME=gaussdb
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD="$PASS"

echo "=== runner ===" | tee "$SUM"
echo "binary  : $BIN" | tee -a "$SUM"
echo "label   : $LABEL" | tee -a "$SUM"
echo "log     : $LOG" | tee -a "$SUM"
echo "binary size bytes: $(stat -c %s "$BIN")" | tee -a "$SUM"

START_MS=$(date +%s%3N)
"$BIN" >"$LOG" 2>&1 &
PID=$!

READY=0
EXITED=0
for _ in $(seq 1 180); do
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    exec 3>&- 2>/dev/null || true
    READY=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    EXITED=1
    break
  fi
  sleep 1
done
READY_MS=$(date +%s%3N)

echo "port_ready      : $READY" | tee -a "$SUM"
echo "process_exited  : $EXITED" | tee -a "$SUM"
if [ "$READY" = "1" ]; then
  echo "startup_ms      : $((READY_MS - START_MS))" | tee -a "$SUM"
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/" || echo 000)
  echo "http_root_code  : $CODE" | tee -a "$SUM"
  sleep "$SAMPLE"
fi

if kill -0 "$PID" 2>/dev/null; then
  RSS_KB=$(ps -o rss= -p "$PID" | tr -d ' ')
  THREADS=$(ps -o nlwp= -p "$PID" | tr -d ' ')
  echo "rss_kb          : ${RSS_KB:-unknown}" | tee -a "$SUM"
  echo "rss_mb          : $(( ${RSS_KB:-0} / 1024 ))" | tee -a "$SUM"
  echo "threads         : ${THREADS:-unknown}" | tee -a "$SUM"
  echo "cpu_time        : $(ps -o time= -p "$PID" | tr -d ' ')" | tee -a "$SUM"
  kill -TERM "$PID" 2>/dev/null
  sleep 3
  kill -KILL "$PID" 2>/dev/null
else
  echo "process_exited_before_sampling: 1" | tee -a "$SUM"
fi

echo "=== last 40 log lines ===" | tee -a "$SUM"
tail -n 40 "$LOG" 2>/dev/null | tee -a "$SUM"
echo "summary: $SUM"
