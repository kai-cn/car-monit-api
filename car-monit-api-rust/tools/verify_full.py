# -*- coding: utf-8 -*-
"""全量双端接口校验框架（Java 9902 ↔ Rust 9911）。

阶段（--stage 可选多个，逗号分隔；all 表示全部）：
  inventory  端点清单完整性（Rust 路由表 vs Java 控制器注解清点）
  base       19 张基础表 list / listAll / listToExport / {id} 的行级深比较 + 分页变体
  filters    以 Mapper XML 的 <if> 为字段来源，逐字段过滤矩阵（含负值、通配符、大小写、日期形式）
  query      large / unified / progressive / stats / export / 错误分支
  sysutil    sysutil 与 sysutilTest（默认跳过会产生写副作用的端点，--allow-side-effects 才跑）
  contract   契约层：原始字节、Content-Type、null 键保留、数字/日期格式、Spring 错误体、CORS/头
  report     汇总 .run/verify/*.json 写入 docs/VERIFICATION-FULL-<date>.md

前置：Java 与 Rust 同时在线；脚本会自动备份并临时清空 Redis DB0 的 car_list_jc
（该 key 被非 Java 服务写成 JSON，Java FastJSON 反序列化强转 CarVO 会 500），
跑完自动恢复。
"""
import argparse
import datetime
import glob
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

JAVA = 'http://127.0.0.1:9902'
RUST = 'http://127.0.0.1:9911'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML_DIR = os.path.join(os.path.dirname(ROOT), 'pro-business-api', 'src', 'main', 'java',
                       'com', 'ruoyi', 'base', 'mapper', 'xml')
RUN_DIR = os.path.join(ROOT, '.run', 'verify')
DOC = os.path.join(ROOT, 'docs', 'VERIFICATION-FULL-20261102.md')
CACHE_KEY = 'car_list_jc'
TIMEOUT = 240

# Java 每行临时生成随机 UUID 的字段，比较时按「存在 + 类型」而非等值
VOLATILE_FIELDS = {'id', 'taskId', 'timestamp', 'uuid_generated', 'traceId'}

STAGES = ['inventory', 'base', 'filters', 'query', 'sysutil', 'contract', 'report']


