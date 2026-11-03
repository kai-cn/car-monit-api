#!/usr/bin/env bash
# =============================================================================
# car-monit-api — 云端一键环境安装脚本 / One-shot cloud provisioning script
#
# 目标 / Goal
#   把"能在云端跑起这个仓库"所需的全部启动必须项装好、配好、验通：
#     * JDK 8 (Temurin) + Maven        -> 跑 Java 侧 Spring Boot 2.4.5
#     * Python 3.12 + venv            -> 跑 Python 侧 FastAPI 移植版
#     * PostgreSQL 16                 -> GaussDB 的线协议等价替代
#     * Redis 7                       -> Java 侧真实依赖
#     * 数据库/角色/密码/schema/扩展/DDL 全部初始化
#     * 生成一套环境变量 + 两个启动脚本，Java 与 Python 共用同一份凭据
#
# 用法 / Usage
#   sudo bash setup.sh                       # 全量安装 + 初始化 + 自检
#   sudo bash setup.sh --no-build-java       # 跳过 mvn package（省 5~15 分钟）
#   sudo bash setup.sh --skip-java           # 只装 Python 运行时
#   sudo bash setup.sh --db-password 'S3cret!'  # 换数据库密码（自动同步到两个运行时）
#   bash setup.sh --help
#
# 幂等 / Idempotent
#   可重复执行。所有 DDL 都是 IF NOT EXISTS；已装好的包 apt 会跳过；
#   已存在的角色/库/schema 不会重建；服务已启动则直接复用。
#
# 已验证事实 / Verified facts（来自仓库实际配置，非推测）
#   * application.yml: url=jdbc:postgresql://192.168.56.10:5432/RuoYi
#                      username=gaussdb  password=OpenGauss@123
#                      driver=org.postgresql.Driver
#   * application.yml: spring.redis.host=127.0.0.1 port=6379 database=0
#                      password 被注释掉 -> 默认无密码
#   * 业务 SQL 全部带 jl_data01. 前缀；index_optimization.sql 需要
#     pg_trgm + btree_gin 两个扩展（已含在 postgresql-contrib 里）
#
# 重要限制 / Known limitation
#   仓库只包含 3 张核心表的 DDL（partition_scheme.sql）。
#   其余表（zdata_trail_tracks / ods_szdn_toll / ods_szdn_service /
#   zdata_location_dict / ...）的建表语句不在本仓库，属于既有数仓。
#   因此本脚本装出来的是"能让服务启动并连上库"的环境，
#   不是"带完整 8 亿行数据"的环境。详见 setup_script/README.md。
# =============================================================================

# 刻意不启用 pipefail：脚本里大量 "cmd | head -n1" 是取版本号/首行的常规写法，
# 开启 pipefail 后 head 提前退出会让上游进程收到 SIGPIPE(141)，在 set -e 下
# 会把整个安装过程误判为失败。
set -Eeu

# 保存原始参数：非 root 时下面会用 sudo 重新执行自身，必须把用户传的参数带过去。
# 参数解析的 while 循环会把 $@ 消费光，所以必须在解析之前保存。
ORIG_ARGS=("$@")

# -----------------------------------------------------------------------------
# 默认参数 / Defaults
# -----------------------------------------------------------------------------
DB_NAME="RuoYi"                 # 与 application.yml 的 jdbc URL 末段一致（大小写敏感，需加引号）
DB_USER="gaussdb"               # 与 yml username 一致
DB_PASSWORD="OpenGauss@123"     # 与 yml password 一致（保持零配置即可启动）
DB_HOST="127.0.0.1"
DB_PORT="5432"
PG_VERSION="16"

REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
REDIS_PASSWORD=""               # 空 = 无密码，与 yml 中被注释掉的 password 一致

DO_JAVA=1
DO_PY=1
DO_DB=1
DO_REDIS=1
DO_SCHEMA=1
DO_BUILD=1                      # 默认构建 Java（让"能跑"成立）
DO_VERIFY=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.runtime"
LOG_FILE="${SCRIPT_DIR}/setup.log"

# -----------------------------------------------------------------------------
# 终端输出 / Output helpers
# -----------------------------------------------------------------------------
if [ -t 1 ]; then
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
  C_BLU=$'\033[36m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_RED=; C_GRN=; C_YEL=; C_BLU=; C_DIM=; C_OFF=
fi

log()  { printf '%s[setup]%s %s\n' "${C_BLU}" "${C_OFF}" "$*"; }
ok()   { printf '%s  OK  %s %s\n' "${C_GRN}" "${C_OFF}" "$*"; }
warn() { printf '%s WARN %s %s\n' "${C_YEL}" "${C_OFF}" "$*" >&2; }
err()  { printf '%s FAIL %s %s\n' "${C_RED}" "${C_OFF}" "$*" >&2; }
step() { printf '\n%s=== %s ===%s\n' "${C_BLU}" "$*" "${C_OFF}"; }
dim()  { printf '%s      %s%s\n' "${C_DIM}" "$*" "${C_OFF}"; }

