#!/usr/bin/env bash
# 停掉正在运行的 Rust 服务、重新编译（关调试信息省磁盘）、再以测试参数后台启动。
set -u
cd "$(dirname "$0")/.." || exit 1

powershell -NoProfile -Command "Get-Process car-monit-api-rust -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Milliseconds 500" >/dev/null 2>&1

RUSTFLAGS="-C debuginfo=0" CARGO_INCREMENTAL=0 cargo build || exit 1

powershell -NoProfile -Command "\$env:APP_SERVER_PORT='9911'; \$env:APP_CONSUMER_ENABLED='false'; \$env:APP_ENABLE_SCHEDULER='false'; \$env:APP_REDIS_DATABASE='15'; \$p = Start-Process -FilePath 'D:\work\IdeaProjects\car-monit-api\car-monit-api-rust\target\debug\car-monit-api-rust.exe' -RedirectStandardOutput 'D:\work\IdeaProjects\car-monit-api\car-monit-api-rust\.run\rust.log' -RedirectStandardError 'D:\work\IdeaProjects\car-monit-api\car-monit-api-rust\.run\rust.err' -WindowStyle Hidden -PassThru; \$p.Id | Out-File -Encoding ascii 'D:\work\IdeaProjects\car-monit-api\car-monit-api-rust\.run\rust.pid'"

sleep 2
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9911/healthz)
echo "rust healthz=$code"
[ "$code" = "200" ]
