#!/usr/bin/env pwsh
# 契约 diff：比较 Java 与 C++ 采集结果。
#
# 用法：
#   powershell -File scripts/contract-diff.ps1
#   powershell -File scripts/contract-diff.ps1 -JavaDir contracts/captured/java -CppDir contracts/captured/cpp
#
# 比较内容：HTTP status + 响应 body 的 JSON 结构/值。
# 忽略易变字段（时间戳/自增 id/分页 total 等），数组按元素 JSON 排序后比较。
param(
  [string]$JavaDir = "contracts/captured/java",
  [string]$CppDir = "contracts/captured/cpp",
  [string[]]$IgnoreKeys = @(
    "id", "uuid", "bigId", "big_id", "datauuid", "taskId", "createTime", "updateTime",
    "loadTime", "timestamp", "sendTime", "send_time", "snapshottime", "entime", "extime",
    "transtime", "total", "time", "date"
  )
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $JavaDir)) { Write-Error "缺少 Java 采集目录: $JavaDir（先运行 contract-collect.ps1）"; exit 2 }
if (-not (Test-Path $CppDir)) { Write-Error "缺少 C++ 采集目录: $CppDir（先运行 contract-collect.ps1）"; exit 2 }

function Normalize($node) {
  if ($null -eq $node) { return $null }
  if ($node -is [string] -or $node -is [ValueType]) { return $node }
  if ($node -is [System.Collections.IEnumerable]) {
    $items = @()
    foreach ($x in $node) { $items += ,(Normalize $x) }
    $sorted = $items | Sort-Object { $_ | ConvertTo-Json -Depth 100 -Compress }
    return ,@($sorted)
  }
  $obj = [ordered]@{}
  foreach ($p in $node.PSObject.Properties) {
    if ($IgnoreKeys -contains $p.Name) { continue }
    $obj[$p.Name] = Normalize $p.Value
  }
  return [PSCustomObject]$obj
}

function Body-Of($record) {
  $body = [string]$record.body
  try { return ($body | ConvertFrom-Json) } catch { return $body }
}

$javaFiles = Get-ChildItem $JavaDir -Filter *.json | Where-Object { $_.Name -notmatch '^(_summary|PENDING)' }
$fail = 0
$pass = 0
foreach ($jf in $javaFiles) {
  $cf = Join-Path $CppDir $jf.Name
  if (-not (Test-Path $cf)) {
    Write-Host "[MISS] 缺少 C++ 样本: $($jf.Name)"
    $fail++
    continue
  }
  $j = Get-Content $jf.FullName -Raw | ConvertFrom-Json
  $c = Get-Content $cf -Raw | ConvertFrom-Json
  if ([int]$j.status -ne [int]$c.status) {
    Write-Host "[FAIL] $($jf.Name) status: java=$($j.status) cpp=$($c.status)"
    $fail++
    continue
  }
  $jn = Normalize (Body-Of $j) | ConvertTo-Json -Depth 100 -Compress
  $cn = Normalize (Body-Of $c) | ConvertTo-Json -Depth 100 -Compress
  if ($jn -ne $cn) {
    Write-Host "[FAIL] $($jf.Name) body 不一致"
    Write-Host "  java: $jn"
    Write-Host "  cpp : $cn"
    $fail++
  } else {
    $pass++
  }
}

Write-Host "[contract-diff] 通过 $pass，失败 $fail"
if ($fail -gt 0) { exit 1 }
