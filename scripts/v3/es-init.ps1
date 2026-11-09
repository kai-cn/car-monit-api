# =============================================================================
# V3 阶段一：Elasticsearch 初始化脚本（ILM + 月索引模板 + 月索引/别名）
#
# 依赖：PowerShell 5.1+，可访问 ES 7.x
# 用法：
#   $env:ES_URL = "http://localhost:9200"
#   .\es-init.ps1                          # 创建 ILM + 模板 + 最近 13 个月索引/别名
#   .\es-init.ps1 -Months 13 -ForwardMonths 1
#   .\es-init.ps1 -Backfill -ApiBaseUrl "http://localhost:9902"
#
# 说明：
#   - 幂等：ILM/模板覆盖写；索引已存在则跳过；别名重复添加无害。
#   - 索引命名：snapshot-flow-YYYYMM / fee-records-YYYYMM / trail-fitting-YYYYMM
#   - 别名：*-read 指向所有保留月；*-write 指向当月。
#   - 回灌调用 V3 API（/api/v3/sync/backfill），由 API 侧从 GaussDB 读取并 bulk 写入 ES。
# =============================================================================

param(
    [string]$EsUrl = $env:ES_URL,
    [int]$Months = 13,
    [int]$ForwardMonths = 1,
    [switch]$Backfill,
    [switch]$Activate,
    [string]$ApiBaseUrl = "http://localhost:9902",
    [string]$EsUser = $env:ES_USERNAME,
    [string]$EsPassword = $env:ES_PASSWORD,
    [string]$InternalToken = $env:TRAFFIC_INTERNAL_TOKEN
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($EsUrl)) {
    $EsUrl = "http://localhost:9200"
}
$EsUrl = $EsUrl.TrimEnd('/')

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$esJsonDir = Join-Path $here "..\..\pro-business-api\src\main\resources\es\v3"
$esJsonDir = (Resolve-Path $esJsonDir).Path

$headers = @{ "Content-Type" = "application/json" }
$apiHeaders = @{}
if (-not [string]::IsNullOrWhiteSpace($InternalToken)) {
    $apiHeaders["X-Internal-Token"] = $InternalToken.Trim()
}
if (-not [string]::IsNullOrWhiteSpace($EsUser)) {
    $pair = "${EsUser}:${EsPassword}"
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
    $headers["Authorization"] = "Basic $b64"
}

