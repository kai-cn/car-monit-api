#!/usr/bin/env bash
# 单机卸载脚本：移除安装目录、日志目录与 systemd unit；不删除系统用户。
set -euo pipefail

PREFIX="/opt"
LOG_DIR="/var/log"
UNIT_DIR="/etc/systemd/system"
SERVICES=""
DO_SYSTEMCTL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --log-dir) LOG_DIR="$2"; shift 2 ;;
    --unit-dir) UNIT_DIR="$2"; shift 2 ;;
    --service) SERVICES="$2"; shift 2 ;;
    --no-systemctl) DO_SYSTEMCTL=0; shift ;;
    -h|--help) echo "用法: $0 [--prefix DIR] [--log-dir DIR] [--unit-dir DIR] [--service java,go,python,rust,cpp] [--no-systemctl]"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done

IFS=',' read -ra ARR <<< "${SERVICES//all/java,go,python,rust,cpp}"
for svc in "${ARR[@]}"; do
  [[ -n "$svc" ]] || continue
  if [[ "$DO_SYSTEMCTL" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
    systemctl stop "car-monit-api-$svc" 2>/dev/null || true
    systemctl disable "car-monit-api-$svc" 2>/dev/null || true
  fi
  rm -rf "$PREFIX/$svc" "$LOG_DIR/$svc" "$UNIT_DIR/car-monit-api-$svc.service"
done

if [[ "$DO_SYSTEMCTL" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload 2>/dev/null || true
fi
echo "卸载完成: $SERVICES"
