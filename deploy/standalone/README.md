# car-monit-api 单机离线部署包

本包由 `.github/workflows/cd-standalone.yml` 构建，包含：

- `payloads/java/app.jar`：Spring Boot 可执行 jar
- `payloads/go/api`：Linux amd64 静态二进制（CGO 关闭）
- `payloads/python/`：Python 源码 + 离线 wheels（runtime 依赖）
- `payloads/rust/car-monit-api-rust` + `config/application.yaml`：Rust 二进制（car-monit-api-rust 分支构建）
- `payloads/cpp/car-monit-api` + `configs/config.yaml`：C++ 二进制（car-monit-api-cpp 分支构建，CM_WITH_KAFKA=ON）
- `systemd/car-monit-api-*.service`：systemd unit（Restart=always / RestartSec / WorkingDirectory / User / EnvironmentFile）
- `config/*.example`：**只有占位符**的配置模板
- `install.sh` / `uninstall.sh`
- `SHA256SUMS`

> Rust / C++ 完整源码不在 master：Rust 在 `car-monit-api-rust` 分支（Cargo.toml + Cargo.lock），
> C++ 在 `car-monit-api-cpp` 分支（CMakeLists.txt + 完整 src/tests）。`cd-standalone` 构建时用
> `actions/checkout(ref=...)` 分别拉到 `src-rust/` / `src-cpp/` 子目录构建后纳入本包，**不合并源码到 master**。
> 配置文件中开发态内网地址在打包时已替换为 `<DB_HOST>` 占位符。
> C# / Kotlin 目前仅有 `java-to-*-migration-prompt.md`（迁移提示文档），无源码，不纳入制品。

> 手动 dispatch 时 `service` 选项决定产出哪些语言；`service=all`（含 push 触发）会产出 java/go/python/rust/cpp 全部 5 种。

## 依赖（外部提供，本包不内置）

| 依赖 | 默认端口 | 说明 |
| --- | --- | --- |
| 数据库（GaussDB/PostgreSQL 协议） | 5432 | 配置模板中 `<DB_HOST>` 占位 |
| Redis | 6379 | `<REDIS_HOST>` |
| Elasticsearch | 9200 | `<ES_HOST>` |
| Kafka | 9092 | `<KAFKA_HOST>` |

服务监听端口：Java/Python/Go 均为 **9901**（来自仓库 `application.yml` / `configs/config.yaml`）。

## 安装

```bash
tar -xzf car-monit-api-standalone-*.tar.gz
cd car-monit-api-standalone

# 默认安装到 /opt、/var/log、/etc/systemd/system
sudo bash install.sh --service java

# 或只安装 Python（离线 venv）
sudo bash install.sh --service python

# 非 root 临时前缀（验证/演练）
bash install.sh --prefix "$PWD/opt" --log-dir "$PWD/log" --unit-dir "$PWD/units" \
  --service java --user "$(id -un)" --no-start
```

编辑 `$PREFIX/<service>/*.env` / `config.yaml` / `python.env`，填入真实依赖地址与口令（文件权限建议 600）。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now car-monit-api-java
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9901/health
```

## 卸载

```bash
sudo bash uninstall.sh --service java
# 非 root 临时前缀：
bash uninstall.sh --prefix "$PWD/opt" --log-dir "$PWD/log" --unit-dir "$PWD/units" \
  --service java --no-systemctl
```

## JVM 参数

仓库未提供生产固定 JVM 参数。`config/java.env.example` 中给出保守基线：

```
JAVA_OPTS=-Xms256m -Xmx512m
```

请按机器内存与 GC 目标调整；unit 通过 `EnvironmentFile` 读取。

## 说明

- 包内不含任何真实口令或内网地址。
- Python 生产必须 `CAR_MONIT_RUNTIME=prod`；缺少中间件时启动会失败并输出明确错误。
- Go/Python 的配置模板为最小占位结构，实际键名以仓库 `configs/config.yaml` / `application.yml` 为准。
