# CI/CD 搭建进度（重启恢复用）

> 用途：用户可能随时重启电脑；按本文件勾选状态恢复，不要重复已完成阶段。
> 方案与矩阵见 [CI-CD-PIPELINES.md](CI-CD-PIPELINES.md)。

## 阶段状态

| 阶段 | 内容 | 状态 | 提交 |
| --- | --- | --- | --- |
| 0 | 事实核查（远端/分支/子仓归属/现有 workflow/工具链） | 完成 | 1796547 |
| 1 | 方案矩阵表 + 两个待确认项 + 缺口清单（本文件与方案文档） | 完成 | 1796547 |
| 2 | PR 流水线：`pr.yml` + `_java/_cpp/_go/_python/_rust.yml`，移除 Python-only `ci.yml` | 完成 | c097c12 |
| 3 | 主分支流水线：`master.yml`（全量构建/测试/覆盖率/产物） | 完成 | eeb3573 |
| 4 | 发布流水线：`release.yml`（tag + Release 资产）、`deploy.yml` 占位 | 完成 | 3de9ab9 |
| 5 | YAML 自检（PyYAML + actionlint 全绿）；Actions 实跑未确认 | 完成 | - |
| 6 | 分支推送到 origin：cpp、cpp-ops、go-V2、python；rust 已存在且无新提交 | 完成 | 见下 |
| 7 | 镜像构建补全：Java/Go/C++/Rust Dockerfile + 选型说明 | 完成 | 868e23b |
| 8 | GHCR 推送：`_image.yml` + master/release 接入，sha/semver/latest | 完成 | 8b547ac |
| 9 | K8s 部署：deploy.yml（kubectl set image + rollout + imagePullSecret 校验） | 完成 | f43e6c1 |
| 10 | CD 实跑验证（需集群/凭据） | **未验证** | - |
| 11 | Actions 首轮失败静态修复（Mapper XML/golden、Kafka 镜像、CGO、extra-tag、基础镜像固定） | 完成 | 15e4ef1 / 465aeba |
| 12 | 修复后复跑 Actions | **完成**：master run 42491418177 / 42491455889 均 success | - |
| 13 | 分支对齐到 c7ef070 | cpp/cpp-ops/python/java-fix 完成；go 冲突未解 | 见下 |
| 14 | C++ cppcheck/Clang 修复 | 完成（未 CI 验证）：定向 suppress + Clang 定向 -Wno | db770e4 / 8f1a677 / 82520da |
| 15 | Go 53 漏洞治理 | **完成**：Go 1.26.10 + 依赖升级，govulncheck 0 可达 | 024d2f9 |
| 16 | PR / release / GHCR 实测 | **完成**：PR Gate success；release success；tag/Release 已清理 | 48705e7 / 42496000954 |
| 17 | openEuler 容器化（方案 A）+ 自托管切换说明（方案 B） | **完成**：run 42499755525 全绿（Java/Python gates+integration/Go 容器 job 真跑通） | 0191d95 |
| 18 | ARM64 openEuler 验证 | **搁置（用户决定）**：未落代码；TODO 见 docs/CI-OPENEULER.md §5 | - |

## 分支推送记录（2026-11-08）

> 远端默认分支已由用户在网页改为 **`master`**（`git ls-remote --symref origin HEAD` 已确认）。

| 语言 | 本地分支 | 本地/远端 SHA | 远端状态 |
| --- | --- | --- | --- |
| cpp | `car-monit-api-cpp` | `db770e48c932978ee1db850533e137a161635971` | 已 merge master + 删除 cpp-ci.yml + Clang 告警修复，已推送 |
| cpp | `car-monit-api-cpp-ops` | `8f1a6778c6e39e943739e9936d3ef059c6787a9f` | 同上 |
| go | `car-monit-api-go-V2` | `ed6a28163b49c63c48dfcce7d5b482ddc9d6f485` | **merge 冲突未解**（config.yaml / config.verify.yaml / review 文档），未推送 |
| rust | `car-monit-api-rust` | `847441dddc7f3b25d7f8c9d4ba612559c91635b8` | 远端已存在且一致，旧快照 |
| python | `car-monit-api-python` | `c7ef07006c285462388283912c76a38739d8aa69` | 已快进到 c7ef070 并推送 |
| java-fix | `car-monit-api-java-fix` | `2062d28a6716181061b609b5830694b4dc0317d5` | 已 merge master（旧 ci.yml 自动删除）并推送 |

上述分支由 PAT 回读确认；master / pr / release 的实测结论见 `CI-CD-PIPELINES.md §12.5`。

## master 推送与默认分支（2026-11-08）

| 项 | 状态 |
| --- | --- |
| `origin/master` | `48705e713313b7044e60ed783fddaf8ea3d879b7`（含 Go 升级、C++ 检查补齐、release publish 修复） |
| 远端默认分支 | 已是 `master`（用户网页修改后回读确认） |
| Actions 触发 | 已确认：master / pr / release 均 success（详见 CI-CD-PIPELINES.md §12.5）；deploy 未运行 |
| `main` 分支 | 独立历史 `cdee15a Initial commit`（仅 README.md 2 行），非 master 祖先；**未删除**，建议改默认分支且 master CI 跑通后再删 |

## 待确认

1. **Rust 分支同步策略**：主工作区副本比远端分支新（117 个文件不同），需选择"逐文件审查后提交进分支"或"声明为历史快照"。**未执行同步，禁止静默覆盖**（详见 CI-CD-PIPELINES.md §11）。
2. GitHub 远端默认分支已是 `master`；仍需人工配置 `PR Gate` 必需检查。

## CD 决策（已确认）

- 镜像：GHCR `ghcr.io/kai-cn/<service>`，`GITHUB_TOKEN` + `packages: write`。
- 部署：K8s 既有 Deployment，`kubectl set image` + `rollout status`，`secrets.KUBE_CONFIG` + `vars.K8S_*`。
- 首次部署人工 bootstrap（namespace / Deployment / imagePullSecret），命令见方案文档 §10.2。

## 恢复时注意

- 推送策略：语言分支与 `master` 已按用户授权推送（非 force）；后续任何 push 仍以当前用户指令为准，默认不 force push。
- 不要在本机跑长构建或全量测试，只做 YAML 与静态自检（除非用户另行授权）。
- 删除任何构建产物/临时文件前先 `SetLength(0)` 截断，不进回收站。
- `_python.yml` 必须完整保留原 `ci.yml` 的所有门禁（覆盖率 65%、check_*、冒烟、集成、secret 扫描）。