die() { err "$*"; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# 失败时打印出错行，方便云端排查
trap 'err "意外失败于第 ${LINENO} 行: ${BASH_COMMAND}"' ERR

usage() {
  cat <<'EOF'
car-monit-api 云端环境安装 / cloud provisioning

用法:
  sudo bash setup.sh [options]

选项:
  --db-password <pw>     数据库密码（默认取 application.yml 里的 OpenGauss@123）
  --db-host <host>       数据库地址（默认 127.0.0.1）
  --db-port <port>       数据库端口（默认 5432）
  --db-name <name>       数据库名（默认 RuoYi）
  --db-user <name>       数据库用户（默认 gaussdb）
  --redis-password <pw>  Redis 密码（默认无密码，与 yml 一致）
  --pg-version <n>       PostgreSQL 大版本（默认 16）
  --skip-java            不安装 JDK / Maven
  --skip-python          不安装 Python 运行时与 venv
  --skip-db              不安装 PostgreSQL
  --skip-redis           不安装 Redis
  --skip-schema          不执行仓库里的 SQL 建表
  --no-build-java        不执行 mvn package（Java 侧仍需手动构建才能启动）
  --no-verify            跳过最后的自检
  -h, --help             显示本帮助

产物:
  setup_script/.env.runtime   环境变量（含数据库凭据，600 权限）
  setup_script/start-java.sh  启动 Java 侧
  setup_script/start-python.sh 启动 Python 侧
  setup_script/setup.log      本次安装日志
EOF
}

# -----------------------------------------------------------------------------
# 参数解析 / Argument parsing
# -----------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --db-password)   DB_PASSWORD="${2:?}"; shift 2 ;;
    --db-host)       DB_HOST="${2:?}";     shift 2 ;;
    --db-port)       DB_PORT="${2:?}";     shift 2 ;;
    --db-name)       DB_NAME="${2:?}";     shift 2 ;;
    --db-user)       DB_USER="${2:?}";     shift 2 ;;
    --redis-password) REDIS_PASSWORD="${2:?}"; shift 2 ;;
    --pg-version)    PG_VERSION="${2:?}";  shift 2 ;;
    --skip-java)     DO_JAVA=0;   shift ;;
    --skip-python)   DO_PY=0;     shift ;;
    --skip-db)       DO_DB=0;     shift ;;
    --skip-redis)    DO_REDIS=0;  shift ;;
    --skip-schema)   DO_SCHEMA=0; shift ;;
    --no-build-java) DO_BUILD=0;  shift ;;
    --no-verify)     DO_VERIFY=0; shift ;;
    -h|--help)       usage; exit 0 ;;
    *) die "未知参数: $1（用 --help 查看用法）" ;;
  esac
done

# Redis 的可选参数用数组承载：直接写 ${PW:+--requirepass "$PW"} 会被按空格
# 切成两个词，密码里含空格时参数就错位了。
REDIS_SERVE_AUTH=()
REDIS_CLI_AUTH=()
if [ -n "$REDIS_PASSWORD" ]; then
  REDIS_SERVE_AUTH=(--requirepass "$REDIS_PASSWORD")
  REDIS_CLI_AUTH=(-a "$REDIS_PASSWORD" --no-auth-warning)
fi

# -----------------------------------------------------------------------------
# 前置检查 / Preconditions
# -----------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then
    warn "非 root，自动使用 sudo 重新执行"
    exec sudo -E bash "$0" "${ORIG_ARGS[@]+${ORIG_ARGS[@]}}"
  fi
  die "需要 root 权限（请用 sudo bash $0）"
fi

exec > >(tee -a "$LOG_FILE") 2>&1
log "仓库根目录 : ${REPO_ROOT}"
log "日志文件   : ${LOG_FILE}"

[ -d "${REPO_ROOT}/pro-business-api" ] || die "${REPO_ROOT} 看起来不是 car-monit-api 仓库根目录"
[ -f "${REPO_ROOT}/car-monit-api-python/requirements.txt" ] || die "缺少 car-monit-api-python/requirements.txt"

# 发行版识别（不依赖 lsb_release，避免额外依赖）
[ -f /etc/os-release ] || die "无法识别操作系统：缺少 /etc/os-release"
# shellcheck disable=SC1091
. /etc/os-release
DISTRO_ID="${ID:-unknown}"
DISTRO_CODENAME="${VERSION_CODENAME:-}"
log "操作系统   : ${PRETTY_NAME:-$DISTRO_ID} (codename=${DISTRO_CODENAME:-none})"

case "$DISTRO_ID" in
  ubuntu|debian) PKG=apt ;;
  rhel|centos|rocky|almalinux|fedora|amzn|ol) PKG=dnf; have dnf || PKG=yum ;;
  *)
    if have apt-get; then PKG=apt
    elif have dnf; then PKG=dnf
    elif have yum; then PKG=yum
    else die "不支持的发行版: ${DISTRO_ID}（仅支持 apt / dnf / yum）"
    fi ;;