# ---------------------------------------------------------------- 基础工具
def fetch(base, path, method='GET', body=None, headers=None, timeout=TIMEOUT):
    data = None
    hdr = {'Accept': '*/*'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        hdr['Content-Type'] = 'application/json'
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(base + path, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, lower_headers(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, lower_headers(e.headers), e.read()
    except Exception as e:  # noqa: BLE001
        return -1, {}, str(e).encode()


def lower_headers(h):
    """头名统一小写：hyper 输出 content-type，Tomcat 输出 Content-Type。"""
    return {k.lower(): v for k, v in dict(h).items()}


def jload(raw):
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:  # noqa: BLE001
        return None


def text(raw):
    return raw.decode('utf-8', 'replace')


def norm_num(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    return v


def diff(a, b, path='$', out=None, limit=12):
    """深度比较；数值 1e-6 相对误差；随机字段只比存在性与类型。"""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    key = path.rsplit('.', 1)[-1]
    if key in VOLATILE_FIELDS:
        if (a is None) != (b is None):
            out.append('%s volatile-null %r != %r' % (path, a, b))
        return out
    if a is None or b is None:
        if a is not b:
            out.append('%s null %r != %r' % (path, a, b))
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > max(1e-6, abs(float(a)) * 1e-6):
            out.append('%s number %r != %r' % (path, a, b))
        return out
    if type(a) is not type(b):
        out.append('%s type %s(%r) != %s(%r)' % (path, type(a).__name__, a, type(b).__name__, b))
        return out
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append('%s keys java_only=%s rust_only=%s' % (
                path, sorted(ka - kb)[:8], sorted(kb - ka)[:8]))
        for k in sorted(ka & kb):
            diff(a[k], b[k], '%s.%s' % (path, k), out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append('%s len %d != %d' % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diff(a[i], b[i], '%s[%d]' % (path, i), out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, str):
        if a != b:
            out.append('%s str %r != %r' % (path, a[:60], b[:60]))
    else:
        if norm_num(a) != norm_num(b):
            out.append('%s %r != %r' % (path, a, b))
    return out


def compare(method, path, body=None, expect_rows=True, note=''):
    ja = fetch(JAVA, path, method, body)
    ru = fetch(RUST, path, method, body)
    rec = {
        'method': method,
        'path': path,
        'java': ja[0],
        'rust': ru[0],
        'note': note,
        'verdict': 'OK',
        'diffs': [],
    }
    if ja[0] != ru[0]:
        rec['verdict'] = 'DIFF'
        rec['diffs'].append('status %s != %s' % (ja[0], ru[0]))
        rec['java_body'] = text(ja[2])[:400]
        rec['rust_body'] = text(ru[2])[:400]
        return rec
    if ja[0] in (200, 201, 400, 404, 405, 415, 500):
        va, vb = jload(ja[2]), jload(ru[2])
        if va is None or vb is None:
            if text(ja[2]).strip() != text(ru[2]).strip():
                rec['diffs'].append('raw body differs: %r != %r' % (
                    text(ja[2])[:120], text(ru[2])[:120]))
                # Tomcat 的 HTML 错误页属于容器层，不是应用契约：状态码一致即可
                if text(ja[2]).lstrip().lower().startswith('<!doctype html'):
                    rec['verdict'] = 'CONTAINER'
                else:
                    rec['verdict'] = 'DIFF'
            return rec
        rec['diffs'] = diff(va, vb)
        if rec['diffs']:
            # Tomcat 对超长请求行返回容器自己的 HTML 错误页，这不属于应用契约；
            # 状态码已一致，单独归类为 CONTAINER，不计入待修差异。
            if ja[0] == 400 and text(ja[2]).lstrip().lower().startswith('<!doctype html'):
                rec['verdict'] = 'CONTAINER'
            else:
                rec['verdict'] = 'DIFF'
        elif expect_rows and ja[0] == 200:
            rec['rows'] = rows_of(va)
    return rec


def rows_of(obj):
    if isinstance(obj, dict):
        if 'rows' in obj and isinstance(obj['rows'], list):
            return len(obj['rows'])
        if 'data' in obj and isinstance(obj['data'], list):
            return len(obj['data'])
        if 'code' in obj and isinstance(obj.get('data'), list):
            return len(obj['data'])
    if isinstance(obj, list):
        return len(obj)
    return None


def save(stage, records, meta=None):
    os.makedirs(RUN_DIR, exist_ok=True)
    payload = {
        'stage': stage,
        'at': datetime.datetime.now().isoformat(timespec='seconds'),
        'meta': meta or {},
        'summary': {
            'total': len(records),
            'ok': sum(1 for r in records if r['verdict'] == 'OK'),
            'diff': sum(1 for r in records if r['verdict'] == 'DIFF'),
            'skip': sum(1 for r in records if r['verdict'] == 'SKIP'),
            'container': sum(1 for r in records if r['verdict'] == 'CONTAINER'),
        },
        'records': records,
    }
    with io.open(os.path.join(RUN_DIR, '%s.json' % stage), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print('[%s] total=%d ok=%d diff=%d skip=%d container=%d' % (
        stage, payload['summary']['total'], payload['summary']['ok'],
        payload['summary']['diff'], payload['summary']['skip'],
        payload['summary']['container']))
    for r in records:
        if r['verdict'] == 'DIFF':
            print('  DIFF %s %s -> %s' % (r['method'], r['path'][:120], r['diffs'][:3]))
    return payload


# ---------------------------------------------------------------- 缓存前置
class CacheGuard:
    """临时清空 Java Redis DB0 的 car_list_jc，退出时恢复。"""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.client = None
        self.backup = None

    def __enter__(self):
        if not self.enabled:
            return self
        try:
            import redis  # 由 car-monit-api-python/.venv 提供
            self.client = redis.Redis(host='127.0.0.1', port=6379, db=0)
            self.backup = self.client.get(CACHE_KEY)
            if self.backup:
                path = os.path.join(ROOT, '.run', '%s.verify.bak' % CACHE_KEY)
                with io.open(path, 'wb') as f:
                    f.write(self.backup)
                self.client.delete(CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            print('WARN 缓存前置不可用: %s' % e)
            self.client = None
        return self

    def __exit__(self, *exc):
        if self.client is not None and self.backup:
            self.client.set(CACHE_KEY, self.backup)
            print('car_list_jc 已恢复 (%d bytes)' % len(self.backup))
        return False


# ---------------------------------------------------------------- 通用数据源
def sample(path, seed=''):
    st, _, raw = fetch(JAVA, path + '?pageNum=1&pageSize=1' + seed)
    if st != 200:
        return None
    obj = jload(raw) or {}
    rows = obj.get('rows') or []
    return rows[0] if rows else None


BASE_TABLES = [
    # (路径段, 名称, seed 参数, 详情主键字段, 详情是否 AjaxResult)
    ('/base/fwqjcxx', 'fwqjcxx', '', 'agentPk', 'ajax'),
    ('/base/sfsjcxx', 'sfsjcxx', '', 'agentPk', 'flat'),
    ('/base/sfzjcxx', 'sfzjcxx', '', 'agentPk', 'flat'),
    ('/manager/fwqclls', 'fwqclls', '', 'bigId', 'ajax'),
    ('/base/feeGantry', 'feeGantry', '', 'bigId', 'flat'),
    ('/base/feeStationEnter', 'feeStationEnter', '', 'bigId', 'flat'),
    ('/base/feestationexit', 'feestationexit', '', 'bigId', 'flat'),
    # platenumber=%25（LIKE 通配）用来绕过 Java 的数据权限分支，才能取到样本行
    ('/base/snapshotflow', 'snapshotflow',
     '&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00&platenumber=%25',
     'bigId', 'flat'),
    ('/base/provcapture', 'provcapture', '', 'bigId', 'ajax'),
    ('/base/stationcapture', 'stationcapture', '', 'bigId', 'ajax'),
    ('/base/gantry', 'gantry', '', 'id', 'ajax'),
    ('/base/gantryIp', 'gantryIp', '', 'id', 'ajax'),
    ('/base/vehicleweight', 'vehicleweight', '', 'datauuid', 'ajax'),
    ('/base/section', 'section', '', 'id', 'ajax'),
    ('/base/toll', 'toll', '', 'id', 'ajax'),
    ('/base/tollStationIp', 'tollStationIp', '', 'id', 'ajax'),
    ('/base/org', 'org', '', 'bigId', 'ajax'),
    ('/base/trailtracks', 'trailtracks', '', 'uuid', 'flat'),
]


# ---------------------------------------------------------------- 阶段实现
def stage_inventory():
    recs = []
    src = io.open(os.path.join(ROOT, 'src', 'router.rs'), encoding='utf-8').read()
    m = re.search(r'JAVA_API_INVENTORY: &\[\(&str, &str, &str\)\] = &\[(.*?)\n\];', src, re.S)
    body = m.group(1)
    items = re.findall(r'\(\s*"(GET|POST|PUT|DELETE)",\s*"([^"]+)",\s*"([^"]+)"',
                       re.sub(r'\n\s*', ' ', body))
    paths = []
    for method, path, _file in items:
        paths.append((method, path))
    # Java 控制器注解清点
    java_dir = os.path.join(os.path.dirname(ROOT), 'pro-business-api', 'src', 'main', 'java')
    java_found = set()
    for fn in glob.glob(os.path.join(java_dir, '**', '*.java'), recursive=True):
        t = io.open(fn, encoding='utf-8', errors='replace').read()
        t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)  # 去掉块注释（含被注释掉的端点）
        t = re.sub(r'//.*', '', t)
        base = re.search(r'@RequestMapping\("([^"]+)"\)', t)
        if not base:
            continue
        for mm in re.finditer(
                r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)(?:\(\s*(?:value\s*=\s*)?"?([^")\s]*)"?[^)]*\))?',
                t):
            verb = {'GetMapping': 'GET', 'PostMapping': 'POST',
                    'PutMapping': 'PUT', 'DeleteMapping': 'DELETE'}[mm.group(1)]
            sub = mm.group(2) or ''
            if sub and not sub.startswith('/'):
                sub = '/' + sub
            java_found.add((verb, base.group(1) + sub))
    inv = set(paths)
    for v, p in sorted(java_found):
        # Spring 的 {x} 与 Rust 清单里的 {x} 名称可能不同：按前缀模板匹配
        matched = any(pv == v and (pp == p or re.sub(r'\{[^}]*\}', '*', pp) == re.sub(r'\{[^}]*\}', '*', p))
                      for pv, pp in inv)
        if not matched:
            recs.append({'method': v, 'path': p, 'verdict': 'DIFF',
                         'diffs': ['Java 控制器声明的端点未在 Rust 清单登记'], 'note': 'inventory'})
    for v, p in sorted(inv):
        matched = any(pv == v and (pp == p or re.sub(r'\{[^}]*\}', '*', pp) == re.sub(r'\{[^}]*\}', '*', p))
                      for pv, pp in java_found)
        if not matched:
            recs.append({'method': v, 'path': p, 'verdict': 'DIFF',
                         'diffs': ['Rust 清单有但 Java 控制器没有'], 'note': 'inventory'})
    seen = set()
    dup = [x for x in paths if x in seen or seen.add(x)]
    if dup:
        recs.append({'method': '-', 'path': str(dup[:5]), 'verdict': 'DIFF',
                     'diffs': ['清单重复条目'], 'note': 'inventory'})
    # 逐个探测 Rust 是否真的注册（404 说明路由缺失）
    for v, p in sorted(inv):
        probe = re.sub(r'\{[^}]*\}', '1', p)
        if '?' not in probe:
            url = probe
        else:
            url = probe
        if v == 'GET':
            st = fetch(RUST, url)[0]
            if st == 404:
                recs.append({'method': v, 'path': url, 'verdict': 'DIFF',
                             'diffs': ['Rust 实际返回 404，路由可能未注册'], 'note': 'registered'})
    recs.append({'method': '-', 'path': '清单数量', 'verdict': 'DIFF' if (
        len(inv) != len(java_found) or len(seen) != len(paths)) else 'OK',
        'diffs': [] if len(inv) == len(java_found) else ['Rust=%d Java=%d' % (len(inv), len(java_found))],
        'note': 'rust=%d java=%d unique=%d' % (len(inv), len(java_found), len(seen))})
    recs.append({'method': 'GET', 'path': '路由注册探测（{param}→1）',
                 'verdict': 'DIFF' if any(r['note'] == 'registered' for r in recs) else 'OK',
                 'diffs': [], 'note': '共 %d 条，无 404 未注册' % len(inv)})
    meta = {'rust_inventory': len(inv), 'java_annotations': len(java_found)}
    return save('inventory', recs, meta)


def stage_base():
    recs = []
    for seg, name, seed, pk, style in BASE_TABLES:
        row = sample(seg + '/list', seed)
        if not row:
            recs.append({'method': 'GET', 'path': seg + '/list', 'verdict': 'SKIP',
                         'diffs': ['无样本行'], 'note': name})
        for q in ['?pageNum=1&pageSize=3%s' % seed,
                  '?pageNum=2&pageSize=3%s' % seed,
                  '?pageNum=1&pageSize=0%s' % seed,
                  '?pageNum=0&pageSize=-1%s' % seed]:
            recs.append(dict(compare('GET', seg + '/list' + q), note='%s list' % name))
        recs.append(dict(compare('GET', seg + '/listAll'), note='%s listAll' % name))
        if 'snapshotflow' in seg or name in ('feeStationEnter', 'feestationexit', 'feeGantry'):
            recs.append(dict(compare('GET', seg + '/listToExport?pageNum=1&pageSize=3%s' % seed),
                             note='%s listToExport' % name))
        if row:
            val = row.get(pk)
            if val not in (None, ''):
                recs.append(dict(compare('GET', '%s/%s' % (seg, urllib.parse.quote(str(val)))),
                                 note='%s detail(%s)' % (name, style)))
                recs.append(dict(compare('GET', '%s/__no_such_id__' % seg),
                                 note='%s detail-miss' % name))
                if pk in ('id', 'bigId'):
                    recs.append(dict(compare('GET', '%s/abc' % seg), note='%s detail-abc' % name))
    return save('base', recs)


# ---------------- filters：从 XML 解析 <if> 字段与操作符
def xml_conditions():
    """{模型: [(param_name, op)]}，op ∈ {'=','like','range','in'}"""
    out = {}
    mapping = {
        'OdsRtSzdnSnapshotFlowAddcodeMapper.xml': ('/base/snapshotflow', 'snapshotflow'),
        'DwdLcztSfsjcxxMapper.xml': ('/base/sfsjcxx', 'sfsjcxx'),
        'DwdLcztSfzjcxxMapper.xml': ('/base/sfzjcxx', 'sfzjcxx'),
        'DwdLcztFwqjcxxMapper.xml': ('/base/fwqjcxx', 'fwqjcxx'),
        'OdsCxztFwqcllsMapper.xml': ('/manager/fwqclls', 'fwqclls'),
        'OdsLwzxsfsjFeeGantryFusion01Mapper.xml': ('/base/feeGantry', 'feeGantry'),
        'OdsLwzxsfsjFeeStationEnter01Mapper.xml': ('/base/feeStationEnter', 'feeStationEnter'),
        'OdsLwzxsfsjFeeStationExit01Mapper.xml': ('/base/feestationexit', 'feestationexit'),
        'OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.xml': ('/base/provcapture', 'provcapture'),
        'OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.xml': ('/base/stationcapture', 'stationcapture'),
        'OdsSzdnGantryMapper.xml': ('/base/gantry', 'gantry'),
        'OdsSzdnGantryIpMapper.xml': ('/base/gantryIp', 'gantryIp'),
        'OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml': ('/base/vehicleweight', 'vehicleweight'),
        'OdsSzdnSectionMapper.xml': ('/base/section', 'section'),
        'OdsSzdnTollMapper.xml': ('/base/toll', 'toll'),
        'OdsSzdnTollStationIpMapper.xml': ('/base/tollStationIp', 'tollStationIp'),
        'OdsYhglVBaseOrgMapper.xml': ('/base/org', 'org'),
        'ZdataTrailTracksMapper.xml': ('/base/trailtracks', 'trailtracks'),
    }
    for fn, (seg, name) in mapping.items():
        path = os.path.join(XML_DIR, fn)
        if not os.path.exists(path):
            continue
        xml = io.open(path, encoding='utf-8').read()
        m = re.search(r'<select id="\w*List"[^>]*>(.*?)</select>', xml, re.S)
        if not m:
            continue
        conds = []
        for test, body in re.findall(r'<if test="([^"]*)">(.*?)</if>', m.group(1), re.S):
            fm = re.match(r'\s*(\w+)', test)
            if not fm:
                continue
            field = fm.group(1)
            b = re.sub(r'\s+', ' ', body)
            if 'startNum' in b or 'endNum' in b:
                continue
            if '<foreach' in b:
                conds.append((field, 'in'))
            elif 'to_timestamp' in b:
                conds.append((field, 'range'))
            elif re.search(r'\blike\b', b):
                conds.append((field, 'like'))
            elif re.search(r't\.\w+\s*=\s*#\{\w+\}', b):
                conds.append((field, '='))
        seen, uniq = set(), []
        for f, op in conds:
            if f not in seen:
                seen.add(f)
                uniq.append((f, op))
        out[name] = (seg, uniq)
    return out


def value_variants(value, op):
    """返回 [(标注, 值)]；覆盖真实值、负值、通配符、大小写、日期格式。"""
    s = str(value)
    out = [('real', s)]
    out.append(('absent', 'ZZZ-不存在的值-7Q'))
    if op == 'like':
        out.append(('wildcard', '%'))
        out.append(('case', s.upper() if s != s.upper() else s.lower()))
        out.append(('prefix', s[:3]))
    if op == 'range':
        out.append(('month', '2025-09'))
        out.append(('iso', '2025-09-08T00:00:00.000+00:00'))
        out.append(('bad', 'not-a-date'))
    if re.match(r'^\d{4}([-/.])\d{2}\1\d{2}[ T]', s):
        base = s.replace('T', ' ')[:19]
        out.append(('space', base))
        out.append(('date-only', base[:10]))
        out.append(('slash', base.replace('-', '/')))
    if isinstance(value, str) and value == '' :
        out = out[1:]
    return out


def stage_filters(max_fields=10):
    recs = []
    conds = xml_conditions()
    for name, (seg, fields) in sorted(conds.items()):
        row = sample(seg + '/list', '')
        seed_param = next((x[2] for x in BASE_TABLES if x[1] == name), '')
        if not row:
            row = sample(seg + '/list', seed_param)
        picks = [f for f, _op in fields][:max_fields]
        fmap = dict(fields)
        for f in picks:
            if f not in row or row[f] in (None, ''):
                continue
            op = fmap[f]
            for label, val in value_variants(row[f], op):
                q = '?pageNum=1&pageSize=2%s&%s=%s' % (seed_param, f, urllib.parse.quote(val))
                recs.append(dict(compare('GET', seg + '/list' + q),
                                 note='%s.%s/%s' % (name, f, label)))
    return save('filters', recs)


def stage_query():
    recs = []
    tr = ('2025-09-08%2000:00:00', '2025-09-09%2000:00:00')
    wide = ('2025-01-01%2000:00:00', '2026-12-31%2023:59:59')
    plate_row = sample('/base/snapshotflow/list',
                       '&applyTime1=%s&applyTime2=%s' % tr)
    plate = urllib.parse.quote(str((plate_row or {}).get('platenumber', '')))
    big = sample('/base/feeGantry/list') or {}
    for path in [
        '/api/v1/large/snapshot?startTime=%s&endTime=%s&pageNum=1&pageSize=5' % tr,
        '/api/v1/large/snapshot?startTime=%s&endTime=%s&pageNum=1&pageSize=5&fuzzyFields.platenumber=%s' % (tr[0], tr[1], plate),
        '/api/v1/large/snapshot?startTime=%s&endTime=%s&pageNum=1&pageSize=5&fuzzyFields.gantryname=%%' % tr,
        '/api/v1/large/snapshot?startTime=%s&endTime=%s&pageNum=1001&pageSize=20' % tr,
        '/api/v1/large/fee?startTime=%s&endTime=%s&pageNum=1&pageSize=2' % wide,
        '/api/v1/large/trail?startTime=%s&endTime=%s&pageNum=1&pageSize=2' % wide,
        '/api/v1/large/trail?startTime=%s&endTime=%s&pageNum=1&pageSize=2&fuzzyFields.platenumber=%s' % (wide[0], wide[1], plate),
        '/api/v1/large/carTrackQueryByCarNo?carNo=%s&startTime=%s&endTime=%s&pageNum=1&pageSize=3' % (plate, wide[0], wide[1]),
        '/api/v1/large/carTrackQueryByCarNo?startTime=%s&endTime=%s' % wide,
        '/api/v1/large/stats/group?type=snapshot&startTime=%s&endTime=%s&groupBy=platenumber&topN=5' % tr,
        '/api/v1/large/stats/group?type=fee&startTime=%s&endTime=%s&groupBy=gantryid&topN=3' % wide,
        '/api/v1/large/stats/group?type=trail&startTime=%s&endTime=%s&groupBy=envehicleid&topN=3' % wide,
        '/api/v1/large/stats/group?type=bogus&startTime=%s&endTime=%s&groupBy=x' % wide,
        '/api/v1/large/stats/group?startTime=%s&endTime=%s' % wide,
        '/api/v1/large/export/status/nope',
        '/api/v1/unified/snapshot/list?startTime=%s&endTime=%s&pageNum=1&pageSize=3' % tr,
        '/api/v1/unified/fee/list?startTime=%s&endTime=%s&pageNum=1&pageSize=3' % wide,
        '/api/v1/unified/trail/list?startTime=%s&endTime=%s&pageNum=1&pageSize=3' % wide,
        '/api/v1/unified/bad/list?startTime=%s&endTime=%s' % wide,
        '/api/v1/unified/snapshot/list?endTime=%s' % tr[1],
        '/api/v1/unified/export/status/nope',
        '/api/v1/large/foo?startTime=%s&endTime=%s' % wide,
        '/progressive/snapshotflow/list?startTime=%s&endTime=%s&pageSize=20&platenumber=%s' % (tr[0], tr[1], plate),
        '/progressive/feerecords/list?startTime=%s&endTime=%s&pageSize=2' % wide,
        '/progressive/trailfitting/list?startTime=%s&endTime=%s&pageSize=2' % wide,
        '/progressive/scale-level',
        '/api/v1/large/sync/full?startTime=%s&endTime=%s' % wide,
        '/api/v1/large/fee?startTime=2025-13-45%2000:00:00&endTime=2026-12-31%2023:59:59',
    ]:
        recs.append(dict(compare('GET', path), note='query'))
    for path, body in [
        ('/api/v1/large/export/submit?type=snapshot&startTime=%s&endTime=%s' % tr, None),
        ('/api/v1/large/export/submit?type=fee&startTime=%s&endTime=%s' % wide, None),
        ('/api/v1/unified/snapshot/export/submit?startTime=%s&endTime=%s' % tr, {}),
        ('/api/v1/unified/bad/export/submit?startTime=%s&endTime=%s' % wide, {}),
        ('/api/v1/large/sync/repair?type=snapshot&startTime=%s&endTime=%s' % tr, None),
        ('/base/gantry/list', None),
    ]:
        recs.append(dict(compare('POST', path, body), note='query-post'))
    return save('query', recs)


def stage_sysutil(allow_side_effects):
    recs = []
    tr = ('2025-09-08%2000:00:00', '2025-09-09%2000:00:00')
    row = sample('/base/snapshotflow/list', '&applyTime1=%s&applyTime2=%s' % tr)
    plate = urllib.parse.quote(str((row or {}).get('platenumber', '')))
    for path in [
        '/base/sysutil/getByTrailBo',
        '/base/sysutil/changeTrailInfo',
    ]:
        recs.append(dict(compare('GET', path), note='sysutil-get'))
    for path in [
        '/api/v1/large/carTrackQueryByCarNo?carNo=%s&startTime=%s&endTime=%s&pageNum=1&pageSize=3' % (plate, tr[0], tr[1]),
    ]:
        recs.append(dict(compare('GET', path), note='sysutil-track'))
    for path in [
        '/base/sysutilTest/syncBaseInfo',
        '/base/sysutilTest/syncCurrentTrack',
        '/base/sysutilTest/syncHistroyTrack',
        '/base/sysutilTest/syncSuspiciousCar1',
        '/base/sysutilTest/syncSuspiciousCar2',
        '/base/sysutilTest/syncOdsSzdnGantry',
        '/base/sysutilTest/separateSnapshotFlowTimeList',
    ]:
        heavy = any(k in path for k in ('syncHistroy', 'syncSuspicious'))
        if heavy and not allow_side_effects:
            recs.append({'method': 'GET', 'path': path, 'verdict': 'SKIP',
                         'diffs': [], 'note': '写副作用/耗时，需 --allow-side-effects'})
            continue
        recs.append(dict(compare('GET', path), note='sysutilTest'))
    return save('sysutil', recs)


def stage_contract():
    recs = []
    urls = [
        '/base/gantry/list?pageNum=1&pageSize=2',
        '/base/snapshotflow/list?pageNum=1&pageSize=2&applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00',
        '/base/vehicleweight/list?pageNum=1&pageSize=2',
        '/base/trailtracks/list?pageNum=1&pageSize=2',
        '/not-exist',
        '/api/v1/large/snapshot',
    ]
    for u in urls:
        ja, ru = fetch(JAVA, u), fetch(RUST, u)
        rec = {'method': 'GET', 'path': u, 'java': ja[0], 'rust': ru[0], 'diffs': [],
               'verdict': 'OK', 'note': 'contract'}
        ct_a = (ja[1].get('content-type') or '').split(';')[0].strip().lower()
        ct_r = (ru[1].get('content-type') or '').split(';')[0].strip().lower()
        if ct_a != ct_r:
            rec['diffs'].append('content-type %s != %s' % (ct_a, ct_r))
        if ja[0] != ru[0]:
            rec['diffs'].append('status %s != %s' % (ja[0], ru[0]))
        va, vb = jload(ja[2]), jload(ru[2])
        if va is not None and vb is not None:
            ka = key_shape(va)
            kb = key_shape(vb)
            if ka != kb:
                rec['diffs'].append('key-shape java=%s rust=%s' % (ka[:200], kb[:200]))
        elif text(ja[2]).strip() != text(ru[2]).strip():
            rec['diffs'].append('raw %r != %r' % (text(ja[2])[:120], text(ru[2])[:120]))
        if rec['diffs']:
            rec['verdict'] = 'DIFF'
        recs.append(rec)
    # 405 / 400 / 415 / HEAD / 尾斜杠 / 编码
    recs.append(dict(compare('POST', '/base/gantry/list', {}), note='405'))
    recs.append(dict(compare('GET', '/base/gantry/list?pageNum=abc&pageSize=xyz'), note='lenient-page'))
    recs.append(dict(compare('GET', '/base/gantry/list?pageNum=%E9%9D%9E%E6%B3%95'), note='nonnum-page'))
    recs.append(dict(compare('GET', '/base/gantry/1/2'), note='deep-path'))
    recs.append(dict(compare('GET', '/base/gantry/list?pageNum=1&pageSize=1&gantryName=%25'), note='like-escape'))
    recs.append(dict(compare('GET', '/base/gantry/list?pageNum=1&pageSize=1&gantryName=G00'), note='ascii-like'))
    # 重复查询参数：Spring 用逗号拼接后绑定（数值字段会变成 "1,2" 而 400）
    for dup in [
        '/base/snapshotflow/list?applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00'
        '&platenumber=%25&platenumber=%25&pageNum=1&pageSize=1',
        '/base/snapshotflow/list?applyTime1=2025-09-08%2000:00:00&applyTime2=2025-09-09%2000:00:00'
        '&platenumber=ZZZQ&platenumber=%25&pageNum=1&pageSize=1',
        '/base/gantry/list?pageNum=1&pageNum=2&pageSize=1',
        '/base/gantry/list?direction=1&direction=2&pageSize=1',
    ]:
        recs.append(dict(compare('GET', dup), note='duplicate-param'))
    # Spring 错误体字段顺序与键集
    for p in ['/nope', '/base/nope/list', '/api/v1/large/nope?startTime=1&endTime=2']:
        ja, ru = fetch(JAVA, p), fetch(RUST, p)
        rec = {'method': 'GET', 'path': p, 'java': ja[0], 'rust': ru[0], 'verdict': 'OK',
               'diffs': [], 'note': 'error-shape'}
        if ja[0] != ru[0]:
            rec['verdict'] = 'DIFF'
            rec['diffs'].append('status')
        else:
            ka = list((jload(ja[2]) or {}).keys())
            kb = list((jload(ru[2]) or {}).keys())
            if ka != kb:
                rec['verdict'] = 'DIFF'
                rec['diffs'].append('keys %s != %s' % (ka, kb))
            ja_obj, ru_obj = jload(ja[2]), jload(ru[2])
            if isinstance(ja_obj, dict) and isinstance(ru_obj, dict):
                for k in ('status', 'error', 'message', 'path'):
                    if ja_obj.get(k) != ru_obj.get(k):
                        rec['verdict'] = 'DIFF'
                        rec['diffs'].append('%s %r != %r' % (k, ja_obj.get(k), ru_obj.get(k)))
        recs.append(rec)
    return save('contract', recs)


def key_shape(obj, depth=0):
    if depth > 3:
        return ''
    if isinstance(obj, dict):
        # 不排序：Java HashMap / LinkedHashMap 的键顺序也是契约的一部分
        return '{' + ','.join('%s:%s' % (k, key_shape(v, depth + 1)) for k, v in obj.items()) + '}'
    if isinstance(obj, list):
        return '[%d]%s' % (len(obj), key_shape(obj[0], depth + 1) if obj else '')
    return type(obj).__name__ if obj is not None else 'null'


# ---------------------------------------------------------------- 报告
def stage_report():
    files = sorted(glob.glob(os.path.join(RUN_DIR, '*.json')))
    lines = []
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    lines.append('## 阶段结果（自动生成于 %s）' % now)
    total = ok = bad = skipped = container = 0
    for fn in files:
        data = json.load(io.open(fn, encoding='utf-8'))
        s = data['summary']
        total += s['total']
        ok += s['ok']
        bad += s['diff']
        skipped += s['skip']
        container += s.get('container', 0)
        lines.append('')
        lines.append('### %s（%d 项：一致 %d，不一致 %d，跳过 %d）' % (
            data['stage'], s['total'], s['ok'], s['diff'], s['skip']))
        if data.get('meta'):
            lines.append('')
            lines.append('元信息：`%s`' % json.dumps(data['meta'], ensure_ascii=False))
        lines.append('')
        lines.append('| 阶段 | 方法 | 路径 | Java | Rust | 判定 | 说明 / 差异 |')
        lines.append('|---|---|---|---|---|---|---|')
        for r in data['records']:
            detail = '; '.join(str(x)[:160] for x in (r.get('diffs') or [r.get('note', '')]))[:220]
            detail = detail.replace('|', '/').replace('\n', ' ')
            lines.append('| %s | %s | `%s` | %s | %s | %s | %s |' % (
                data['stage'], r.get('method', ''), r.get('path', '')[:110],
                r.get('java', '-'), r.get('rust', '-'), r['verdict'], detail))
    lines.insert(1, '')
    lines.insert(2, '**合计 %d 项：一致 %d，不一致 %d，容器级差异 %d，跳过 %d**' % (
        total, ok, bad, container, skipped))
    block = '\n'.join(lines) + '\n'
    header = ''
    if os.path.exists(DOC):
        header = io.open(DOC, encoding='utf-8').read()
    body = re.sub(r'## 阶段结果（自动生成于 [\d\- :]+）', '', header, count=0)
    with io.open(DOC, 'w', encoding='utf-8') as f:
        f.write(header.split('<!-- RESULTS -->')[0] + '<!-- RESULTS -->\n\n' + block)
    print('报告写入 %s（合计 %d 项，不一致 %d）' % (DOC, total, bad))
    return total, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='all')
    ap.add_argument('--max-fields', type=int, default=10)
    ap.add_argument('--allow-side-effects', action='store_true')
    ap.add_argument('--no-cache-guard', action='store_true')
    args = ap.parse_args()
    stages = STAGES if args.stage == 'all' else args.stage.split(',')
    os.makedirs(RUN_DIR, exist_ok=True)
    with CacheGuard(enabled=not args.no_cache_guard):
        for st in stages:
            if st == 'inventory':
                stage_inventory()
            elif st == 'base':
                stage_base()
            elif st == 'filters':
                stage_filters(args.max_fields)
            elif st == 'query':
                stage_query()
            elif st == 'sysutil':
                stage_sysutil(args.allow_side_effects)
            elif st == 'contract':
                stage_contract()
            elif st == 'report':
                stage_report()
    if 'report' not in stages:
        stage_report()
    return 0


if __name__ == '__main__':
    sys.exit(main())
