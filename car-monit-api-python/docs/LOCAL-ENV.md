# 本机环境与集成测试 Runbook / Local Environment

> 记录日期：2026-11-08（实测快照，后续每次实跑前重新测量）
> 适用目录：`car-monit-api-python`

---

## 0. 实测快照（先看这一节）

| 项 | 实测值 | 判定 |
|---|---|---|
| C 盘可用 | **10.99 GB** | 已恢复（清理回收站后），高于 5 GB 阈值 |
| D 盘可用 | **38.84 GB** | 已恢复（清理回收站后），高于 8 GB 阈值 |
| `D:\pagefile.sys` | 25,075 MB（用户已要求改为 8 GB 固定，**重启后生效**） | 重启前仍占约 25 GB |
| 本机 Docker CLI | **未安装/不在 PATH**（`docker --version` 失败） | 本地 compose 暂不可用 |
| 端口 6379（Redis） | UP | 已有实例，不要重复启动 |
| 端口 9200（ES） | DOWN | 仅在需要 ES 集成测试时启动，并显式限制 `ES_JAVA_OPTS` |
| 端口 9092（Kafka） | 状态不稳定（曾观测 UP，复测 DOWN） | **以 `run_integration.ps1` 实时探测为准**；已在跑就不要重复启动 |
| `192.168.56.10:22`（Linux VM） | 当时未连通 | 需要时先确认虚拟机已开机 |

> 端口/磁盘都会随其他会话变化；每次实跑前先执行 `scripts/run_integration.ps1`，
> 它会在启动任何容器前重新实测并打印上述信息。

**硬规则（与用户指令一致，仍保留）**：D 盘可用 < 8 GB 或 C 盘可用 < 5 GB 时，
**不启动任何容器**（ES/Kafka 镜像与数据目录会直接写满磁盘，并拖垮本机其他会话）。
当前空间已恢复，但仍建议每次跑前用 `scripts/run_integration.ps1` 重新实测。

---

## 1. Java 服务启动约定

- `car-monit-api` 的 Java 服务连 **openGauss**。
- `car-monit-backend-new` 的 Java 服务连 **MySQL 8**。
- 启动必须显式限制 JVM 内存（`-Xmx` / `-Xms`），**禁止使用默认值**。
- 启动前先探测端口/进程；Java 服务已在跑就不要重复启动。
- Windows 本机最多同时运行 **一个 backend Java 服务 + 一个 api Java 服务**。

> 本仓库的 Python 服务（`python run.py`）不属于上述“Java 服务”，但同样注意端口占用：
> 默认 9901，可用 `CAR_MONIT_PORT` 覆盖。

---

## 2. 基础设施清单

### Linux 虚拟机
- `192.168.56.10`，SSH 端口 22，CentOS 7，账号/密码 `root/root`。
- 已具备 Docker；openGauss 容器在跑，如果不在可自行启动。

### WSL
- openEuler 24（24.03 LTS SP4，WSL2，2 GB / 2 核）。

### JDK
- `D:\jdk`，含 8、21、25 多版本。

### Windows 本机中间件
| 组件 | 路径 | 备注 |
|---|---|---|
| MySQL 8 | `D:\work\mysql-8.0.30-winx64`，`root/root` | 已监听（本机 mysqld 进程） |
| Redis 8 | `D:\work\Redis-8.10.2-Windows-x64-msys2` | 端口 6379 已监听 |
| Elasticsearch | `D:\work\elasticsearch-7.15.2` | 启动前必须限制堆内存；当前磁盘不足，禁止启动 |
| Kafka | `D:\work\kafka_2.13-4.0.0` | 端口 9092 已监听 |

---

## 3. 集成测试 Runbook（只差一条命令）

### 3.1 目标与文件

| 文件 | 作用 |
|---|---|
| `docker-compose.integration.yml` | Redis 7 / ES 7.17.13 / Kafka 3.7（与 CI 镜像一致），带内存上限、健康检查、数据目录外置 |
| `scripts/run_integration.ps1` | 磁盘门禁 → 端口探测 → 按需启动 compose → 就绪等待 → 跑 `tests/business -m integration` |
| `tests/business/test_integration_{redis,es,kafka,db}.py` | 真实中间件集成用例（默认 skip，需要 `CAR_MONIT_TEST_*` 开关） |