esac
log "包管理器   : ${PKG}"

# -----------------------------------------------------------------------------
# 包安装封装 / Package helpers
# -----------------------------------------------------------------------------
APT_UPDATED=0
apt_refresh() {
  if [ "$APT_UPDATED" -eq 0 ]; then
    log "apt-get update ..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq || warn "apt-get update 有告警，继续"
    APT_UPDATED=1
  fi
}

pkg_install() {
  [ $# -gt 0 ] || return 0
  case "$PKG" in
    apt)
      apt_refresh
      DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "$@"
      ;;
    dnf) dnf install -y -q "$@" ;;
    yum) yum install -y -q "$@" ;;
  esac
}

pkg_available() {
  case "$PKG" in
    apt) apt-cache show "$1" >/dev/null 2>&1 ;;
    dnf) dnf -q list available "$1" >/dev/null 2>&1 ;;
    yum) yum -q list available "$1" >/dev/null 2>&1 ;;
  esac
}

# -----------------------------------------------------------------------------
# 1. 基础工具 / Base tooling
# -----------------------------------------------------------------------------
step "1/8 基础工具 / base tooling"
BASE_PKGS=(curl ca-certificates gnupg tar git "procps")
case "$PKG" in
  apt) BASE_PKGS+=(apt-transport-https lsb-release) ;;
esac
pkg_install "${BASE_PKGS[@]}"
ok "基础工具就绪"

# -----------------------------------------------------------------------------
# 2. JDK 8 + Maven
# -----------------------------------------------------------------------------
if [ "$DO_JAVA" -eq 1 ]; then
  step "2/8 JDK 8 (Temurin) + Maven"

  java_major() {
    have java || { echo 0; return; }
    java -version 2>&1 | awk -F'"' '/version/{split($2,v,"."); if (v[1]=="1") print v[2]; else print v[1]}' | head -n1
  }

  CUR_JAVA="$(java_major)"
  if [ "${CUR_JAVA:-0}" = "8" ]; then
    ok "已存在 JDK 8: $(java -version 2>&1 | head -n1)"
  else
    installed=0
    case "$PKG" in
      apt)
        # 首选 Adoptium 官方仓库（Ubuntu 24.04 已不再提供 openjdk-8-jdk）
        if [ -n "$DISTRO_CODENAME" ]; then
          log "尝试 Adoptium apt 仓库 ..."
          install -d -m 0755 /etc/apt/keyrings
          if curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public \
               | gpg --dearmor --yes -o /etc/apt/keyrings/adoptium.gpg 2>/dev/null; then
            echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb ${DISTRO_CODENAME} main" \
              > /etc/apt/sources.list.d/adoptium.list
            APT_UPDATED=0
            if pkg_install temurin-8-jdk; then installed=1; fi
          fi
          if [ "$installed" -eq 0 ]; then
            warn "Adoptium 仓库不可用，回退到发行版自带的 openjdk-8-jdk"
            rm -f /etc/apt/sources.list.d/adoptium.list
            APT_UPDATED=0
            if pkg_install openjdk-8-jdk; then installed=1; fi
          fi
        fi
        ;;
      *)
        if pkg_install java-1.8.0-openjdk-devel; then installed=1
        elif pkg_install java-1.8.0-openjdk; then installed=1
        fi
        ;;
    esac
    [ "$installed" -eq 1 ] || die "JDK 8 安装失败：仓库里没有可用的 Java 8 包"
    ok "JDK 8 已安装"
  fi

  # JAVA_HOME 落盘（Java 侧 mvn 需要）
  JAVA_BIN="$(readlink -f "$(command -v java)")"
  JAVA_HOME_RESOLVED="$(dirname "$(dirname "$JAVA_BIN")")"
  export JAVA_HOME="$JAVA_HOME_RESOLVED"
  ok "JAVA_HOME=${JAVA_HOME}"
  java -version 2>&1 | head -n1 | sed 's/^/      /'

  # Maven（apt 的 maven 会顺带拉一个默认 JDK，无所谓，JAVA_HOME 会覆盖）
  if have mvn; then
    ok "已存在 Maven: $(mvn -v 2>/dev/null | head -n1)"
  else
    pkg_install maven || die "Maven 安装失败"
    ok "Maven 已安装: $(mvn -v 2>/dev/null | head -n1)"
  fi
else
  step "2/8 跳过 JDK / Maven (--skip-java)"
fi

