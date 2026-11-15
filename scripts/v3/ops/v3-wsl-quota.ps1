<#
.SYNOPSIS
    Apply .wslconfig memory/CPU quotas derived from real measurements.

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).

    Measured baseline (history sessions, host = 13.84 GB RAM / 12 logical CPUs):
      quota 8GB/4cpu (current file) -> vmmemWSL 4247 MB, host free 1.86 GB   [2026-11-15 14:41]
      quota 6GB/4cpu               -> vmmemWSL 5505 MB, host free 0.00 GB   [CI peak, page cache not returned]
      quota 4GB/2cpu               -> vmmemWSL 2469 MB, host free 3.71 GB   [3 k3d nodes Ready 13 min, runners online]
      quota 3GB/2cpu               -> vmmemWSL 1620 MB, host free 5.07 GB   [OK for standalone; k3s cold start FAILS]

    Profiles:
      cluster : 4GB / 2GB swap / 2 cpu  -- required when k3d 3-node cluster runs
      lean    : 3GB / 2GB swap / 2 cpu  -- only when k3d is stopped (max host free RAM)
      auto    : detect cluster activity and pick cluster/lean (default)
      custom  : -Memory/-Swap/-Processors

    A backup is always written before modification. A quota change only takes
    effect after `wsl.exe --shutdown` (or VM restart); use -Shutdown explicitly.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1 -Profile auto -Apply
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1 -Profile lean -Apply -Shutdown
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-wsl-quota.ps1 -Profile custom -Memory 4GB -Swap 2GB -Processors 2 -Apply
#>
[CmdletBinding()]
param(
    [ValidateSet('auto','cluster','lean','custom','show')][string]$Profile = 'auto',
    [switch]$Apply,
    [switch]$Shutdown,
    [string]$Memory,
    [string]$Swap,
    [int]$Processors,
    [string]$Distro = 'openEuler-24.03-LTS-SP4',
    [string]$ConfigPath = "$env:USERPROFILE\.wslconfig",
    [string]$BackupDir = 'D:\work\runtime-logs\v3-ops\backup'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ConfigPath)) { throw "Config not found: $ConfigPath" }
$original = Get-Content -LiteralPath $ConfigPath
Write-Host "==== CURRENT $ConfigPath ====" -ForegroundColor White
$original | ForEach-Object { Write-Host "  $_" }

if ($Profile -eq 'show') { return }

$clusterActive = $false
if ($Profile -eq 'auto') {
    try {
        $raw = (& wsl.exe -d $Distro -- bash -lc "docker exec k3d-v3-server-0 kubectl get deploy car-monit-api car-monit-backend --no-headers 2>/dev/null || true" 2>&1 | Out-String)
        foreach ($line in ($raw -split "`n")) {
            $p = ($line.Trim() -split '\s+')
            if ($p.Count -ge 3 -and $p[2] -match '^\d+$' -and [int]$p[2] -gt 0) { $clusterActive = $true }
        }
    } catch { Write-Host "WARN: WSL probe unavailable, assuming cluster is active (safer quota)." -ForegroundColor Yellow; $clusterActive = $true }
    $Profile = if ($clusterActive) { 'cluster' } else { 'lean' }
    Write-Host "auto -> profile '$Profile' (clusterActive=$clusterActive)" -ForegroundColor Cyan
}

switch ($Profile) {
    'cluster' { $m='4GB'; $s='2GB'; $c=2; $note='measured: 3 k3d nodes Ready, host free 3.71 GB' }
    'lean'    { $m='3GB'; $s='2GB'; $c=2; $note='measured: host free 5.07 GB; k3d MUST be stopped' }
    'custom'  {
        if (-not $Memory -or -not $Swap -or -not $Processors) { throw "-Profile custom needs -Memory -Swap -Processors" }
        $m=$Memory; $s=$Swap; $c=$Processors; $note='user supplied'
    }
}
Write-Host "TARGET profile=$Profile memory=$m swap=$s processors=$c  ($note)" -ForegroundColor Cyan

# Replace only the three [wsl2] keys; keep every other line/section untouched.
$new = New-Object System.Collections.Generic.List[string]
$seenM=$false; $seenS=$false; $seenC=$false
foreach ($line in $original) {
    if ($line -match '^\s*memory\s*=')      { $new.Add("memory=$m");      $seenM=$true }
    elseif ($line -match '^\s*swap\s*=')    { $new.Add("swap=$s");        $seenS=$true }
    elseif ($line -match '^\s*processors\s*=') { $new.Add("processors=$c"); $seenC=$true }
    else { $new.Add($line) }
}
if (-not $seenM) { $new.Insert(1,"memory=$m") }
if (-not $seenS) { $new.Insert(2,"swap=$s") }
if (-not $seenC) { $new.Insert(3,"processors=$c") }

Write-Host "==== DIFF ====" -ForegroundColor White
Compare-Object -ReferenceObject $original -DifferenceObject $new | ForEach-Object {
    Write-Host ("  {0} {1}" -f $_.SideIndicator, $_.InputObject)
}
if (-not (Compare-Object -ReferenceObject $original -DifferenceObject $new)) {
    Write-Host "  (no change; already at target)" -ForegroundColor Green
}

if (-not $Apply) {
    Write-Host "DRY-RUN: re-run with -Apply (and optionally -Shutdown) to write." -ForegroundColor Yellow
    return
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bak = Join-Path $BackupDir ".wslconfig.bak-$stamp"
Copy-Item -LiteralPath $ConfigPath -Destination $bak -Force
Write-Host "Backup: $bak" -ForegroundColor Green
# UTF8 without BOM is acceptable here because the file content is pure ASCII.
[System.IO.File]::WriteAllLines($ConfigPath, [string[]]$new, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Written: $ConfigPath" -ForegroundColor Green

if ($Shutdown) {
    Write-Host "WARNING: wsl --shutdown terminates ALL running WSL containers/services." -ForegroundColor Red
    & wsl.exe --shutdown
    Write-Host "WSL shut down. Start it again with your normal entrypoint; DB containers may need 'docker start mysql_wsl opengauss'." -ForegroundColor Yellow
} else {
    Write-Host "Quota NOT active yet. Run 'wsl.exe --shutdown' (or use -Shutdown) then restart WSL." -ForegroundColor Yellow
}

$os = Get-CimInstance Win32_OperatingSystem
$vm = (Get-Process vmmemWSL -ErrorAction SilentlyContinue).WorkingSet64 / 1MB
Write-Host ("host free RAM now = {0:N2} GB ; vmmemWSL = {1:N0} MB" -f ($os.FreePhysicalMemory/1MB), $vm)
