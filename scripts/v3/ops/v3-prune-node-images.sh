#!/usr/bin/env bash
# ======================================================================
# 文件：scripts/v3/ops/v3-prune-node-images.sh
# 用途：Linux shell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# v3-prune-node-images.sh -- keep exactly ONE current image per repo on each k3d node.
#
# Run INSIDE WSL:
#   bash /mnt/d/work/IdeaProjects/car-monit-api-java-V3/scripts/v3/ops/v3-prune-node-images.sh              # dry-run
#   bash .../v3-prune-node-images.sh --apply                                                              # delete
#   bash .../v3-prune-node-images.sh --apply --keep-tag slim --no-prune
#
# Repos handled: car-monit-api, car-monit-backend (one kept version per repo per node).
# Selection order for the version to KEEP:
#   1) digest currently referenced by a running pod (kubectl containerStatuses.imageID)
#   2) the image carrying tag $KEEP_TAG (default: slim)
#   3) explicit --keep-digest sha256:... (overrides 1 and 2)
# If no unambiguous keeper can be determined, the repo is SKIPPED (never guess-delete).
# Untagged leftovers from repeated `k3d image import` are removed by `crictl rmi --prune`.
# Recovery (if a needed image was removed): `k3d image import <image:tag> -c v3`.
set -uo pipefail

NODES=(k3d-v3-server-0 k3d-v3-agent-0 k3d-v3-agent-1)
REPOS=(car-monit-api car-monit-backend)
EP=unix:///run/k3s/containerd/containerd.sock
OUT=${OUT:-/mnt/d/work/runtime-logs/v3-ops/evidence}
KEEP_TAG=${KEEP_TAG:-slim}
APPLY=0
PRUNE=1
KEEP_DIGEST_OVERRIDE=""
PROFILE_TAG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --no-prune) PRUNE=0 ;;
    --keep-tag) KEEP_TAG="$2"; shift ;;
    --keep-digest) KEEP_DIGEST_OVERRIDE="$2"; shift ;;
    --profile-tag) PROFILE_TAG="$2"; shift ;;   # optional image tag suffix, e.g. min-jdk25
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)
PLAN="$OUT/prune-plan-$TS.txt"
exec > >(tee "$PLAN") 2>&1

command -v jq >/dev/null 2>&1 || { echo "FATAL: jq is required inside WSL"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "FATAL: docker CLI is required inside WSL"; exit 1; }

[ -n "$PROFILE_TAG" ] && KEEP_TAG="$PROFILE_TAG"
echo "################ K3D IMAGE PRUNE PLAN $TS ################"
echo "mode=$([ "$APPLY" = 1 ] && echo APPLY || echo DRY-RUN) keep_tag=$KEEP_TAG keep_digest_override=${KEEP_DIGEST_OVERRIDE:-none} prune_untagged=$PRUNE"
echo

# ---------- 1. digests currently used by running pods ----------
K="docker exec k3d-v3-server-0 kubectl"
declare -a KEEP_DIGESTS=()
if [ -n "$KEEP_DIGEST_OVERRIDE" ]; then
  KEEP_DIGESTS=("$KEEP_DIGEST_OVERRIDE")
  echo "keep digest (override): ${KEEP_DIGESTS[0]}"
else
  raw=$($K get pods -l 'app in (car-monit-api,car-monit-backend)' \
        -o jsonpath='{range .items[*]}{range .status.containerStatuses[*]}{.imageID}{"\n"}{end}{end}' 2>/dev/null || true)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in
      *sha256:*) d="sha256:${line##*sha256:}" ;;
      *) d="$line" ;;
    esac
    KEEP_DIGESTS+=("$d")
  done <<< "$raw"
  # de-duplicate
  if [ "${#KEEP_DIGESTS[@]}" -gt 0 ]; then
    mapfile -t KEEP_DIGESTS < <(printf '%s\n' "${KEEP_DIGESTS[@]}" | sort -u)
  fi
  echo "in-use digests (${#KEEP_DIGESTS[@]}): ${KEEP_DIGESTS[*]:-none}"
fi
echo

TOTAL_KEEP=0
TOTAL_DEL=0
declare -a DEL_CMDS=()

