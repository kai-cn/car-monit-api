# ======================================================================
# 文件：scripts/v3/ops/v3-run-native-with-db.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Launch the Windows native .exe with the database credentials of the local
# openGauss container, then measure startup / RSS via v3-native-bench.ps1.
#
# Why this wrapper exists:
#   application.yml defaults the datasource password to EMPTY (env placeholder
#   SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD with no default).
#   openGauss pg_hba.conf trusts only container-local 127.0.0.1/32; connections
#   arriving through WSL2 localhostForwarding are NAT-ed to the docker gateway
#   and match the 0.0.0.0/0 md5 rule -> "no password was provided".
#   The credential lives ONLY in the container env (GS_PASSWORD). This script
#   reads it at runtime, never echoes it, and never writes it to the repo.
#
# Usage:
#   powershell -File v3-run-native-with-db.ps1 -Exe <path> [-Port 19902] [-Label x]
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [int]$Port = 19902,
    [string]$Label = 'api-jdk25-win-db',
    [int]$SampleSec = 25,
    [int]$IntervalSec = 2,
    [int]$StartupTimeoutSec = 180,
    [string]$Distro = 'openEuler-24.03-LTS-SP4',
    [string]$Container = 'opengauss'
)

$ErrorActionPreference = 'Stop'
$OpsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bench = Join-Path $OpsDir 'v3-native-bench.ps1'

if (-not (Test-Path -LiteralPath $Exe)) { throw "native exe not found: $Exe" }

# Delegate the WSL/docker call to a standalone Python reader: PowerShell's
# native-command argument marshalling mangles the Go template braces in
# `docker inspect --format`, and the JSON it receives back is incomplete.
$reader = Join-Path $OpsDir 'v3-read-db-password.py'
$dbPass = ((& python $reader) -join '').Trim()
if ([string]::IsNullOrWhiteSpace($dbPass) -or $dbPass -like '*NOT_FOUND*') {
    throw "cannot read $Container GS_PASSWORD via v3-read-db-password.py (WSL/container up?)"
}

# Spring Boot relaxed binding maps these to
# spring.datasource.dynamic.datasource.master.{username,password}
$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME = 'gaussdb'
$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD = $dbPass
Write-Host 'DB credential injected from container env (value not logged)'

& powershell -NoProfile -ExecutionPolicy Bypass -File $Bench `
    -Exe $Exe -Port $Port -Label $Label -SampleSec $SampleSec `
    -IntervalSec $IntervalSec -StartupTimeoutSec $StartupTimeoutSec `
    -ExtraArgs "--server.port=$Port"

# Credentials must not linger in this shell.
Remove-Item Env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME -ErrorAction SilentlyContinue
