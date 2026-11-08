# 自托管 Runner 接入（WSL + openEuler 24.03 x64）

> 目标：在 Windows 宿主机的 WSL 发行版（openEuler 24.03 x64）上运行 GitHub Actions self-hosted runner。
> 本文只做准备，不注册 runner、不生成 token、不连接实际机器。label 统一为：
> `[self-hosted, linux, x64, wsl, openeuler]`

## 1. 前置条件（openEuler WSL 内）

```bash
# 基础工具
sudo dnf install -y git tar gzip curl ca-certificates libstdc++ findutils which
# 若 workflow 继续使用 container:，需要 Docker（WSL 内 Docker Engine 或 Docker Desktop 的 WSL 集成）
# 若直接在 WSL 主机跑语言 job，再装：
sudo dnf install -y java-1.8.0-openjdk-devel gcc gcc-c++ clang cmake ninja-build make \
  libpq-devel openssl-devel cppcheck
```

- openEuler 24.03 的 glibc 2.38，满足 GitHub runner 的最低 glibc 要求；CentOS 7 EOL / glibc 不兼容的旧前提**不再适用**。
- Go 1.26.10 / Python 3.12：openEuler 仓库不提供所需版本，使用 `actions/setup-go` / `actions/setup-python`（需 runner 出站联网），或提前手工安装到 PATH。
- Maven 3.9.9：openEuler 仓库只有 `maven-plugin`，按 CI 方式下载 Apache tarball。
- 若使用 `container: openeuler/openeuler:24.03-lts`，runner 用户必须在 `docker` 组（等价 root 风险，见 §4）。

## 2. systemd 是否启用（决定常驻方式）

WSL 默认可能未启用 systemd。检查：

```bash
systemctl is-system-running
```

若提示 systemd 未运行，在 WSL 内编辑 `/etc/wsl.conf`：

```ini
[boot]
systemd=true
```

然后在 Windows 侧执行 `wsl --shutdown`，重新进入发行版；再次 `systemctl is-system-running` 应返回 `running`（或 `degraded`）。

- **已启用 systemd**：用 `./svc.sh install/start` 把 runner 注册成系统服务。
- **未启用 systemd**：`svc.sh` 不可用，只能前台/后台运行 `run.sh`（见 §3.2）。

## 3. 注册与常驻

### 3.1 下载与注册（在有 systemd 的情况下）

```bash
sudo useradd --system --create-home --shell /bin/bash gh-runner || true
sudo -u gh-runner -H bash <<'EOF'
set -euo pipefail
mkdir -p /home/gh-runner/actions-runner && cd /home/gh-runner/actions-runner
curl -fsSL -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v<runner-version>/actions-runner-linux-x64-<runner-version>.tar.gz"
tar xzf runner.tar.gz
./config.sh \
  --url https://github.com/kai-cn/car-monit-api \
  --token <RUNNER_TOKEN> \
  --name wsl-openeuler-01 \
  --labels self-hosted,linux,x64,wsl,openeuler \
  --work /home/gh-runner/actions-runner/_work
EOF

# systemd 常驻（svc.sh 需要在 runner 目录执行）
cd /home/gh-runner/actions-runner
sudo ./svc.sh install gh-runner
sudo ./svc.sh start
sudo ./svc.sh status
```

> `<RUNNER_TOKEN>` 只能从 GitHub 仓库 Settings → Actions → Runners → New self-hosted runner 获取；**本任务不生成、不填写真实 token**。

### 3.2 WSL 不随 Windows 启动的问题

WSL 实例不会在 Windows 重启后自动启动，runner 会离线。可选做法：

1. **Windows 计划任务（推荐）**：登录时触发：
   ```powershell
   schtasks /Create /TN "GitHubRunner-WSL-openEuler" /SC ONLOGON /RL LIMITED `
     /TR "wsl.exe -d <WSL发行版名> -u gh-runner --exec /home/gh-runner/actions-runner/run.sh"
   ```
   - `<WSL发行版名>` 用 `wsl -l -v` 查看。
   - 计划任务只负责拉起 WSL；runner 本身仍以非 root 的 `gh-runner` 运行。
2. **手动**：每次重启后执行 `wsl -d <发行版> -u gh-runner --exec /home/gh-runner/actions-runner/run.sh`，放到 tmux/screen。
3. **systemd 已启用**：可在 WSL 内 `systemctl enable` runner 服务，但 WSL 实例本身仍需要被 Windows 侧拉起。

## 4. 运行用户与权限

- **推荐非 root**：`gh-runner` 专用用户。CI 任务可能执行任意代码，root 会放大对 WSL 文件系统、`/mnt/c` Windows 挂载与凭据的破坏面。
- 需要 `container:` 或镜像构建时，把用户加入 `docker` 组；这等价于 root 权限，必须在文档/评审中显式接受该风险。
- 部署 job 需要安装到 `/opt`、`/var/log`、`/etc/systemd/system`，可给该用户**限定命令的 NOPASSWD sudo**（仅 `install.sh`/`systemctl`/`uninstall.sh`），不要无限制 sudo。
- runner 工作目录 `_work` 不要放在 `/mnt/c`（跨文件系统权限/换行/性能问题），放 WSL 原生磁盘。

## 5. WSL2 网络

- 出站（拉镜像、下载制品、访问 GitHub）默认可用。
- **入站默认不可达**（NAT）：别人要访问部署在 WSL 里的服务时：
  1. 端口转发（Windows 管理员）：
     ```powershell
     # 在 WSL 内用 hostname -I 获取 IP
     netsh interface portproxy add v4tov4 listenport=9901 listenaddress=0.0.0.0 `
       connectport=9901 connectaddress=<WSL_IP>
     New-NetFirewallRule -DisplayName "car-monit-api-9901" -Direction Inbound -LocalPort 9901 -Protocol TCP -Action Allow
     ```
     WSL IP 重启会变化，需要重新执行（或用脚本刷新）。
  2. Windows 11 22H2+ 可在 `%USERPROFILE%\.wslconfig` 启用 mirrored networking：
     ```ini
     [wsl2]
     networkingMode=mirrored
     ```
     然后 `wsl --shutdown`；WSL 共享宿主 IP，入站可达（部分 VPN/网络环境不兼容）。
- 仅作为 GitHub runner 使用时，出站即可，不需要入站。

## 6. 建议放在自托管 runner 的 job

- 适合：Java/Go/Python/C++ Linux 全量构建与测试、container 内欧拉 job、离线/内网依赖验证。
- 不适合/需另议：Windows MSVC（仍需 windows-latest）、K8s deploy（需集群凭据与网络）、依赖公网大带宽的镜像构建（WSL 宿主资源与网络可能受限）。

## 7. 启用方式

1. 按 §3 注册 runner，label 必须是 `self-hosted,linux,x64,wsl,openeuler`。
2. 仓库 Variables 设置 `CI_RUNNER_LABELS=["self-hosted","linux","x64","wsl","openeuler"]`，所有 Linux job 的 `runs-on` 会切换（Windows job 固定 `windows-latest` 不受影响）。
3. 单机部署 workflow `deploy-selfhosted.yml` 默认关闭；手动触发时把 `confirm` 设为 true 才会执行。
