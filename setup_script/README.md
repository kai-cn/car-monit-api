# setup_script — 云端一键环境安装 / cloud provisioning

把"能让本仓库代码在云端跑起来"所需的全部启动必须项一次装好、配好、验通。

- 适用：Ubuntu 20.04 / 22.04 / 24.04、Debian 11 / 12（x86_64），
  以及 RHEL 系（dnf / yum）的尽力兼容分支。
- 权限：需要 root（脚本会在非 root 时自动 `sudo` 重跑自身）。
- 网络：需要能访问系统软件源、`apt.postgresql.org`、`packages.adoptium.net`、
  和 Maven 镜像（仓库根 `pom.xml` 里已配好 `https://maven.aliyun.com/repository/public`）。

---

## 1. 装了什么

| # | 组件 | 版本 | 为什么需要 |
|---|------|------|-----------|
| 1 | 基础工具 | curl / gnupg / git / tar / procps / lsb-release | 加仓库、解包、查进程 |
| 2 | JDK | Temurin 8（回退 `openjdk-8-jdk`） | 仓库根 `pom.xml`：`<java.version>1.8</java.version>` |
| 3 | Maven | 发行版自带 | 多模块构建 `pro-api` + `pro-business-api` |
| 4 | Python | 3.12（distro 包 → deadsnakes → uv） | `car-monit-api-python/pyproject.toml` 要求 `>=3.12` |
| 5 | PostgreSQL | 16（PGDG 官方仓库） | GaussDB 的线协议等价替代，见 §2 |
| 6 | Redis | 发行版自带（7.x） | `application.yml` 的 `spring.redis` |
| 7 | Python venv + 依赖 | 见 `requirements.txt` | FastAPI / SQLAlchemy / psycopg / orjson |

数据库侧还会自动完成：

- 创建角色 `gaussdb`、数据库 `"RuoYi"`（**大小写敏感，必须带引号**）
- 安装扩展 `pg_trgm`、`btree_gin`（`index_optimization.sql` 需要，必须超级用户）
- 创建 schema `jl_data01 AUTHORIZATION gaussdb`
- 执行仓库自带的 DDL（见 §2 的限制）
- 给角色设置 `search_path = jl_data01, public`

---

## 2. 三个必须先知道的限制

**① 仓库里只有 3 张核心表的建表语句。**

`pro-business-api/src/main/resources/sql/partition_scheme.sql` 里有
`ods_rt_szdn_snapshot_flow_addcode`、`ods_lwzxsfsj_fee_records_01`、
`zdata_trail_fitting` 三张表的 DDL，`progressive_architecture_indexes.sql`
里是三张归档表。

Mapper XML 里还引用了 `zdata_trail_tracks`、`zdata_trail_unfitting`、
`ods_szdn_toll`、`ods_szdn_service`、`zdata_location_dict`、
`ods_szdn_route_stationcapture_addcode`、
`ods_szdn_province_border_vehicle_weight_newstructure` 等表，**这些表的
DDL 不在本仓库**（属于既有数仓）。本脚本装出来的是"服务能启动、能连库、
核心接口能跑通"的环境，不是"带 8 亿行真实数据"的环境。
调用这些表的接口会返回 500，属于预期行为，与代码正确性无关。

**② GaussDB 用 PostgreSQL 16 替代，不是同一个数据库产品。**

GaussDB 没有公开的云端安装包。仓库自己的 `partition_scheme.sql` 头注释写的是
"PostgreSQL 11+"，语法也是标准的 PostgreSQL 分区 DDL，所以用 PG 16 承载。
Python 侧还专门打了两个补丁来抹平 GaussDB 与 PG 的差异
（`app/db/engine.py` 的 `install_gaussdb_version_shim` 和
`_install_pgjdbc_string_dumper`），说明迁移时已经考虑过这件事。

**③ 中间件没有装。**

Java 侧的 `pom.xml` 引了 Kafka、Pulsar、RocketMQ、RabbitMQ、Elasticsearch、
Flink，但按你选的范围，本脚本只装 **数据库 + Redis**。后果是：

- 需要连接这些中间件的消费者/生产者，在 Java 侧启动时会报连接失败；
  这些代码路径的"行为等价"只能在 Python 侧验证（Python 侧是进程内替身）。
- 如果你后面要完整跑 Java 侧的全链路，需要额外补 Kafka / Pulsar 等，
  这不在本脚本范围内。

---

## 3. 快速开始

```bash
# 进入仓库根目录
cd car-monit-api

# 一条命令装完（默认也会 mvn package，5~15 分钟）
sudo bash setup_script/setup.sh

# 想先跳过 Java 构建，快速把 Python 侧跑起来
sudo bash setup_script/setup.sh --no-build-java
```

