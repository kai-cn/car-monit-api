#!/usr/bin/env bash
# 重编译 release 并用 release 二进制重启 9911（性能对比用；日常校验仍用 rust_restart.sh）。
set -u
cd "$(dirname "$0")/../.." || exit 1
PID=$(netstat -ano 2>/dev/null | grep ':9911 .*LISTENING' | awk '{print $5}' | head -1)
if [ -n "${PID:-}" ]; then
  taskkill //PID "$PID" //F >/dev/null 2>&1
  sleep 1
fi
if ! cargo build --release --message-format=short 2>&1 | grep -E "^error[[:space:]]|error\["; then
  echo "BUILD_OK"
else
  echo "BUILD_FAILED"
  exit 1
fi
APP_SERVER_PORT=9911 APP_REDIS_DATABASE=1 APP_CONSUMER_ENABLED=false \
  APP_ENABLE_SCHEDULER=false RUST_LOG=info nohup ./target/release/car-monit-api-rust.exe \
  > .run/rust-9911.log 2>&1 &
sleep 3
curl -s -m 5 http://127.0.0.1:9911/healthz && echo " RUST_UP(release)"
