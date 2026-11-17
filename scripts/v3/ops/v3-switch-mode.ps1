# ======================================================================
# 文件：scripts/v3/ops/v3-switch-mode.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
<#
.SYNOPSIS
    Windows wrapper that enforces "standalone XOR k3d-cluster" inside WSL.

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).

    VERIFIED REALITY on this host (2026-11-15 15:23):
      standalone = systemd units car-monit-api.service / car-monit-backend.service
                   running /opt/car-monit-{api,backend}/app.jar inside WSL
      cluster    = k3d v3 deployments car-monit-api / car-monit-backend
      Windows ports 9989/9902 are forwarded by wslrelay.exe, NOT by Windows
      java processes. The earlier Windows-side stop logic was therefore wrong;
      all switching now delegates to v3-enforce-single-mode.sh inside WSL.

    Measured switch -> standalone:
      WSL Mem.used 6019 MB -> 3474 MB (freed 2545 MB)
      java processes 10 -> 4, cluster replicas 6 -> 0

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1 -Mode standalone -Apply
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-switch-mode.ps1 -Mode cluster -Apply
#>
[CmdletBinding()]
param(
    [ValidateSet('status','standalone','cluster')][string]$Mode = 'status',
    [switch]$Apply,
    [string]$Distro = 'openEuler-24.03-LTS-SP4',
    [string]$OpsDir = 'D:\work\IdeaProjects\car-monit-api-java-V3\scripts\v3\ops',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence'
)
$ErrorActionPreference = 'Stop'
$sh = Join-Path $OpsDir 'v3-enforce-single-mode.sh'
if (-not (Test-Path -LiteralPath $sh)) { throw "WSL switch script not found: $sh" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $EvidenceDir "switch-$Mode-$stamp.log"

function Get-WslPath {
    param([string]$WinPath)
    $drive = $WinPath.Substring(0,1).ToLower()
    return '/mnt/' + $drive + ($WinPath.Substring(2) -replace '\\','/')
}
$wslSh = Get-WslPath -WinPath $sh

$os = Get-CimInstance Win32_OperatingSystem
$vm = Get-Process vmmemWSL -ErrorAction SilentlyContinue
$vmMB = 0
if ($vm) { $vmMB = $vm.WorkingSet64 / 1MB }
Write-Host ("BEFORE: host_free_GB={0:N2} vmmem_MB={1:N0}" -f ($os.FreePhysicalMemory/1MB), $vmMB)

if ($Mode -eq 'status') {
    & wsl.exe -d $Distro -- bash $wslSh status 2>&1 | Tee-Object -FilePath $log
    return
}
if (-not $Apply) {
    Write-Host "DRY-RUN: would run 'bash $wslSh $Mode'. Re-run with -Apply." -ForegroundColor Yellow
    return
}

Write-Host "APPLY: switching to $Mode (all WSL services are managed by the script)" -ForegroundColor Cyan
& wsl.exe -d $Distro -- bash $wslSh $Mode 2>&1 | Tee-Object -FilePath $log
$os2 = Get-CimInstance Win32_OperatingSystem
$vm2 = Get-Process vmmemWSL -ErrorAction SilentlyContinue
$vmMB2 = 0
if ($vm2) { $vmMB2 = $vm2.WorkingSet64 / 1MB }
Write-Host ("AFTER: host_free_GB={0:N2} vmmem_MB={1:N0}" -f ($os2.FreePhysicalMemory/1MB), $vmMB2)
Write-Host "log=$log"
