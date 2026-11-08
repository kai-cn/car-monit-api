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

## 分支推送记录（2026-11-08）

> 远端默认分支实际为 `main`（`origin/HEAD -> main`），与用户口径 `master` 不一致；
> 需在 GitHub Settings 手动改默认分支，本机无凭据/无 gh CLI 无法修改。

| 语言 | 本地分支 | 本地/远端 SHA | 远端状态 |
| --- | --- | --- | --- |
| cpp | `car-monit-api-cpp` | 63bb3c9e8ad4ab4a8663a403ce814880643f4b34 | 已推送（新建，非 force） |
| cpp | `car-monit-api-cpp-ops` | 119e438aaa47ecd6ca80b8dc62d1d51a8372ea28 | 已推送（新建，非 force） |
| go | `car-monit-api-go-V2` | ed6a28163b49c63c48dfcce7d5b482ddc9d6f485 | 已推送（新建，非 force） |
| rust | `car-monit-api-rust` | 847441dddc7f3b25d7f8c9d4ba612559c91635b8 | 远端已存在且一致，**无需推送** |
| python | `car-monit-api-python` | 6fff93ccbd37f006bc8a4b98fff6641729561f7c | 已推送（从 master 新建，基于当时 master tip；master 后续已另行推送） |

gh CLI 不可用 → **已推送，未验证 Actions 是否触发**。

## master 推送与默认分支（2026-11-08）

| 项 | 状态 |
| --- | --- |
| `origin/master` | `5c8b89a67d46c92ef05e1d7e6a9c95be7e38ce51`（快进，非 force，领先 10 提交、落后 0） |
| 远端默认分支 | 仍是 `main`；`gh` 未安装、`GH_TOKEN`/`GITHUB_TOKEN` 为空、未认证 API 404（私有仓库）→ 需人工在 `settings/branches` 改为 `master` |
| Actions 触发 | 无凭据读 `actions/runs`（404），**未确认** |
| `main` 分支 | 独立历史 `cdee15a Initial commit`（仅 README.md 2 行），非 master 祖先；**未删除**，建议改默认分支且 master CI 跑通后再删 |

## 待确认

1. **Rust 分支同步策略**：主工作区副本比远端分支新（117 个文件不同），需选择"逐文件审查后提交进分支"或"声明为历史快照"。**未执行同步，禁止静默覆盖**（详见 CI-CD-PIPELINES.md §11）。
2. GitHub 远端默认分支仍为 `main`，需人工改为 `master` 并配置 `PR Gate` 必需检查。

## CD 决策（已确认）

- 镜像：GHCR `ghcr.io/kai-cn/<service>`，`GITHUB_TOKEN` + `packages: write`。
- 部署：K8s 既有 Deployment，`kubectl set image` + `rollout status`，`secrets.KUBE_CONFIG` + `vars.K8S_*`。
- 首次部署人工 bootstrap（namespace / Deployment / imagePullSecret），命令见方案文档 §10.2。

## 恢复时注意

- 推送策略：语言分支与 `master` 已按用户授权推送（非 force）；后续任何 push 仍以当前用户指令为准，默认不 force push。
- 不要在本机跑长构建或全量测试，只做 YAML 与静态自检（除非用户另行授权）。
- 删除任何构建产物/临时文件前先 `SetLength(0)` 截断，不进回收站。
- `_python.yml` 必须完整保留原 `ci.yml` 的所有门禁（覆盖率 65%、check_*、冒烟、集成、secret 扫描）。
