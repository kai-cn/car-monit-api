#!/usr/bin/env bash
# car-monit-api 单机离线安装脚本。
# 所有路径均可参数化，默认值适合生产；验证环境用临时前缀即可非 root 运行。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="/opt"
LOG_DIR="/var/log"
UNIT_DIR="/etc/systemd/system"
SERVICE_USER="carmonit"
SERVICES=""
DO_START=1

usage() {
  echo "用法: $0 [--prefix DIR] [--log-dir DIR] [--unit-dir DIR] [--service java,go,python,rust,cpp] [--user NAME] [--no-start]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --log-dir) LOG_DIR="$2"; shift 2 ;;
    --unit-dir) UNIT_DIR="$2"; shift 2 ;;
    --service) SERVICES="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --no-start) DO_START=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$SERVICES" ]]; then
  SERVICES="$(find "$SCRIPT_DIR/payloads" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tr '\n' ',' | sed 's/,$//')"
else
  SERVICES="${SERVICES//all/$(find "$SCRIPT_DIR/payloads" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tr '\n' ',' | sed 's/,$//')}"
fi

IFS=',' read -ra ARR <<< "$SERVICES"
for svc in "${ARR[@]}"; do
  [[ -n "$svc" ]] || continue
  if [[ ! -d "$SCRIPT_DIR/payloads/$svc" ]]; then
    echo "ERROR: artifact 中不存在服务 $svc" >&2
    exit 1
  fi

  install -d "$PREFIX/$svc" "$LOG_DIR/$svc"
  cp -a "$SCRIPT_DIR/payloads/$svc/." "$PREFIX/$svc/"

  case "$svc" in
    java)
      [[ -f "$PREFIX/java/app.jar" ]] || { echo "ERROR: java/app.jar 缺失" >&2; exit 1; }
      cp -n "$SCRIPT_DIR/config/java.env.example" "$PREFIX/java/java.env" 2>/dev/null || true
      ;;
    go)
      [[ -f "$PREFIX/go/api" ]] || { echo "ERROR: go/api 缺失" >&2; exit 1; }
      cp -n "$SCRIPT_DIR/config/go.config.yaml.example" "$PREFIX/go/config.yaml" 2>/dev/null || true
      ;;
    python)
      [[ -d "$PREFIX/python/wheels" ]] || { echo "ERROR: python/wheels 缺失" >&2; exit 1; }
      cp -n "$SCRIPT_DIR/config/python.env.example" "$PREFIX/python/python.env" 2>/dev/null || true
      if [[ ! -x "$PREFIX/python/venv/bin/python" ]]; then
        python3 -m venv "$PREFIX/python/venv"
      fi
      "$PREFIX/python/venv/bin/pip" install --no-index --find-links "$PREFIX/python/wheels" \
        -r "$PREFIX/python/requirements.lock.txt"
      ;;
    rust)
      [[ -x "$PREFIX/rust/car-monit-api-rust" ]] || { echo "ERROR: rust/car-monit-api-rust 缺失或不可执行" >&2; exit 1; }
      [[ -f "$PREFIX/rust/config/application.yaml" ]] || { echo "ERROR: rust/config/application.yaml 缺失" >&2; exit 1; }
      ;;
    cpp)
      [[ -x "$PREFIX/cpp/car-monit-api" ]] || { echo "ERROR: cpp/car-monit-api 缺失或不可执行" >&2; exit 1; }
      [[ -f "$PREFIX/cpp/configs/config.yaml" ]] || { echo "ERROR: cpp/configs/config.yaml 缺失" >&2; exit 1; }
      ;;
  esac

  if [[ -f "$SCRIPT_DIR/systemd/car-monit-api-$svc.service" ]]; then
    install -d "$UNIT_DIR"
    sed -e "s|@PREFIX@|$PREFIX|g" \
        -e "s|@LOG_DIR@|$LOG_DIR|g" \
        -e "s|@USER@|$SERVICE_USER|g" \
        "$SCRIPT_DIR/systemd/car-monit-api-$svc.service" > "$UNIT_DIR/car-monit-api-$svc.service"
  fi
done

if [[ "$DO_START" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
  if [[ "$(id -u)" -eq 0 ]] && ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER" || true
  fi
  systemctl daemon-reload
  for svc in "${ARR[@]}"; do
    [[ -n "$svc" ]] || continue
    systemctl enable --now "car-monit-api-$svc" || true
  done
fi

echo "安装完成: $SERVICES -> $PREFIX"
[[ "$DO_START" -eq 0 ]] && echo "（--no-start：未启动 systemd 服务，可按 README 手动启动）"