# -----------------------------------------------------------------------------
# 3. Python 3.12
# -----------------------------------------------------------------------------
PYTHON_BIN=""
if [ "$DO_PY" -eq 1 ]; then
  step "3/8 Python 3.12"

  pick_python() {
    for c in python3.12 python3; do
      if have "$c"; then
        v="$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
        if [ "$v" = "3.12" ]; then PYTHON_BIN="$c"; return 0; fi
      fi
    done
    return 1
  }

  if pick_python; then
    ok "已存在 Python 3.12: $(command -v "$PYTHON_BIN")"
  else
    case "$PKG" in
      apt)
        # Ubuntu 24.04 / Debian 13 自带 3.12；22.04 需要 deadsnakes
        if pkg_install python3.12 python3.12-venv python3.12-dev; then
          :
        elif [ "$DISTRO_ID" = "ubuntu" ] && [ -n "$DISTRO_CODENAME" ]; then
          warn "发行版无 python3.12，添加 deadsnakes PPA"
          pkg_install software-properties-common
          add-apt-repository -y ppa:deadsnakes/ppa >/dev/null 2>&1 || warn "deadsnakes PPA 添加失败"
          APT_UPDATED=0
          pkg_install python3.12 python3.12-venv python3.12-dev || true
        fi
        ;;
      *)
        pkg_install python3.12 python3.12-devel || true
        ;;
    esac

    if ! pick_python; then
      warn "包管理器装不到 3.12，改用 uv 安装独立解释器"
      if ! have uv; then
        curl -fsSL https://astral.sh/uv/install.sh | sh || true
        export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
      fi
      if have uv; then
        uv python install 3.12 || warn "uv python install 失败"
        UV_PY="$(uv python find 3.12 2>/dev/null || true)"
        if [ -n "$UV_PY" ] && [ -x "$UV_PY" ]; then PYTHON_BIN="$UV_PY"; fi
      fi
    fi
  fi

  [ -n "$PYTHON_BIN" ] || die "Python 3.12 安装失败：请手动安装后重跑，或用 --skip-python"
  ok "Python: $("$PYTHON_BIN" --version 2>&1) ($(command -v "$PYTHON_BIN"))"

  # venv（Ubuntu 需要单独装 python3.12-venv，前面已尝试）
  if ! "$PYTHON_BIN" -c 'import venv, ensurepip' >/dev/null 2>&1; then
    pkg_install "python3.12-venv" || warn "python3.12-venv 安装失败"
  fi
else
  step "3/8 跳过 Python (--skip-python)"
fi

# -----------------------------------------------------------------------------
# 4. PostgreSQL
# -----------------------------------------------------------------------------
PG_CLUSTER="main"
if [ "$DO_DB" -eq 1 ]; then
  step "4/8 PostgreSQL ${PG_VERSION}"

  if have psql && [ -d "/usr/lib/postgresql/${PG_VERSION}" ]; then
    ok "已存在 PostgreSQL ${PG_VERSION}"
  else
    case "$PKG" in
      apt)
        if ! pkg_available "postgresql-${PG_VERSION}"; then
          [ -n "$DISTRO_CODENAME" ] || die "无法识别发行版代号（VERSION_CODENAME），无法添加 PGDG 仓库"
          log "添加 PGDG apt 仓库（官方仓库，含 ${PG_VERSION}）"
          install -d -m 0755 /usr/share/postgresql-common/pgdg
          curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
            https://www.postgresql.org/media/keys/ACCC4CF8.asc \
            || warn "PGDG GPG key 下载失败"
          echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${DISTRO_CODENAME}-pgdg main" \
            > /etc/apt/sources.list.d/pgdg.list
          APT_UPDATED=0
        fi
        ;;
    esac
    # contrib 必须装：pg_trgm / btree_gin 在 contrib 里
    case "$PKG" in
      apt) pkg_install "postgresql-${PG_VERSION}" "postgresql-contrib-${PG_VERSION}" || die "PostgreSQL 安装失败" ;;
      *)   pkg_install "postgresql-server" "postgresql-contrib" || die "PostgreSQL 安装失败" ;;
    esac
    ok "PostgreSQL 已安装"
  fi

  # 启动（云端容器通常没有 systemd，所以优先用 pg_ctlcluster）
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
    ok "PostgreSQL 已在运行 (${DB_HOST}:${DB_PORT})"
  else
    if have pg_ctlcluster; then
      log "pg_ctlcluster ${PG_VERSION} ${PG_CLUSTER} start"
      pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" start 2>/dev/null \
        || warn "pg_ctlcluster 启动返回非零（可能已在运行）"
    elif have systemctl; then
      systemctl enable --now "postgresql" || warn "systemctl 启动 postgresql 失败"
    else
      PG_DATA="$(find /var/lib/postgresql /var/lib/pgsql -maxdepth 3 -name PG_VERSION 2>/dev/null | head -n1 | xargs -r dirname)"
      [ -n "$PG_DATA" ] || die "找不到 PostgreSQL 数据目录"
      su postgres -c "/usr/lib/postgresql/${PG_VERSION}/bin/pg_ctl -D '${PG_DATA}' -l /tmp/pg.log start" \
        || die "直接启动 PostgreSQL 失败，见 /tmp/pg.log"
    fi

    for i in $(seq 1 30); do
      if pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then break; fi
      sleep 1
    done
    pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1 \
      || die "PostgreSQL 启动超时（端口 ${DB_PORT} 未监听）"
    ok "PostgreSQL 已启动"
  fi

  # 注：不再做“TCP 连接 postgres 试探”——全新安装的 PG 默认不允许无密码
  # TCP 登录，试探只会产生误导性输出。下面建角色/库时会用 su postgres 走
  # unix socket，并在 6.4 用密码走 TCP 验证，那才是真正的连通性检查。
