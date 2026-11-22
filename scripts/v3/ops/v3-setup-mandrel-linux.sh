#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-setup-mandrel-linux.sh
# 用途：安装配置 Mandrel 工具链
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Install a pinned Mandrel (Linux amd64) inside WSL2 and verify the native-image
# C toolchain. Idempotent; never overwrites an existing install.
#
#   bash v3-setup-mandrel-linux.sh [jdk-or-archive] [dest]
#     jdk-or-archive : 25 | 21 | 17   (default 25)  OR an explicit .tar.gz path
#     dest           : /home/dev/tools (Mandrel lands in dest/mandrel-<jdk>)
#
# Pinned releases (must match download-mandrel-linux.py):
#   25 -> 25.0.4.1-Final, 21 -> 23.1.13.0-Final, 17 -> 23.0.6.0-Final
# If the tarball is absent, the script tries the GitHub API asset endpoint from
# WSL; on networks where that is blocked, run on the Windows side first:
#   python D:\work\runtime-logs\v3-ops\download-mandrel-linux.py D:\jdk <jdk>
#
# The .tar.gz must be unpacked INSIDE the WSL ext4 filesystem: extracting it on
# /mnt/d (drvfs) loses symlinks/executable bits that native-image needs.
set -euo pipefail

ARG1="${1:-25}"
DEST="${2:-/home/dev/tools}"
JDK_DIR="/mnt/d/jdk"

case "$ARG1" in
  17|21|25)
    JDK="$ARG1"
    case "$JDK" in
      25) VER=25.0.4.1-Final ;;
      21) VER=23.1.13.0-Final ;;
      17) VER=23.0.6.0-Final ;;
    esac
    ARCHIVE=$(ls -1 "$JDK_DIR"/mandrel-java${JDK}-linux-amd64-*.tar.gz 2>/dev/null | grep -F "$VER" | head -1 || true)
    ARCHIVE=${ARCHIVE:-"$JDK_DIR/mandrel-java${JDK}-linux-amd64-${VER}.tar.gz"}
    ;;
  *)
    JDK=25
    ARCHIVE="$ARG1"
    ;;
esac
LINK="$DEST/mandrel-$JDK"

echo "==== Mandrel linux setup ===="
echo "date    : $(date -Is)"
echo "jdk     : $JDK"
echo "archive : $ARCHIVE"
echo "link    : $LINK"
echo "dest    : $DEST"
echo "user    : $(id -un) uid=$(id -u)"
echo "kernel  : $(uname -sr)"

# Already installed? Skip archive handling entirely (fast path for CI).
if [[ -x "$LINK/bin/native-image" ]]; then
  echo "ALREADY_INSTALLED: $LINK"
else
  if [[ ! -f "$ARCHIVE" ]]; then
    echo "---- archive missing, trying GitHub API asset download from WSL ----"
    python3 - "$ARCHIVE" "$JDK" "$VER" <<'PY' || true
