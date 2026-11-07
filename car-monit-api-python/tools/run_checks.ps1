# -*- coding: utf-8 -*-
"""一键门禁（P1-4）：按 CI 相同的顺序跑全部校验，任一失败则 exit 1。

用法（在 car-monit-api-python 目录下）：
    powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1
    powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1 -SkipSmoke  # 跳过两个冒烟
"""
param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$failed = @()

function Invoke-Gate([string]$Name, [scriptblock]$Block) {
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        $script:failed += $Name
    } else {
        Write-Host "ok  : $Name" -ForegroundColor Green
    }
}

Invoke-Gate "pytest" { & $py -m pytest -q }
Invoke-Gate "check_routes" { & $py (Join-Path $root "tools\check_routes.py") }
Invoke-Gate "check_mappers (含 XML 同步校验)" { & $py (Join-Path $root "tools\check_mappers.py") }
Invoke-Gate "check_parity" { & $py (Join-Path $root "tools\check_parity.py") }
Invoke-Gate "check_env" { & $py (Join-Path $root "tools\check_env.py") }
if (-not $SkipSmoke) {
    Invoke-Gate "smoke_test (交付自检)" { & $py (Join-Path $root "scripts\smoke_test.py") }
    Invoke-Gate "smoke_all_routes (85 路由)" { & $py (Join-Path $root "tools\smoke_all_routes.py") }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "RESULT: $($failed.Count) gate(s) FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "RESULT: all gates passed" -ForegroundColor Green
exit 0
