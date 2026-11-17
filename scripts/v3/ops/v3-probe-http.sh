#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-probe-http.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Start an api binary/jar with runtime DB credentials, wait for the port, then
# probe a light read-only business endpoint that hits the openGauss datasource.
#
# Usage: v3-probe-http.sh <binary> <label> [port] [path]
# Credentials are injected into the child process only; never printed or stored.
set -u
BIN=${1:?binary required}
LABEL=${2:?label required}
PORT=${3:-19902}
PATHQ=${4:-/base/feerecords/list?pageNum=1\&pageSize=1}
EVID=/mnt/d/work/runtime-logs/v3-ops/evidence
LOG="$EVID/http-probe-$LABEL.log"
SUM="$EVID/http-probe-$LABEL.summary.txt"

GS_PASS=$(docker exec opengauss env 2>/dev/null | sed -n 's/^[^=]*GS_PASSWORD=//p' | tr -d '\r' | head -n 1)
MYSQL_PASS=$(docker exec mysql_wsl env 2>/dev/null | sed -n 's/^[^=]*MYSQL_ROOT_PASSWORD=//p' | tr -d '\r' | head -n 1)
[ -n "${GS_PASS:-}" ] && [ -n "${MYSQL_PASS:-}" ] || { echo FATAL_NO_CREDENTIALS >&2; exit 4; }
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME=gaussdb
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD="$GS_PASS"
export CARMONIT_MYSQL_USERNAME=root
export CARMONIT_MYSQL_PASSWORD="$MYSQL_PASS"

if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then echo FATAL_PORT_BUSY >&2; exit 5; fi

if [[ "$BIN" == *.jar ]]; then
  JAVA=${JAVA:-/home/dev/tools/mandrel-25/bin/java}
  "$JAVA" --add-opens=java.base/java.lang=ALL-UNNAMED -jar "$BIN" --server.port="$PORT" >"$LOG" 2>&1 &
else
  "$BIN" --server.port="$PORT" >"$LOG" 2>&1 &
fi
PID=$!
READY=0
for _ in $(seq 1 180); do
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then READY=1; break; fi
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
echo "port_ready=$READY" | tee "$SUM"
if [ "$READY" = "1" ]; then
  CODE=$(curl -s -o "$EVID/http-probe-$LABEL.body.json" -w '%{http_code}' --max-time 20 "http://127.0.0.1:$PORT$PATHQ" || echo 000)
  BYTES=$(stat -c %s "$EVID/http-probe-$LABEL.body.json" 2>/dev/null || echo 0)
  echo "http_code=$CODE body_bytes=$BYTES" | tee -a "$SUM"
  head -c 400 "$EVID/http-probe-$LABEL.body.json" | tee -a "$SUM" 2>/dev/null
  echo | tee -a "$SUM"
fi
echo "error_lines=$(grep -c 'ERROR' "$LOG" 2>/dev/null || echo 0)" | tee -a "$SUM"
tail -n 15 "$LOG" >>"$SUM" 2>/dev/null
kill -TERM "$PID" 2>/dev/null; sleep 2; kill -KILL "$PID" 2>/dev/null || true
echo "summary=$SUM"
