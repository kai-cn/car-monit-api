#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-slim-jars.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# v3-slim-jars.sh -- minimal release packaging for all six JDK worktrees.
#
# Run INSIDE WSL:
#   bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-slim-jars.sh --audit
#   bash .../v3-slim-jars.sh --build --rebuild-jars        # FIRST re-package 4 stale jars, then build
#   bash .../v3-slim-jars.sh --build --jdk 25 --app api
#   bash .../v3-slim-jars.sh --build                       # all 6 combos
#   bash .../v3-slim-jars.sh --build --strip --flat        # + strip useless entries, flatten final image
#
# KEY FINDING (verified 2026-11-15): all six poms already carry the same
# excludeGroupIds / classifier excludes, but the jdk21/25 jars were built at
# 12:46-13:01 on 11-14, BEFORE the pom slimming change at 21:06-21:09.
# Only jdk17 jars (built 22:00) reflect the slim config. Stale jars contain:
#   backend jdk21/25 : calcite-core + groovy + aliyun-mns + linq4j = 21,448,068 B
#   api     jdk21/25 : 4 non-linux-x86_64 netty-codec-native-quic = 9,331,379 B
# Therefore --rebuild-jars is the single highest-value minimization step:
# no source change needed, just re-package with the CURRENT poms.
#
# What it does (each step independently verifiable):
#   A. audit    : read-only size report of the 6 fat jars and their BOOT-INF/lib
#   B. jdeps    : compute per-JDK module set -> jlink runtime (~66MB vs JDK ~303MB)
#   C. strip    : optional, remove ONLY provably dead entries (non-linux-x86_64
#                 Netty native jars, Flink leftovers, docs/licenses). Writes a
#                 NEW jar, never overwrites the source jar.
#   D. build    : layered Dockerfile FROM car-monit-sys:local (152MB, MySQL-free)
#                 + shared JRE layer + thin app layer. Output tag :min-jdkN.
#                 Existing :slim tags are NEVER touched (rollback path).
#   E. flat     : optional `docker export | docker import` to collapse layers for
#                 a single deliverable. NOTE: this DESTROYS cross-image layer
#                 sharing, so only use it for one-off export, not local storage.
#   F. report   : byte-size comparison table + smoke test (java -version).
#
# Measured baseline already achieved (history, do not re-do blindly):
#   api jar 275,304,862 -> 211,030,709 B (-23.3%), backend -10.7%
#   jlink runtime 66MB vs full JDK 303MB
#   car-monit-sys:local 255MB -> 152MB (MySQL RPMs removed)
#   backend image 965MB -> 504MB -> 401MB ; api 1.04GB -> 537MB -> 434MB
set -uo pipefail

ROOT=${ROOT:-/mnt/d/work/IdeaProjects}
OUT=${OUT:-/mnt/d/work/runtime-logs/v3-ops/slim}
CACHE=${CACHE:-/home/dev/.cache/ci-toolchain}
BASE=${BASE:-car-monit-sys:local}
JDKS=(17 21 25)
APPS=(api backend)
EP=/dev/null

DO_AUDIT=0; DO_BUILD=0; DO_STRIP=0; DO_FLAT=0; DO_REBUILD=0
ONLY_JDK=""; ONLY_APP=""
MVN_OFFLINE=${MVN_OFFLINE:-0}
while [ $# -gt 0 ]; do
  case "$1" in
    --audit) DO_AUDIT=1 ;;
    --build) DO_BUILD=1 ;;
    --rebuild-jars) DO_REBUILD=1 ;;
    --strip) DO_STRIP=1 ;;
    --flat) DO_FLAT=1 ;;
    --jdk) ONLY_JDK="$2"; shift ;;
    --app) ONLY_APP="$2"; shift ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done
[ "$DO_AUDIT" = 0 ] && [ "$DO_BUILD" = 0 ] && DO_AUDIT=1

mkdir -p "$OUT"/{jars,jre,build,report}
TS=$(date +%Y%m%d-%H%M%S)
REPORT="$OUT/report/slim-$TS.txt"
exec > >(tee "$REPORT") 2>&1
echo "################ V3 MINIMAL PACKAGING $TS ################"

