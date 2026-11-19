#!/usr/bin/env bash
# =============================================================================
# 文件：scripts/agent/run-e2e-local.sh
# 用途：一条命令跑通本地 E2E（Redis + openGauss + 假模型 + 应用 + 断言）
#
# 与 .github/workflows/agent-e2e.yml 用同一套组件版本与同一份 e2e.sh，
# 因此"本地过了"与"云 runner 过了"含义一致。CI 里不用这个脚本（它有分步日志），
# 这里只是把同样的步骤串起来，便于改完代码先本地回归。
#
# 用法：
#   bash scripts/agent/run-e2e-local.sh                 # 自动按当前分支判断框架
#   bash scripts/agent/run-e2e-local.sh --reset-db      # 重建库（夹具改动后用）
#   FRAMEWORK=spring-ai bash scripts/agent/run-e2e-local.sh
#
# 前置：docker 可用、JDK25 已安装（默认 /opt/jdk25，可用 JAVA_HOME 覆盖）、
#       本地 6379 / 5432 / 18080 / 9902 端口空闲。
# 退出码：透传 e2e.sh 的结果（0=全通过）
# =============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31m[FATAL]\033[0m %s\n' "$*" >&2; exit 1; }

GS_PASSWORD="${GS_PASSWORD:-Passw0rd@123}"
INTERNAL_TOKEN="${INTERNAL_TOKEN:-e2e-token}"
MOCK_PORT="${MOCK_PORT:-18080}"
APP_PORT="${APP_PORT:-9902}"
REDIS_NAME="${REDIS_NAME:-redis-e2e}"
OG_NAME="${OG_NAME:-og-e2e}"
ARTIFACT_DIR="${ARTIFACT_DIR:-out/agent-e2e}"

RESET_DB=0
for arg in "$@"; do
  case "$arg" in
    --reset-db) RESET_DB=1 ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

# JDK：用独立变量而不是复用 JAVA_HOME——很多机器上 JAVA_HOME 已被设成 JDK 8/17/20，
# 而 -proc:full 这类编译参数只有 JDK 21+ 认识，复用会让构建在编译阶段莫名失败。
JAVA_HOME="${E2E_JAVA_HOME:-/opt/jdk25}"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
[ -x "$JAVA_HOME/bin/javac" ] || die "找不到 $JAVA_HOME/bin/javac，请用 E2E_JAVA_HOME 指定 JDK25 目录"
echo "java: $("$JAVA_HOME/bin/java" -version 2>&1 | head -1)"

# ---------------------------------------------------------------------------
# 0. 框架：必须与实际装配的实现一致，否则 T0 的断言会变成"自己跟自己比"
# ---------------------------------------------------------------------------
if [ -z "${FRAMEWORK:-}" ]; then
  branch="$(git branch --show-current 2>/dev/null || echo '')"
  case "$branch" in
    springAi)       FRAMEWORK="spring-ai" ;;
    agentScope2java) FRAMEWORK="agentscope" ;;
    *) die "无法从分支 '$branch' 推断框架，请显式指定 FRAMEWORK=spring-ai|agentscope" ;;
  esac
fi
say "框架=$FRAMEWORK 分支=$(git branch --show-current)"

# ---------------------------------------------------------------------------
# 1. 依赖容器（已存在则复用，不重建，省掉 openGauss 的 30s 启动）
# ---------------------------------------------------------------------------
say "确认 Redis / openGauss 容器"
docker ps --format '{{.Names}}' | grep -qx "$REDIS_NAME" || \
  docker run -d --name "$REDIS_NAME" -p 6379:6379 redis:7-alpine >/dev/null
docker ps --format '{{.Names}}' | grep -qx "$OG_NAME" || \
  docker run -d --name "$OG_NAME" --privileged --shm-size=512m \
    -e "GS_PASSWORD=$GS_PASSWORD" -e LD_LIBRARY_PATH=/usr/local/opengauss/lib \
    -p 5432:5432 enmotech/opengauss:3.0.0 >/dev/null

OG="docker exec -u 70 -e LD_LIBRARY_PATH=/usr/local/opengauss/lib $OG_NAME /usr/local/opengauss/bin/gsql"
for i in $(seq 1 60); do
  $OG -d postgres -Atc 'select 1' >/dev/null 2>&1 && { echo "openGauss ready (${i}x3s)"; break; }
  [ "$i" = 60 ] && die "openGauss 60 次探测仍未就绪，看：docker logs $OG_NAME"
  sleep 3
done

# ---------------------------------------------------------------------------
# 2. 建库与夹具
#    openGauss 3.0 不支持 CREATE SCHEMA IF NOT EXISTS，用 DO 块做幂等；
#    夹具本身不是幂等的，因此 --reset-db 会先 drop。
# ---------------------------------------------------------------------------
has_db=$($OG -d postgres -Atc "select 1 from pg_database where datname='ruoyi'" 2>/dev/null | tr -d ' ')
if [ "$RESET_DB" = "1" ] && [ "$has_db" = "1" ]; then
  say "重建数据库 ruoyi"
  $OG -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='ruoyi'" >/dev/null 2>&1
  $OG -d postgres -c "drop database ruoyi" || die "drop database 失败"
  has_db=""
