# ======================================================================
# 文件：scripts/v3/ops/v3-compare-native-jvm.ps1
# 用途：PowerShell 运维/构建脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
# Windows A/B measurement: Spring Boot native .exe vs ordinary fat jar.
#
#   powershell -File v3-compare-native-jvm.ps1 `
#      -NativeExe <...\pro-business-api.exe> -Jar <...\pro-business-api-1.0.jar> `
#      -JavaExe <...\bin\java.exe> -DurationSec 180 -IntervalSec 5
#
# Prerequisites: WSL is up, openGauss/redis reachable on 127.0.0.1, and the DB
# credential is readable from the container (v3-read-db-password.py).
# The JVM variant needs --add-opens=java.base/java.lang=ALL-UNNAMED (Orika),
# which native images do not need. Both variants otherwise get identical args.
#
# Outputs under $EvidenceDir:
#   compare-win-<label>.csv / .json / -summary.txt
#   native-run-* logs produced by v3-native-bench.ps1
param(
    [Parameter(Mandatory = $true)][string]$NativeExe,
    [Parameter(Mandatory = $true)][string]$Jar,
    [string]$JavaExe = 'D:\jdk\mandrel-25.0.4.1-Final\bin\java.exe',
    [int]$PortNative = 19902,
    [int]$PortJvm = 19903,
    [int]$SampleSec = 20,
    [int]$DurationSec = 180,
    [int]$IntervalSec = 5,
    [int]$StartupTimeoutSec = 180,
    [string]$ProbePath = '/doc.html',
    [string]$Label = 'api-jdk25-win',
    [string]$EvidenceDir = 'D:\work\runtime-logs\v3-ops\evidence'
)

$ErrorActionPreference = 'Stop'
$OpsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bench = Join-Path $OpsDir 'v3-native-bench.ps1'
$Reader = Join-Path $OpsDir 'v3-read-db-password.py'
if (-not (Test-Path -LiteralPath $NativeExe)) { throw "native exe missing: $NativeExe" }
if (-not (Test-Path -LiteralPath $Jar)) { throw "jar missing: $Jar" }
if (-not (Test-Path -LiteralPath $JavaExe)) { throw "java missing: $JavaExe" }
if (-not (Test-Path -LiteralPath $EvidenceDir)) { New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null }

$dbPass = ((& python $Reader) -join '').Trim()
if ([string]::IsNullOrWhiteSpace($dbPass) -or $dbPass -like '*NOT_FOUND*') {
    throw 'cannot read openGauss GS_PASSWORD (is WSL + container running?)'
}
$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME = 'gaussdb'
$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD = $dbPass
Write-Host 'DB credential injected from container env (value not logged)'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$csv = Join-Path $EvidenceDir "compare-win-$Label-$stamp.csv"
$jsonPath = Join-Path $EvidenceDir "compare-win-$Label-$stamp.json"
$rows = New-Object System.Collections.ArrayList
function Add-Row($variant, $phase, $elapsed, $rssMB, $cpuSec, $httpCode, $httpMs) {
    [void]$rows.Add([pscustomobject]@{
        variant = $variant; phase = $phase; elapsed_s = $elapsed; rss_MB = $rssMB
        cpu_seconds = $cpuSec; http_code = $httpCode; http_ms = $httpMs
    })
}

$beforeCsv = @(Get-ChildItem -LiteralPath $EvidenceDir -Filter "native-bench-$Label-*.csv" |
    Select-Object -ExpandProperty Name)

Write-Host '==== A/B: JVM fat jar ===='
& powershell -NoProfile -ExecutionPolicy Bypass -File $Bench `
    -Exe $JavaExe -Port $PortJvm -Label "$Label-jvm" -SampleSec $SampleSec `
    -IntervalSec 2 -StartupTimeoutSec $StartupTimeoutSec `
    -ExtraArgs "--add-opens=java.base/java.lang=ALL-UNNAMED -jar $Jar --server.port=$PortJvm"

Write-Host '==== A/B: native exe ===='
& powershell -NoProfile -ExecutionPolicy Bypass -File $Bench `
    -Exe $NativeExe -Port $PortNative -Label "$Label-native" -SampleSec $SampleSec `
    -IntervalSec 2 -StartupTimeoutSec $StartupTimeoutSec `
    -ExtraArgs "--server.port=$PortNative"