jar_path() {
  local v=$1 a=$2
  if [ "$a" = api ]; then echo "$ROOT/car-monit-api-jdk$v/pro-business-api/target/pro-business-api-1.0.jar"
  else echo "$ROOT/car-monit-backend-jdk$v/ruoyi-admin/target/ruoyi-admin.jar"; fi
}
jdk_home() {
  local v=$1
  local override="JDK${v}_HOME"
  if [ -n "${!override:-}" ]; then echo "${!override}"; return; fi
  find "$CACHE" -maxdepth 1 -type d \( -name "jdk-$v*" -o -name "jdk-${v}.*" -o -name "*jdk*${v}*" \) 2>/dev/null | sort | head -1
}

# ---------------- A. audit ----------------
if [ "$DO_AUDIT" = 1 ]; then
  echo "== A. jar audit (read-only) =="
  printf '%-8s %-8s %14s %10s %12s %12s\n' APP JDK JAR_BYTES LIB_COUNT LIB_BYTES CLASSES_BYTES
  for v in "${JDKS[@]}"; do
    for a in "${APPS[@]}"; do
      j=$(jar_path "$v" "$a")
      [ -f "$j" ] || { echo "MISSING $j"; continue; }
      sz=$(stat -c %s "$j")
      tmp=$(mktemp -d)
      unzip -qq -o "$j" 'BOOT-INF/lib/*' 'BOOT-INF/classes/*' -d "$tmp" 2>/dev/null || true
      lc=$(find "$tmp/BOOT-INF/lib" -name '*.jar' 2>/dev/null | wc -l)
      lb=$(du -sb "$tmp/BOOT-INF/lib" 2>/dev/null | cut -f1); lb=${lb:-0}
      cb=$(du -sb "$tmp/BOOT-INF/classes" 2>/dev/null | cut -f1); cb=${cb:-0}
      printf '%-8s %-8s %14s %10s %12s %12s\n' "$a" "jdk$v" "$sz" "$lc" "$lb" "$cb"
      rm -rf "$tmp"
    done
  done
  echo
  echo "-- largest nested jars (jdk17/api) --"
  j=$(jar_path 17 api)
  if [ -f "$j" ]; then
    tmp=$(mktemp -d); unzip -qq -o "$j" 'BOOT-INF/lib/*' -d "$tmp" 2>/dev/null || true
    find "$tmp/BOOT-INF/lib" -name '*.jar' -printf '%s %f\n' 2>/dev/null | sort -rn | head -20
    echo "-- dead-weight candidates (non linux-x86_64 native / flink / docs) --"
    find "$tmp/BOOT-INF/lib" -name '*.jar' -printf '%f\n' 2>/dev/null | \
      grep -iE 'osx|macos|windows|aarch_64|flink|LICENSE|README' || echo "   none"
    rm -rf "$tmp"
  fi
  echo
fi

if [ "$DO_BUILD" != 1 ]; then echo "AUDIT only. Use --build to produce images. Report: $REPORT"; exit 0; fi

command -v docker >/dev/null 2>&1 || { echo "FATAL: docker required"; exit 1; }
command -v jq >/dev/null 2>&1 && echo "jq: available" || echo "jq: absent (not required)"

proj_root() {
  local v=$1 a=$2
  if [ "$a" = api ]; then echo "$ROOT/car-monit-api-jdk$v"; else echo "$ROOT/car-monit-backend-jdk$v"; fi
}
module_for() { if [ "$1" = api ]; then echo "pro-business-api"; else echo "ruoyi-admin"; fi; }

