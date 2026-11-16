# 09 公开仓库安全加固记录（api）

> 日期：2026-11-16；决策：参数化 + GitHub Secrets + 用户外部轮换；暂不公开；保留自托管 runner 但加固流程。

## 1. 处置内容

### 凭据/地址参数化（工作树已无明文）
- `pro-business-api/src/main/resources/application.yml`、`car-monit-api-python/.../application.yml`：
  GaussDB URL/账号（${SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL/USERNAME}）、
  Redis 集群节点（${REDISCLUSTER_CLUSTERNODES}）、sysbaseUrl（${SYSBASE_URL}）改为环境变量注入，
  移除内网/公网 IP 与注释中的历史地址。
- `car-monit-api-go/configs/config.yaml`、`config.verify.yaml`：GaussDB URL、sysbase-url 改本地回环 + 环境变量说明。
- `car-monit-api-python/tools/check_secrets.py`：docstring 不再复述历史口令字面量（拆开拼接的检测规则保留）。
- `car-monit-api-go/docs/parity-2026-11-02/*.md`：实测记录中的公网 IP 脱敏为 `<REDACTED-HOST>`。

### Workflow 加固（自托管 runner 隔离）
- `self-hosted-ci.yml`：**删除 `push` 触发与 `runner`/AUTO_DEPLOY 输入**，仅保留 `workflow_dispatch`；
  build job 固定 `ubuntu-latest`；deploy job 增加 `github.repository_owner == 'kai-cn'` 守卫。
- `_java.yml`/`_cpp.yml`/`_go.yml`/`_python.yml`：移除 `vars.CI_RUNNER_LABELS` 自托管切换，固定云 runner。
- 全仓无 `pull_request_target` / `workflow_run`；PR 事件仅在 `pr.yml`，job 全为云 runner。

### GitHub Secrets（repo 级，已写入）
`CI_OPENGAUSS_PASSWORD`、`CI_INTERNAL_TOKEN`、`SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD`、`TRAFFIC_INTERNAL_TOKEN`。
内部令牌为会话级随机值；两侧（api/backend）CI_INTERNAL_TOKEN 已写入同一值，保证 internal-token 一致。

## 2. 上线前必须轮换（用户操作，值不写入本仓库/文档）
| 项 | 注入位置 | 说明 |
| --- | --- | --- |
| GaussDB/openGauss 口令 | `SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD` / `CI_OPENGAUSS_PASSWORD` | 轮换后同步更新 GitHub Secrets |
| 内部端点令牌 | `TRAFFIC_INTERNAL_TOKEN`（api）/ `CI_INTERNAL_TOKEN`（两仓一致） | 与 backend 保持一致 |
| TCP 生产地址 | 部署时注入，不入库 | — |

> git 历史未重写：所有已轮换凭据在旧提交中仍可读取。公开仓库相当于公开历史；
> 因此**轮换是公开的前提**，而非可选项。轮换后旧值即失效，历史残留不构成可利用风险。
>
> **暴露面实测（2026-11-16）**：本仓库几乎所有远端分支（`master`、`car-monit-api-jdk17/21/25`、
> `car-monit-api-cpp(-ops)`、`car-monit-api-go-V2`、`car-monit-api-python`、`car-monit-api-rust`、
> `feature/springboot3` 等）的当前 tip 仍含 `redis321` / `OpenGauss@123` / 公网 IP 明文（仅 `main` 干净）。
> 本次参数化只落在 `car-monit-api-java-V3` 工作分支。公开前**必须**完成上表全部轮换。

## 3. 复核
独立只读会话复核结论：**无阻断项，可 push 触发 CI**（详见会话记录）。