跑完直接启动：

```bash
bash setup_script/start-python.sh      # FastAPI 移植版，端口 9901
curl http://127.0.0.1:9901/health

bash setup_script/start-java.sh        # 原始 Spring Boot 版，端口 9901
```

> 两个启动脚本都会先 `source setup_script/.env.runtime`，把数据库地址/账号/
> 密码注入为 Spring 风格的环境变量。**不要直接 `python run.py` 或
> `java -jar`**，否则会用上 `application.yml` 里写死的 `192.168.56.10`。

---

## 4. 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--db-password <pw>` | *(必须显式提供)* | 数据库密码，同时同步到 Java 与 Python 两侧；禁止写入仓库默认值 |
| `--db-host <host>` | `127.0.0.1` | 数据库地址 |
| `--db-port <port>` | `5432` | 数据库端口 |
| `--db-name <name>` | `RuoYi` | 库名（大小写敏感） |
| `--db-user <name>` | `gaussdb` | 角色名 |
| `--redis-password <pw>` | 空（无密码） | Redis 密码 |
| `--pg-version <n>` | `16` | PostgreSQL 大版本 |
| `--skip-java` | — | 不装 JDK / Maven，也不构建 |
| `--skip-python` | — | 不装 Python 运行时与 venv |
| `--skip-db` | — | 不装 PostgreSQL，也不初始化库 |
| `--skip-redis` | — | 不装 Redis |
| `--skip-schema` | — | 不执行仓库里的 DDL |
| `--no-build-java` | — | 不执行 `mvn package` |
| `--no-verify` | — | 跳过最后的自检 |
| `-h`, `--help` | — | 显示帮助 |

默认值全部来自仓库实际配置，**零参数就能起来**：

| 配置项 | 出处 |
|--------|------|
| `jdbc:postgresql://192.168.56.10:5432/RuoYi` | `pro-business-api/src/main/resources/application.yml` |
| `username: gaussdb` / `password: ${DB_PASSWORD}` | 同上（口令经环境变量注入） |
| `spring.redis.host=127.0.0.1` `port=6379` `database=0` | 同上 |
| Redis 无密码 | 真实口令经 `SPRING_REDIS_PASSWORD` 注入，仓库不保留明文 |

脚本只把 `192.168.56.10` 换成了本机 `127.0.0.1`（云端没有那个网段的虚机），
其余凭据一字不改。

---

## 5. 产物

| 文件 | 说明 |
|------|------|
| `setup_script/.env.runtime` | 环境变量，权限 `600`，含数据库明文密码 |
| `setup_script/start-python.sh` | 启动 Python 侧（已 `chmod +x`） |
| `setup_script/start-java.sh` | 启动 Java 侧（已 `chmod +x`），自动挑 `target/pro-business-api-*.jar` |
| `setup_script/setup.log` | 本次安装完整日志 |
| `setup_script/smoke-python.log` | Python 启动自检输出 |
| `car-monit-api-python/.venv/` | Python 虚拟环境 |
| `pro-business-api/target/*.jar` | Maven 构建产物（除非 `--no-build-java`） |

前三个文件已被 `setup_script/.gitignore` 排除，**不要提交**（里面有密码）。

---

## 6. 执行阶段

脚本按 10 步走，每步都会打印 `=== N/8 标题 ===`，失败时打印出错行号：

| 步骤 | 内容 | 可以跳过 |
|------|------|---------|
| 1 | 基础工具 | — |
| 2 | JDK 8 + Maven，落盘 `JAVA_HOME` | `--skip-java` |
| 3 | Python 3.12（装不到就退回 uv） | `--skip-python` |
| 4 | PostgreSQL 安装 + 启动（`pg_ctlcluster` → `systemctl` → `pg_ctl` 三级回退，云端容器通常没有 systemd） | `--skip-db` |
| 5 | Redis 安装 + 密码 + 启动 + PING | `--skip-redis` |
| 6 | 角色 / 库 / 扩展 / schema / 仓库 DDL | `--skip-db` / `--skip-schema` |
| 7 | venv + `pip install -r requirements.txt` | `--skip-python` |
| 8 | 生成 `.env.runtime` + 两个启动脚本 | — |
| 9 | `mvn -B -q -DskipTests package` | `--no-build-java`（失败只告警，不影响 Python） |
| 10 | 自检：版本 / 数据库连通 / 核心表存在 / Redis PING / `scripts/smoke_test.py` | `--no-verify` |

第 10 步的 `smoke_test.py` 是**进程内**自检（不启 HTTP 服务），跑通
即代表 Python 侧的 28 项接口契约断言全部成立。