else
  step "4/8 跳过 PostgreSQL (--skip-db)"
fi

# -----------------------------------------------------------------------------
# 5. Redis
# -----------------------------------------------------------------------------
if [ "$DO_REDIS" -eq 1 ]; then
  step "5/8 Redis"

  # 端口上存在实例就会应答：无密码返回 PONG，有密码返回 NOAUTH，都说明"活着"。
  # 这样重复执行本脚本时不会因为"端口已被占用"而启动失败。
  redis_alive() {
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -qE 'PONG|NOAUTH'
  }

  if have redis-cli && redis_alive; then
    ok "Redis 已在运行 (${REDIS_HOST}:${REDIS_PORT})"
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
         ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} ping 2>/dev/null | grep -q PONG; then
      ok "Redis 认证通过"
    else
      warn "在跑的实例不接受当前凭据（密码不一致）：如需重置请先 'redis-cli shutdown' 再重跑本脚本"
    fi
  else
    if ! have redis-server; then
      case "$PKG" in
        apt) pkg_install redis-server || die "Redis 安装失败" ;;
        *)   pkg_install redis || die "Redis 安装失败" ;;
      esac
    fi
    ok "Redis 已安装: $(redis-server --version | head -n1)"

    # 密码配置：不设置则与 application.yml（password 被注释）保持一致
    REDIS_CONF="/etc/redis/redis.conf"
    if [ -f "$REDIS_CONF" ] && [ -n "$REDIS_PASSWORD" ]; then
      if grep -qE '^\s*requirepass\s' "$REDIS_CONF"; then
        sed -i -E "s|^\s*requirepass\s.*|requirepass ${REDIS_PASSWORD}|" "$REDIS_CONF"
      else
        printf '\nrequirepass %s\n' "$REDIS_PASSWORD" >> "$REDIS_CONF"
      fi
      # 保护模式会拒绝带密码的本地连接？不会，但统一关掉更省事
      sed -i -E 's|^\s*protected-mode\s.*|protected-mode no|' "$REDIS_CONF" || true
      ok "Redis 密码已写入 ${REDIS_CONF}"
    elif [ -f "$REDIS_CONF" ]; then
      dim "未设置 Redis 密码（与 application.yml 一致：password 被注释）"
    fi

    if [ -f "$REDIS_CONF" ]; then
      redis-server "$REDIS_CONF" --daemonize yes --supervised no || die "Redis 启动失败"
    else
      redis-server --daemonize yes --port "$REDIS_PORT" \
        ${REDIS_SERVE_AUTH[@]+"${REDIS_SERVE_AUTH[@]}"} || die "Redis 启动失败"
    fi

    for i in $(seq 1 20); do
      if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
           ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} ping 2>/dev/null | grep -q PONG; then
        break
      fi
      sleep 0.5
    done
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
      ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} ping 2>/dev/null | grep -q PONG \
      || die "Redis 启动后 PING 失败"
    ok "Redis 已启动并 PING 通"
  fi
else
  step "5/8 跳过 Redis (--skip-redis)"
fi

# -----------------------------------------------------------------------------
# 6. 数据库初始化：角色 / 库 / schema / 扩展 / DDL
# -----------------------------------------------------------------------------
sql_as_super() {   # sql_as_super <db> <sql>
  su postgres -c "psql -v ON_ERROR_STOP=1 -q -d \"$1\" -c \"$2\""
}

# su 会继承当前目录：若从 /root 下执行，postgres 用户读不了 /root，
# psql 会先吐一行 "could not change directory to "/root": Permission denied"。
# 后面用到的路径全是绝对路径，切到 / 不影响任何事。
cd /

