# ======================================================================
# 文件：scripts/v3/ops/v3-compact-wsl.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
<#
.SYNOPSIS
    Reclaim WSL2 VHDX disk space: shutdown -> set-sparse false -> compact -> verify.

.DESCRIPTION
    Pure ASCII on purpose (PowerShell 5.1 GBK pitfall).

    Reproduces the operator's sequence exactly:
        $d = 'openEuler-24.03-LTS-SP4'
        wsl.exe --shutdown
        wsl.exe --manage $d --set-sparse false
        wsl.exe --manage $d --compact
        fsutil sparse queryflag 'D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx'

    IMPORTANT: compact only returns space that the guest filesystem has already
    released. Run the image/prune step and fstrim FIRST, otherwise the VHDX will
    barely shrink. Default is DRY-RUN; -Apply executes.

    Observed on 2026-11-15 14:41 (BEFORE this script ran):
        VHDX = 42.812 GB (43840 MB), sparse flag = NOT sparse
        D: free = 10.72 GB, C: free = 9.07 GB
    The operator's note "16.454GB -> 9.617GB" is an EARLIER run, not the current
    file size. Do not expect that number here.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-compact-wsl.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-compact-wsl.ps1 -Apply -CleanFirst
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\v3\ops\v3-compact-wsl.ps1 -Apply -Force
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$CleanFirst,
    [switch]$Force,
    [string]$Distro = 'openEuler-24.03-LTS-SP4',
    [string]$Vhdx = 'D:\wsl\openEuler-24.03-LTS-SP4\ext4.vhdx',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence',
    [double]$MinFreeGB = 8
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Vhdx)) { throw "VHDX not found: $Vhdx" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $EvidenceDir "compact-$stamp.log"
function Write-Log { param([string]$Text) $line = "$(Get-Date -Format s) $Text"; Write-Host $line; Add-Content -LiteralPath $log -Value $line -Encoding UTF8 }

$before = (Get-Item -LiteralPath $Vhdx).Length
$beforeGB = [math]::Round($before/1GB,3)
$drive = (Get-Item -LiteralPath $Vhdx).PSDrive.Name
$dsk = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "${drive}:" }
$freeGB = [math]::Round($dsk.FreeSpace/1GB,2)
$sparseRaw = (& fsutil sparse queryflag $Vhdx 2>&1 | Out-String).Trim()

$modeText = 'DRY-RUN'
if ($Apply) { $modeText = 'APPLY' }
Write-Log "==== WSL VHDX COMPACT PRECHECK ===="
Write-Log "mode=$modeText"
Write-Log "distro=$Distro"
Write-Log "vhdx=$Vhdx"
Write-Log "size_before=$before bytes ($beforeGB GB)"
Write-Log "${drive}: free=$freeGB GB ; minRequired=$MinFreeGB GB"
Write-Log "sparse_queryflag=$sparseRaw"
# Do not pattern-match the localized fsutil text (this file is pure ASCII on
# purpose). `--set-sparse false` is idempotent and is always applied below,
# so the pre-state only needs to be recorded, not interpreted.
Write-Log "note: --set-sparse false is applied unconditionally before --compact"
if ($freeGB -lt $MinFreeGB -and -not $Force) {
    Write-Log "BLOCKED: only $freeGB GB free on ${drive}:. Clean images / old logs first, or pass -Force."
    return
}

Write-Log "==== PLAN ===="
Write-Log " 0) optional: prune dangling docker images, builder cache, fstrim -av inside WSL"
Write-Log " 1) wsl.exe --shutdown                 (terminates ALL WSL containers/services)"
Write-Log " 2) wsl.exe --manage $Distro --set-sparse false"
Write-Log " 3) wsl.exe --manage $Distro --compact"
Write-Log " 4) fsutil sparse queryflag $Vhdx"
Write-Log " 5) record size_after and delta"

if (-not $Apply) {
    Write-Log "DRY-RUN: re-run with -Apply (add -CleanFirst to reclaim guest-side space first)."
    return
}

# ---- Step 0: release space inside the guest FIRST ----
if ($CleanFirst) {
    Write-Log "---- step 0: guest-side cleanup ----"
    $clean = @'
echo "=== docker system df (before) ==="; docker system df 2>&1
echo "=== prune dangling images (NOT volumes) ==="; docker image prune -f 2>&1 | tail -5
echo "=== prune builder cache ==="; docker builder prune -f 2>&1 | tail -5
echo "=== fstrim ==="; sudo fstrim -av 2>&1 | tail -10
echo "=== docker system df (after) ==="; docker system df 2>&1
'@
    $tmp = Join-Path $EvidenceDir "guest-clean-$stamp.sh"
    [System.IO.File]::WriteAllText($tmp, ($clean -replace "`r`n","`n"), (New-Object System.Text.UTF8Encoding($false)))
    # D:\work\... -> /mnt/d/work/... (explicit, no regex replacement risk)
    $wslPath = '/mnt/d' + ($tmp.Substring(2) -replace '\\','/')
    Write-Log "guest cleanup script (WSL path): $wslPath"
    try { (& wsl.exe -d $Distro -- bash $wslPath 2>&1 | Out-String).Trim() -split "`n" | ForEach-Object { Write-Log "  $_" } }
    catch { Write-Log "WARN: guest cleanup failed: $_" }
}

# ---- Step 1: shutdown ----
Write-Host "WARNING: about to shut down ALL WSL distributions (all containers/services stop)." -ForegroundColor Red
Write-Log "---- step 1: shutdown ----"
& wsl.exe --shutdown 2>&1 | ForEach-Object { Write-Log "  $_" }
Start-Sleep -Seconds 3

# ---- Step 2: force non-sparse ----
Write-Log "---- step 2: set-sparse false ----"
& wsl.exe --manage $Distro --set-sparse false 2>&1 | ForEach-Object { Write-Log "  $_" }

# ---- Step 3: compact ----
Write-Log "---- step 3: compact (can take several minutes) ----"
& wsl.exe --manage $Distro --compact 2>&1 | ForEach-Object { Write-Log "  $_" }

# ---- Step 4/5: verify ----
$after = (Get-Item -LiteralPath $Vhdx).Length
$afterGB = [math]::Round($after/1GB,3)
Write-Log "---- step 4/5: verify ----"
Write-Log ("fsutil sparse queryflag -> {0}" -f ((& fsutil sparse queryflag $Vhdx 2>&1 | Out-String).Trim()))
Write-Log "size_before=$beforeGB GB ; size_after=$afterGB GB ; reclaimed=$([math]::Round($beforeGB-$afterGB,3)) GB"
$freeAfter = [math]::Round((Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "${drive}:" }).FreeSpace/1GB,2)
Write-Log "${drive}: free_after=$freeAfter GB"
Write-Log "NOTE: WSL was shut down. Restart it and re-check DB containers (docker start mysql_wsl opengauss)."
Write-Log "Evidence log: $log"
