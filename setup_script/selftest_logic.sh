#!/usr/bin/env bash
# setup.sh 的离线逻辑测试（可在 Git Bash 下跑，不需要 root / apt / PostgreSQL）
#
# 为什么需要它：setup.sh 真正执行要 root + apt + PostgreSQL，Windows 上跑不了。
# 这个脚本把 setup.sh 里"纯逻辑"的片段原样抠出来，在隔离目录里用假命令跑，
# 验证那些只在真正运行时才会暴露的问题（生成脚本的语法、env 文件能不能 source、
# JDK 版本识别、apply_sql 在"DDL 有报错"时是否仍然返回 0）。
set -uo pipefail

SETUP="${1:?用法: _t_logic.sh <setup.sh 路径>}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$*"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$*"; }
head_() { printf '\n=== %s ===\n' "$*"; }

# ---------------------------------------------------------------------------
head_ "0. 文件自身健康"
if head -c2 "$SETUP" | grep -q '#!'; then ok "首行是 shebang"; else bad "首行不是 shebang"; fi
# 注意：不能用 grep -c $'\r' 判 CRLF —— MSYS2 的 grep 在 text 模式下
# 会把 \r 当成行尾锚点，任何文件都会命中。直接数 CR 字节才准。
if [ "$(tr -dc '\r' < "$SETUP" | wc -c | tr -d ' ')" = "0" ]; then
  ok "无 CR 字节（LF-only）"
else
  bad "存在 CR 字节（CRLF 行尾）"
fi
if head -c3 "$SETUP" | grep -q $'\xef\xbb\xbf'; then bad "存在 UTF-8 BOM"; else ok "无 BOM"; fi

# ---------------------------------------------------------------------------
head_ "1. 抠出 setup.sh 自己生成的启动脚本并做语法检查"

extract_block() {   # extract_block <起止行特征> <输出文件>
  awk -v pat="$1" '
    index($0, pat) { inside = 1; next }
    inside && $0 == "EOF" { exit }
    inside { print }
  ' "$SETUP" | sed 's/\\//g' > "$2"
}

extract_block 'start-python.sh" <<EOF' "$TMP/start-python.sh"
extract_block 'start-java.sh" <<EOF'   "$TMP/start-java.sh"

for f in start-python.sh start-java.sh; do
  if [ -s "$TMP/$f" ]; then
    ok "$f 已提取（$(wc -l < "$TMP/$f" | tr -d ' ') 行）"
    if bash -n "$TMP/$f"; then ok "$f 语法正确"; else bad "$f 语法错误"; fi
  else
    bad "$f 提取为空"
  fi
done

# 生成的 java 启动脚本必须能挑到 pro-business-api-1.0.jar
mkdir -p "$TMP/repo/setup_script" "$TMP/repo/pro-business-api/target"
cp "$TMP/start-java.sh" "$TMP/repo/setup_script/start-java.sh"
cp "$TMP/start-python.sh" "$TMP/repo/setup_script/start-python.sh"
: > "$TMP/repo/setup_script/.env.runtime"

pick() {   # pick <目标文件名>  -> 打印脚本挑中的 jar 名
  rm -f "$TMP"/repo/pro-business-api/target/*.jar*
  case "$1" in
    none) ;;
    single) : > "$TMP/repo/pro-business-api/target/pro-business-api-1.0.jar" ;;
    both)
      : > "$TMP/repo/pro-business-api/target/pro-business-api-1.0.jar"
      : > "$TMP/repo/pro-business-api/target/pro-business-api-1.0.jar.original"
      ;;
  esac
  # 只跑到 "echo 启动" 之前：把 exec java 换成 echo，避免真的去执行
  # probe.sh 必须落在真正的 setup_script 目录里，否则 HERE 解析错、相对路径全歪
  sed 's/^exec java -jar/echo JARPICK:/' "$TMP/repo/setup_script/start-java.sh" \
    > "$TMP/repo/setup_script/probe.sh"
  bash "$TMP/repo/setup_script/probe.sh" 2>&1 | grep '^JARPICK:' | sed 's/^JARPICK: *//'
}