---

## 7. 幂等

可以反复执行：

- apt 已装的包会跳过；已存在的角色 / 库 / schema 不会重建，只同步密码；
- 所有 DDL 都是 `IF NOT EXISTS`；
- PostgreSQL 已在监听就直接复用；
- Redis 端口上已有实例（返回 `PONG` 或 `NOAUTH` 都算"活着"）就复用，
  不会再启动一次导致"端口被占用"。

唯一会累积的是 `setup.log`（追加写）。

---

## 8. 怎么确认装好了

```bash
# 1) 版本
java -version            # 期望 1.8.0_xxx
mvn -v                   # 期望 Java version: 1.8
python3.12 --version

# 2) 数据库
PGPASSWORD="${DB_PASSWORD:?}" psql -h 127.0.0.1 -U gaussdb -d RuoYi \
  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='jl_data01'"
# 期望核心 3 表 + 归档 3 表 + kafka_message_record 共 7 张

# 3) Redis
redis-cli ping           # 无密码时 PONG

# 4) Python 侧
bash setup_script/start-python.sh &
curl -s http://127.0.0.1:9901/health | head -c 400
bash car-monit-api-python/scripts/smoke_test.py --live http://127.0.0.1:9901
```

`/health` 期望返回里能看到顶层 `config` 和 `components.db.status = "UP"`。

---

## 9. 一次跑两侧做 1:1 对比

云端同一台机器上可以同时跑 Java 与 Python 两个版本，各自换端口：

```bash
bash setup_script/start-java.sh   --server.port=9902
bash setup_script/start-python.sh            # 9901

curl -s http://127.0.0.1:9901/health          > py.json
curl -s http://127.0.0.1:9902/health          > java.json
diff py.json java.json
```

`start-*.sh` 会把多余参数原样透传给 `run.py` / `java -jar`，所以换端口不需要改脚本。

---

## 10. 故障排查

| 现象 | 原因 / 处理 |
|------|-------------|
| `JDK 8 安装失败` | 发行版仓库没有 Java 8，且 Adoptium 不可达。检查能否访问 `packages.adoptium.net`，或手动装 JDK 8 后重跑 |
| `PostgreSQL 启动超时` | 容器里没有 systemd，用 `pg_ctlcluster 16 main start` 看报错；`/var/log/postgresql/` 有日志 |
| `创建 schema 失败：请检查密码与 pg_hba.conf` | `pg_hba.conf` 里 `host all all 127.0.0.1/32` 不是 `scram-sha-256` / `md5`，改成密码认证 |
| `扩展 pg_trgm 安装失败` | `postgresql-contrib-16` 没装上；扩展必须超级用户创建，脚本已用 `su postgres` |
| `Python 依赖安装失败` | 网络到 PyPI 不通；换国内源后重跑（`pip config set global.index-url ...`） |
| `Java 构建失败` | **只告警不中断**。看 `mvn` 输出；常见原因是依赖下载不全，重跑 `cd . && mvn -DskipTests package` |
| Maven 编译报 `source option 8 is no longer supported` | `JAVA_HOME` 指向了高版本 JDK。`source setup_script/.env.runtime` 后再构建 |
| 接口 500 且日志是 `relation "jl_data01.xxx" does not exist` | 该表不在仓库 DDL 里，见 §2 ① |
| 接口 500 且日志是 `Invalid bound statement (not found)` | Mapper XML 里声明了但 XML 没有对应 `<select>`，这是**原项目既有缺陷**（共 6 个方法），Python 侧刻意保留同样行为，见 `COMPATIBILITY.md` §4 |

完整的 Java ↔ Python 差异清单见 `car-monit-api-python/COMPATIBILITY.md`，
模块对照见 `car-monit-api-python/MIGRATION_GUIDE.md`。

---

## 11. 实测记录（Git Bash）+ 可复跑的自检脚本

写脚本的机器是 Windows。一开始以为没有 bash（WSL 服务被禁用），后来发现装了
Git for Windows（`D:\work\Git\bin\bash.exe`，bash 5.2.37），于是做了实测。

**能测的都测了，测不了的也明确标出来了。**

Windows 上没有 apt、没有 PostgreSQL/Redis，所以"真正装包"那几步只能在 Linux
云主机上验证。除此之外的逻辑全部实测通过：

| 测试 | 断言数 | 结果 |
|------|--------|------|
| `bash -n setup.sh`（语法） | — | 通过 |
| `--help` / 未知参数 / 非 root 三条早退路径 | — | 全部按预期退出 |
| `selftest_logic.sh` | 28 | 28 PASS / 0 FAIL |
| `selftest_full.sh` | 33 | 33 PASS / 0 FAIL |

