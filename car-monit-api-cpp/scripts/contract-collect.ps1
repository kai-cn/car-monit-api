#!/usr/bin/env pwsh
# 契约采集脚本（只读）。
#
# 用途：把 Java（或 C++）实例的真实响应按端点固化为样本文件，供 contract-diff.ps1 比较。
# 只采集 GET 端点（skipMethods 中的方法一律跳过），不会修改任何数据。
#
# 用法（在 car-monit-api-cpp 目录下执行）：
#   powershell -File scripts/contract-collect.ps1 -BaseUrl http://127.0.0.1:9902 -OutDir contracts/captured/java
#   powershell -File scripts/contract-collect.ps1 -BaseUrl http://127.0.0.1:9901 -OutDir contracts/captured/cpp
#
# 说明：
#   - 端点清单来自 contracts/endpoints.golden.json（由 carmonit_tests 生成/校验）。
#   - path 参数与 query 参数来自 contracts/samples.json，可按环境覆盖。
#   - 实例不可达时写 PENDING 文件并以 0 退出（不反复重试）。
param(
  [string]$BaseUrl = "http://127.0.0.1:9902",
  [string]$OutDir = "contracts/captured/java",
  [string]$Manifest = "contracts/endpoints.golden.json",
  [string]$Samples = "contracts/samples.json",
  [int]$TimeoutSec = 10
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Manifest)) { Write-Error "缺少端点清单: $Manifest（先运行 carmonit_tests 生成）"; exit 2 }
if (-not (Test-Path $Samples)) { Write-Error "缺少样本配置: $Samples"; exit 2 }

$manifestObj = Get-Content $Manifest -Raw | ConvertFrom-Json
$sampleCfg = Get-Content $Samples -Raw | ConvertFrom-Json
$endpoints = @($manifestObj.endpoints)
$skip = @($sampleCfg.skipMethods)

# 预检：一次 GET /health；失败即标记待采集，不反复重试。
$preflightOk = $false
try {
  $null = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec $TimeoutSec
  $preflightOk = $true
} catch {
  try {
    # /health 可能不存在（Java），退化为请求一个已知端点看是否只返回 404/业务错误。
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/large/fee?pageNum=1&pageSize=1" -UseBasicParsing -TimeoutSec $TimeoutSec
    $preflightOk = $true
  } catch {
    $resp = $_.Exception.Response
    if ($null -ne $resp) { $preflightOk = $true }  # 有 HTTP 响应说明实例可达
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (-not $preflightOk) {
  $pending = @{
    status = "PENDING"
    baseUrl = $BaseUrl
    reason = "实例不可达（连接被拒绝/超时）"
    capturedAt = (Get-Date).ToString("s")
  } | ConvertTo-Json -Depth 4
  Set-Content -Path (Join-Path $OutDir "PENDING.json") -Value $pending -Encoding UTF8
  Write-Host "[contract] $BaseUrl 不可达，已标记为待采集：$OutDir/PENDING.json"
  exit 0
}

function Get-Slug([string]$method, [string]$path) {
  $s = ($method + "_" + $path).ToLower()
  $s = $s -replace '[^a-z0-9]+', '_'
  $s = $s.Trim('_')
  return $s
}

function Expand-Path([string]$pattern) {
  $p = $pattern
  foreach ($m in [regex]::Matches($pattern, '\{([^}]+)\}')) {
    $name = $m.Groups[1].Value
    $val = $sampleCfg.pathParams.$name
    if ($null -eq $val -or $val -eq "") { $val = "1" }
    $p = $p -replace [regex]::Escape($m.Value), [uri]::EscapeDataString([string]$val)
  }
  return $p
}

$captured = 0
$skipped = 0
foreach ($e in $endpoints) {
  if ($skip -contains $e.method) { $skipped++; continue }
  $path = Expand-Path $e.path
  $url = "$BaseUrl$path"
  if ($e.kind -eq "table") {
    $qs = @()
    foreach ($k in $sampleCfg.query.PSObject.Properties.Name) {
      $qs += "$k=$([uri]::EscapeDataString([string]$sampleCfg.query.$k))"
    }
    if ($qs.Count -gt 0) { $url += "?" + ($qs -join "&") }
  }
  $status = 0
  $body = ""
  $contentType = ""
  try {
    $r = Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec $TimeoutSec -Headers $sampleCfg.headers
    $status = [int]$r.StatusCode
    $body = $r.Content
    $contentType = $r.Headers["Content-Type"]
  } catch {
    $resp = $_.Exception.Response
    if ($null -ne $resp) {
      $status = [int]$resp.StatusCode
      $sr = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $body = $sr.ReadToEnd()
      $contentType = $resp.Headers["Content-Type"]
    } else {
      $body = $_.Exception.Message
    }
  }
  $record = @{
    method = $e.method
    path = $e.path
    url = $url
    kind = $e.kind
    status = $status
    contentType = [string]$contentType
    body = $body
    capturedAt = (Get-Date).ToString("s")
  } | ConvertTo-Json -Depth 5
  Set-Content -Path (Join-Path $OutDir ((Get-Slug $e.method $e.path) + ".json")) -Value $record -Encoding UTF8
  $captured++
}

$summary = @{
  baseUrl = $BaseUrl
  captured = $captured
  skipped = $skipped
  capturedAt = (Get-Date).ToString("s")
} | ConvertTo-Json
Set-Content -Path (Join-Path $OutDir "_summary.json") -Value $summary -Encoding UTF8
Write-Host "[contract] 采集完成：$captured 个端点（跳过 $skipped 个写方法）→ $OutDir"
