# ======================================================================
# 文件：scripts/v3/ops/v3-native-bench.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
<#
.SYNOPSIS
    Measure a Spring Boot native executable: size, startup time, RSS, CPU.

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).
    Starts the exe on a dedicated port, polls TCP readiness, samples WorkingSet
    and CPU for -SampleSec seconds, writes a CSV, then stops the process.

    Reference JVM baselines (measured in prior sessions):
      k3d pod workingSet : api 271-338 MiB, backend 259-263 MiB (400Mi limit)
      standalone JVM RSS : api ~405 MB, backend ~509 MB (JDK17, -Xmx256m)
      DB limits          : mysql_wsl 256m (peak 32 MiB), opengauss 256m (peak 81 MiB)

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-native-bench.ps1 `
      -Exe 'D:\...\target\pro-business-api.exe' -Port 19902 -Label api-jdk25 `
      -ExtraArgs '--server.port=19902','--spring.datasource.dynamic.datasource.master.url=jdbc:postgresql://localhost:5432/RuoYi'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [int]$Port = 19902,
    [string]$Label = 'native',
    [string[]]$ExtraArgs = @(),
    [int]$SampleSec = 30,
    [int]$IntervalSec = 2,
    [int]$StartupTimeoutSec = 180,
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Exe)) { throw "Exe not found: $Exe" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$csv = Join-Path $EvidenceDir "native-bench-$Label-$stamp.csv"
's,phase,rss_MB,cpu_seconds,port_open' | Out-File -LiteralPath $csv -Encoding UTF8

$exeBytes = (Get-Item -LiteralPath $Exe).Length
Write-Host "==== NATIVE BENCH $Label ====" -ForegroundColor White
Write-Host "exe=$Exe"
Write-Host ("size={0:N2} MB ({1} bytes)" -f ($exeBytes/1MB), $exeBytes)

$psiArgs = @()
if ($ExtraArgs.Count -gt 0) { $psiArgs = $ExtraArgs }
$runLog = Join-Path $EvidenceDir "native-run-$Label-$stamp.log"
$runErr = Join-Path $EvidenceDir "native-run-$Label-$stamp.err.log"
# PowerShell 5.1 Start-Process builds a case-insensitive env dictionary and
# throws "An item with the same key has already been added" when both
# HTTPS_PROXY and https_proxy exist (Git Bash exports both). Drop lowercase dupes.
foreach ($n in @('http_proxy','https_proxy','all_proxy','no_proxy',
                 'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY')) {
    [System.Environment]::SetEnvironmentVariable($n, $null)
}
$sw = [System.Diagnostics.Stopwatch]::StartNew()
# Windows PowerShell 5.1 joins a string[] passed to -ArgumentList with commas,
# which Spring Boot then sees as one malformed --server.port value. Join with
# spaces explicitly so each --key=value stays a separate argv element.
# When this script is invoked via `powershell.exe -File`, a string[] argument
# arrives as ONE comma-joined string. Split it back into separate argv tokens.
$argLine = (($psiArgs -join ' ') -replace ',', ' ')
Write-Host "argLine=$argLine"
$proc = Start-Process -FilePath $Exe -ArgumentList $argLine -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $runLog -RedirectStandardError $runErr
Write-Host "pid=$($proc.Id) stdout=$runLog stderr=$runErr"

$ready = $false
$startupMs = -1
for ($i = 0; $i -lt ($StartupTimeoutSec * 2); $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) {
        Write-Host "PROCESS EXITED during startup, exit=$($proc.ExitCode)" -ForegroundColor Red
        break
    }
    $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($c) {
        $ready = $true
        $startupMs = $sw.ElapsedMilliseconds
        break
    }
}
Write-Host ("port_ready={0} startup_ms={1}" -f $ready, $startupMs)

$rounds = [math]::Ceiling($SampleSec / $IntervalSec)
$rssList = New-Object System.Collections.Generic.List[double]
$cpuStart = $null
for ($i = 0; $i -lt $rounds; $i++) {
    if ($proc.HasExited) { Write-Host "process exited at sample $i"; break }
    $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $p) { break }
    $rssMB = [math]::Round($p.WorkingSet64 / 1MB, 1)
    $cpu = [math]::Round($p.CPU, 2)
    if ($null -eq $cpuStart) { $cpuStart = $cpu }
    $rssList.Add($rssMB)
    $line = "{0},{1},{2},{3},{4}" -f ($i*$IntervalSec), 'steady', $rssMB, $cpu, $ready
    Write-Host $line
    Add-Content -LiteralPath $csv -Value $line -Encoding UTF8
    Start-Sleep -Seconds $IntervalSec
}

$peak = 0; $avg = 0
if ($rssList.Count -gt 0) {
    $peak = ($rssList | Measure-Object -Maximum).Maximum
    $avg = [math]::Round(($rssList | Measure-Object -Average).Average, 1)
}
Write-Host "==== RESULT ====" -ForegroundColor White
Write-Host ("label={0} size_MB={1:N2} startup_ms={2} port_ready={3} rss_avg_MB={4} rss_peak_MB={5}" -f $Label, ($exeBytes/1MB), $startupMs, $ready, $avg, $peak)
if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force
    Write-Host "process stopped"
}
Write-Host "csv=$csv"