if [ "$DO_DB" -eq 1 ]; then
  step "6/8 数据库初始化 / database provisioning"

  # 6.1 角色
  log "配置角色 ${DB_USER} ..."
  if su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" | grep -q 1; then
    sql_as_super postgres "ALTER ROLE \\\"${DB_USER}\\\" WITH LOGIN PASSWORD '${DB_PASSWORD}'"
    ok "角色 ${DB_USER} 已存在，密码已同步"
  else
    sql_as_super postgres "CREATE ROLE \\\"${DB_USER}\\\" WITH LOGIN PASSWORD '${DB_PASSWORD}'"
    ok "角色 ${DB_USER} 已创建"
  fi

  # 6.2 数据库（名字含大写，必须加双引号）
  log "配置数据库 \"${DB_NAME}\" ..."
  if su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" | grep -q 1; then
    ok "数据库 \"${DB_NAME}\" 已存在"
  else
    sql_as_super postgres "CREATE DATABASE \\\"${DB_NAME}\\\" OWNER \\\"${DB_USER}\\\""
    ok "数据库 \"${DB_NAME}\" 已创建（owner=${DB_USER}）"
  fi

  # 6.3 扩展（必须超级用户）
  log "安装扩展 pg_trgm / btree_gin ..."
  sql_as_super "$DB_NAME" "CREATE EXTENSION IF NOT EXISTS pg_trgm" || warn "pg_trgm 安装失败（trigram 模糊索引将不可用）"
  sql_as_super "$DB_NAME" "CREATE EXTENSION IF NOT EXISTS btree_gin" || warn "btree_gin 安装失败"
  ok "扩展就绪"

  # 6.4 schema（必须与 XML 里的 jl_data01. 前缀一致）
  log "创建 schema jl_data01（owner=${DB_USER}）..."
  export PGPASSWORD="$DB_PASSWORD"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q \
    -c "CREATE SCHEMA IF NOT EXISTS jl_data01 AUTHORIZATION \"${DB_USER}\"" \
    || die "创建 schema 失败：请检查密码与 pg_hba.conf"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q \
    -c "ALTER ROLE \"${DB_USER}\" SET search_path TO jl_data01, public" \
    || warn "设置 search_path 失败（不影响：SQL 都带 schema 前缀）"
  ok "schema jl_data01 就绪"

  # 6.5 仓库自带 DDL
  if [ "$DO_SCHEMA" -eq 1 ]; then
    SQL_DIR="${REPO_ROOT}/pro-business-api/src/main/resources/sql"

    # 这些文件是"设计文档 + 可执行 DDL"混合体：里面有 EXPLAIN ANALYZE、
    # ANALYZE 不存在的分区等语句，所以用 ON_ERROR_STOP=0 执行并统计错误条数。
    apply_sql() {
      local file="$1" label="$2" errlog
      [ -f "$file" ] || { warn "缺少 SQL 文件: $file"; return 0; }
      errlog="$(mktemp)"
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
           -v ON_ERROR_STOP=0 -q -f "$file" >"$errlog" 2>&1 || true
      local nerr
      nerr="$(grep -c '^psql:.*ERROR' "$errlog" 2>/dev/null || true)"
      nerr="${nerr:-0}"
      if [ "$nerr" -eq 0 ]; then
        ok "${label} 执行完成，无错误"
        # 成功时顺手删掉临时日志；有错误则保留供排查
        rm -f "$errlog"
      else
        warn "${label} 执行完成，有 ${nerr} 条语句报错（多为示例查询/缺表，详见下方）"
        # head 提前退出会让 grep 收到 SIGPIPE，用 || true 兜住
        grep '^psql:.*ERROR' "$errlog" 2>/dev/null | head -n 8 | sed 's/^/      /' || true
        dim "完整日志: ${errlog}"
      fi
      # 必须显式 return 0：否则上面 if 分支的返回值会成为函数返回值，
      # 在 set -e 下会把"DDL 有预期错误"变成整个安装中止。
      return 0
    }

    step "6.5 应用仓库 DDL / apply repository DDL"

    # 顺序不可颠倒：
    #   partition_scheme 先建 3 张核心表 -> 后面两个才有对象可加索引
    apply_sql "${SQL_DIR}/partition_scheme.sql"                "partition_scheme.sql"
    apply_sql "${SQL_DIR}/progressive_architecture_indexes.sql" "progressive_architecture_indexes.sql"
    apply_sql "${SQL_DIR}/index_optimization.sql"              "index_optimization.sql"

    # 仓库根的 kafka_message_record.sql 是 MySQL 方言（内联 COMMENT 在 PG 里非法），
    # 这里用等价的 PostgreSQL 版本，见 setup_script/sql/10_kafka_message_record.pg.sql
    apply_sql "${SCRIPT_DIR}/sql/10_kafka_message_record.pg.sql" "kafka_message_record (PG 等价版)"

    # 6.6 统计
    # 这里不需要额外 GRANT：schema 是以 AUTHORIZATION "$DB_USER" 创建的，
    # 库的 owner 也是同一个角色，权限天然具备。（PostgreSQL 的 GRANT TO
    # 只接受角色名，写 CURRENT_USER 属于非法语法。）

    TABLES="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema='jl_data01'")"
    ok "jl_data01 中现有 ${TABLES} 张表"
    dim "核心 3 表应为: ods_rt_szdn_snapshot_flow_addcode / ods_lwzxsfsj_fee_records_01 / zdata_trail_fitting"

    warn "仓库不含其余业务表的 DDL（zdata_trail_tracks、ods_szdn_toll、ods_szdn_service、"
    warn "zdata_location_dict 等属于既有数仓）。这些表的接口会返回 500，属预期。"
  else
    step "6.5 跳过 DDL (--skip-schema)"
  fi
