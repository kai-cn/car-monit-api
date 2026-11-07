# car-monit-api (C++) 启动脚本
#
# 用法：
#   .\scripts\run.ps1                       # 默认 configs/config.yaml，端口取自配置
#   .\scripts\run.ps1 -Port 9910            # 覆盖端口（等价 CM_SERVER_PORT）
#   .\scripts\run.ps1 -LogLevel debug       # debug/info/warn/error
#   .\scripts\run.ps1 -Config configs\config.yaml -Exe build-rel\car-monit-api.exe
#
# 说明：工作目录强制切到工程根，保证 logs/car-monit-api.log 与 configs/ 相对路径正确。
param(
    [string]$Config = "configs\config.yaml",
    [int]$Port = 0,
    [ValidateSet("debug", "info", "warn", "error")]
    [string]$LogLevel = "",
    [string]$Exe = "build\car-monit-api.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Exe)) {
    throw "未找到 $Exe，请先构建：cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug; cmake --build build"
}
if (-not (Test-Path $Config)) {
    throw "未找到配置文件：$Config"
}
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

if ($Port -gt 0) { $env:CM_SERVER_PORT = "$Port" }
if ($LogLevel) { $env:CM_LOG_LEVEL = $LogLevel }

Write-Host "启动 $Exe --config $Config (端口覆盖=$Port, 日志级别=$LogLevel)"
& $Exe --config $Config