# Fold the two bench CSVs into the comparison CSV (steady-state samples).
Get-ChildItem -LiteralPath $EvidenceDir -Filter "native-bench-$Label-*.csv" |
    Where-Object { $beforeCsv -notcontains $_.Name } | ForEach-Object {
        $variant = if ($_.Name -like '*-jvm-*') { 'jvm' } else { 'native' }
        Import-Csv $_.FullName | Where-Object { $_.phase -eq 'steady' } | ForEach-Object {
            Add-Row $variant 'steady' $_.s $_.rss_MB $_.cpu_seconds '' ''
        }
    }

Write-Host "==== stability: native for $DurationSec s ===="
$log = Join-Path $EvidenceDir "compare-win-$Label-$stamp-stability.log"
$psiArgs = "--server.port=$PortNative"
$proc = Start-Process -FilePath $NativeExe -ArgumentList $psiArgs -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$ready = $false
for ($i = 0; $i -lt 300; $i++) {
    if ($proc.HasExited) { Write-Host 'native stability process exited'; break }
    $tcp = New-Object System.Net.Sockets.TcpClient
    try { $tcp.Connect('127.0.0.1', $PortNative); $ready = $true; $tcp.Close(); break }
    catch { Start-Sleep -Milliseconds 500 }
    finally { $tcp.Dispose() }
}
Write-Host "stability port_ready=$ready startup_ms=$($sw.ElapsedMilliseconds)"
if ($ready) {
    $n = [Math]::Max(1, [int]($DurationSec / $IntervalSec))
    for ($i = 1; $i -le $n; $i++) {
        Start-Sleep -Seconds $IntervalSec
        $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        if (-not $p) { Write-Host 'native exited during stability'; break }
        $rss = [math]::Round($p.WorkingSet64 / 1MB, 1)
        $cpu = [math]::Round($p.CPU, 2)
        $code = '000'; $ms = 0.0
        try {
            $t0 = Get-Date
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PortNative$ProbePath" -UseBasicParsing -TimeoutSec 5
            $code = [string][int]$r.StatusCode
            $ms = [math]::Round(((Get-Date) - $t0).TotalMilliseconds, 1)
        } catch {
            if ($_.Exception.Response) { $code = [string][int]$_.Exception.Response.StatusCode }
            $ms = -1
        }
        Add-Row 'native' 'stability' ($i * $IntervalSec) $rss $cpu $code $ms
    }
}
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }

$rows | Export-Csv -LiteralPath $csv -NoTypeInformation -Encoding UTF8

# Aggregate with Python (consistent with the Linux comparison script).
$nativeBytes = (Get-Item -LiteralPath $NativeExe).Length
$jarBytes = (Get-Item -LiteralPath $Jar).Length
& python -c @"
import csv,json,sys
p=r'$csv'; j=r'$jsonPath'
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
def st(v,ph):
    rs=[r for r in rows if r['variant']==v and r['phase']==ph]
    rss=[float(r['rss_MB']) for r in rs if r['rss_MB'] not in ('','0')]
    codes=[r['http_code'] for r in rs if r['http_code']]
    lat=[float(r['http_ms']) for r in rs if r['http_ms'] not in ('',None)]
    return {'samples':len(rs),'rss_avg_MB':round(sum(rss)/len(rss),1) if rss else None,
            'rss_min_MB':min(rss) if rss else None,'rss_max_MB':max(rss) if rss else None,
            'http_success':sum(1 for c in codes if c not in ('000','0')),'http_total':len(codes),
            'http_latency_avg_ms':round(sum(lat)/len(lat),1) if lat else None,
            'rss_first_MB':rss[0] if rss else None,'rss_last_MB':rss[-1] if rss else None,
            'rss_drift_MB':round(rss[-1]-rss[0],1) if len(rss)>1 else None}
out={'label':'$Label','native_bytes':$nativeBytes,'jar_bytes':$jarBytes,'duration_s':$DurationSec,
     'steady':{v:st(v,'steady') for v in ('jvm','native')},'native_stability':st('native','stability')}
json.dump(out,open(j,'w',encoding='utf-8'),indent=2,ensure_ascii=False)
print(json.dumps(out,indent=2,ensure_ascii=False))
"@

Remove-Item Env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME -ErrorAction SilentlyContinue
Write-Host "COMPARE_WIN_OK csv=$csv json=$jsonPath"
