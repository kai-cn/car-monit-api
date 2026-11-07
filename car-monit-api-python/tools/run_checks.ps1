# -*- coding: utf-8 -*-
"""一键门禁（P1-4 起；P2 起含覆盖率门禁）：任一失败则 exit 1。

用法（在 car-monit-api-python 目录下）：
    powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1
    powershell -ExecutionPolicy Bypass -File tools\run_checks.ps1 -SkipSmoke  # 跳过两个冒烟

覆盖率口径（P2）：
    * 业务覆盖率（app/** + com/ruoyi/**，含 23 个冒烟脚本追加）= 门禁，fail-under=65
      （实测基线 68.3%，留跨平台余量）；
    * 总覆盖率（含替身层）= 信息展示；
    * HTML/XML 产物写入 coverage/（已 gitignore）。
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

Invoke-Gate "pytest（覆盖率采集）" { & $py -m pytest -q --cov --cov-report= }
if (-not $SkipSmoke) {
    Invoke-Gate "smoke coverage（23 个冒烟脚本 append）" { & $py (Join-Path $root "tools\smoke_coverage.py") }
    Invoke-Gate "smoke_test (交付自检)" { & $py (Join-Path $root "scripts\smoke_test.py") }
    Invoke-Gate "smoke_all_routes (85 路由)" { & $py (Join-Path $root "tools\smoke_all_routes.py") }
}
Invoke-Gate "coverage 门禁（业务 app+com/ruoyi >= 65%）" { & $py -m coverage report --include="app/*,*/com/ruoyi/*" --fail-under=65 }
Invoke-Gate "check_routes" { & $py (Join-Path $root "tools\check_routes.py") }
Invoke-Gate "check_mappers (含 XML 同步校验)" { & $py (Join-Path $root "tools\check_mappers.py") }
Invoke-Gate "check_parity" { & $py (Join-Path $root "tools\check_parity.py") }
Invoke-Gate "check_env" { & $py (Join-Path $root "tools\check_env.py") }

# 总覆盖率（信息展示，不作为门禁）+ HTML/XML 产物
Write-Host ""
Write-Host "=== 总覆盖率（含替身层，信息展示） ===" -ForegroundColor Cyan
& $py -m coverage report | Select-Object -Last 3
& $py -m coverage html
& $py -m coverage xml

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "RESULT: $($failed.Count) gate(s) FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "RESULT: all gates passed" -ForegroundColor Green
exit 0
