<#
.SYNOPSIS
    Sample host RAM / vmmemWSL / WSL guest RAM to verify a quota or mode change.

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).
    Writes a CSV to D:\work\runtime-logs\v3-ops\evidence\mem-<timestamp>.csv
    Reference values to compare against:
      quota 8GB/4cpu : vmmem 4247 MB, host free 1.86 GB
      quota 4GB/2cpu : vmmem 2469 MB, host free 3.71 GB
      quota 3GB/2cpu : vmmem 1620 MB, host free 5.07 GB

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-measure.ps1 -Seconds 60 -Interval 5
#>
[CmdletBinding()]
param(
    [int]$Seconds = 60,
    [int]$Interval = 5,
    [string]$Distro = 'openEuler-24.03-LTS-SP4',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$csv = Join-Path $EvidenceDir "mem-$stamp.csv"
' time,vmmem_MB,host_free_GB,wsl_used_MB,wsl_avail_MB,api9902,backend9989' | Out-File -LiteralPath $csv -Encoding UTF8

$rounds = [math]::Ceiling($Seconds / $Interval)
for ($i = 0; $i -lt $rounds; $i++) {
    $os = Get-CimInstance Win32_OperatingSystem
    $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB / 1024, 2)
    $vm = Get-Process vmmemWSL -ErrorAction SilentlyContinue
    $vmMB = if ($vm) { [math]::Round($vm.WorkingSet64 / 1MB, 0) } else { 0 }
    $wslUsed = 0; $wslAvail = 0
    try {
        $raw = (& wsl.exe -d $Distro -- free -m 2>&1 | Out-String)
        $m = [regex]::Match($raw, 'Mem:\s+(\d+)\s+(\d+)\s+(\d+)')
        if ($m.Success) { $wslUsed = [int]$m.Groups[2].Value; $wslAvail = [int]$m.Groups[3].Value }
    } catch { }
    $api = [bool](Get-NetTCPConnection -State Listen -LocalPort 9902 -ErrorAction SilentlyContinue)
    $be  = [bool](Get-NetTCPConnection -State Listen -LocalPort 9989 -ErrorAction SilentlyContinue)
    $line = "{0},{1},{2},{3},{4},{5},{6}" -f (Get-Date -Format HH:mm:ss), $vmMB, $freeGB, $wslUsed, $wslAvail, $api, $be
    Write-Host $line
    Add-Content -LiteralPath $csv -Value $line -Encoding UTF8
    Start-Sleep -Seconds $Interval
}
Write-Host "Saved: $csv"
