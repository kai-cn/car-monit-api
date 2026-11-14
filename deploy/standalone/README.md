# car-monit-api 单机离线部署包

本包由 `.github/workflows/cd-standalone.yml` 构建，包含：

- `payloads/java/app.jar`：Spring Boot 可执行 jar
- `payloads/go/api`：Linux amd64 静态二进制（CGO 关闭）
- `payloads/python/`：Python 源码 + 离线 wheels（runtime 依赖）
- `systemd/car-monit-api-*.service`：systemd unit（Restart=always / RestartSec / WorkingDirectory / User / EnvironmentFile）
- `config/*.example`：**只有占位符**的配置模板
- `install.sh` / `uninstall.sh`
- `SHA256SUMS`

> Rust 产物：当前 master 的 `car-monit-api-rust/` 被 `.gitignore` 忽略、未入库，因此本包不包含 Rust 二进制；需要时先把 rust 目录入库。

## 依赖（外部提供，本包不内置）

| 依赖 | 默认端口 | 说明 |
| --- | --- | --- |
| 数据库（GaussDB/PostgreSQL 协议） | 5432 | 配置模板中 `<DB_HOST>` 占位 |
| Redis | 6379 | `<REDIS_HOST>` |
| Elasticsearch | 9200 | `<ES_HOST>` |
| Kafka | 9092 | `<KAFKA_HOST>` |

服务监听端口：Java 为 **9902**（`pro-business-api/src/main/resources/application.yml` 的 `server.port`，
也是 `docker/java.Dockerfile` 的 `EXPOSE`）；Python / Go / C++ / Rust 实现为 **9901**（各自 `configs/config.yaml` / Dockerfile）。

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
# Java 服务端口为 9902（Python/Go/C++/Rust 为 9901）；未引入 actuator，用内部端点做连通性探测
# 未带令牌预期 403，带 X-Internal-Token 预期 200，两者都说明服务已监听
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9902/api/v3/es/readiness
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
JAVA_OPTS=-Xms256m -Xmx512m --add-opens=java.base/java.lang=ALL-UNNAMED
```

请按机器内存与 GC 目标调整；unit 通过 `EnvironmentFile` 读取。

## 说明

- 包内不含任何真实口令或内网地址。
- Python 生产必须 `CAR_MONIT_RUNTIME=prod`；缺少中间件时启动会失败并输出明确错误。
- Go/Python 的配置模板为最小占位结构，实际键名以仓库 `configs/config.yaml` / `application.yml` 为准。

> --add-opens=java.base/java.lang=ALL-UNNAMED is REQUIRED by Orika 1.5.4 on JDK 17+;
> removing it makes startup fail with InaccessibleObjectException. See docs/v3/springboot4-migration.md.
