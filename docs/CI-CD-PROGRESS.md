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
| 5 | YAML 自检（PyYAML + actionlint 全绿）；GitHub 实跑未验证 | 完成 | - |

## 分支推送记录（2026-11-08）

> 远端默认分支实际为 `main`（`origin/HEAD -> main`），与用户口径 `master` 不一致；
> 需在 GitHub Settings 手动改默认分支，本机无凭据/无 gh CLI 无法修改。

| 语言 | 本地分支 | 本地 SHA | 远端状态 |
| --- | --- | --- | --- |
| cpp | `car-monit-api-cpp` | 63bb3c9 | 待推送（远端无） |
| cpp | `car-monit-api-cpp-ops` | 119e438 | 待推送（远端无，第二分支） |
| go | `car-monit-api-go-V2` | ed6a281 | 待推送（远端无） |
| rust | `car-monit-api-rust` | 847441d | **远端已存在且一致**，无需推送 |
| python | 无本地分支 | - | **阻塞**：无分支名可沿用，需决策 |

## 待用户确认（阻塞 CD）

1. 镜像推送目标：GHCR 还是私有 registry。
2. 部署目标：K8s / 单机 / 只出制品。

## 恢复时注意

- 不要 push；用户明确要求不推送。
- 不要在本机跑长构建或全量测试，只做 YAML 与静态自检。
- 删除任何构建产物/临时文件前先 `SetLength(0)` 截断，不进回收站。
- `_python.yml` 必须完整保留原 `ci.yml` 的所有门禁（覆盖率 65%、check_*、冒烟、集成、secret 扫描）。
