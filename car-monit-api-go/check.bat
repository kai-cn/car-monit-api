@echo off
rem 统一校验门：gofmt(只查不改) -> go build(产物落临时目录) -> go vet -> go test
rem 任何一步失败就把退出码带出去。CI 见 .github/workflows/car-monit-api-go-ci.yml。
setlocal
cd /d "%~dp0"

set GO=go

rem ---- gofmt：只检查，不改写（报告 02 R13：原脚本的 -w 会静默改动工作区）----
rem Windows 上 core.autocrlf=true 时整个工作区是 CRLF，gofmt 会把所有文件列为未格式化，
rem 这时跳过该步（CI 在 Linux/LF 上执行真正的 gofmt 门禁）。
set CRLF=
for /f "delims=" %%a in ('git config core.autocrlf 2^>nul') do set CRLF=%%a
if /i "%CRLF%"=="true" (
  echo [GOFMT] SKIP：工作区为 CRLF 检出（core.autocrlf=true），以 CI 的 LF gofmt 为准
) else (
  %GO%\gofmt.exe -l .\cmd .\internal > _gofmt.log 2>&1
  if errorlevel 1 (echo [GOFMT] FAIL & type _gofmt.log & exit /b 1)
  for %%f in (_gofmt.log) do if not "%%~zf"=="0" (echo [GOFMT] FAIL：以下文件未格式化，见 _gofmt.log & type _gofmt.log & exit /b 1)
)

rem ---- build：产物写临时目录并清理，避免 bin/ 里的二进制再次入库 ----
set OUT=%TEMP%\car-monit-api-check.exe
%GO%\go.exe build -o "%OUT%" .\cmd\api > _build.log 2>&1
if errorlevel 1 (echo [BUILD] FAIL & type _build.log & exit /b 1)
if exist "%OUT%" del /q "%OUT%"

%GO%\go.exe vet ./... > _vet.log 2>&1
if errorlevel 1 (echo [VET] FAIL & type _vet.log & exit /b 1)

%GO%\go.exe test ./... -count=1 > _test.log 2>&1
if errorlevel 1 (echo [TEST] FAIL & type _test.log & exit /b 1)

echo [OK] gofmt / build / vet / test 全部通过
endlocal
