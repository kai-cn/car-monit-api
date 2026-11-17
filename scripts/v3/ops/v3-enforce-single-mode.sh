#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-enforce-single-mode.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Enforce exactly ONE car-monit serving mode inside WSL (measured 2026-11-15).
#
# Reality on this host (verified via systemd + ps + kubectl):
#   standalone = systemd units car-monit-api.service / car-monit-backend.service
#                running /opt/car-monit-{api,backend}/app.jar (JDK17, 9902/9989)
#   cluster    = k3d v3, deployments car-monit-api / car-monit-backend (3+3 pods)
# Both were running simultaneously at 15:15 -> wasting ~2GB WSL RAM.
#
# Usage:
#   bash v3-enforce-single-mode.sh status
#   bash v3-enforce-single-mode.sh standalone   # keep systemd standalone, stop k3d
#   bash v3-enforce-single-mode.sh cluster      # keep k3d, stop systemd standalone
#
# No image/volume deletion. Reversible in the opposite mode.
set -uo pipefail
MODE=${1:-status}
K="docker exec k3d-v3-server-0 kubectl"
NODES=(k3d-v3-server-0 k3d-v3-agent-0 k3d-v3-agent-1 k3d-v3-serverlb)
UNITS=(car-monit-api.service car-monit-backend.service)

snapshot() {
  echo "---- snapshot $(date -Is) ----"
  echo "mem: $(free -m | awk '/^Mem:/{printf "total=%s used=%s avail=%s",$2,$3,$7}')"
  echo "standalone units:"
  for u in "${UNITS[@]}"; do printf "  %-32s %s\n" "$u" "$(systemctl is-active "$u" 2>/dev/null || echo unknown)"; done
  echo "standalone java pids: $(pgrep -f '/opt/car-monit-(api|backend)/app.jar' 2>/dev/null | tr '\n' ' ' || true)"
  echo "k3d node containers:"
  for n in "${NODES[@]}"; do
    printf "  %-24s %s\n" "$n" "$(docker inspect -f '{{.State.Status}}' "$n" 2>/dev/null || echo absent)"
  done
  local reps
  reps=$(docker exec k3d-v3-server-0 kubectl get deploy car-monit-api car-monit-backend --no-headers 2>/dev/null | awk '{s+=$3} END{print s+0}')
  echo "cluster ready replicas: ${reps:-0}"
  echo "java process count (all): $(pgrep -c java 2>/dev/null || echo 0)"
}

case "$MODE" in
  status) snapshot; exit 0 ;;
esac

echo "################ BEFORE ################"
snapshot

if [ "$MODE" = standalone ]; then
  echo "################ SWITCH -> STANDALONE ################"
  # 1) drain cluster workloads, then stop node containers (frees k3s/containerd RAM)
  if docker inspect -f '{{.State.Status}}' k3d-v3-server-0 2>/dev/null | grep -q running; then
    echo "-- scale deployments to 0"
    $K scale deploy car-monit-api car-monit-backend --replicas=0 2>&1 | head -5
    sleep 3
  fi
  echo "-- stop k3d node containers"
  docker stop "${NODES[@]}" 2>&1 | head -10 || true
  echo "-- ensure standalone units are active"
  for u in "${UNITS[@]}"; do
    if ! systemctl is-active --quiet "$u"; then
      sudo systemctl start "$u" 2>&1 | head -3
    fi
  done
elif [ "$MODE" = cluster ]; then
  echo "################ SWITCH -> CLUSTER ################"
  echo "-- stop standalone units"
  for u in "${UNITS[@]}"; do sudo systemctl stop "$u" 2>&1 | head -3; done
  echo "-- start k3d nodes"
  docker start "${NODES[@]}" 2>&1 | head -10 || k3d cluster start v3 2>&1 | head -10
  echo "-- wait for nodes Ready"
  for i in $(seq 1 24); do
    n=$($K get nodes --no-headers 2>/dev/null | grep -c ' Ready' || true)
    [ "${n:-0}" = 3 ] && break
    sleep 5
  done
  echo "-- scale to 3+3"
  $K scale deploy car-monit-api --replicas=3 2>&1 | head -3
  $K scale deploy car-monit-backend --replicas=3 2>&1 | head -3
else
  echo "unknown mode: $MODE"; exit 2
fi

sleep 3
echo "################ AFTER ################"
snapshot
echo "Revert with: bash $0 $([ "$MODE" = standalone ] && echo cluster || echo standalone)"