else
  step "6/8 跳过数据库初始化 (--skip-db)"
fi

# -----------------------------------------------------------------------------
# 7. Python venv + 依赖
# -----------------------------------------------------------------------------
if [ "$DO_PY" -eq 1 ]; then
  step "7/8 Python 依赖 / python dependencies"
  PY_ROOT="${REPO_ROOT}/car-monit-api-python"
  VENV="${PY_ROOT}/.venv"

  if [ -d "$VENV" ] && [ -x "${VENV}/bin/python" ]; then
    ok "已存在 venv: ${VENV}"
  else
    log "创建 venv ..."
    "$PYTHON_BIN" -m venv "$VENV" || die "创建 venv 失败"
    ok "venv 已创建"
  fi

  log "pip install -r requirements.txt ..."
  "${VENV}/bin/python" -m pip install --upgrade pip -q || warn "pip 升级失败，继续"
  "${VENV}/bin/python" -m pip install -q -r "${PY_ROOT}/requirements.txt" \
    || die "Python 依赖安装失败（检查网络 / pip 源）"
  ok "Python 依赖已安装"
  "${VENV}/bin/python" -m pip list --format=freeze 2>/dev/null | grep -iE '^(fastapi|uvicorn|SQLAlchemy|psycopg|httpx|orjson|pytest)=' | sed 's/^/      /' || true
else
  step "7/8 跳过 Python 依赖 (--skip-python)"
fi

# -----------------------------------------------------------------------------
# 8. 生成环境变量 + 启动脚本
# -----------------------------------------------------------------------------
step "8/8 生成凭据与启动脚本 / emit env + launchers"

# 说明：Java(Spring 松弛绑定) 与 Python(Environment 替身) 都认这套变量名，
# 所以一份 .env.runtime 同时服务两个运行时。
JDBC_URL="jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}?characterEncoding=UTF-8&useUnicode=true&useSSL=false&tinyInt1isBit=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai"

umask 077
cat > "$ENV_FILE" <<EOF
# 由 setup.sh 生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 用法: source setup_script/.env.runtime
#
# 这套变量名同时被两个运行时识别：
#   Java   -> Spring 的 SystemEnvironmentPropertySource 松弛绑定
#   Python -> org/springframework/core/env/Environment.py 的 _relaxed_names
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL='${JDBC_URL}'
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME='${DB_USER}'
export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD='${DB_PASSWORD}'
export SPRING_REDIS_HOST='${REDIS_HOST}'
export SPRING_REDIS_PORT='${REDIS_PORT}'
EOF

if [ -n "$REDIS_PASSWORD" ]; then
  echo "export SPRING_REDIS_PASSWORD='${REDIS_PASSWORD}'" >> "$ENV_FILE"
fi

if [ "$DO_JAVA" -eq 1 ] && [ -n "${JAVA_HOME:-}" ]; then
  echo "export JAVA_HOME='${JAVA_HOME}'" >> "$ENV_FILE"
  echo "export PATH=\"${JAVA_HOME}/bin:\$PATH\"" >> "$ENV_FILE"
fi

chmod 600 "$ENV_FILE"
ok "已写入 ${ENV_FILE}（权限 600）"

# --- Python 启动脚本
cat > "${SCRIPT_DIR}/start-python.sh" <<EOF
#!/usr/bin/env bash
# 启动 Python 侧（FastAPI 移植版）
set -Eeuo pipefail
HERE="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "\${HERE}/.env.runtime"
cd "\${HERE}/../car-monit-api-python"
exec .venv/bin/python run.py "\$@"
EOF

# --- Java 启动脚本
cat > "${SCRIPT_DIR}/start-java.sh" <<EOF
#!/usr/bin/env bash
# 启动 Java 侧（Spring Boot 2.4.5 原始版本）
set -Eeuo pipefail
HERE="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "\${HERE}/.env.runtime"
JAR=""
# 不写死文件名：多模块构建产物是 pro-business-api-<version>.jar，
# 且 repackage 会同时留下 *.jar.original，这里按通配符挑第一个真正的 fat jar。
for f in "\${HERE}/../pro-business-api/target"/pro-business-api-*.jar; do
  [ -f "\$f" ] || continue
  JAR="\$f"
  break
done
if [ -z "\$JAR" ]; then
  echo "未找到 pro-business-api/target/pro-business-api-*.jar，请先构建：" >&2
  echo "  cd \${HERE}/.. && mvn -q -DskipTests package" >&2
  exit 1
fi
echo "启动 \$JAR" >&2
exec java -jar "\$JAR" "\$@"
EOF

chmod +x "${SCRIPT_DIR}/start-python.sh" "${SCRIPT_DIR}/start-java.sh"
ok "已生成 start-python.sh / start-java.sh"