# ---------------- R. re-package stale jars with the CURRENT poms ----------------
if [ "$DO_REBUILD" = 1 ]; then
  echo "== R. re-package jars with CURRENT poms (fixes stale jdk21/25 artifacts) =="
  if ! command -v mvn >/dev/null 2>&1; then
    echo "FATAL: mvn is not on PATH. Use the WSL Maven (e.g. /opt/maven/bin) and re-run."
    exit 1
  fi
  for v in "${JDKS[@]}"; do
    [ -n "$ONLY_JDK" ] && [ "$ONLY_JDK" != "$v" ] && continue
    JH=$(jdk_home "$v")
    [ -z "$JH" ] && { echo "WARN: no JDK $v -> skip rebuild for jdk$v"; continue; }
    for a in "${APPS[@]}"; do
      [ -n "$ONLY_APP" ] && [ "$ONLY_APP" != "$a" ] && continue
      proj=$(proj_root "$v" "$a"); mod=$(module_for "$a")
      [ -f "$proj/pom.xml" ] || { echo "WARN: missing $proj/pom.xml -> skip"; continue; }
      before=$(stat -c %s "$(jar_path "$v" "$a")" 2>/dev/null || echo 0)
      off=""; [ "$MVN_OFFLINE" = 1 ] && off="-o"
      echo "  mvn package $a jdk$v JAVA_HOME=$JH"
      (cd "$proj" && JAVA_HOME="$JH" PATH="$JH/bin:$PATH" \
         mvn -B -ntp $off -DskipTests package -pl "$mod" -am) \
         > "$OUT/build/mvn-$a$v.log" 2>&1 \
        || { echo "  FAIL: see $OUT/build/mvn-$a$v.log"; continue; }
      after=$(stat -c %s "$(jar_path "$v" "$a")" 2>/dev/null || echo 0)
      echo "  bytes: $before -> $after (delta $((after-before)))"
    done
  done
  echo "Re-run --audit afterwards to confirm the dead-weight candidates dropped to ~0."
  echo
fi

