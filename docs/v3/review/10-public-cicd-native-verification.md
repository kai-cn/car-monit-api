# 10 公开仓库安全加固 + 云 runner CICD + native 镜像验收（api 侧）

> 日期：2026-11-16 ~ 11-17；承接 09-public-repo-hardening.md。
> 本记录覆盖：全分支 workflow 加固、临时凭据实测、artifact 体积 bug、Release artifact 下载、
> native vs JVM 完整业务对比、Windows native CICD。所有真实凭据值均不写入本文档。

## 1. 全分支 workflow 加固（公开仓库安全前提）

对两仓库所有远端分支（api 13 个、backend 11 个）逐分支盘点 workflow，按统一原则加固，
共改造 **12 个分支、61 处 workflow 文件**（api 5+5 分支、backend 3+1 分支；V3 分支此前已加固）：

| 规则 | 内容 |
| --- | --- |
| R1 | `self-hosted-ci.yml` 删除 `push` 触发与 runner 切换输入，仅 `workflow_dispatch`；build 固定 `ubuntu-latest`；deploy job 加 `github.repository_owner == 'kai-cn'` 守卫，去掉 `AUTO_DEPLOY_CLUSTER` |
| R2 | `_java/_cpp/_go/_python.yml` 的 `fromJSON(vars.CI_RUNNER_LABELS ...)` → 固定 `ubuntu-latest`/`windows-latest` |
| R3 | `native-image.yml`（自托管版）job 加 owner 守卫 |
| R4 | `native-image-cloud.yml` 的 `runner_mode` 选项去掉 `self-hosted`，仅保留 cloud；job 加 owner 守卫 |
| R5 | `deploy-selfhosted.yml` / `selfhost-canary.yml` job 加 owner 守卫 |

实现：git plumbing（`hash-object`/`commit-tree`/`update-ref`）在不切换 worktree 的前提下逐分支建提交，
SSH:443 + deploy key 快进推送。校验：dry-run 全分支无待改造项；不变量脚本全绿
（无 push 自托管部署、无 runner 变量切换、自托管 job 必有 owner 守卫、无 `pull_request_target`）。

## 2. 云 runner 账单阻塞与临时凭据实测

- 现象：私有仓库云 runner 全部 job 3s 内 failure、`runner_id=0`、annotation 为
  "recent account payments have failed or spending limit needs increase"。2026-11-08 曾正常（账号级问题）。
- 处置：生成一次性临时凭据（自包含密钥=随机值，外部凭据=测试占位值；内存生成、不回显、不落盘），
  更新两仓 Secrets；临时公开仓库解锁免费 Actions 分钟。
- canary 验证：run `43900329364` success（ubuntu-latest + Mandrel 25.0.5 + gcc/ld/zlib OK）。

## 3. 云 runner 真跑暴露的既存 CI 缺陷（均已修复）

| # | 缺陷 | 修复 |
| --- | --- | --- |
| 1 | Go `GO-2026-6859`（net/http，修于 go1.26.11） | `go.mod`/`go.Dockerfile` → 1.26.11（commit 3159149） |
| 2 | openEuler 容器 setup-python 的 ssl 模块不可用，pip 无法走 HTTPS | `_python.yml` 两 job 改为源码编译 Python 3.12（--with-openssl），去掉 setup-python（commit 60cfc5e） |
| 3 | backend native 缺 `process-aot`/插件钉版/mainClass（远端落后本地提交） | 推送本地未推提交 e23ecbc6 + 补 `/home/ruoyi/logs` 目录（commit 76c133f） |
| 4 | 移除默认 JWT 密钥后 backend py 单测空 key | `ci.yml` 注入 `TOKEN__SECRET` 测试夹具（commit 82bc87c） |
| 5 | backend py 时间炸弹测试（wall-clock 漂移）+ 硬编码口令断言 | 冻结 datetime.now + 去掉 root:root 断言（commit 156954bd） |
| 6 | api `check_parity` 因 V3 内部端点守卫 Java-only 文件红 | 加入 Java-only 作用域豁免（commit 2909f29） |

最终 CICD：api master `43908432856` success、pr `43908459793` success；backend ci 全 job success；
api native `43905084757` / backend native `43905459051` success。

