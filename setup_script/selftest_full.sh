#!/usr/bin/env bash
# 全流程集成测试（step 1 -> step 8 -> 汇总）
#
# 唯一对 setup.sh 做的改动：把它硬编码的 /etc/os-release 换成临时文件
# （Git Bash 没有 /etc/os-release，Linux 上必然存在）。其余每一行都原样执行。
# 再配合一个假 apt-get（Windows 没有 apt），让脚本能真正跑到第 8 步：
#   真装 JDK 检测（本机确实装了 JDK 8）-> 生成 .env.runtime -> 生成两个启动脚本 -> 打印汇总
set -uo pipefail

SETUP="${1:?用法: _t_full.sh <setup.sh 路径>}"
REPO="$(cd "$(dirname "$SETUP")/.." && pwd)"
VARIANT="$REPO/_t_variant"
TMP="$(mktemp -d)"
PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$*"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$*"; }

cleanup() { rm -rf "$VARIANT" "$TMP"; }
trap cleanup EXIT

rm -rf "$VARIANT"
mkdir -p "$VARIANT" "$TMP/bin"

# 假 os-release
cat > "$VARIANT/fake-os-release" <<'EOF'
ID=ubuntu
VERSION_CODENAME=noble
PRETTY_NAME="Ubuntu 24.04 LTS (simulated by Git Bash test)"
EOF

# 假 apt-get：本机没有 apt，这里直接返回成功，不安装任何东西
cat > "$TMP/bin/apt-get" <<'EOF'
#!/usr/bin/env bash
echo "[stub apt-get] $*"
exit 0
EOF
cat > "$TMP/bin/apt-cache" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
# 假 id：报告 uid=0，其他子命令透传（让脚本越过 root 检查）
cat > "$TMP/bin/id" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "-u" ]; then
  echo 0
else
  exec /usr/bin/id "$@"
fi
EOF
chmod +x "$TMP/bin/apt-get" "$TMP/bin/apt-cache" "$TMP/bin/id"

# 只改 os-release 的路径，其他原样
sed "s#/etc/os-release#${VARIANT}/fake-os-release#g" "$SETUP" > "$VARIANT/setup.sh"

echo "=== 全流程集成测试 ==="
echo "  setup.sh 副本: $VARIANT/setup.sh"
echo "  参数: 保留 JDK 检测，跳过 python/db/redis/schema/build/verify"
echo

out="$( PATH="$TMP/bin:$PATH" bash "$VARIANT/setup.sh" \
        --skip-python --skip-db --skip-redis --skip-schema \
        --no-build-java --no-verify 2>&1 )"
rc=$?
printf '%s\n' "$out" | sed 's/^/    | /'
printf '\n'

[ "$rc" -eq 0 ] && ok "整体退出码 0" || bad "退出码 $rc"

for t in "1/8" "2/8" "3/8" "4/8" "5/8" "6/8" "7/8" "8/8"; do
  case "$out" in
    *"$t"*) ok "走到了 step $t" ;;
    *) bad "缺少 step $t" ;;
  esac
done

case "$out" in
  *"已存在 JDK 8"*) ok "识别出本机已有 JDK 8（没有去装）" ;;
  *"JDK 8 已安装"*) ok "装了 JDK 8" ;;
  *) bad "JDK 8 检测分支没走到" ;;
esac
if printf '%s' "$out" | grep -q 'JAVA_HOME=/'; then
  ok "JAVA_HOME 解析成功（$(printf '%s' "$out" | grep -o 'JAVA_HOME=/[^ ]*' | head -n1)）"
else
  bad "JAVA_HOME 未解析"
fi
case "$out" in
  *"跳过 Python"*|*"3/8 跳过"*) ok "按参数跳过了 Python" ;;
  *) bad "没有跳过 Python" ;;
esac
case "$out" in
  *"意外失败于第"*) bad "触发了 ERR trap: $(printf '%s' "$out" | grep '意外失败于第' | head -n1)" ;;
  *) ok "全程没有触发 ERR trap" ;;
esac

echo
echo "--- 产物校验 ---"
ENVF="$VARIANT/.env.runtime"
[ -s "$ENVF" ] && ok "已生成 .env.runtime" || bad ".env.runtime 缺失"

if bash -n "$ENVF" 2>/dev/null; then ok ".env.runtime 语法正确"; else bad ".env.runtime 语法错误"; fi
if ( set -u; . "$ENVF" ) >/dev/null 2>&1; then ok ".env.runtime 可 source"; else bad ".env.runtime 不可 source"; fi

for k in SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL \
         SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME \
         SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD \
         SPRING_REDIS_HOST SPRING_REDIS_PORT JAVA_HOME; do
  grep -q "$k=" "$ENVF" && ok ".env.runtime 含 $k" || bad ".env.runtime 缺 $k"
done
grep -q "SPRING_REDIS_PASSWORD" "$ENVF" \
  && bad ".env.runtime 不该出现 SPRING_REDIS_PASSWORD（默认无密码）" \
  || ok ".env.runtime 无密码时未写入 SPRING_REDIS_PASSWORD"

url="$( (. "$ENVF"; printf '%s' "$SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL") )"
case "$url" in
  "jdbc:postgresql://127.0.0.1:5432/RuoYi?"*) ok "URL 已指向本机 RuoYi: ${url:0:52}..." ;;
  *) bad "URL 不对: $url" ;;
esac

for s in start-python.sh start-java.sh; do
  if [ -s "$VARIANT/$s" ]; then
    ok "已生成 $s（$(wc -l < "$VARIANT/$s" | tr -d ' ') 行）"
    bash -n "$VARIANT/$s" && ok "$s 语法正确" || bad "$s 语法错误"
    [ -x "$VARIANT/$s" ] && ok "$s 可执行" || bad "$s 不可执行"
  else
    bad "$s 缺失"
  fi
done

case "$out" in
  *"启动 Python 侧"*"启动 Java 侧"*) ok "汇总信息完整打印" ;;
  *) bad "汇总信息缺失" ;;
esac
case "$out" in
  *"全部自检通过"*|*"自检"*) ok "汇总/自检段落有输出" ;;
  *) bad "汇总/自检段落无输出" ;;
esac

if [ -s "$VARIANT/setup.log" ]; then
  ok "setup.log 落盘（$(wc -l < "$VARIANT/setup.log" | tr -d ' ') 行）"
else
  bad "setup.log 未落盘"
fi

printf '\nPASS = %s   FAIL = %s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
