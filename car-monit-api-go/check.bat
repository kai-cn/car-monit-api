@echo off
rem 本地校验门：与 CI（.github/workflows/car-monit-api-go-ci.yml）保持一致口径。
rem   gofmt(只查不改) -> goimports -> build(产物写 %TEMP% 并清理) -> vet -> test
rem 任一失败即返回非零退出码。
rem
rem 换行说明：Windows 上 core.autocrlf=true 时工作区是 CRLF，gofmt/goimports 会把
rem 所有文件列为"未格式化"（假失败）。此时本脚本跳过这两步，以 Linux CI 的 LF 结果为准；
rem 想本地检查格式，请设置 core.autocrlf=false 重新检出后再跑。
setlocal
cd /d "%~dp0"

set GO=go

set CRLF=
for /f "delims=" %%a in ('git config core.autocrlf 2^>nul') do set CRLF=%%a
if /i "%CRLF%"=="true" (
  echo [GOFMT] SKIP：工作区为 CRLF 检出（core.autocrlf=true），以 CI 的 LF 结果为准
  echo [GOIMPORTS] SKIP：同上
) else (
  %GO%\gofmt.exe -l .\cmd .\internal > _gofmt.log 2>&1
  if errorlevel 1 (echo [GOFMT] FAIL & type _gofmt.log & exit /b 1)
  for %%f in (_gofmt.log) do if not "%%~zf"=="0" (echo [GOFMT] FAIL：以下文件未格式化，见 _gofmt.log & type _gofmt.log & exit /b 1)

  %GO%\bin\goimports.exe -l .\cmd .\internal > _goimports.log 2>&1
  if errorlevel 1 (echo [GOIMPORTS] FAIL（未安装可执行 go install golang.org/x/tools/cmd/goimports@v0.30.0）& type _goimports.log & exit /b 1)
  for %%f in (_goimports.log) do if not "%%~zf"=="0" (echo [GOIMPORTS] FAIL：以下文件 import 未整理，见 _goimports.log & type _goimports.log & exit /b 1)
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

echo [OK] gofmt / goimports / build / vet / test 全部通过
endlocal