### 3.2 前置条件（全部满足才可实跑）

1. **磁盘**：C 盘 ≥ 5 GB 且 D 盘 ≥ 8 GB；或 `CAR_MONIT_IT_DATA_DIR` 指向一个剩余 ≥ 8 GB 的卷。
2. **Docker**：本机有 Docker CLI（当前没有），或在 Linux VM `192.168.56.10` 上执行 compose。
3. **端口**：本机 6379/9092 已被现有 Redis/Kafka 占用——二选一：
   - 复用现有 Redis/Kafka，只起 ES（`docker compose up -d elasticsearch`）；
   - 或给 compose 换宿主端口：`CAR_MONIT_IT_REDIS_PORT=16379`、`CAR_MONIT_IT_KAFKA_PORT=19092`，
     并同步把测试 URL 指到新端口（Kafka 的 advertised listener 也随该变量变化）。
4. **数据目录**：必须显式设置 `CAR_MONIT_IT_DATA_DIR`（不要把数据写进已满的 D 盘默认路径）。

### 3.3 一条命令（本机 Docker Desktop 可用时）

```powershell
cd d:\work\IdeaProjects\car-monit-api\car-monit-api-python
$env:CAR_MONIT_IT_DATA_DIR = "E:\car-monit-it-data"   # 改成 ≥8GB 可用的卷
powershell -ExecutionPolicy Bypass -File scripts\run_integration.ps1 -DataDir $env:CAR_MONIT_IT_DATA_DIR
```

脚本会按顺序执行：

1. 实测 C/D 可用空间；低于阈值直接退出（**不碰 Docker**）；
2. 探测 `6379 / 9200 / 9092`：三个都通 → 跳过启动，直接跑测试；
3. 三个都不通 → 校验数据目录后 `docker compose up -d`；
4. 等待就绪（Redis PING、ES cluster health=yellow、Kafka 端口/broker 可列 topic）；
5. 设置与 CI 相同的环境变量跑 pytest；
6. 结束时 `docker compose down`（**不加 `-v`，不删数据卷**）；`-KeepUp` 可保留容器。

### 3.4 Linux VM 方式（本机无 Docker 时）

在 VM 上：

```bash
cd /path/to/car-monit-api-python
export CAR_MONIT_IT_DATA_DIR=/data/car-monit-it-data
docker compose -f docker-compose.integration.yml up -d
docker compose -f docker-compose.integration.yml ps
```

在 Windows 上跑测试（URL 指向 VM）：

```powershell
cd d:\work\IdeaProjects\car-monit-api\car-monit-api-python
$env:CAR_MONIT_TEST_REDIS="1"; $env:CAR_MONIT_REDIS_URL="redis://192.168.56.10:6379/0"
$env:CAR_MONIT_TEST_ES="1";    $env:CAR_MONIT_ES_URL="http://192.168.56.10:9200"
$env:CAR_MONIT_TEST_KAFKA="1"; $env:CAR_MONIT_KAFKA_URL="192.168.56.10:9092"
.venv\Scripts\python.exe -m pytest tests\business -m integration -q
```

### 3.5 环境变量（与 CI 完全一致）

| 变量 | 值 |
|---|---|
| `CAR_MONIT_TEST_REDIS` | `1` |
| `CAR_MONIT_REDIS_URL` | `redis://127.0.0.1:6379/0`（VM 方式改 IP） |
| `CAR_MONIT_TEST_ES` | `1` |
| `CAR_MONIT_ES_URL` | `http://127.0.0.1:9200`（VM 方式改 IP） |
| `CAR_MONIT_TEST_KAFKA` | `1` |
| `CAR_MONIT_KAFKA_URL` | `127.0.0.1:9092`（VM 方式改 IP） |
| `CAR_MONIT_TEST_DB` | 默认不设（真实 GaussDB 集成测试需另行确认；CI 也不跑） |

### 3.6 当前还差什么（阻塞项）

1. **磁盘**：C 4.34 GB / D 0.12 GB（重启前实测），未达到 5 GB / 8 GB 阈值。
2. **页面文件**：`D:\pagefile.sys` 25,075 MB，需用户重启让 8 GB 固定设置生效（本会话不得修改）。
3. **Windows Docker CLI 缺失**：本地 compose 无法启动；需安装 Docker Desktop，或改用 Linux VM。
4. **Linux VM 当时不可达**（22 端口不通）：需先确认虚拟机开机与网络。
5. **ES 未运行**（9200 不通），且当前不允许启动。

