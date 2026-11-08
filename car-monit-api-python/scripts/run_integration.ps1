# 真实中间件集成测试一键运行（本地 / VM 均可，但只有需要起容器时才检查磁盘与 Docker）
#
# 用法（在 car-monit-api-python 目录下）：
#   $env:CAR_MONIT_IT_DATA_DIR = "E:\car-monit-it-data"
#   powershell -ExecutionPolicy Bypass -File scripts\run_integration.ps1 -DataDir $env:CAR_MONIT_IT_DATA_DIR
#
# 只跑已就绪的中间件（不启动容器）：
#   powershell -ExecutionPolicy Bypass -File scripts\run_integration.ps1 -SkipStart
#
# 测试 Linux VM 上的中间件（不启动本地容器）：
#   powershell -ExecutionPolicy Bypass -File scripts\run_integration.ps1 -SkipStart -ServiceHost 192.168.56.10
#
# 规则（docs/LOCAL-ENV.md）：
#   * 需要起容器时，C 盘 < 5GB 或 D 盘 < 8GB 直接 BLOCKED，不碰 Docker；
#   * 数据目录必须显式指定，且其所在卷 >= 8GB；
#   * 不删除任何用户数据；`docker compose down` 不带 `-v`。
param(
    [string]$DataDir = $env:CAR_MONIT_IT_DATA_DIR,
    [switch]$SkipStart,
    [switch]$KeepUp,
    [string]$ServiceHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $root "docker-compose.integration.yml"
$C_MIN_GB = 5
$D_MIN_GB = 8
$DATA_MIN_GB = 8

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $mainPy = Join-Path (Split-Path -Parent (Split-Path -Parent $root)) "car-monit-api-python\.venv\Scripts\python.exe"
    if (Test-Path $mainPy) { $py = $mainPy } else { $py = "python" }
}

function Write-Step([string]$Text) { Write-Host ""; Write-Host "=== $Text ===" -ForegroundColor Cyan }
function Write-Blocked([string]$Text) { Write-Host "BLOCKED: $Text" -ForegroundColor Red; exit 2 }