r="$(pick single)"
case "$r" in
  *pro-business-api-1.0.jar) ok "单 jar 时挑中 pro-business-api-1.0.jar" ;;
  *) bad "单 jar 时挑错: [$r]" ;;
esac

r="$(pick both)"
case "$r" in
  *pro-business-api-1.0.jar) ok "jar + jar.original 时只挑 .jar（没挑 .original）" ;;
  *.original) bad "挑中了 .jar.original" ;;
  *) bad "双 jar 时挑错: [$r]" ;;
esac

r="$(pick none)"
case "$r" in
  "") ok "无 jar 时不误启动（走 exit 1 分支）" ;;
  *) bad "无 jar 时居然挑到: [$r]" ;;
esac

# ---------------------------------------------------------------------------
head_ "2. 渲染 .env.runtime 并 source 它"

awk 'index($0, "ENV_FILE\" <<EOF") {f=1; next} f && $0 == "EOF" {exit} f {print}' \
  "$SETUP" > "$TMP/env-body.txt"
grep -m1 '^JDBC_URL=' "$SETUP" > "$TMP/jdbc.sh"

{
  printf '%s\n' \
    'DB_NAME="RuoYi"' 'DB_USER="gaussdb"' 'DB_PASSWORD="${SELFTEST_DB_PASSWORD:-}"' \
    'DB_HOST="127.0.0.1"' 'DB_PORT="5432"' \
    'REDIS_HOST="127.0.0.1"' 'REDIS_PORT="6379"' 'REDIS_PASSWORD=""'
  cat "$TMP/jdbc.sh"
  printf '%s\n' 'ENV_FILE="'"$TMP"'/.env.runtime"' 'umask 077' \
    'cat > "$ENV_FILE" <<EOF'
  cat "$TMP/env-body.txt"
  printf '%s\n' 'EOF' 'chmod 600 "$ENV_FILE"'
} > "$TMP/render.sh"

if bash "$TMP/render.sh" && [ -s "$TMP/.env.runtime" ]; then
  ok ".env.runtime 渲染成功"
else
  bad ".env.runtime 渲染失败"
fi

if bash -n "$TMP/.env.runtime"; then ok ".env.runtime 语法正确"; else bad ".env.runtime 语法错误"; fi

if ( set -u; . "$TMP/.env.runtime" ) >/dev/null 2>&1; then
  ok ".env.runtime 可在 set -u 下 source"
else
  bad ".env.runtime 无法 source"
fi

url="$( ( . "$TMP/.env.runtime"; printf '%s' "$SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL" ) )"
case "$url" in
  jdbc:postgresql://127.0.0.1:5432/RuoYi\?*) ok "URL 以 jdbc:postgresql://127.0.0.1:5432/RuoYi? 开头" ;;
  *) bad "URL 不正确: [$url]" ;;
esac

usr="$( ( . "$TMP/.env.runtime"; printf '%s' "$SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME" ) )"
[ "$usr" = "gaussdb" ] && ok "username=gaussdb" || bad "username 错误: [$usr]"

pwd_="$( ( . "$TMP/.env.runtime"; printf '%s' "$SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD" ) )"
[ "$pwd_" = "" ] && ok "password 为空（由外部环境变量注入）" || bad "password 应为空（占位符化后不得内置明文）: [$pwd_]"

for _ in 1; do
  # URL 里的 & 必须被单引号保护住，否则 source 时会被当成后台执行符
  if grep -q "^export SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL='.*&.*'$" "$TMP/.env.runtime"; then
    ok "URL 被单引号包裹（& 不会截断语句）"
  else
    bad "URL 没有被单引号包裹"
  fi
done

# ---------------------------------------------------------------------------
head_ "3. JDK 版本识别（决定是否要装 JDK 8）"

JAWK="$(grep -m1 'awk -F' "$SETUP")"
mkdir -p "$TMP/bin"
fake_java() {
  printf '#!/usr/bin/env bash\nprintf %%s\\\\n %s >&2\n' "'openjdk version \"$1\"'" > "$TMP/bin/java"
  chmod +x "$TMP/bin/java"
}
jv() { ( PATH="$TMP/bin:$PATH"; eval "$JAWK" ); }

