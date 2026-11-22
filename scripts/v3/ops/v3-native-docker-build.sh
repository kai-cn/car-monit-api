#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-native-docker-build.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Package a Linux native ELF into a minimal OCI image and record its size.
#   BASE_IMAGE=... bash v3-native-docker-build.sh <elf> <tag> [dockerfile]
set -euo pipefail
ELF="${1:-}"
TAG="${2:-car-monit-api:native-jdk25}"
DOCKERFILE="${3:-/mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/templates/Dockerfile.native}"
EV="${EVIDENCE_DIR:-/mnt/d/work/runtime-logs/v3-ops/evidence}"
mkdir -p "$EV"
LOG="$EV/native-docker-$(echo "$TAG" | tr '/:' '__').log"
exec > >(tee "$LOG") 2>&1

[[ -f "$ELF" ]] || { echo "FATAL: ELF missing: $ELF"; exit 3; }
chmod 0755 "$ELF"
echo "==== native container build ===="
echo "elf=$ELF size=$(stat -c %s "$ELF") bytes"
echo "tag=$TAG base=${BASE_IMAGE:-debian:12-slim}"
file "$ELF"
echo "---- local base images ----"
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | head -20
# Keep the build context minimal: only the ELF (the Maven target/ also holds a
# 200MB fat jar and .so shims which must not be sent to the docker daemon).
CONTEXT=$(mktemp -d /tmp/native-docker-XXXXXX)
cp "$ELF" "$CONTEXT/app"
chmod 0755 "$CONTEXT/app"
docker build -f "$DOCKERFILE" \
  ${BASE_IMAGE:+--build-arg "BASE_IMAGE=$BASE_IMAGE"} \
  --build-arg "BINARY=app" \
  -t "$TAG" "$CONTEXT"
echo "context=$CONTEXT (contains only the ELF)"
echo "---- resulting image ----"
docker images "$TAG" --format '{{.Repository}}:{{.Tag}} {{.Size}} {{.ID}}'
echo "---- history ----"
docker history "$TAG" --no-trunc --format '{{.Size}}\t{{.CreatedBy}}' | head -10
echo "DOCKER_OK tag=$TAG"