for node in "${NODES[@]}"; do
  echo "================ $node ================"
  if ! docker ps --format '{{.Names}}' | grep -qx "$node"; then
    echo "WARN: node container not running -> skipped"; echo; continue
  fi
  json=$(docker exec "$node" crictl --runtime-endpoint "$EP" images -o json 2>/dev/null) || {
    echo "WARN: crictl images failed on $node -> skipped"; echo; continue
  }
  if [ -z "$json" ]; then echo "WARN: empty crictl output -> skipped"; echo; continue; fi
  printf '%s\n' "$json" > "$OUT/node-images-$node-$TS.json"

  for repo in "${REPOS[@]}"; do
    mapfile -t rows < <(printf '%s\n' "$json" | jq -r --arg r "$repo" '
      .images[]?
      | select((((.repoTags // []) + (.repoDigests // [])) | join(" ") | test($r)))
      | [ .id,
          ((.repoTags // []) | join(",")),
          ((.repoDigests // []) | join(",")),
          ((.size // "0") | tostring) ] | @tsv' 2>/dev/null)

    echo "-- repo $repo : ${#rows[@]} image(s) --"
    for row in "${rows[@]}"; do
      IFS=$'\t' read -r id tags digests size <<< "$row"
      echo "   id=${id} size=${size} tags=${tags:-<none>} digests=${digests:-<none>}"
    done
    if [ "${#rows[@]}" -eq 0 ]; then echo "   SKIP (not present)"; continue; fi

    declare -a keepers=()
    for row in "${rows[@]}"; do
      IFS=$'\t' read -r id tags digests size <<< "$row"
      for kd in "${KEEP_DIGESTS[@]}"; do
        if [ "$id" = "$kd" ] || [[ "$digests" == *"$kd"* ]]; then
          keepers+=("$id"); break
        fi
      done
    done
    if [ "${#keepers[@]}" -eq 0 ]; then
      for row in "${rows[@]}"; do
        IFS=$'\t' read -r id tags digests size <<< "$row"
        [[ "$tags" == *":${KEEP_TAG}"* ]] && keepers+=("$id")
      done
    fi
    if [ "${#keepers[@]}" -gt 0 ]; then
      mapfile -t keepers < <(printf '%s\n' "${keepers[@]}" | sort -u)
    fi

    if [ "${#keepers[@]}" -eq 0 ]; then
      echo "   !! SKIP $repo on $node: no in-use digest and no tag ':$KEEP_TAG'."
      echo "      Use --keep-tag <tag> or --keep-digest sha256:... to disambiguate. Nothing deleted."
      continue
    fi
    if [ "${#keepers[@]}" -gt 1 ]; then
      echo "   !! SKIP $repo on $node: ${#keepers[@]} ambiguous keepers (rollout in progress?). Nothing deleted."
      continue
    fi

    keep_id="${keepers[0]}"
    echo "   KEEP  $keep_id"
    TOTAL_KEEP=$((TOTAL_KEEP+1))
    for row in "${rows[@]}"; do
      IFS=$'\t' read -r id tags digests size <<< "$row"
      [ "$id" = "$keep_id" ] && continue
      echo "   DROP  $id  (${tags:-untagged})"
      TOTAL_DEL=$((TOTAL_DEL+1))
      DEL_CMDS+=("$node|$id")
    done
    echo
  done
  echo
done

echo "################ SUMMARY ################"
echo "kept images: $TOTAL_KEEP ; images to drop: $TOTAL_DEL"

if [ "$APPLY" != 1 ]; then
  echo "DRY-RUN only. Re-run with --apply to execute. Plan saved: $PLAN"
  exit 0
fi

echo
echo "################ EXECUTING ################"
for item in "${DEL_CMDS[@]}"; do
  IFS='|' read -r node id <<< "$item"
  echo "-- rmi $node $id"
  docker exec "$node" crictl --runtime-endpoint "$EP" rmi "$id" 2>&1 || \
    echo "   WARN: rmi failed (image may be in use by a container); left untouched"
done

if [ "$PRUNE" = 1 ]; then
  for node in "${NODES[@]}"; do
    docker ps --format '{{.Names}}' | grep -qx "$node" || continue
    echo "-- crictl rmi --prune on $node"
    docker exec "$node" crictl --runtime-endpoint "$EP" rmi --prune 2>&1 | tail -5
  done
fi

echo
echo "################ VERIFY ################"
for node in "${NODES[@]}"; do
  echo "-- $node --"
  docker exec "$node" crictl --runtime-endpoint "$EP" images 2>/dev/null | grep -E 'car-monit|IMAGE' || echo "   (no car-monit image)"
done
echo "Plan / result log: $PLAN"
