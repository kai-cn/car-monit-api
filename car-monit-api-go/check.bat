@echo off
rem 统一校验门：gofmt -> go build -> go vet。任何一步失败就把退出码带出去。
setlocal
set GO=D:\golang\go1.24.1\bin
cd /d d:\work\IdeaProjects\car-monit-api\car-monit-api-go

%GO%\gofmt.exe -l -w .\cmd .\internal > _gofmt.log 2>&1
if errorlevel 1 (echo [GOFMT] FAIL & type _gofmt.log & exit /b 1)
for %%f in (_gofmt.log) do if not "%%~zf"=="0" (echo [GOFMT] 改写了文件，见 _gofmt.log & type _gofmt.log)

%GO%\go.exe build -o bin\api.exe .\cmd\api > _build.log 2>&1
if errorlevel 1 (echo [BUILD] FAIL & type _build.log & exit /b 1)

%GO%\go.exe vet ./... > _vet.log 2>&1
if errorlevel 1 (echo [VET] FAIL & type _vet.log & exit /b 1)

echo [OK] gofmt / build / vet 全部通过
endlocal