## 4. native artifact 体积 bug（关键）

- 现象：native 构建 success 但 artifact 仅 **1331 B**；日志 `binary_bytes=9232`。
- 根因：`find target -perm -u+x ! -name '*.jar' ! -name '*.exe' -print -quit` 按字典序先命中
  `libjvm.so` 等 9KB JDK shim，而非真产物 `target/<artifactId>`。
- 修复：按 artifactId 精确定位 `bin="$mod/target/$mod"`（Windows 为 `.exe`），
  并加 `MIN_NATIVE_BYTES=10000000` 体积下限门禁；推送 9 分支。
- 验证：重跑 `43910432157` → artifact `120,184,320 B`（zip，内含 `api-jdk25-linux-amd64.bin` 368,249,088 B）。

## 5. Release 页面下载 native artifact

- 改造：`native-image-cloud.yml` 新增 `release_tag` 输入 + `publish` job
  （`needs: build`、`if: release_tag != ''`、`permissions: contents: write`），
  `actions/download-artifact` 拉 `native-*` → 校验每个目录有 >10MB 二进制 → `gh release upload --clobber`。
  推送 9 分支。
- 验证：tag `v3.0.0-native-test`，run `43912645154` → `upload native to GitHub Release` success。
  Release 资产 5 个：`api-jdk25-linux-amd64.bin`(368MB) / `.sha256` / `manifest.json` / `SHA256SUMS` /
  `car-monit-api-standalone-*.tar.gz`。

## 6. native vs JVM 完整业务对比验收（本地 WSL，新产物）

- 产物：云 runner 新 native 二进制（368MB）vs 同版本 jdk25 JVM jar（212MB）；
  DB 用 WSL 的 openGauss(5432)/MySQL(3307)/Redis(6379)。
- 业务完整性（`v3-compare-business.sh`，7 端点）：**7/7 字节级 exact + 语义级 semantic 全 true**，
  证据 `D:/work/runtime-logs/v3-ops/evidence/api-jdk25-cloudnative-20261117-business.json`。
- 性能 A/B（`v3-compare-native-jvm.sh`，60s 采样）：

| 指标 | JVM | native |
| --- | --- | --- |
| 启动耗时 | 16,899 ms | 2,654 ms |
| 启动峰值 RSS | 598.4 MB | 305.1 MB |
| 稳态 RSS | 601.0 MB | 307.1 MB |
| HTTP 延迟 | 15.7 ms | 2.4 ms |
| 稳态探活 | 20/20 | 20/20 |
| 60s 稳定性 | — | 12/12，RSS 漂移 1.9 MB |

证据 `evidence/compare-api-jdk25-cloudnative-20261117-*.json`。

## 7. Windows 端原生镜像完整 CICD

- 能力：`native-image-cloud.yml` 的 `platform=windows` → `windows-latest` + `ilammy/msvc-dev-cmd@v1`
  （注入 cl.exe/link.exe）+ `mvn.cmd`；产物定位按 `$mod.exe`；复用同一 `publish` job 上传 Release。
- 实测：run `43914875664`（`platform=windows`、`release_tag=v3.0.0-native-test`）已触发，
  prepare success、build in_progress（Windows native-image 约 10–15 min）。结果见任务清单 G6。

## 8. 凭据轮换（用户后续必做）

本轮用测试值仅供 CICD；**公开前必须外部轮换**全部真实凭据（清单见 09-public-repo-hardening.md）：
阿里云 AK、JWT、MinIO、恒达、DB 口令、Druid 控制台、内部令牌。轮换后用
`D:\work\runtime-logs\update_gh_secrets.py` 更新 Secrets。git 历史未重写，靠轮换使旧值失效。

## 9. 脚本与产物索引

见 `D:\work\runtime-logs\公开仓库安全加固-任务清单.md` 与同目录脚本（`*-rotate*`/`harden_workflows.py`/
`fix_artifact_selection.py`/`add_native_release.py`/`gh_api.ps1`/`download_artifact.py` 等）。

## 10. 复核与状态
- 独立只读会话复核：无阻断项。
- 两仓库当前 **public**（用户决定公开一段时间，不频繁切换）。