function Get-FreeGB([string]$PathOrDrive) {
    try {
        $full = [System.IO.Path]::GetFullPath($PathOrDrive)
        $rootPart = [System.IO.Path]::GetPathRoot($full)
        if (-not $rootPart) { return $null }
        $letter = $rootPart.TrimEnd('\').TrimEnd(':')
        $drive = Get-PSDrive -Name $letter -ErrorAction SilentlyContinue
        if ($null -eq $drive) { return $null }
        return [math]::Round($drive.Free / 1GB, 2)
    } catch {
        return $null
    }
}

function Test-TcpPort([string]$HostName, [int]$Port) {
    try {
        return (Test-NetConnection -ComputerName $HostName -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
    } catch {
        return $false
    }
}

function Wait-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutSeconds = 120) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort $HostName $Port) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-EsHealthy([string]$HostName, [int]$Port, [int]$TimeoutSeconds = 120) {
    $url = "http://${HostName}:${Port}/_cluster/health?wait_for_status=yellow&timeout=5s"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri $url -TimeoutSec 10
            if ($health.status -in @("yellow", "green")) { return $true }
        } catch {
            # 容器还在启动，继续等
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

# ------------------------------------------------------------------ 磁盘快照
Write-Step "磁盘实测"
$cFree = (Get-PSDrive -Name C).Free / 1GB
$dDrive = Get-PSDrive -Name D -ErrorAction SilentlyContinue
$dFree = if ($null -eq $dDrive) { $null } else { $dDrive.Free / 1GB }
"C 盘可用 : {0:N2} GB (阈值 {1} GB)" -f $cFree, $C_MIN_GB
if ($null -eq $dFree) { "D 盘      : 不存在或不可读" } else { "D 盘可用 : {0:N2} GB (阈值 {1} GB)" -f $dFree, $D_MIN_GB }

# ------------------------------------------------------------------ 端口探测
$redisPort = if ($env:CAR_MONIT_IT_REDIS_PORT) { [int]$env:CAR_MONIT_IT_REDIS_PORT } else { 6379 }
$esPort = if ($env:CAR_MONIT_IT_ES_PORT) { [int]$env:CAR_MONIT_IT_ES_PORT } else { 9200 }
$kafkaPort = if ($env:CAR_MONIT_IT_KAFKA_PORT) { [int]$env:CAR_MONIT_IT_KAFKA_PORT } else { 9092 }

Write-Step "中间件端口探测（$ServiceHost）"
$redisUp = Test-TcpPort $ServiceHost $redisPort
$esUp = Test-TcpPort $ServiceHost $esPort
$kafkaUp = Test-TcpPort $ServiceHost $kafkaPort
"redis        : {0}:{1} -> {2}" -f $ServiceHost, $redisPort, $(if ($redisUp) { "UP" } else { "DOWN" })
"elasticsearch: {0}:{1} -> {2}" -f $ServiceHost, $esPort, $(if ($esUp) { "UP" } else { "DOWN" })
"kafka        : {0}:{1} -> {2}" -f $ServiceHost, $kafkaPort, $(if ($kafkaUp) { "UP" } else { "DOWN" })

$missingServices = @()
if (-not $redisUp) { $missingServices += "redis" }
if (-not $esUp) { $missingServices += "elasticsearch" }
if (-not $kafkaUp) { $missingServices += "kafka" }

$startedContainers = $false
if ($missingServices.Count -gt 0) {
    if ($SkipStart) {
        Write-Blocked ("以下中间件未就绪且指定了 -SkipStart：" + ($missingServices -join ", "))
    }
    # 需要启动容器：先过磁盘硬门禁（不允许为了跑起来写满本机）
    if ($cFree -lt $C_MIN_GB -or ($null -ne $dFree -and $dFree -lt $D_MIN_GB) -or ($null -eq $dFree)) {
        Write-Blocked ("磁盘不足：C={0:N2}GB / D={1:N2}GB；需 C>={2}GB 且 D>={3}GB 才允许启动容器（见 docs/LOCAL-ENV.md）" -f $cFree, $dFree, $C_MIN_GB, $D_MIN_GB)
    }
    if ($ServiceHost -ne "127.0.0.1" -and $ServiceHost -ne "localhost") {
        Write-Blocked "远程 ServiceHost 需要先在目标机执行 docker compose up -d，本脚本不远程启动容器"
    }
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        Write-Blocked "未找到 docker CLI：请安装 Docker Desktop，或改用 Linux VM（见 docs/LOCAL-ENV.md §3.4）"
    }
    if ([string]::IsNullOrWhiteSpace($DataDir)) {
        Write-Blocked "必须显式指定 -DataDir 或 CAR_MONIT_IT_DATA_DIR（避免写入已满的系统盘）"
    }
    $dataFree = Get-FreeGB $DataDir
    if ($null -eq $dataFree -or $dataFree -lt $DATA_MIN_GB) {
        Write-Blocked ("数据目录所在卷可用空间不足 {0}GB 或不可读：{1}（可用 {2} GB）" -f $DATA_MIN_GB, $DataDir, $dataFree)
    }
    if (-not (Test-Path $DataDir)) {
        New-Item -ItemType Directory -Path $DataDir | Out-Null
    }
    $env:CAR_MONIT_IT_DATA_DIR = [System.IO.Path]::GetFullPath($DataDir)
    "数据目录 : {0}（可用 {1} GB）" -f $env:CAR_MONIT_IT_DATA_DIR, $dataFree

    Write-Step "启动容器：$($missingServices -join ', ')"
    & docker compose -f $composeFile up -d $missingServices
    if ($LASTEXITCODE -ne 0) {
        Write-Host "docker compose up 失败（exit $LASTEXITCODE）" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    $startedContainers = $true

    Write-Step "等待就绪"
    if (-not (Wait-TcpPort $ServiceHost $redisPort)) { Write-Blocked "redis 未在 120s 内就绪" }
    if (-not (Wait-EsHealthy $ServiceHost $esPort)) { Write-Blocked "elasticsearch 未在 120s 内达到 yellow/green" }
    if (-not (Wait-TcpPort $ServiceHost $kafkaPort)) { Write-Blocked "kafka 未在 120s 内就绪" }
} else {
    Write-Host "三个中间件均已就绪，跳过容器启动。" -ForegroundColor Green
}

# ------------------------------------------------------------------ 跑测试
Write-Step "pytest tests/business -m integration"
$env:CAR_MONIT_TEST_REDIS = "1"
$env:CAR_MONIT_REDIS_URL = "redis://${ServiceHost}:${redisPort}/0"
$env:CAR_MONIT_TEST_ES = "1"
$env:CAR_MONIT_ES_URL = "http://${ServiceHost}:${esPort}"
$env:CAR_MONIT_TEST_KAFKA = "1"
$env:CAR_MONIT_KAFKA_URL = "${ServiceHost}:${kafkaPort}"

& $py -m pytest (Join-Path $root "tests\business") -m integration -q
$testExit = $LASTEXITCODE

if ($startedContainers -and -not $KeepUp) {
    Write-Step "关闭 compose（不删数据卷）"
    & docker compose -f $composeFile down | Out-Null
}

if ($testExit -eq 0) {
    Write-Host "RESULT: integration PASSED" -ForegroundColor Green
} else {
    Write-Host "RESULT: integration FAILED (exit $testExit)" -ForegroundColor Red
}
exit $testExit
