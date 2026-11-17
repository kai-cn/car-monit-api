# ======================================================================
# 文件：scripts/v3/ops/v3-native-build-all.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
<#
.SYNOPSIS
    Build all six Spring Boot 4 native images (jdk25/21/17 x api/backend).

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).
    Delegates to D:\work\runtime-logs\v3-ops\native-build.bat, which sets up
    VS2022 C++ environment + Mandrel 25 and runs AOT + native-image.
    Each build is logged separately; a summary CSV is written at the end.

    IMPORTANT: each native-image build needs ~2.4GB peak RSS. Shut WSL down
    before running this batch, then restore it afterwards.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-native-build-all.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-native-build-all.ps1 -Only 'api-jdk25'
#>
[CmdletBinding()]
param(
    [string]$Only = '',
    [string]$BuildBat = 'D:\work\runtime-logs\v3-ops\native-build.bat',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence',
    [string]$Root = 'D:\work\IdeaProjects'
)
$ErrorActionPreference = 'Continue'
if (-not (Test-Path -LiteralPath $BuildBat)) { throw "Build bat not found: $BuildBat" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$summary = Join-Path $EvidenceDir "native-build-all-$stamp.csv"

$plan = @(
    @{ j='25'; a='api';     mod='pro-business-api'; label='api-jdk25' },
    @{ j='25'; a='backend'; mod='ruoyi-admin';      label='backend-jdk25' },
    @{ j='21'; a='api';     mod='pro-business-api'; label='api-jdk21' },
    @{ j='21'; a='backend'; mod='ruoyi-admin';      label='backend-jdk21' },
    @{ j='17'; a='api';     mod='pro-business-api'; label='api-jdk17' },
    @{ j='17'; a='backend'; mod='ruoyi-admin';      label='backend-jdk17' }
)
if ($Only) { $plan = $plan | Where-Object { $_.label -eq $Only } }

'label,jdk,app,exit,seconds,exe_bytes,log' | Out-File -LiteralPath $summary -Encoding UTF8
foreach ($p in $plan) {
    $proj = Join-Path $Root ("car-monit-{0}-jdk{1}" -f $p.a, $p.j)
    $log = Join-Path $EvidenceDir ("native-{0}-{1}.log" -f $p.label, $stamp)
    Write-Host "==== BUILD $($p.label) ====" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $BuildBat $proj $p.mod $p.label 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $sw.Stop()
    $exe = Get-ChildItem -Path (Join-Path $proj $p.mod) -Recurse -Filter *.exe -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $bytes = 0
    if ($exe) { $bytes = $exe.Length }
    $line = "{0},{1},{2},{3},{4},{5},{6}" -f $p.label,$p.j,$p.a,$code,[int]$sw.Elapsed.TotalSeconds,$bytes,$log
    Write-Host $line
    Add-Content -LiteralPath $summary -Value $line -Encoding UTF8
}
Write-Host "summary=$summary"