自己复跑（Linux 或 Git Bash 都行）：

```bash
bash setup_script/selftest_logic.sh setup_script/setup.sh
bash setup_script/selftest_full.sh  setup_script/setup.sh
```

两个脚本各测什么：

**`selftest_logic.sh`** —— 纯离线，不需要 root / 数据库：

- 抠出 `setup.sh` 自己生成的 `start-python.sh` / `start-java.sh` 做 `bash -n`；
- 验证 jar 挑选逻辑：`jar` 与 `jar.original` 并存时只挑前者，没有 jar 时报错退出；
- 把 `.env.runtime` 模板渲染出来再 `source`，逐项检查变量名与值，
  以及 URL 里的 `&` 是否被单引号保护住；
- 用假 `java -version` 验 `1.8.0_402 → 8`、`17.0.2 → 17`、`21 → 21`；
- 验 `set -u` 下空数组展开成 0 个参数（挡的是 `unbound variable` 崩溃）；
- 用假 `psql` 验 `apply_sql` 在 DDL 有报错时**仍然返回 0**（否则 `set -e`
  会在"预期内的报错"处中止整个安装）。

**`selftest_full.sh`** —— 全流程：

把 `setup.sh` 复制到临时目录，只把 `/etc/os-release` 的路径指向一个假文件
（Git Bash 没这个文件，Linux 上必然有），再加两个 stub：假 `id`（报告 uid=0）
和假 `apt-get`（不装任何东西），然后**原样跑完整流程**：step 1 基础工具 →
step 2 真实 JDK 检测（本机确实有 JDK 8，顺带验证了"已有就跳过安装"和
`JAVA_HOME` 解析）→ step 3~7 按参数跳过 → step 8 真正生成 `.env.runtime`
与两个启动脚本 → 汇总输出。断言覆盖每一步都走到了、没触发 ERR trap、
生成的 env 文件语法正确且能 `source`、两个启动脚本可执行且语法正确、
`setup.log` 正常落盘。

实测中发现并修掉的问题（说明这轮不是走过场）：

- `--no-verify` 时汇总仍打印"全部自检通过" → 改为"已跳过自检"；
- `start-java.sh` 原本写死 `pro-business-api.jar`，而 `repackage` 的实际产物是
  `pro-business-api-1.0.jar` → 改为按 `pro-business-api-*.jar` 通配挑选；
- `pipefail` + `cmd | head -n1` 的 SIGPIPE(141) 会让脚本误中止 → 关掉 pipefail；
- `ORIG_ARGS` 被 sudo 重跑分支引用却从未赋值 → 补上 `ORIG_ARGS=("$@")`；
- `GRANT ... TO CURRENT_USER` 是非法 PostgreSQL 语法（`GRANT TO` 只接受角色名）→ 删掉；
- Redis 密码用 `${PW:+-a "$PW"}` 会被空格拆词 → 改成数组展开。

**仍然没有验证过的**：apt / PGDG / Adoptium 仓库能否访问、PostgreSQL 与 Redis
能否真的装起来并启动、仓库 DDL 能否在 PG 16 上跑通、`mvn package` 能否构建
成功。这些只能在云主机第一次运行时才知道；失败时脚本会打印
`意外失败于第 N 行: <命令>`，直接定位即可。

> 顺带一个 MSYS 的坑：Git Bash 的 `grep` 在 text 模式下把 `\r` 当成行尾锚点，
> `grep -c $'\r' file` 对**任何**文件都会报全命中。判断 CRLF 要数 CR 字节
> （`tr -dc '\r' < file | wc -c`）。`selftest_logic.sh` 里就是这么做的 ——
> 这也是它一开始误报"存在 CRLF"的原因。

---

## 12. 文件清单

```
setup_script/
├── setup.sh                         主脚本
├── README.md                        本文件
├── .gitignore                       排除生成的凭据文件
├── selftest_logic.sh                离线自检（28 项）
├── selftest_full.sh                 全流程自检（33 项）
└── sql/
    └── 10_kafka_message_record.pg.sql
       仓库根的 kafka_message_record.sql 是 MySQL 方言（列内联 COMMENT 在
       PG 里非法），这里做等价转换：列名/类型/默认值/索引逐项一致，
       只把注释改成 COMMENT ON COLUMN，并补上 jl_data01. schema 限定
       （实体上是 @TableName(schema = "jl_data01")）。
```

生成的（不提交）：`.env.runtime`、`start-python.sh`、`start-java.sh`、
`setup.log`、`smoke-python.log`。