fi
if [ "$has_db" != "1" ]; then
  say "建库 + 加载夹具"
  $OG -d postgres -c "create database ruoyi" || die "create database 失败"
  sed 's/^CREATE SCHEMA IF NOT EXISTS jl_data01;/DO $$ BEGIN CREATE SCHEMA jl_data01; EXCEPTION WHEN duplicate_object THEN NULL; END $$;/' \
    scripts/v3/ops/parity/sql/schema_jl_data01.sql > /tmp/schema.sql
  gunzip -c scripts/v3/ops/parity/sql/seed_jl_data01.sql.gz > /tmp/seed.sql
  docker cp /tmp/schema.sql "$OG_NAME":/tmp/schema.sql >/dev/null
  docker cp /tmp/seed.sql "$OG_NAME":/tmp/seed.sql >/dev/null
  $OG -d ruoyi -v ON_ERROR_STOP=1 -f /tmp/schema.sql > /tmp/schema.log || die "schema 导入失败，看 /tmp/schema.log"
  $OG -d ruoyi -v ON_ERROR_STOP=1 -f /tmp/seed.sql > /tmp/seed.log || die "seed 导入失败，看 /tmp/seed.log"
fi
rows=$($OG -d ruoyi -Atc "select count(*) from jl_data01.ods_szdn_gantry" 2>/dev/null | tr -d ' ')
[ "${rows:-0}" -gt 0 ] || die "夹具表为空（gantry rows=${rows:-?}），用 --reset-db 重来"
echo "gantry rows=$rows"

# ---------------------------------------------------------------------------
# 3. 构建（单测先行：E2E 跑 3 分钟，不值得为一个编译错误白等）
# ---------------------------------------------------------------------------
say "单测"
mvn -o -B -q -pl pro-business-api -am test -DskipTests=false > /tmp/e2e-unit.log 2>&1 \
  || { tail -40 /tmp/e2e-unit.log; die "单测失败"; }

say "打包 fat jar"
mvn -o -B -q -pl pro-business-api -am package -DskipTests > /tmp/e2e-package.log 2>&1 \
  || { tail -40 /tmp/e2e-package.log; die "打包失败"; }
JAR=pro-business-api/target/pro-business-api-1.0.jar
[ -f "$JAR" ] || die "未生成 $JAR"

# ---------------------------------------------------------------------------
# 4. 假模型 + 应用（后台起，退出时统一收）
# ---------------------------------------------------------------------------
APP_PID=""
MOCK_PID=""
cleanup() {
  [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null
  [ -n "$MOCK_PID" ] && kill "$MOCK_PID" 2>/dev/null
}
trap cleanup EXIT

# 端口占用多半是上一轮没退干净：直接拒绝，避免 E2E 打到旧实例（曾因此误判为"修复无效"）。
# 用 bash 内建的 /dev/tcp 探测，不依赖 nc/lsof 是否安装。
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- && return 0 || return 1; }
for p in "$MOCK_PORT" "$APP_PORT"; do
  if port_busy "$p"; then
    die "端口 $p 已被占用，先清理旧进程：lsof -i :$p 或 pkill -f pro-business-api"
  fi
done

say "启动假模型 :$MOCK_PORT"
python3 scripts/agent/mock_llm.py --port "$MOCK_PORT" --record /tmp/mock-llm.jsonl > /tmp/mock.log 2>&1 &
MOCK_PID=$!
for i in $(seq 1 20); do
  curl -sf "http://127.0.0.1:$MOCK_PORT/health" >/dev/null && break
  [ "$i" = 20 ] && die "假模型未就绪，看 /tmp/mock.log"
  sleep 1
done

say "启动应用 :$APP_PORT"
TRAFFIC_INTERNAL_TOKEN="$INTERNAL_TOKEN" \
SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL="jdbc:postgresql://127.0.0.1:5432/ruoyi?characterEncoding=UTF-8&useUnicode=true&useSSL=false&serverTimezone=Asia/Shanghai" \
SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME=gaussdb \
SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD="$GS_PASSWORD" \
TRAFFIC_AGENT_ENABLED=true \
TRAFFIC_AGENT_BASE_URL="http://127.0.0.1:$MOCK_PORT/v1" \
TRAFFIC_AGENT_API_KEY=mock-key \
TRAFFIC_AGENT_MODEL=mock-model \
  java -jar "$JAR" \
    --server.port="$APP_PORT" \
    --sync.full-sync-enabled=false \
    --spring.kafka.producer.properties.max.block.ms=2000 \
    > /tmp/app.log 2>&1 &
APP_PID=$!

for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "X-Internal-Token: $INTERNAL_TOKEN" \
    -H 'X-Tenant-Id: t1' -H 'X-User-Id: u1' \
    "http://127.0.0.1:$APP_PORT/api/v1/agent/health" || true)
  if [ "$code" = "200" ]; then echo "app ready (${i}x3s)"; break; fi
  if [ "$i" = 60 ]; then tail -60 /tmp/app.log; die "应用未在 180s 内就绪"; fi
  sleep 3
done

# ---------------------------------------------------------------------------
# 5. 断言 + 证据归集
# ---------------------------------------------------------------------------
say "运行 E2E 断言"
APP_BASE_URL="http://127.0.0.1:$APP_PORT" \
EXPECT_FRAMEWORK="$FRAMEWORK" \
INTERNAL_TOKEN="$INTERNAL_TOKEN" \
ARTIFACT_DIR="$ARTIFACT_DIR" \
  bash scripts/agent/e2e.sh
rc=$?

mkdir -p "$ARTIFACT_DIR"
cp -f /tmp/app.log /tmp/mock.log /tmp/mock-llm.jsonl "$ARTIFACT_DIR"/ 2>/dev/null || true
say "证据已归集到 $ARTIFACT_DIR（分支 $FRAMEWORK，退出码 $rc）"
exit "$rc"
