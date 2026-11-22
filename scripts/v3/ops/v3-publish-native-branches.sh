#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-publish-native-branches.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Commit and push ONLY the native-image related files to the six JDK branches.
#
#   bash v3-publish-native-branches.sh            # dry-run: show what would be staged
#   bash v3-publish-native-branches.sh --apply   # commit + push (no force)
#
# Why a whitelist: each worktree also contains unrelated uncommitted work
# (self-hosted-ci.yml edits, local experiments). Those must NOT be pushed by
# this script. Nothing is ever force-pushed and no branch is created.
#
# Preconditions: each worktree is on its own branch with an upstream, and the
# Git Credential Manager holds a token with workflow scope.
set -euo pipefail

ROOT="/d/work/IdeaProjects"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1
MSG="build(native): Spring Boot 4 AOT mapper fix + Mandrel buildArgs + cloud/self-host CI"

for APP in api backend; do
  for JDK in 17 21 25; do
    D="$ROOT/car-monit-$APP-jdk$JDK"
    if [[ "$APP" == "api" ]]; then
      MOD="pro-business-api"
      AGENT_DIR="$MOD/src/main/resources/META-INF/native-image/com.ruoyi/pro-business-api-agent"
      REGISTRAR="$MOD/src/main/java/com/ruoyi/base/config/NativeMapperSqlSessionFactoryRegistrar.java"
      LABEL="wsl-k3s-api"
    else
      MOD="ruoyi-admin"
      AGENT_DIR="$MOD/src/main/resources/META-INF/native-image"
      REGISTRAR="ruoyi-framework/src/main/java/com/ruoyi/framework/config/NativeMapperSqlSessionFactoryRegistrar.java"
      LABEL="wsl-k3s"
    fi
    FILES=(
      ".github/workflows/native-image.yml"
      ".github/workflows/native-image-cloud.yml"
      "$MOD/pom.xml"
      "$REGISTRAR"
      "$AGENT_DIR"
    )
    echo "==== $D (branch $(git -C "$D" branch --show-current)) ===="
    PRESENT=()
    for f in "${FILES[@]}"; do
      if [[ -e "$D/$f" ]]; then PRESENT+=("$f"); else echo "  MISSING (skipped): $f"; fi
    done
    # Modified Mapper XML files (fully-qualified type alias fix) are tracked
    # files scattered over several modules, so collect them from git diff.
    while IFS= read -r f; do
      [[ -n "$f" ]] && PRESENT+=("$f")
    done < <(git -C "$D" diff --name-only -- '*Mapper.xml')
    if [[ "$APPLY" == "1" ]]; then
      git -C "$D" add -- "${PRESENT[@]}"
      if ! git -C "$D" diff --cached --quiet; then
        git -C "$D" commit -m "$MSG" >/dev/null
        echo "  committed: $(git -C "$D" rev-parse --short HEAD)"
      else
        echo "  nothing new to commit"
      fi
      # Always attempt the push: a previous run may have committed successfully
      # but failed on the network (Windows schannel + proxy drops the connection).
      # openssl backend + bounded retry is the verified workaround on this host.
      branch=$(git -C "$D" branch --show-current)
      pushed=0
      for attempt in 1 2 3; do
        if git -C "$D" -c http.sslBackend=openssl push origin "$branch" >/dev/null 2>&1; then
          echo "  PUSHED attempt=$attempt (runner label $LABEL)"; pushed=1; break
        fi
        echo "  push attempt $attempt failed, retrying..."
        sleep 5
      done
      if [[ "$pushed" == "0" ]]; then
        echo "  PUSH_FAILED for $branch (committed locally; rerun with --apply)"
      fi
    else
      printf '  would stage: %s\n' "${PRESENT[@]}"
    fi
  done
done

echo "PUBLISH_${APPLY}_DONE"
