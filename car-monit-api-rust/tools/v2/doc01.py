# -*- coding: utf-8 -*-
"""渲染 docs/verify/01-接口清单对比.md（数据源 .run/verify2/inventory.json，可重复生成）。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUST_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

INV = json.load(open(os.path.join(H.RUN_DIR, 'inventory.json'), encoding='utf-8'))
OUT = os.path.join(RUST_ROOT, 'docs', 'verify', '01-接口清单对比.md')

# 人工确认过的「同义路由」：Java 用多个具体路径，Rust 用一个带约束的通配路径
SYNONYMS = [
    ('/api/v1/large/{snapshot,fee,trail}', '/api/v1/large/{ds}',
     'Rust 用 `{ds}` 通配覆盖 3 个 Java 路径；未知 ds 的行为必须与 Java 的 404/400 一致（见 query 阶段）'),
    ('/progressive/{snapshotflow,feerecords,trailfitting}/list', '/progressive/{table}/list',
     '同上，Rust 通配 3 个表名；未知表名的错误体需与 Java 一致'),
]
RUST_ONLY = [
    ('/healthz', 'Rust 新增，只读无副作用；Java 未接 Actuator'),
    ('/readyz', 'Rust 新增，含 DB 连通性探测'),
    ('/health', 'Rust 新增，等价 /readyz'),
]


def _covers(pattern, concrete):
    a = pattern.strip('/').split('/')
    b = concrete.strip('/').split('/')
    return len(a) == len(b) and all(x == '*' or x == y for x, y in zip(a, b))


def norm(p):
    return '/'.join('*' if (s.startswith('{') and s.endswith('}')) else s for s in p.strip('/').split('/'))


def main():
    java = INV['java_endpoints']
    rust = INV['rust_endpoints']
    rlist = [norm(r['path']) for r in rust]
    rmap = {}
    for r in rust:
        rmap.setdefault(norm(r['path']), []).append(r)

    def match(pattern):
        """Rust 侧的 {x} 通配段能覆盖 Java 的具体段（/api/v1/large/{ds} ↔ /api/v1/large/snapshot）。"""
        segs = pattern.strip('/').split('/')
        for rp in rlist:
            rsegs = rp.strip('/').split('/')
            if len(rsegs) != len(segs):
                continue
            if all(a == '*' or a == b for a, b in zip(rsegs, segs)):
                return True
        return False

    lines = []
    A = lines.append
    A('# 阶段1 · 接口清单静态对比')
    A('')
    A('- 数据源：`pro-business-api/src/main/java/com/ruoyi/base/controller/*.java`（剥离注释后解析注解）')
    A('  ↔ `car-monit-api-rust/src/router.rs`（解析 `.route(...)` 注册表）；生成脚本 `tools/v2/inventory.py`。')
    A('- 计数：Java 有效端点 **%d** 个，Rust 注册路由 **%d** 条（通配路由一条覆盖多个 Java 端点，'
      'Rust 另有 %d 条健康检查路由）。' % (len(java), len(rust), len(RUST_ONLY)))
    A('')
    A('## 1. 路径等价性')
    A('')
    A('| Java 端点 | Rust 路由 | 说明 |')
    A('|---|---|---|')
    for j, r, note in SYNONYMS:
        A('| `%s` | `%s` | %s |' % (j, r, note))
    A('')
    A('## 2. Rust 独有路由')
    A('')
    A('| 路由 | 说明 |')
    A('|---|---|')
    for p, note in RUST_ONLY:
        A('| `%s` | %s |' % (p, note))
    A('')
    A('## 3. Java 端点全表（%d 条）' % len(java))
    A('')
    A('「Rust 覆盖」按段模式匹配（`{任意}` 视为同一段）；`参数绑定` 列出 Java 侧通过实体自动绑定的类型。')
    A('')
    A('| # | 方法 | 路径 | Java 方法 | 返回类型 | 绑定 | Rust 覆盖 |')
    A('|---|---|---|---|---|---|---|')
    missing = []
    for i, r in enumerate(sorted(java, key=lambda x: (x['path'], x['method'])), 1):
        key = norm(r['path'])
        cov = [x for x in rmap.get(key, []) if x['method'] in (r['method'], 'ANY')]
        if not cov and match(key):
            cov = [{'path': next(rp for rp in rlist if _covers(rp, key))}]
        bind = r['bind_entity'] or ('@RequestBody' if any(
            p['kind'] == 'RequestBody' for p in r['params']) else '-')
        rp = cov[0]['path'] if cov else '—'
        if not cov:
            missing.append(r)
        A('| %d | %s | `%s` | `%s` | `%s` | %s | `%s` |' % (
            i, r['method'], r['path'], r['java_method'], r['return_type'], bind, rp))
    A('')
    A('## 4. 未被 Rust 覆盖的 Java 端点')
    A('')
    if missing:
        A('| 方法 | 路径 | Java 方法 |')
        A('|---|---|---|')
        for r in missing:
            A('| %s | `%s` | `%s` |' % (r['method'], r['path'], r['java_method']))
    else:
        A('无（全部 Java 端点在 Rust 侧都有可达路由）。')
    A('')
    A('## 5. Java 源码里被注释掉、Rust 侧同样不注册的端点')
    A('')
    A('`SysUtilController.java:39-70` 是一段块注释，包住了 `POST /base/sysutil/syncTrack` 与')
    A('`POST /base/sysutil/syncSuspiciousCar`。这两个路径在运行中的 Java 服务上返回 404，Rust 侧不注册，'
      '行为一致。（旧版清点脚本没剥注释，会把它们误记为 Java 端点。）')
    A('')
    A('## 6. 入参绑定面（后续阶段的用例来源）')
    A('')
    A('| Controller 基路径 | 绑定实体 | 实体字段数 | Mapper `<if>` 可过滤字段数 |')
    A('|---|---|---|---|')
    seen = set()
    for r in java:
        if not r['bind_entity']:
            continue
        base = '/'.join(r['path'].strip('/').split('/')[:-1])
        if base in seen:
            continue
        seen.add(base)
        mapper = r['bind_entity'] + 'Mapper'
        A('| `%s` | %s | %d | %d |' % (
            base, r['bind_entity'], len(r['entity_fields']),
            len(INV['mapper_filters'].get(mapper, []))))
    A('')
    A('> 过滤字段以 Mapper XML 的 `<if test>` 为准（Spring 会把任意实体字段当查询参数绑定，')
    A('> 但只有 XML 里出现的字段才真正影响 SQL），据此生成 `filters` 阶段的逐字段矩阵。')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('written %s (%d lines, missing=%d)' % (OUT, len(lines), len(missing)))


if __name__ == '__main__':
    main()
