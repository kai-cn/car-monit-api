#!/usr/bin/env bash
# Start the plain fat jar (JVM mode) with the same env as the native run, wait for
# the HTTP port, report startup time and RSS, then stop it.
# Usage: v3-run-jvm-linux.sh <jar> <label> [sample-seconds] [port]
set -u

JAR=${1:?usage: v3-run-jvm-linux.sh <jar> <label> [sample-seconds] [port]}
LABEL=${2:?label required}
SAMPLE=${3:-20}
PORT=${4:-9902}
JAVA=${JAVA:-/home/dev/tools/mandrel-25/bin/java}
EVID=/mnt/d/work/runtime-logs/v3-ops/evidence
LOG="$EVID/jvm-run-linux-$LABEL.log"
SUM="$EVID/jvm-run-linux-$LABEL.summary.txt"

PASS=$(docker exec opengauss env 2>/dev/null | sed -n 's/^[^=]*GS_PASSWORD=//p' | tr -d '\r' | head -n 1)
if [ -z "${PASS:-}" ]; then echo "FATAL: cannot read GS_PASSWORD" >&2; exit 4; fi

export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME=gaussdb
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD="$PASS"

echo "=== jvm runner ===" | tee "$SUM"
echo "jar   : $JAR" | tee -a "$SUM"
echo "java  : $JAVA" | tee -a "$SUM"
echo "label : $LABEL" | tee -a "$SUM"
echo "jar size bytes: $(stat -c %s "$JAR")" | tee -a "$SUM"

START_MS=$(date +%s%3N)
"$JAVA" -XX:+UseSerialGC -Xmx512m -jar "$JAR" >"$LOG" 2>&1 &
PID=$!

READY=0
EXITED=0
for _ in $(seq 1 240); do
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    exec 3>&- 2>/dev/null || true
    READY=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then EXITED=1; break; fi
  sleep 1
done
READY_MS=$(date +%s%3N)
echo "port_ready     : $READY" | tee -a "$SUM"
echo "process_exited : $EXITED" | tee -a "$SUM"
if [ "$READY" = "1" ]; then
  echo "startup_ms     : $((READY_MS - START_MS))" | tee -a "$SUM"
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/" || echo 000)
  echo "http_root_code : $CODE" | tee -a "$SUM"
  sleep "$SAMPLE"
fi

if kill -0 "$PID" 2>/dev/null; then
  RSS_KB=$(ps -o rss= -p "$PID" | tr -d ' ')
  echo "rss_kb         : ${RSS_KB:-unknown}" | tee -a "$SUM"
  echo "rss_mb         : $(( ${RSS_KB:-0} / 1024 ))" | tee -a "$SUM"
  echo "threads        : $(ps -o nlwp= -p "$PID" | tr -d ' ')" | tee -a "$SUM"
  echo "cpu_time       : $(ps -o time= -p "$PID" | tr -d ' ')" | tee -a "$SUM"
  kill -TERM "$PID" 2>/dev/null; sleep 5; kill -KILL "$PID" 2>/dev/null
fi

echo "=== startup evidence ===" | tee -a "$SUM"
grep -E "Started EcBusinessApiApplication|Tomcat started|APPLICATION FAILED" "$LOG" | tail -n 5 | tee -a "$SUM"
echo "summary: $SUM"