function Invoke-EsPut([string]$path, [string]$body) {
    $uri = "$EsUrl$path"
    try {
        # 显式 UTF-8 字节，避免 PowerShell 5 默认编码把 §/中文等写成非 UTF-8
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $resp = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $bytes
        Write-Host "[ES] PUT $path -> OK"
        return $resp
    } catch {
        Write-Host "[ES] PUT $path -> FAILED: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

function Test-EsIndex([string]$indexName) {
    try {
        Invoke-WebRequest -Uri "$EsUrl/$indexName" -Method Head -Headers $headers | Out-Null
        return $true
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 404) {
            return $false
        }
        throw
    }
}

function Invoke-EsAliases([string]$body) {
    Invoke-RestMethod -Uri "$EsUrl/_aliases" -Method Post -Headers $headers -Body $body | Out-Null
}

# -----------------------------------------------------------------------------
# 1. ILM 策略（必须先于模板/索引创建）
# -----------------------------------------------------------------------------
$ilmFile = Join-Path $esJsonDir "ilm_traffic_hot_warm_cold.json"
Invoke-EsPut "/_ilm/policy/traffic_hot_warm_cold" (Get-Content $ilmFile -Raw -Encoding UTF8)

# -----------------------------------------------------------------------------
# 2. 月索引模板
# -----------------------------------------------------------------------------
$templates = @(
    @{ name = "snapshot-flow-template"; file = "snapshot_flow_template.json" },
    @{ name = "fee-records-template";   file = "fee_records_template.json" },
    @{ name = "trail-fitting-template"; file = "trail_fitting_template.json" },
    @{ name = "car-warning-template";   file = "car_warning_template.json" }
)
foreach ($t in $templates) {
    $body = Get-Content (Join-Path $esJsonDir $t.file) -Raw -Encoding UTF8
    Invoke-EsPut "/_index_template/$($t.name)" $body
}

# -----------------------------------------------------------------------------
# 3. 月索引 + 读写别名
# -----------------------------------------------------------------------------
$bases = @("snapshot-flow", "fee-records", "trail-fitting")
$now = Get-Date
$currentYm = $now.ToString("yyyyMM")

for ($offset = -($Months - 1); $offset -le $ForwardMonths; $offset++) {
    $month = $now.AddMonths($offset)
    $ym = $month.ToString("yyyyMM")
    foreach ($base in $bases) {
        $index = "$base-$ym"
        if (Test-EsIndex $index) {
            Write-Host "[ES] 索引已存在，跳过: $index"
        } else {
            # 创建索引时直接挂 read 别名；模板按 index_patterns 自动应用
            $body = "{ ""aliases"": { ""$base-read"": {} } }"
            Invoke-EsPut "/$index" $body
        }

        # 当月追加 write 别名
        if ($ym -eq $currentYm) {
            $aliasBody = "{ ""actions"": [ { ""add"": { ""index"": ""$index"", ""alias"": ""$base-write"" } } ] }"
            Invoke-EsAliases $aliasBody
            Write-Host "[ES] 写别名: $base-write -> $index"
        }
    }
}

Write-Host "[ES] 初始化完成：月索引 $($Months + $ForwardMonths) 个/表，读别名 $($bases.Count) 个，写别名指向 $currentYm"

# 实时预警固定索引 car-warning（不挂 ILM，模板由上面 car-warning-template 应用）
if (Test-EsIndex "car-warning") {
    Write-Host "[ES] car-warning 已存在，跳过创建"
} else {
    Invoke-EsPut "/car-warning" "{}"
}

# -----------------------------------------------------------------------------
# 4. 可选：触发回灌（API 异步任务）
# -----------------------------------------------------------------------------
$backfillFailed = $false
if ($Backfill) {
    # 按月分片：单任务窗口恒为 1 个月，既不受 sync.backfill-max-days 限制，
    # 也便于失败重放；整段窗口 = 过去 Months-1 个月 + 当月 + 预建 ForwardMonths 个月。
    $submitted = 0
    for ($m = -($Months - 1); $m -le $ForwardMonths; $m++) {
        $chunkStart = $now.AddMonths($m).ToString("yyyy-MM-01 00:00:00")
        $chunkEnd = $now.AddMonths($m + 1).ToString("yyyy-MM-01 00:00:00")
        foreach ($table in @("snapshot", "fee", "trail")) {
            $uri = "$ApiBaseUrl/api/v3/sync/backfill?table=$table&startTime=$([uri]::EscapeDataString($chunkStart))&endTime=$([uri]::EscapeDataString($chunkEnd))"
            try {
                $resp = Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Headers $apiHeaders
                # 管理端点失败时返回 HTTP 200 + code:500，PowerShell 不会进 catch，必须显式判业务码
                if ($null -eq $resp -or $resp.code -ne 200) {
                    $backfillFailed = $true
                    Write-Host "[Backfill] $table $chunkStart -> REJECTED: $($resp | ConvertTo-Json -Compress)" -ForegroundColor Red
                } else {
                    $submitted++
                }
            } catch {
                $backfillFailed = $true
                Write-Host "[Backfill] $table $chunkStart -> FAILED: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
    Write-Host "[Backfill] 已提交 $submitted 个分片任务，是否存在失败分片：$backfillFailed。"
    Write-Host "[Backfill] 任务为异步执行；请先轮询 /api/v3/sync/backfill/status/{taskId} 确认完成，再切换 es。"
}

# -----------------------------------------------------------------------------
# 5. 就绪检查与可选启用 es（运行期临时生效）
# -----------------------------------------------------------------------------
try {
    $ready = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v3/es/readiness" -Method Get -Headers $apiHeaders
    Write-Host "[Readiness] $($ready.data | ConvertTo-Json -Compress)"
} catch {
    Write-Host "[Readiness] 查询失败（API 未启动或不可达）: $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($Activate -and $backfillFailed) {
    Write-Host "[Activate] 回灌存在失败分片，拒绝切换 es（保持 legacy），请先修复并重放回灌。" -ForegroundColor Red
} elseif ($Activate) {
    try {
        $act = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v3/es/activate?engine=es" -Method Post -Headers $apiHeaders
        Write-Host "[Activate] $($act | ConvertTo-Json -Compress)"
        if ($act.code -ne 200) {
            Write-Host "[Activate] 未就绪，保持 legacy；请先完成 bootstrap/回灌。" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[Activate] 调用失败: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "切换 es 的两种方式（默认配置仍为 legacy，安全启动）："
Write-Host "  1) 持久化：设置环境变量 TRAFFIC_QUERY_ENGINE=es（或 application.yml 中 traffic.query.engine=es）并重启；"
Write-Host "  2) 临时生效（重启后失效）：POST $ApiBaseUrl/api/v3/es/activate?engine=es"
Write-Host "回滚：POST $ApiBaseUrl/api/v3/es/activate?engine=legacy，或把配置改回 legacy。"
Write-Host "注意：回灌未完成时不要切换 es，否则查询结果可能缺数据。"
