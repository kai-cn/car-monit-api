# -*- coding: utf-8 -*-
"""静态清单抽取（v2）：Java Controller ↔ Rust router。

与旧版差异：
  * 先剥离 Java 注释（SysUtilController 的 syncTrack/syncSuspiciousCar 是块注释掉的，不能算端点）
  * 路径中的 {xxx} 变量段统一按段名归一，避免 {agentPk}/{bigId} 与 {id} 误判为「缺失」
  * 从 Mapper XML 的 <if test> 抽取每表可过滤字段，作为动态用例矩阵的字段来源
产物: .run/verify2/inventory.json
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUST_ROOT = os.path.dirname(os.path.dirname(HERE))
JAVA_ROOT = os.path.join(os.path.dirname(RUST_ROOT), 'pro-business-api', 'src', 'main', 'java')
CTL_DIR = os.path.join(JAVA_ROOT, 'com', 'ruoyi', 'base', 'controller')
DOM_DIR = os.path.join(JAVA_ROOT, 'com', 'ruoyi', 'base', 'domain')
XML_DIR = os.path.join(JAVA_ROOT, 'com', 'ruoyi', 'base', 'mapper', 'xml')
COMMON_DIR = os.path.join(os.path.dirname(RUST_ROOT), 'pro-base-common', 'src', 'main', 'java')
RUST_SRC = os.path.join(RUST_ROOT, 'src')
OUT_DIR = os.path.join(RUST_ROOT, '.run', 'verify2')


def read(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def strip_java_comments(src):
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == c:
                    break
                j += 1
            out.append(src[i:j + 1])
            i = j + 1
            continue
        if src.startswith('/*', i):
            e = src.find('*/', i + 2)
            i = n if e < 0 else e + 2
            out.append(' ')
            continue
        if src.startswith('//', i):
            e = src.find('\n', i)
            i = n if e < 0 else e
            out.append(' ')
            continue
        out.append(c)
        i += 1
    return ''.join(out)


MAP_ANN = re.compile(r'@(Get|Post|Put|Delete|Patch|Request)Mapping(?:\(\s*(?:value\s*=\s*)?\{?\s*"([^"]*)"[^)]*\)|\s*"([^"]*)")?')
CLASS_ANN = re.compile(r'@RequestMapping\(\s*(?:value\s*=\s*)?"([^"]*)"')
METHOD_RE = re.compile(r'public\s+(?:(?:static|final|synchronized)\s+)*([\w<>,\s\[\]\.?]+?)\s+(\w+)\s*\(')


def match_params(src, open_idx):
    """从 '(' 开始做括号配平，返回 (参数串, 其后是否有 '{')。"""
    depth, i, n = 0, open_idx, len(src)
    while i < n:
        c = src[i]
        if c in '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                rest = src[i + 1:i + 200]
                return src[open_idx + 1:i], bool(re.match(r'\s*(?:throws\s+[\w,\s\.]+?)?\{', rest))
        i += 1
    return None, False
PARAM_ANN_RE = re.compile(r'@(RequestParam|PathVariable|RequestBody|RequestHeader|RequestPart)(?:\(([^)]*)\))?\s+(?:final\s+)?([\w<>,\s\.]+?)\s+(\w+)')
NAME_ATTR = re.compile(r'(?:value\s*=\s*)?"([^"]*)"')
FIELD_RE = re.compile(r'(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?([\w<>,\s\[\]\.?]+?)\s+(\w+)\s*(?:=[^;]*)?;')


def split_params(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '<([':
            depth += 1
        elif ch in '>)]':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


ENTITY_SKIP = {'serialVersionUID', 'log'}
_cache = {}


def resolve_entity(name, depth=0):
    key = (name, depth)
    if name in _cache and depth == 0:
        return _cache[name]
    if depth > 5:
        return []
    for d in (DOM_DIR, os.path.join(COMMON_DIR, 'com', 'ruoyi', 'common', 'core', 'domain'),
              os.path.join(COMMON_DIR, 'com', 'ruoyi', 'common', 'core', 'page'),
              os.path.join(COMMON_DIR, 'com', 'ruoyi', 'common', 'web', 'domain')):
        p = os.path.join(d, name + '.java')
        if os.path.exists(p):
            break
    else:
        return []
    src = strip_java_comments(read(p))
    fields = [{'name': m.group(2), 'type': m.group(1).strip()}
              for m in FIELD_RE.finditer(src) if m.group(2) not in ENTITY_SKIP]
    pm = re.search(r'class\s+\w+\s+extends\s+(\w+)', src)
    if pm:
        seen = {f['name'] for f in fields}
        for f in resolve_entity(pm.group(1), depth + 1):
            if f['name'] not in seen:
                fields.append(f)
                seen.add(f['name'])
    if depth == 0:
        _cache[name] = fields
    return fields


def parse_controller(path):
    src = strip_java_comments(read(path))
    cm = CLASS_ANN.search(src)
    base = cm.group(1) if cm else ''
    routes = []
    # 逐个注解定位，向后找最近的方法签名
    for m in MAP_ANN.finditer(src):
        if m.group(0).startswith('@RequestMapping') and m.start() < src.find('class '):
            continue
        verb = m.group(1).upper()
        sub = m.group(2) or m.group(3) or ''
        tail = src[m.end():m.end() + 6000]
        sm = METHOD_RE.search(tail)
        if not sm:
            continue
        ret, mname = sm.group(1).strip(), sm.group(2)
        params, has_body = match_params(tail, sm.end() - 1)
        if params is None or not has_body:
            continue
        entries, bind = [], None
        for p in split_params(params):
            pm = PARAM_ANN_RE.search(p)
            if pm:
                nm = NAME_ATTR.search(pm.group(2) or '')
                entries.append({'kind': pm.group(1), 'explicit_name': nm.group(1) if nm else None,
                                'type': pm.group(3).strip(), 'java_name': pm.group(4)})
            else:
                qm = re.match(r'^(?:final\s+)?([\w<>,\s\.]+?)\s+(\w+)$', p.strip())
                if qm and qm.group(1).strip()[0].isupper():
                    bind = qm.group(1).strip()
        full = base + sub if sub.startswith('/') or not base else base + '/' + sub
        routes.append({
            'path': re.sub(r'//+', '/', full),
            'method': 'ANY' if verb == 'REQUEST' else verb,
            'java_method': mname, 'return_type': ret,
            'params': entries, 'bind_entity': bind,
            'entity_fields': resolve_entity(bind) if bind else [],
        })
    return base, routes


def norm_path(p):
    """把 {var} 段统一成 *，用于路径等价性比较。"""
    return '/'.join('*' if (s.startswith('{') and s.endswith('}')) else s for s in p.strip('/').split('/'))


def mapper_filters():
    """Mapper XML <if test="x ..."> → 可过滤字段（按 XML 文件名）。"""
    out = {}
    if not os.path.isdir(XML_DIR):
        return out
    for fn in os.listdir(XML_DIR):
        if not fn.endswith('.xml'):
            continue
        src = read(os.path.join(XML_DIR, fn))
        names = []
        for m in re.finditer(r'<if\s+test="([^"]+)"', src):
            t = m.group(1)
            for v in re.findall(r"([A-Za-z_]\w*)\s*(!=|==|&gt;|&lt;|\s+like\s+|\s+in\b)", t):
                n = v[0]
                if n not in names and n != 'null':
                    names.append(n)
        out[fn[:-4]] = names
    return out


ROUTE_RE = re.compile(r'\.route\(\s*"([^"]+)"\s*,\s*(get|post|put|delete|patch|any_method)\s*\(\s*([\w:]+)\s*\)')


def parse_rust_routes():
    src = read(os.path.join(RUST_SRC, 'router.rs'))
    out = []
    for m in ROUTE_RE.finditer(src):
        out.append({'path': m.group(1), 'method': m.group(2).upper().replace('ANY_METHOD', 'ANY'),
                    'handler': m.group(3)})
    seen, uniq = set(), []
    for r in out:
        k = (r['path'], r['method'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return sorted(uniq, key=lambda r: (r['path'], r['method']))


def parse_rust_structs():
    structs = {}
    for root, _, files in os.walk(RUST_SRC):
        for fn in files:
            if not fn.endswith('.rs'):
                continue
            src = read(os.path.join(root, fn))
            for m in re.finditer(r'#\[derive\([^)]*\)\]\s*(?:#\w+[^\n]*\n)*pub struct (\w+)[^{}]*\{(.*?)\n\}', src, re.S):
                name, body = m.group(1), m.group(2)
                fields = []
                for fm in re.finditer(r'(?:#\[[^\]]*\]\s*)*pub\s+(\w+)\s*:\s*([^,\n]+)', body):
                    fields.append({'field': fm.group(1), 'ty': fm.group(2).strip().rstrip(','),
                                   'attrs': re.findall(r'#\[(serde\([^\]]*\)|default)\]', body[:fm.start()][-(fm.start() and 200):])})
                structs[name] = {'fields': fields, 'file': fn}
    return structs


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    java = []
    for fn in sorted(os.listdir(CTL_DIR)):
        if not fn.endswith('.java'):
            continue
        base, routes = parse_controller(os.path.join(CTL_DIR, fn))
        for r in routes:
            r['controller'] = fn[:-5]
            r['base'] = base
        java.extend(routes)
    rust = parse_rust_routes()

    jnorm = {}
    for r in java:
        jnorm.setdefault((r['method'], norm_path(r['path'])), []).append(r)
    rnorm = {}
    for r in rust:
        rnorm.setdefault((r['method'], norm_path(r['path'])), []).append(r)
    def expand(ms):
        # Spring 的 @GetMapping 只收 GET；ANY 收全部
        return {'GET', 'POST', 'PUT', 'DELETE'} if ms == 'ANY' else {ms}

    jkeys = {(m, p) for (mt, p), rs in jnorm.items() for m in expand(mt) for rs in [rs]}
    rkeys = {(m, p) for (mt, p), rs in rnorm.items() for m in expand(mt) for rs in [rs]}

    only_java = sorted(jkeys - rkeys)
    only_rust = sorted(rkeys - jkeys)

    result = {
        'java_endpoints': java,
        'rust_endpoints': rust,
        'paths_only_java': [list(k) for k in only_java],
        'paths_only_rust': [list(k) for k in only_rust],
        'mapper_filters': mapper_filters(),
        'rust_structs': parse_rust_structs(),
        'counts': {'java': len(java), 'rust': len(rust)},
    }
    with open(os.path.join(OUT_DIR, 'inventory.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print('java=%d rust=%d' % (len(java), len(rust)))
    print('-- only java --')
    for k in only_java:
        print('  ', k)
    print('-- only rust --')
    for k in only_rust:
        print('  ', k)
    print('-- java path detail --')
    for r in java:
        print('   %-6s %-45s %s%s' % (r['method'], r['path'], r['java_method'],
                                      '  bind=' + r['bind_entity'] if r['bind_entity'] else ''))


if __name__ == '__main__':
    sys.exit(main())