# -----------------------------------------------------------------------------
# 9. Java 构建（可选，失败不致命）
# -----------------------------------------------------------------------------
if [ "$DO_JAVA" -eq 1 ] && [ "$DO_BUILD" -eq 1 ]; then
  step "9 Java 构建 / mvn package"
  # shellcheck disable=SC1091
  . "$ENV_FILE"
  log "首次构建需要下载依赖（Aliyun 镜像），通常 5~15 分钟 ..."
  if ( cd "$REPO_ROOT" && mvn -B -q -DskipTests package ); then
    JAR="$(ls -1 "${REPO_ROOT}"/pro-business-api/target/pro-business-api-*.jar 2>/dev/null | head -n1 || true)"
    if [ -n "$JAR" ]; then
      ok "构建成功: ${JAR}"
    else
      warn "mvn 返回成功但没找到 jar，请检查 pro-business-api/target/"
    fi
  else
    warn "Java 构建失败，但 Python 侧不受影响。可稍后手动重试："
    warn "  cd ${REPO_ROOT} && mvn -DskipTests package"
  fi
elif [ "$DO_JAVA" -eq 1 ]; then
  step "9 跳过 Java 构建 (--no-build-java)"
  dim "手动构建: cd ${REPO_ROOT} && mvn -DskipTests package"
fi

# -----------------------------------------------------------------------------
# 10. 自检
# -----------------------------------------------------------------------------
RC=0
if [ "$DO_VERIFY" -eq 1 ]; then
  step "10 自检 / verification"

  # 10.1 版本
  if [ "$DO_JAVA" -eq 1 ]; then
    if java -version >/dev/null 2>&1; then ok "java: $(java -version 2>&1 | head -n1)"; else err "java 不可用"; RC=1; fi
    if mvn -v >/dev/null 2>&1; then ok "mvn : $(mvn -v 2>/dev/null | head -n1)"; else err "mvn 不可用"; RC=1; fi
  fi
  if [ "$DO_PY" -eq 1 ]; then
    if [ -x "${REPO_ROOT}/car-monit-api-python/.venv/bin/python" ]; then
      ok "python: $("${REPO_ROOT}/car-monit-api-python/.venv/bin/python" --version 2>&1)"
    else err "python venv 不可用"; RC=1; fi
  fi

  # 10.2 数据库
  if [ "$DO_DB" -eq 1 ]; then
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc 'select 1' 2>/dev/null | grep -q 1; then
      ok "PostgreSQL 连接成功 (${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME})"
      NTAB="$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='jl_data01'" 2>/dev/null || echo '?')"
      ok "jl_data01 表数量: ${NTAB}"
      for t in ods_rt_szdn_snapshot_flow_addcode ods_lwzxsfsj_fee_records_01 zdata_trail_fitting; do
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
             "SELECT to_regclass('jl_data01.${t}')" 2>/dev/null | grep -q jl_data01; then
          ok "核心表存在: ${t}"
        else
          warn "核心表缺失: ${t}（见上面 DDL 报错）"
        fi
      done
    else
      err "PostgreSQL 连接失败 (${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME})"
      RC=1
    fi
  fi

  # 10.3 Redis
  if [ "$DO_REDIS" -eq 1 ]; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
         ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} ping 2>/dev/null | grep -q PONG; then
      ok "Redis PING -> PONG"
    else
      err "Redis PING 失败"
      RC=1
    fi
  fi

  # 10.4 Python 侧启动自检（进程内，不依赖外部服务）
  if [ "$DO_PY" -eq 1 ] && [ -x "${REPO_ROOT}/car-monit-api-python/.venv/bin/python" ]; then
    log "运行 Python 启动自检 scripts/smoke_test.py ..."
    if ( cd "${REPO_ROOT}/car-monit-api-python" && .venv/bin/python scripts/smoke_test.py ) \
         > "${SCRIPT_DIR}/smoke-python.log" 2>&1; then
      ok "Python 自检通过（详见 smoke-python.log）"
    else
      err "Python 自检失败，见 ${SCRIPT_DIR}/smoke-python.log"
      RC=1
    fi
  fi
fi

# -----------------------------------------------------------------------------
# 汇总
# -----------------------------------------------------------------------------
step "完成 / done"
cat <<EOF
  仓库根      : ${REPO_ROOT}
  环境变量    : ${ENV_FILE}          (source 后用)
  安装日志    : ${LOG_FILE}

  启动 Python 侧:
      bash ${SCRIPT_DIR}/start-python.sh
      然后: curl http://127.0.0.1:9901/health

  启动 Java 侧:
      bash ${SCRIPT_DIR}/start-java.sh

  数据库        : ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}  schema=jl_data01
  Redis         : ${REDIS_HOST}:${REDIS_PORT} $( [ -n "$REDIS_PASSWORD" ] && echo '(有密码)' || echo '(无密码)' )
EOF

if [ "$DO_VERIFY" -eq 0 ]; then
  dim "已跳过自检 (--no-verify)"
elif [ "$RC" -ne 0 ]; then
  warn "自检有失败项，请查看上面的 FAIL 与日志"
else
  ok "全部自检通过"
fi
exit "$RC"