> 满足以上 1–4 后，执行 §3.3 的一条命令即可实跑；在此之前不做任何容器启动。

---

## 4. CI integration job 与本地 compose 对齐

| 项 | CI（`.github/workflows/ci.yml`） | 本地 `docker-compose.integration.yml` |
|---|---|---|
| Redis | `redis:7`，6379 | `redis:7`，6379（可用 `CAR_MONIT_IT_REDIS_PORT` 改） |
| Elasticsearch | `elasticsearch:7.17.13`，single-node，security=false | 同镜像、同模式，`ES_JAVA_OPTS=-Xms512m -Xmx512m` |
| Kafka | `bitnami/kafka:3.7`，KRaft，9092 | 同镜像、同 KRaft 环境变量，`KAFKA_HEAP_OPTS=-Xms256m -Xmx256m` |
| 测试命令 | `python -m pytest tests/business -m integration -q` | 同 |
| 开关/URL | `CAR_MONIT_TEST_*` + `CAR_MONIT_*_URL` | 同（脚本自动注入） |
| 失败语义 | 门禁失败（已移除 `continue-on-error`） | 脚本返回 pytest 退出码 |

---

## 5. 测试库与删除约定（硬约束）

### 5.1 测试库

- **禁止**在另外的 data 目录另起一个 MySQL 8 实例。
- 需要全新测试库时，直接在现有实例上操作：
  `D:\work\mysql-8.0.30-winx64`，端口 **3307**，账号/密码 `root/root`。
- 用 `CREATE DATABASE` 建库，用完 `DROP DATABASE` 删除。

### 5.2 删除必须"结果导向"验证

测试数据、构建产物、日志、临时文件一律**直接删除，不得放入回收站**。
本机存在"命令返回成功、实际被转进回收站、磁盘没释放"的拦截问题。

**实测教训（2026-08）**：`Remove-Item` 删除 `car-monit-api-rust\target`（4.77 GB）
被转进回收站，D 盘实际释放 **0 GB**；`Clear-RecycleBin` 也被转回，条目反而增加。
**因此不得假设任何命令"一定不会进回收站"。**

删除流程（强制）：

1. 删除前记录：`Get-PSDrive D`（或目标所在卷）的 `Free` 字节数 + `Test-Path 目标`。
2. **先截断再删空壳（实测唯一能立即释放空间的方式）**：
   - 文件：`SetLength(0)` 把内容截断成 0 字节；
   - 目录：逐个文件截断（或直接写 0 字节）后再删空目录；
   - 最后再 `Remove-Item` / `rd` 删除空壳；即使空壳进了回收站，内容空间已释放。
3. 删除后再次记录 `Get-PSDrive` 的 `Free` 字节数 + `Test-Path 目标`。
4. **判定标准**：目标路径确实消失（`Test-Path` = False）**且**可用字节确实增加。
   - 可用字节没涨 = 只是"搬家"（进了回收站），必须换绕过方式重试；
   - 报告中必须如实写明实际释放了多少字节（不能只写"已删除"）。

示例（PowerShell）：

```powershell
$before = (Get-PSDrive D).Free
$target = "D:\work\IdeaProjects\car-monit-api\car-monit-api-rust\target"
Get-ChildItem $target -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $fs = [IO.File]::Open($_.FullName, 'Open', 'ReadWrite')
    $fs.SetLength(0)
    $fs.Close()
}
Remove-Item $target -Recurse -Force
$after = (Get-PSDrive D).Free
"freed: {0:N2} GB; gone: {1}" -f (($after - $before) / 1GB), (-not (Test-Path $target))
```

> 若 `freed` 接近 0 或为负，说明删除仍被拦截/转入回收站，**不得当作已完成**。

---

## 6. 禁止事项（用户明确约束）

- 不为跑起来删除用户数据、清空回收站、修改页面文件。
- 磁盘低于阈值时，不启动任何容器、不拉镜像、不启动本地 ES/Kafka。
- Java 服务已在跑时不重复启动；Windows 本机最多一个 backend + 一个 api Java 服务。
