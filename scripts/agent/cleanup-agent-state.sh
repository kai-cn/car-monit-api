#!/usr/bin/env bash
# =============================================================================
# 文件：scripts/agent/cleanup-agent-state.sh
# 用途：清理 AgentScope 会话状态（官方 RedisAgentStateStore 不设 TTL）
#
# 背景：
#   agentscope-extensions-redis 的 RedisAgentStateStore 只负责读写，全程不 EXPIRE，
#   会话状态会一直保留。用户主动"清空会话"（DELETE /sessions/{id}）能清掉单个会话，
#   但离线用户、异常断开的会话会长期堆积。本脚本按 **key 空闲时间**（OBJECT IDLETIME）
#   清理，用 SCAN 游标遍历，不会阻塞 Redis。
#
# 用法：
#   ./cleanup-agent-state.sh                       # 默认 prefix=agent:as idle=7d
#   ./cleanup-agent-state.sh --prefix agent:as --idle-seconds 2592000
#   ./cleanup-agent-state.sh --dry-run             # 只统计不删除
#   REDIS_HOST=10.0.0.5 REDIS_PORT=6379 REDIS_PASSWORD=xxx ./cleanup-agent-state.sh
#
# 建议：与 Redis maxmemory-policy（allkeys-lru）配合；生产按日跑一次即可。
#
# 限制：脚本用单节点 SCAN，**只适合单机/主从**。集群模式下每条 Key 分散在不同节点，
#   需要按节点分别执行（REDIS_HOST/REDIS_PORT 指向各节点），或改用支持集群的客户端；
#   `redis-cli -c` 也无法让 SCAN 跨节点遍历。
# =============================================================================
set -euo pipefail

PREFIX="${PREFIX:-agent:as}"
IDLE_SECONDS="${IDLE_SECONDS:-604800}"   # 默认 7 天
DRY_RUN=0
BATCH=200

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --idle-seconds) IDLE_SECONDS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

command -v redis-cli >/dev/null 2>&1 \
  || { echo "未找到 redis-cli，请先安装 redis-tools（或在对端机器上执行本脚本）" >&2; exit 1; }

REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"

cli() {
  if [ -n "${REDIS_PASSWORD:-}" ]; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" --no-auth-warning "$@"
  else
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" "$@"
  fi
}

cli ping >/dev/null || { echo "无法连接 Redis ${REDIS_HOST}:${REDIS_PORT}" >&2; exit 1; }

echo "[cleanup] prefix=${PREFIX}* idle>${IDLE_SECONDS}s dry-run=${DRY_RUN}"

scanned=0
deleted=0
kept=0

# SCAN 游标遍历：每次 BATCH 个 key，避免 KEYS 阻塞主线程。
# 注意循环体内每个 cli 调用都要 </dev/null 并把游标流放到 fd 3：
# 否则子进程会继承并消费循环的 stdin，导致"只处理了第一个 key 就结束"（真踩过）。
exec 3< <(cli --scan --pattern "${PREFIX}:*" --count "$BATCH")
while IFS= read -r key <&3; do
  [ -z "$key" ] && continue
  scanned=$((scanned + 1))
  idle=$(cli object idletime "$key" </dev/null 2>/dev/null || echo "")
  # key 可能在扫描与判断之间过期/被删
  if [ -z "$idle" ] || [ "$idle" = "nil" ]; then continue; fi
  # 非数字直接跳过：`[ "$idle" -gt N ]` 遇到非数字会在 set -e 下把整个脚本打掉
  case "$idle" in *[!0-9]*) continue ;; esac
  if [ "$idle" -gt "$IDLE_SECONDS" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  would delete: $key (idle=${idle}s)"
    else
      cli del "$key" </dev/null >/dev/null
    fi
    deleted=$((deleted + 1))
  else
    kept=$((kept + 1))
  fi
done
exec 3<&-

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[cleanup] scanned=${scanned} would-delete=${deleted} kept=${kept}（dry-run，未实际删除）"
else
  echo "[cleanup] scanned=${scanned} deleted=${deleted} kept=${kept}"
fi