import json, os, sys, urllib.request
dest, jdk, ver = sys.argv[1], sys.argv[2], sys.argv[3]
UA = {"User-Agent": "car-monit-v3-ops/1.0"}
tag = "mandrel-" + ver
url = "https://api.github.com/repos/graalvm/mandrel/releases/tags/" + tag
try:
    rel = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
    names = [a for a in rel["assets"]
             if a["name"].startswith("mandrel-java%s-linux-amd64-" % jdk)
             and a["name"].endswith(".tar.gz")]
    if not names:
        raise RuntimeError("no matching asset in " + tag)
    a = names[0]
    req = urllib.request.Request(a["url"], headers={**UA, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    print("DOWNLOADED", dest, os.path.getsize(dest), "bytes")
except Exception as e:
    print("WSL_DOWNLOAD_FAILED", type(e).__name__, e)
    print("Run on Windows: python D:\\work\\runtime-logs\\v3-ops\\download-mandrel-linux.py D:\\jdk " + jdk)
PY
  fi
  [[ -f "$ARCHIVE" ]] || {
    echo "FATAL: archive missing: $ARCHIVE"
    echo "HINT : python D:\\work\\runtime-logs\\v3-ops\\download-mandrel-linux.py D:\\jdk $JDK"
    exit 3
  }
fi
mkdir -p "$DEST"

if [[ ! -x "$LINK/bin/native-image" ]]; then
  echo "---- archive integrity ----"
  gzip -t "$ARCHIVE" || { echo "FATAL: corrupt gzip archive"; exit 5; }
fi

if [[ -x "$LINK/bin/native-image" ]]; then
  echo "ALREADY_INSTALLED: $LINK"
else
  echo "---- archive listing (top level) ----"
  # NOTE: never pipe tar -tzf into `head`: with `set -o pipefail` the SIGPIPE
  # from head closing early aborts the whole script (observed 2026-11-15).
  LIST=$(mktemp)
  tar -tzf "$ARCHIVE" > "$LIST"
  sed -n '1,5p' "$LIST"
  TOP=$(sed -n '1p' "$LIST" | cut -d/ -f1)
  rm -f "$LIST"
  echo "top_level_dir=$TOP"

  echo "---- extracting (ext4, preserves symlinks/modes) ----"
  tar -xzf "$ARCHIVE" -C "$DEST"
  [[ -d "$DEST/$TOP" ]] || { echo "FATAL: expected $DEST/$TOP after extract"; exit 4; }
  ln -sfn "$DEST/$TOP" "$LINK"
  echo "linked $LINK -> $DEST/$TOP"
fi

export JAVA_HOME="$LINK"
export PATH="$LINK/bin:$PATH"

echo "---- versions ----"
"$LINK/bin/java" -version 2>&1 | head -4
"$LINK/bin/native-image" --version 2>&1 | head -5
cat "$LINK/release" 2>/dev/null | head -8 || true

echo "---- C toolchain ----"
MISSING=0
for c in gcc g++ ld pkg-config make; do
  p=$(command -v "$c" || true)
  printf '%-12s %s\n' "$c" "${p:-MISSING}"
  [[ -z "$p" ]] && MISSING=1
done
echo "---- devel headers ----"
for f in /usr/include/zlib.h /usr/include/stdio.h; do
  [[ -f "$f" ]] && echo "OK $f" || { echo "MISSING $f"; MISSING=1; }
done

if [[ "$MISSING" == "1" ]]; then
  echo "---- attempting package install ----"
  if [[ "$(id -u)" == "0" ]]; then
    dnf install -y gcc gcc-c++ glibc-devel zlib-devel libstdc++-devel make pkgconf-pkg-config
  elif sudo -n true 2>/dev/null; then
    sudo -n dnf install -y gcc gcc-c++ glibc-devel zlib-devel libstdc++-devel make pkgconf-pkg-config
  else
    echo "WARN: no passwordless sudo; install manually:"
    echo "  sudo dnf install -y gcc gcc-c++ glibc-devel zlib-devel libstdc++-devel make pkgconf-pkg-config"
  fi
fi

echo "---- maven / repo ----"
MVN="${MVN:-/mnt/d/work/apache-maven/bin/mvn}"
if [[ -x "$MVN" ]]; then
  "$MVN" -v 2>&1 | head -4
else
  echo "WARN: $MVN not executable on this filesystem; set MVN=/path/to/mvn"
fi
du -sh "${MAVEN_REPO:-/home/dev/.m2/repository}" 2>/dev/null || echo "WARN: maven repo not pre-warmed"

echo "---- smoke: native-image on Hello world ----"
TMP=$(mktemp -d)
cat > "$TMP/Hello.java" <<'JAVA'
public class Hello { public static void main(String[] a) { System.out.println("hello native"); } }
JAVA
"$LINK/bin/javac" -d "$TMP" "$TMP/Hello.java"
(cd "$TMP" && "$LINK/bin/native-image" --no-fallback -H:Name=hello-native -cp . Hello) 2>&1 | tail -12
"$TMP/hello-native" 2>&1 | head -3
echo "hello_binary_bytes=$(stat -c %s "$TMP/hello-native" 2>/dev/null || echo 0)"
rm -rf "$TMP"

echo "SETUP_OK mandrel=$LINK"
