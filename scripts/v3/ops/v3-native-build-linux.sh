#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-native-build-linux.sh
# 用途：在 Linux 构建 native image
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Spring Boot 4.1.2 AOT + Mandrel native-image build on Linux x86_64 (inside WSL2).
#
#   bash v3-native-build-linux.sh <app> <jdk> <project-dir> [label]
#     app        : api | backend
#     jdk        : 25 | 21 | 17   (25 uses Mandrel java25; 21/17 fall back to GraalVM CE if installed)
#     project-dir: e.g. /mnt/d/work/IdeaProjects/car-monit-api-jdk25
#
# Prerequisites (verified by this script, never silently skipped):
#   * Mandrel Linux amd64 unpacked under $MANDREL_HOME (default /home/dev/tools/mandrel-25)
#   * gcc / ld / zlib headers (dnf install -y gcc glibc-devel zlib-devel libstdc++-devel)
#   * Maven (default /mnt/d/work/apache-maven/bin/mvn, the Windows Maven install;
#            its bin/mvn is a POSIX script and works from WSL)
#   * Maven local repository (default /home/dev/.m2/repository, pre-warmed by CI)
#
# The buildArgs live in each module pom.xml (native-maven-plugin configuration),
# so the SAME pom drives both Windows and Linux native builds.
#
# All console output is tee'd to the evidence directory supplied by EVIDENCE_DIR.
set -euo pipefail

APP="${1:-}"
JDK="${2:-}"
PROJ="${3:-}"
LABEL="${4:-${APP}-jdk${JDK}-linux-$(date +%H%M%S)}"

if [[ -z "$APP" || -z "$JDK" || -z "$PROJ" ]]; then
  echo "usage: $0 <api|backend> <25|21|17> <project-dir> [label]" >&2
  exit 2
fi

case "$APP" in
  api)     MOD=pro-business-api ;;
  backend) MOD=ruoyi-admin ;;
  *) echo "unknown app: $APP" >&2; exit 2 ;;
esac

MANDREL_HOME="${MANDREL_HOME:-/home/dev/tools/mandrel-25}"
MVN="${MVN:-/mnt/d/work/apache-maven/bin/mvn}"
MAVEN_REPO="${MAVEN_REPO:-/home/dev/.m2/repository}"
EVIDENCE_DIR="${EVIDENCE_DIR:-/mnt/d/work/runtime-logs/v3-ops/evidence}"
LOG="$EVIDENCE_DIR/native-$LABEL.log"

mkdir -p "$EVIDENCE_DIR"
exec > >(tee "$LOG") 2>&1

echo "==== Linux native build ===="
echo "date        : $(date -Is)"
echo "app/jdk     : $APP / jdk$JDK"
echo "project     : $PROJ"
echo "module      : $MOD"
echo "mandrel     : $MANDREL_HOME"
echo "maven       : $MVN"
echo "repo        : $MAVEN_REPO"
echo "label       : $LABEL"
echo "kernel      : $(uname -sr)"
echo "cpu/mem     : nproc=$(nproc) $(free -m | awk '/^Mem:/{print $2" MB total, "$3" MB used"}')"

# ---------- stage sources into ext4 (optional, strongly recommended) ----------
# /mnt/d is drvfs: thousands of small target/classes writes are very slow.
# WORK_ROOT (e.g. /home/dev/native-work) keeps the whole build on ext4.
ORIG_PROJ="$PROJ"
if [[ -n "${WORK_ROOT:-}" ]]; then
  DST="$WORK_ROOT/$(basename "$PROJ")"
  echo "staging sources to ext4: $DST (excluding .git/target)"
  mkdir -p "$DST"
  (cd "$PROJ" && tar --exclude='./.git' --exclude='./target' -cf - .) | (cd "$DST" && tar -xf -)
  PROJ="$DST"
fi

# ---------- preconditions ----------
[[ -f "$MANDREL_HOME/bin/native-image" ]] || { echo "FATAL: $MANDREL_HOME/bin/native-image missing"; exit 3; }
[[ -x "$MVN" ]] || { echo "FATAL: maven not executable: $MVN"; exit 3; }
[[ -d "$PROJ/$MOD" ]] || { echo "FATAL: module dir missing: $PROJ/$MOD"; exit 3; }

export JAVA_HOME="$MANDREL_HOME"
export PATH="$MANDREL_HOME/bin:$PATH"
export MAVEN_OPTS="-Xmx2g -XX:+UseSerialGC"

echo "---- toolchain ----"
java -version 2>&1 | head -3
native-image --version 2>&1 | head -3
for c in gcc g++ ld pkg-config; do
  printf '%-10s %s\n' "$c" "$(command -v "$c" || echo MISSING)"
done
command -v gcc >/dev/null || { echo "FATAL: gcc missing (dnf install -y gcc glibc-devel zlib-devel libstdc++-devel)"; exit 3; }
"$MVN" -v 2>&1 | head -4

# ---------- stage 1: JVM reactor install ----------
# clean is required: a plain `install` keeps stale classes from a previous build in
# target/classes, so a deleted/renamed source file would silently survive in the jar
# that native-image consumes (observed with a deleted Orika @Configuration bean).
echo "==== [1/2] install reactor modules (JVM jar) ===="
cd "$PROJ"
"$MVN" -B -ntp -DskipTests -Dmaven.repo.local="$MAVEN_REPO" clean install -pl "$MOD" -am

# ---------- stage 2: AOT + native-image ----------
# clean is mandatory: the default JVM build leaves VehicleTrackFlinkJob.class in
# target/classes; the native-flink-exclude profile drops it at compile time because
# its Flink deps are provided and absent from the native classpath.
echo "==== [2/2] AOT + native-image ===="
T0=$(date +%s)
"$MVN" -B -ntp -Pnative,native-flink-exclude -DskipTests -Dmaven.repo.local="$MAVEN_REPO" \
  -pl "$MOD" clean native:compile
T1=$(date +%s)

BIN="$PROJ/$MOD/target/$MOD"
if [[ "$APP" == "api" ]]; then
  BIN="$PROJ/$MOD/target/pro-business-api"
fi
echo "==== artifacts ===="
find "$PROJ/$MOD/target" -maxdepth 1 -type f -printf '%f %s bytes\n' 2>/dev/null | sort
if [[ ! -f "$BIN" ]]; then
  echo "FATAL: expected binary not found: $BIN"
  exit 5
fi
file "$BIN"
echo "binary_bytes=$(stat -c %s "$BIN")"
echo "build_seconds=$((T1-T0))"
if [[ "$PROJ" != "$ORIG_PROJ" ]]; then
  mkdir -p "$ORIG_PROJ/$MOD/target"
  cp -f "$BIN" "$ORIG_PROJ/$MOD/target/"
  echo "copied_back=$ORIG_PROJ/$MOD/target/$(basename "$BIN")"
fi
echo "BUILD_OK label=$LABEL binary=$BIN"
