#!/usr/bin/env bash
# 重编译并重启 Rust 服务（端口/Redis DB 见下）。构建失败时保留旧进程不动。
set -u
cd "$(dirname "$0")/../.." || exit 1
PID=$(netstat -ano 2>/dev/null | grep ':9911 .*LISTENING' | awk '{print $5}' | head -1)
if [ -n "${PID:-}" ]; then
  taskkill //PID "$PID" //F >/dev/null 2>&1
  sleep 1
fi
if ! cargo build --message-format=short 2>&1 | grep -E "^error[[:space:]]|error\["; then
  echo "BUILD_OK"
else
  echo "BUILD_FAILED"
  exit 1
fi
APP_SERVER_PORT=9911 APP_REDIS_DATABASE=1 APP_CONSUMER_ENABLED=false \
  APP_ENABLE_SCHEDULER=false RUST_LOG=info nohup ./target/debug/car-monit-api-rust.exe \
  > .run/rust-9911.log 2>&1 &
sleep 4
curl -s -m 5 http://127.0.0.1:9911/healthz && echo " RUST_UP"
