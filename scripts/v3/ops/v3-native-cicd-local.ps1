# ======================================================================
# 文件：scripts/v3/ops/v3-native-cicd-local.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
<#
.SYNOPSIS
    Local equivalent of the artifact-collection steps in native-image.yml.
.DESCRIPTION
    Pure ASCII (PowerShell 5.1 GBK pitfall). Copies the native binary into a
    dist/ folder, writes SHA256, packs a zip and a manifest. This is NOT a
    GitHub Actions run: it exercises the exact same commands the workflow uses
    on the self-hosted runner, without a PAT or workflow_dispatch.
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\v3-native-cicd-local.ps1 `
      -Exe 'D:\...\target\pro-business-api.exe' -App api -Jdk 25 -Platform windows
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [string]$App = 'api',
    [string]$Jdk = '25',
    [ValidateSet('windows','linux')][string]$Platform = 'windows',
    [string]$RepoDir = '',
    [string]$DistDir = 'D:\work\runtime-logs\v3-ops\dist',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence',
    [switch]$SkipZip
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Exe)) { throw "Binary not found: $Exe" }
New-Item -ItemType Directory -Force -Path $DistDir, $EvidenceDir | Out-Null

$ext = if ($Platform -eq 'windows') { '.exe' } else { '' }
$name = "$App-jdk$Jdk-$Platform-amd64$ext"
$dest = Join-Path $DistDir $name
Copy-Item -LiteralPath $Exe -Destination $dest -Force
$bytes = (Get-Item -LiteralPath $dest).Length
$hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
$hash | Out-File -LiteralPath "$dest.sha256" -Encoding ascii

$sha = 'unknown'
if ($RepoDir -ne '' -and (Test-Path -LiteralPath $RepoDir)) {
    try { $sha = (& git -C $RepoDir rev-parse --short HEAD 2>$null) } catch { $sha = 'unknown' }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$manifest = [ordered]@{
    app = $App; jdk = $Jdk; platform = $Platform; name = $name
    bytes = $bytes; size_MB = [math]::Round($bytes/1MB,2); sha256 = $hash
    git_sha = "$sha"; collected_at = $stamp; source = $Exe
}
$json = $manifest | ConvertTo-Json -Depth 3
$mfile = Join-Path $EvidenceDir "native-artifact-$name-$stamp.json"
$json | Out-File -LiteralPath $mfile -Encoding ascii
$zip = 'skipped'
if (-not $SkipZip) {
    $zip = Join-Path $DistDir "$name.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -LiteralPath $dest,"$dest.sha256" -DestinationPath $zip -CompressionLevel Optimal
}

Write-Host "==== CICD LOCAL ARTIFACT ===="
Write-Host "name=$name bytes=$bytes size_MB=$($manifest.size_MB)"
Write-Host "sha256=$hash"
Write-Host "git_sha=$sha"
Write-Host "manifest=$mfile"
Write-Host "zip=$zip"
Write-Host "CICD_LOCAL_OK"