fake_java "1.8.0_402";  v="$(jv)"; [ "$v" = "8" ]  && ok '1.8.0_402 -> 8'  || bad "1.8.0_402 -> [$v]"
fake_java "17.0.2";     v="$(jv)"; [ "$v" = "17" ] && ok '17.0.2    -> 17' || bad "17.0.2    -> [$v]"
fake_java "21";         v="$(jv)"; [ "$v" = "21" ] && ok '21        -> 21' || bad "21        -> [$v]"

# ---------------------------------------------------------------------------
head_ "4. set -u 下的数组展开（空数组不能报 unbound variable）"

argc() { printf '%s' "$#"; }

REDIS_CLI_AUTH=()
n="$( argc ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} )"
[ "$n" = "0" ] && ok "空 REDIS_CLI_AUTH 展开为 0 个参数" || bad "空 REDIS_CLI_AUTH 展开为 $n 个参数"

REDIS_CLI_AUTH=(-a "p w" --no-auth-warning)
n="$( argc ${REDIS_CLI_AUTH[@]+"${REDIS_CLI_AUTH[@]}"} )"
[ "$n" = "3" ] && ok "有密码时展开为 3 个参数（含空格的密码不被拆开）" || bad "有密码时展开为 $n 个参数"

ORIG_ARGS=()
n="$( argc ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} )"
[ "$n" = "0" ] && ok "空 ORIG_ARGS 展开为 0 个参数" || bad "空 ORIG_ARGS 展开为 $n 个参数"

ORIG_ARGS=("--skip-db" "--db-password" "a b")
n="$( argc ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} )"
[ "$n" = "3" ] && ok "ORIG_ARGS 原样透传 3 个参数" || bad "ORIG_ARGS 透传了 $n 个参数"

# ---------------------------------------------------------------------------
head_ "5. apply_sql：DDL 有报错时也必须返回 0（否则 set -e 会中止安装）"

awk '/^    apply_sql\(\) \{$/{f=1} f{print} f && /^    \}$/{exit}' "$SETUP" > "$TMP/apply_sql.sh"
if [ -s "$TMP/apply_sql.sh" ]; then
  ok "apply_sql 已提取（$(wc -l < "$TMP/apply_sql.sh" | tr -d ' ') 行）"
else
  bad "apply_sql 提取失败"
fi

DB_HOST=x DB_PORT=1 DB_USER=u DB_NAME=d
cat > "$TMP/bin/psql" <<'FAKE'
#!/usr/bin/env bash
# 假 psql：把 $FAKE_ERRORS 行 "psql:...: ERROR: ..." 打到 stdout
for ((i = 0; i < ${FAKE_ERRORS:-0}; i++)); do
  echo "psql:$3: ERROR: relation \"jl_data01.nope\" does not exist"
done
exit 0
FAKE
chmod +x "$TMP/bin/psql"

run_apply() {   # run_apply <错误行数>
  (
    export PATH="$TMP/bin:$PATH"
    ok()   { printf 'OK %s\n' "$*"; }
    warn() { printf 'WARN %s\n' "$*"; }
    dim()  { printf 'DIM %s\n' "$*"; }
    FAKE_ERRORS="$1"
    export FAKE_ERRORS
    # shellcheck disable=SC1090
    . "$TMP/apply_sql.sh"
    : > "$TMP/dummy.sql"
    apply_sql "$TMP/dummy.sql" "dummy.sql"
    printf 'RC=%s\n' "$?"
  )
}

out="$(run_apply 0)"
case "$out" in
  *RC=0*) ok "无报错时 apply_sql 返回 0" ;;
  *) bad "无报错时 apply_sql 返回值异常: $out" ;;
esac

out="$(run_apply 2)"
case "$out" in
  *RC=0*) ok "有 2 条报错时 apply_sql 仍返回 0（不会中止安装）" ;;
  *) bad "有报错时 apply_sql 返回非 0: $out" ;;
esac
case "$out" in
  *WARN*) ok "有报错时打印了告警" ;;
  *) bad "有报错时没打印告警" ;;
esac

# ---------------------------------------------------------------------------
printf '\n==============================\n'
printf 'PASS = %s   FAIL = %s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
