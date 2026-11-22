#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-inventory.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# v3-inventory.sh -- read-only inventory for WSL / docker / k3d node images.
# Run INSIDE WSL:  bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-inventory.sh
# No destructive command. Output is tee'd into D:\work\runtime-logs\v3-ops\evidence\.
set -uo pipefail

NODES=(k3d-v3-server-0 k3d-v3-agent-0 k3d-v3-agent-1)
OUT=${OUT:-/mnt/d/work/runtime-logs/v3-ops/evidence}
EP=unix:///run/k3s/containerd/containerd.sock
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$OUT/inventory-$TS.log"
exec > >(tee "$LOG") 2>&1

echo "################ V3 INVENTORY $TS ################"
echo "== host =="
date -Is
uname -r
echo "nproc=$(nproc)"
free -m
df -h / /mnt/d 2>/dev/null

echo
echo "== docker daemon =="
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}' 2>&1
docker info --format 'driver={{.Driver}} root={{.DockerRootDir}}' 2>&1
docker system df 2>&1

echo
echo "== docker images (WSL daemon) =="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}' 2>&1

echo
echo "== dangling images =="
docker images -f dangling=true --format '{{.ID}} {{.Size}}' 2>&1

echo
echo "== docker containers =="
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>&1

echo
echo "== k3d cluster =="
k3d cluster list 2>&1

echo
echo "== workloads in use (image / imageID) =="
K="docker exec k3d-v3-server-0 kubectl"
$K get nodes -o wide 2>&1
echo "-- deployments --"
$K get deploy -o wide 2>&1 | head -20
echo "-- pods --"
$K get pods -l 'app in (car-monit-api,car-monit-backend)' -o wide 2>&1 | head -20
echo "-- containerStatuses (name / image / imageID) --"
$K get pods -l 'app in (car-monit-api,car-monit-backend)' \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.image}{"\t"}{.imageID}{"\n"}{end}{end}' 2>&1

echo
for n in "${NODES[@]}"; do
  echo "================ NODE $n ================"
  docker exec "$n" crictl --runtime-endpoint "$EP" images 2>&1 | head -60
  echo "-- car-monit refs (ctr view) --"
  docker exec "$n" sh -c "ctr -n k8s.io images ls 2>/dev/null | grep -iE 'car-monit|REFERENCE' || true" 2>&1 | head -40
  echo "-- disk usage inside node --"
  docker exec "$n" sh -c "du -sh /var/lib/rancher/k3s/agent/containerd 2>/dev/null || true" 2>&1
done

echo
echo "== listening business ports on WSL host =="
ss -ltnp 2>/dev/null | grep -E ':(9989|9902|30989|30902|6379|6380|3307|5432)' || echo "none"

echo
echo "################ END (log: $LOG) ################"
