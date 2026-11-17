#!/usr/bin/env bash
# Reproduce startup + business-endpoint checks for every existing JDK artifact in the worktrees.
# Does NOT build artifacts; run build-jvm-jar.sh / v3-native-build-linux.sh first.
# ======================================================================
# 文件：scripts/v3/ops/v3-verify-jdk-matrix.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Reproduce api-side startup + business-endpoint verification across the JDK/framework
# matrix. Uses the corrected runners (both DB credentials injected, port 19902).
#
# Usage: v3-verify-jdk-matrix.sh [all|jdk25|boot4|boot3]
#   all   : every artifact that exists (default)
#   jdk25 : Boot4 JDK25 native + JVM
#   boot4 : Boot4 JDK25/21/17 JVM (+ JDK25 native)
#   boot3 : Boot3 JDK21/17 JVM + any native ELF present
#
# Builds are NOT performed here; use build-jvm-jar.sh and v3-native-build-linux.sh.
set -u
BASE=/mnt/d/work/IdeaProjects
OPS=$BASE/car-monit-api-java-V3/scripts/v3/ops
EVID=/mnt/d/work/runtime-logs/v3-ops/evidence
MODE=${1:-all}
PORT=19902

for C in opengauss mysql_wsl; do
  docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$C" || { echo "FATAL: container $C not running" >&2; exit 4; }
done

verify_one() {
  local KIND=$1 LABEL=$2 ART=$3 JAVA=${4:-}
  if [[ ! -f "$ART" ]]; then echo "SKIP $LABEL (artifact missing: $ART)"; return 0; fi
  echo "==== $LABEL ($KIND) ===="
  if [[ "$KIND" == jar ]]; then
    env JAVA="$JAVA" bash "$OPS/v3-run-jvm-linux.sh" "$ART" "$LABEL" 15 "$PORT" || true
    env JAVA="$JAVA" bash "$OPS/v3-probe-http.sh" "$ART" "$LABEL-http" "$PORT" || true
  else
    bash "$OPS/v3-run-native-linux.sh" "$ART" "$LABEL" 15 "$PORT" || true
    bash "$OPS/v3-probe-http.sh" "$ART" "$LABEL-http" "$PORT" || true
  fi
  echo
}

J25=$BASE/car-monit-api-jdk25/pro-business-api/target
J21=$BASE/car-monit-api-jdk21/pro-business-api/target
J17=$BASE/car-monit-api-jdk17/pro-business-api/target
JAVA21=/home/dev/.cache/ci-toolchain/jdk-21.0.13+9/bin/java
JAVA17=/home/dev/.cache/ci-toolchain/jdk-17.0.21+9/bin/java
JAVA25=/home/dev/tools/mandrel-25/bin/java

case "$MODE" in
  jdk25|all|boot4)
    verify_one native api-jdk25-boot4-native "$J25/pro-business-api"
    verify_one jar api-jdk25-boot4-jvm "$J25/pro-business-api-1.0.jar" "$JAVA25"
    ;;
esac
case "$MODE" in
  boot4|all)
    verify_one jar api-jdk21-boot4-jvm "$J21/pro-business-api-1.0.jar" "$JAVA21"
    verify_one jar api-jdk17-boot4-jvm "$J17/pro-business-api-1.0.jar" "$JAVA17"
    ;;
esac
case "$MODE" in
  boot3|all)
    verify_one jar api-jdk21-boot3-jvm "$J21/pro-business-api-1.0.jar" "$JAVA21"
    verify_one jar api-jdk17-boot3-jvm "$J17/pro-business-api-1.0.jar" "$JAVA17"
    verify_one native api-jdk21-boot3-native "$J21/pro-business-api"
    verify_one native api-jdk17-boot3-native "$J17/pro-business-api"
    ;;
esac

echo "==== summaries ===="
grep -H -E '^(port_ready|http_code|startup_ms|rss_mb|threads|error_lines)' "$EVID"/*summary.txt 2>/dev/null | tail -n 60