# ---------------- B..F per JDK / app ----------------
for v in "${JDKS[@]}"; do
  [ -n "$ONLY_JDK" ] && [ "$ONLY_JDK" != "$v" ] && continue
  JH=$(jdk_home "$v")
  if [ -z "$JH" ] || [ ! -x "$JH/bin/jlink" ]; then
    echo "WARN: no JDK $v with jlink found under $CACHE (set JDK${v}_HOME) -> skip jdk$v"; continue
  fi
  echo "== B. jlink runtime for JDK $v from $JH =="
  JR="$OUT/jre/jre$v"
  rm -rf "$JR"
  libdir="$OUT/build/libs$v"; rm -rf "$libdir"; mkdir -p "$libdir"
  for a in "${APPS[@]}"; do
    j=$(jar_path "$v" "$a")
    [ -f "$j" ] && unzip -qq -o "$j" 'BOOT-INF/lib/*' -d "$OUT/build/x-$v-$a" 2>/dev/null && \
      cp "$OUT/build/x-$v-$a"/BOOT-INF/lib/*.jar "$libdir/" 2>/dev/null || true
  done
  MODS=$(find "$libdir" -name '*.jar' -print0 | xargs -0 "$JH/bin/jdeps" \
          --ignore-missing-deps --multi-release "$v" --print-module-deps 2>/dev/null \
          | tr ',' '\n' | sort -u | grep -v '^$' | paste -sd,)
  EXTRA="java.desktop,java.instrument,java.management,java.naming,java.sql,java.xml,java.logging,java.net.http,java.prefs,java.rmi,java.security.jgss,java.security.sasl,java.transaction.xa,java.xml.crypto,jdk.unsupported,jdk.crypto.ec,jdk.crypto.cryptoki,jdk.management,jdk.management.agent,java.sql.rowset,jdk.net"
  ALL=$(printf '%s,%s' "$MODS" "$EXTRA" | tr ',' '\n' | sort -u | grep -v '^$' | paste -sd,)
  echo "modules: $ALL"
  "$JH/bin/jlink" --add-modules "$ALL" --output "$JR" \
     --strip-debug --no-man-pages --no-header-files --compress=zip-9 2>&1 | head -5
  echo "jre size: $(du -sh "$JR" | cut -f1)"
  "$JR/bin/java" --version 2>&1 | head -2

  # shared JRE image layer (one per JDK, reused by both apps)
  jretag="car-monit-jre:jdk$v"
  ctx="$OUT/build/jrectx$v"; rm -rf "$ctx"; mkdir -p "$ctx"
  cp -a "$JR" "$ctx/jre"
  cat > "$ctx/Dockerfile" <<EOF
FROM $BASE
COPY jre /opt/jre
ENV JAVA_HOME=/opt/jre
ENV PATH=/opt/jre/bin:/usr/bin:/bin
EOF
  docker build -q -t "$jretag" -f "$ctx/Dockerfile" "$ctx" || { echo "FATAL: jre image build failed"; exit 1; }

  for a in "${APPS[@]}"; do
    [ -n "$ONLY_APP" ] && [ "$ONLY_APP" != "$a" ] && continue
    SRC=$(jar_path "$v" "$a")
    [ -f "$SRC" ] || { echo "WARN: missing jar $SRC -> skip"; continue; }
    echo "== C. strip candidate $a jdk$v =="
    WORK="$OUT/jars/$a$v"; rm -rf "$WORK"; mkdir -p "$WORK"
    cp "$SRC" "$WORK/app.jar"
    echo "   source bytes: $(stat -c %s "$WORK/app.jar")"
    if [ "$DO_STRIP" = 1 ]; then
      # Only entries that are provably unusable on linux/x86_64. Never touches classes.
      dead=$(unzip -Z1 "$WORK/app.jar" 2>/dev/null | grep -E \
        'BOOT-INF/lib/.*(osx|macos|windows|win32|aarch_64|linux-aarch|flink-[^/]*\.jar)|BOOT-INF/lib/.*(LICENSE|README|NOTICE)\.txt' || true)
      if [ -n "$dead" ]; then
        printf '%s\n' "$dead" > "$WORK/removed-entries.txt"
        # zip -d needs arguments; feed line by line to stay under ARG_MAX
        while IFS= read -r e; do
          [ -z "$e" ] && continue
          (cd "$WORK" && zip -qq -d app.jar "$e") 2>/dev/null || true
        done <<< "$dead"
        echo "   removed entries: $(wc -l < "$WORK/removed-entries.txt") ; new bytes: $(stat -c %s "$WORK/app.jar")"
      else
        echo "   nothing to strip"
      fi
    else
      echo "   (strip disabled; pass --strip to enable)"
    fi

    echo "== D. build layered image car-monit-$a:min-jdk$v =="
    ctx="$OUT/build/$a$v"; rm -rf "$ctx"; mkdir -p "$ctx"
    cp "$WORK/app.jar" "$ctx/app.jar"
    # fonts are required by backend captcha; keep the verified offline copy
    cp /usr/share/fonts/dejavu/DejaVuSans.ttf "$ctx/DejaVuSans.ttf" 2>/dev/null || true
    cat > "$ctx/Dockerfile" <<EOF
FROM $jretag
WORKDIR /app
COPY app.jar /app/app.jar
COPY DejaVuSans.ttf /opt/jre/lib/fonts/DejaVuSans.ttf
ENTRYPOINT ["/opt/jre/bin/java"]
EOF
    if [ ! -f "$ctx/DejaVuSans.ttf" ]; then
      sed -i '/DejaVuSans.ttf/d' "$ctx/Dockerfile"
      echo "   WARN: DejaVuSans.ttf missing -> captcha font may break; add it before using backend"
    fi
    tag="car-monit-$a:min-jdk$v"
    docker build -q -t "$tag" -f "$ctx/Dockerfile" "$ctx" || { echo "FATAL: build $tag failed"; exit 1; }

    if [ "$DO_FLAT" = 1 ]; then
      echo "== E. flatten $tag (export|import) =="
      cid=$(docker create "$tag" 2>/dev/null)
      docker export "$cid" | docker import - "${tag}-flat" >/dev/null
      docker rm -f "$cid" >/dev/null 2>&1 || true
      echo "   flattened tag: ${tag}-flat"
    fi

    echo "== F. smoke =="
    docker run --rm --entrypoint /opt/jre/bin/java "$tag" -version 2>&1 | head -2
    # D: had only ~10.7GB free at baseline: never keep 6 x ~200MB jar copies.
    rm -f "$WORK/app.jar" "$ctx/app.jar" "$ctx/DejaVuSans.ttf"
    rm -rf "$ctx/jre" 2>/dev/null || true
  done
  rm -rf "$ctx/jre" "$OUT/build/x-$v-api" "$OUT/build/x-$v-backend" 2>/dev/null || true
done

echo
echo "== SIZE REPORT =="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' | \
  grep -E 'REPOSITORY|car-monit-(api|backend|jre|sys)' | sort
echo
echo "NOTE: layered images share the $BASE and jre layers -> real disk cost is far"
echo "      lower than the sum of the SIZE column. Use --flat ONLY for export."
echo "Rollback: existing car-monit-*:slim tags are untouched."
echo "Import to cluster: k3d image import car-monit-api:min-jdk25 car-monit-backend:min-jdk25 -c v3"
echo "Report: $REPORT"
