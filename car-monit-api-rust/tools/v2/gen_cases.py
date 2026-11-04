# -*- coding: utf-8 -*-
"""用例矩阵生成（v2）。

输入: .run/verify2/inventory.json（静态清单） + 双端实采的样例行
输出: .run/verify2/cases/<stage>.json

分组：
  base      19 张基础表的 list / listToExport / listAll / {id} + 分页与排序边界
  filters   以 Mapper XML <if> 字段为来源，逐字段过滤（真值 / 前缀 / 通配 / 空值 / 不存在 / 类型异常）
  query     large / unified / progressive / stats / export + 未知数据源等错误分支
  contract  状态码、Content-Type、404/405、原始字节、数字与日期序列化、参数重复、编码
说明：只生成只读用例。会写库/写缓存的端点（sysutilTest/*、sync/*、saveRedis）单独放在
      write 阶段，由 --allow-write 显式开启。
"""
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

INV = json.load(open(os.path.join(H.RUN_DIR, 'inventory.json'), encoding='utf-8'))

# Java 侧确认过的分页语义（PageUtils.startPage + PageDomain 默认值）
PAGE_CASES = [
    {},                                              # 缺省 → pageNum=1 pageSize=10
    {'pageNum': '1', 'pageSize': '1'},
    {'pageNum': '1', 'pageSize': '10'},
    {'pageNum': '2', 'pageSize': '5'},
    {'pageNum': '3', 'pageSize': '7'},
    {'pageNum': '0', 'pageSize': '5'},               # reasonable=true → 归 1
    {'pageNum': '-1', 'pageSize': '5'},
    {'pageNum': '9999', 'pageSize': '5'},            # reasonable=true → 钳到最后一页
    {'pageNum': '1', 'pageSize': '0'},
    {'pageNum': '1', 'pageSize': '-5'},
    {'pageNum': '1', 'pageSize': '1000'},
    {'pageNum': '1', 'pageSize': '2000'},            # Rust 侧有 1000 钳位，Java 无
    {'pageNum': 'abc', 'pageSize': '5'},             # 类型不匹配
    {'pageNum': '', 'pageSize': ''},
    {'pageNum': '1.5', 'pageSize': '2.5'},
    {'pageSize': '3'},                               # 只给 pageSize
    {'pageNum': '2'},                                # 只给 pageNum
    {'pageNum': '0', 'pageSize': '5', 'reasonable': 'false'},
    {'pageNum': '2', 'pageSize': '5', 'reasonable': 'false'},
    {'pageNum': '9999', 'pageSize': '5', 'reasonable': 'false'},
    {'pageNum': '9999', 'pageSize': '5', 'reasonable': 'true'},
    {'pageNum': '9999', 'pageSize': '5', 'reasonable': 'abc'},
    {'pageNum': '1', 'pageSize': '5', 'reasonable': '0'},
    {'pageNum': '1', 'pageSize': '5000'},
]
SORT_CASES = [
    {'orderByColumn': 'id', 'isAsc': 'asc'},
    {'orderByColumn': 'id', 'isAsc': 'desc'},
    {'orderByColumn': 'ID', 'isAsc': 'ASC'},
    {'orderByColumn': 'createTime', 'isAsc': 'desc'},   # 驼峰 → 下划线
    {'orderByColumn': 'plate_number', 'isAsc': 'asc'},  # 不存在的列
    {'orderByColumn': 'id', 'isAsc': ''},
    {'orderByColumn': '', 'isAsc': 'desc'},
    {'orderByColumn': '1;drop table x', 'isAsc': 'asc'},   # 非法 → UtilException
    {'orderByColumn': 'id', 'isAsc': 'asc,desc'},
    {'orderByColumn': 'id' * 40, 'isAsc': 'asc'},          # 超长
    {'orderByColumn': 'id'},                               # isAsc 缺省
    {'orderByColumn': 'id', 'isAsc': 'ascending'},
    {'orderByColumn': 'id', 'isAsc': 'descending'},
    {'orderByColumn': 'id', 'isAsc': 'ASC'},
    {'orderByColumn': 'gantryName', 'isAsc': 'desc'},      # 驼峰→下划线
    {'orderByColumn': 'id ', 'isAsc': 'asc'},              # 尾部空格
    {'orderByColumn': 'id', 'isAsc': 'asc),('},            # 括号 → 非法
]
ID_CASES_BAD = ['0', 'nonexistent-id-xyz', "'", "1' OR '1'='1", '%27%20OR%20%271%27=%271', '9' * 30,
                '1.5', '-1', '  12  ', '12abc', '中文']


def load_samples():
    p = os.path.join(H.RUN_DIR, 'samples.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    return {}


def java_list(base, extra='pageSize=2&pageNum=1'):
    for side in ('java', 'rust'):
        st, _, raw, ms, err = H.http_get(H.side_url(side, '%s/list?%s' % (base, extra)), timeout=60)
        if st == 200:
            j = H.parse_json(raw)
            rows = (j or {}).get('rows') or []
            if rows:
                return rows
    return []


def collect_samples(tables):
    samples = load_samples()
    changed = False
    for t in tables:
        if t['base'] in samples:
            continue
        samples[t['base']] = java_list(t['base'])
        changed = True
        print(' sample %-32s rows=%d' % (t['base'], len(samples[t['base']])), flush=True)
    if changed:
        with open(os.path.join(H.RUN_DIR, 'samples.json'), 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False)
    return samples


def tables_from_inventory():
    """从清单里挑出「绑定实体的 list 端点」，配好同前缀的 {id} / listAll / listToExport。"""
    by_base = {}
    # 第一遍：只认「绑定实体的 /list」作为一张基础表的锚点（决定 entity 与过滤字段来源）
    for r in INV['java_endpoints']:
        if r['method'] != 'GET' or not r['bind_entity']:
            continue
        segs = r['path'].strip('/').split('/')
        if segs[-1] != 'list':
            continue
        base = '/' + '/'.join(segs[:-1])
        by_base[base] = {'base': base, 'entity': r['bind_entity'], 'list': True,
                         'list_all': False, 'export': False, 'id_var': None}
    # 第二遍：同前缀的 listAll / listToExport / {id} 挂到这张表上
    # （之前只遍历带 bind_entity 的方法，导致 19 个 {id} 与 14 个 listAll 一条用例都没生成）
    for r in INV['java_endpoints']:
        if r['method'] != 'GET':
            continue
        segs = r['path'].strip('/').split('/')
        base = '/' + '/'.join(segs[:-1])
        d = by_base.get(base)
        if d is None:
            continue
        last = segs[-1]
        if last == 'listAll':
            d['list_all'] = True
        elif last == 'listToExport':
            d['export'] = True
        elif last.startswith('{') and last.endswith('}'):
            d['id_var'] = last[1:-1]
    out = []
    for base, d in sorted(by_base.items()):
        if not d['list']:
            continue          # 只有写端点的（/base/sysutil）不进基础表矩阵
        mapper = d['entity'] + 'Mapper'
        d['filters'] = INV['mapper_filters'].get(mapper, [])
        out.append(d)
    return out


def qstr(d):
    return ('?' + urllib.parse.urlencode(d)) if d else ''


def sample_value(rows, field):
    for row in rows[:3]:
        v = row.get(field)
        if v not in (None, '', [], {}):
            return v
    return None


def scalar_str(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def gen_base(tables, samples):
    cases = []
    for t in tables:
        base, rows = t['base'], samples.get(t['base'], [])
        for i, pg in enumerate(PAGE_CASES):
            cases.append({'id': 'base:%s:pg%02d' % (base, i), 'group': 'base-pagination',
                          'path': base + '/list' + qstr(pg), 'method': 'GET'})
        for i, srt in enumerate(SORT_CASES):
            p = dict(srt)
            p.setdefault('pageSize', '5')
            cases.append({'id': 'base:%s:sort%02d' % (base, i), 'group': 'base-sort',
                          'path': base + '/list' + qstr(p), 'method': 'GET'})
        if t['export']:
            for i, pg in enumerate(PAGE_CASES[:6]):
                cases.append({'id': 'base:%s:exp%02d' % (base, i), 'group': 'base-export',
                              'path': base + '/listToExport' + qstr(pg), 'method': 'GET'})
        if t['list_all']:
            cases.append({'id': 'base:%s:listAll' % base, 'group': 'base-listAll',
                          'path': base + '/listAll', 'method': 'GET'})
        if t['id_var']:
            idf = t['id_var']
            good = sample_value(rows, idf)
            vals = ([scalar_str(good)] if good is not None else []) + ID_CASES_BAD
            for j, v in enumerate(vals):
                cases.append({'id': 'base:%s:id%02d' % (base, j), 'group': 'base-id',
                              'path': '%s/%s' % (base, urllib.parse.quote(v, safe='')),
                              'method': 'GET'})
    return cases


DATE_HINT = ('time', 'date', 'Time', 'Date', 'rq', 'sj')


def gen_filters(tables, samples, per_field=('eq', 'like', 'none', 'empty'), cap_fields=None):
    cases = []
    for t in tables:
        base, rows = t['base'], samples.get(t['base'], [])
        fields = t['filters'][:cap_fields] if cap_fields else t['filters']
        for f in fields:
            v = sample_value(rows, f)
            if v is None:
                # 无样例值时用「类型猜值」，仍然能验证 SQL 拼接是否双端一致
                low = f.lower()
                if any(k in low for k in ('lon', 'lat', 'wd', 'jd')):
                    v = '116.0'
                elif any(k in low for k in ('time', 'date', 'rq', 'sj')):
                    v = '2025-09-10'
                else:
                    v = '1' if any(c.isdigit() for c in f) else 'x'
            s = scalar_str(v)
            for kind in per_field:
                if kind == 'eq':
                    q = {f: s}
                elif kind == 'like':
                    pref = s[:max(1, min(3, len(s) // 2))] if isinstance(v, str) else s
                    q = {f: pref}
                elif kind == 'none':
                    q = {f: 'ZZZ_不存在_ZZZ'}
                elif kind == 'empty':
                    q = {f: ''}
                elif kind == 'wild':
                    q = {f: '%'}
                elif kind == 'space':
                    q = {f: ' '}
                else:
                    continue
                cases.append({'id': 'flt:%s:%s:%s' % (base, f, kind),
                              'group': 'filters', 'path': base + '/list' + qstr(q),
                              'method': 'GET', 'field': f, 'variant': kind, 'value': q[f]})
        # params[beginTime]/params[endTime]：RuoYi BaseEntity 的 Map 语法
        if any(x.startswith('params') for x in t['filters']) or t['filters']:
            for extra in ({'params[beginTime]': '2025-09-01', 'params[endTime]': '2025-09-30'},
                          {'params[beginTime]': '2025-09-01 00:00:00', 'params[endTime]': '2025-09-01 12:00:00'},
                          {'params[beginXx]': '1'}):
                q = dict(extra)
                q['pageSize'] = '3'
                cases.append({'id': 'fltp:%s:%s' % (base, sorted(q)[0]), 'group': 'filters-params',
                              'path': base + '/list' + qstr(q), 'method': 'GET'})
    return cases


# ---------------------------------------------------------------- 高级查询
LARGE_SNAP = [
    {}, {'startTime': '2025-09-01 00:00:00', 'endTime': '2025-09-01 23:59:59'},
    {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'pageSize': '5'},
    {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'platenumber': '%'},
    {'startTime': '2025-09-01'}, {'endTime': '2025-09-02'},
    {'startTime': '', 'endTime': ''},
    {'startTime': '2025-13-45', 'endTime': 'not-a-date'},
    {'startTime': '2025-09-01', 'endTime': '2025-08-01'},
    {'pageSize': '0'}, {'pageSize': '-1'}, {'pageSize': 'abc'},
    {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'pageNum': '2', 'pageSize': '3'},
]
UNIFIED_CASES = [
    ('snapshot', {}), ('fee', {}), ('trail', {}),
    ('snapshot', {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'pageSize': '3'}),
    ('fee', {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'pageSize': '3'}),
    ('trail', {'startTime': '2025-09-01', 'endTime': '2025-09-02', 'pageSize': '3'}),
    ('unknown-ds', {}), ('', {}),
    ('snapshot', {'fuzzyFields.platenumber': 'A'}),
    ('snapshot', {'platenumber': '%', 'gantryname': '门架'}),
]
PROGRESSIVE_CASES = [
    ('snapshotflow', {}), ('feerecords', {}), ('trailfitting', {}),
    ('snapshotflow', {'startTime': '2025-09-01', 'endTime': '2025-09-02'}),
    ('snapshotflow', {'pageSize': '3', 'startTime': '2025-09-01', 'endTime': '2025-09-10'}),
    ('snapshotflow', {'cursor': '2025-09-05 12:00:00', 'startTime': '2025-09-01',
                      'endTime': '2025-09-10', 'pageSize': '3'}),
    ('snapshotflow', {'pageSize': 'abc'}),
    ('snapshotflow', {'platenumber': '%'}),
    ('unknown', {}),
]


def gen_query(samples):
    cases = []
    for i, q in enumerate(LARGE_SNAP):
        for ds in ('snapshot', 'fee', 'trail'):
            cases.append({'id': 'lg:%s:%02d' % (ds, i), 'group': 'large',
                          'path': '/api/v1/large/%s%s' % (ds, qstr(q)), 'method': 'GET'})
    # Rust 用 /api/v1/large/{ds} 通配，Java 只有 3 个具体路径 → 未知 ds 必须一致
    for ds in ('unknown', 'carTrack', 'SNAPSHOT', 'snapshot/../../x'):
        cases.append({'id': 'lg:bad:%s' % ds, 'group': 'large-unknown-ds',
                      'path': '/api/v1/large/%s' % urllib.parse.quote(ds, safe=''), 'method': 'GET'})
    for ds, q in UNIFIED_CASES:
        cases.append({'id': 'un:%s:%s' % (ds, abs(hash(json.dumps(q, sort_keys=True))) % 1000),
                      'group': 'unified', 'path': '/api/v1/unified/%s/list%s' % (ds, qstr(q)),
                      'method': 'GET'})
    for tbl, q in PROGRESSIVE_CASES:
        cases.append({'id': 'pr:%s:%s' % (tbl, qstr(q)[:40].replace('&', '_').replace('?', '')),
                      'group': 'progressive', 'path': '/progressive/%s/list%s' % (tbl, qstr(q)),
                      'method': 'GET'})
    cases.append({'id': 'pr:scale-level', 'group': 'progressive',
                  'path': '/progressive/scale-level', 'method': 'GET'})
    # 「参数出现但为空」与「缺失」在 Spring 里不是一回事（@RequestParam 只看存在性）
    presence = [
        '/api/v1/large/snapshot?startTime=&endTime=',
        '/api/v1/large/fee?startTime=&endTime=',
        '/api/v1/large/trail?startTime=&endTime=',
        '/api/v1/large/snapshot?startTime=&endTime=2025-09-01',
        '/api/v1/unified/snapshot/list?startTime=&endTime=',
        '/api/v1/unified/fee/list?startTime=&endTime=2025-09-01',
        '/api/v1/large/carTrackQueryByCarNo?carNo=&startTime=&endTime=',
        '/api/v1/large/stats/group?groupBy=platenumber&startTime=&endTime=',
        '/api/v1/large/stats/group?groupBy=&startTime=2025-01-01&endTime=2025-12-31',
        '/progressive/snapshotflow/list?pageSize=',
        '/progressive/snapshotflow/list?pageSize=abc',
        '/progressive/snapshotflow/list?pageSize=3.5',
        '/progressive/snapshotflow/list?pageSize=-1',
        '/progressive/snapshotflow/list?pageSize=999999999999',
        '/progressive/snapshotflow/list?pageSize=+5',
    ]
    for i, q in enumerate(presence):
        cases.append({'id': 'pr:presence:%02d' % i, 'group': 'query-presence',
                      'path': q, 'method': 'GET'})
    # 数据源字面量的大小写 / 编码穿越
    for ds in ('SNAPSHOT', 'Snapshot', 'snapshot ', ' snapshot', 'FEE', 'trail%', 'trail%20'):
        cases.append({'id': 'q:ds:%s' % ds.strip() or 'sp', 'group': 'query-ds-case',
                      'path': '/api/v1/large/%s?startTime=2025-01-01&endTime=2025-12-31'
                              % urllib.parse.quote(ds, safe=''), 'method': 'GET'})
        cases.append({'id': 'qu:ds:%s' % ds.strip() or 'sp', 'group': 'query-ds-case',
                      'path': '/api/v1/unified/%s/list?startTime=2025-01-01&endTime=2025-12-31'
                              % urllib.parse.quote(ds, safe=''), 'method': 'GET'})
    for tp in ('%2f', '..', '.'):
        for base in ('/api/v1/large', '/api/v1/unified', '/progressive'):
            cases.append({'id': 'q:trav:%s:%s' % (base, tp), 'group': 'query-traversal',
                          'path': '%s/%s/list' % (base, urllib.parse.quote(tp, safe='')),
                          'method': 'GET'})
    for st, p, body in (('large', 'stats/group', None),):
        cases.append({'id': 'st:group', 'group': 'query-stats',
                      'path': '/api/v1/large/stats/group?startTime=2025-09-01&endTime=2025-09-02',
                      'method': 'GET'})
    cases.append({'id': 'st:group:min', 'group': 'query-stats',
                  'path': '/api/v1/large/stats/group', 'method': 'GET'})
    for extra in ('', '?groupBy=plateKey', '?groupBy=nonexistent', '?days=2',
                  '?startTime=2025-09-01&endTime=2025-09-02&groupBy=gantryname'):
        cases.append({'id': 'st:group:%s' % (extra or 'none'), 'group': 'query-stats',
                      'path': '/api/v1/large/stats/group' + extra, 'method': 'GET'})
    # large 版 carTrackQueryByCarNo（Java 独有路径）
    for q in ('', '?carNo=赣A12345', '?carNo=%E8%B5%A3A12345&startTime=2025-09-01&endTime=2025-09-02',
              '?startTime=2025-09-01&endTime=2025-09-02'):
        cases.append({'id': 'lg:track:%s' % (q or 'none'), 'group': 'large-track',
                      'path': '/api/v1/large/carTrackQueryByCarNo' + q, 'method': 'GET'})
    return cases


def gen_contract():
    cases = []
    # 404 / 405 / 方法不匹配 / 非法 JSON / 参数重复 / 编码
    cases.append({'id': 'ct:404', 'group': 'contract', 'path': '/no/such/endpoint', 'method': 'GET'})
    cases.append({'id': 'ct:404b', 'group': 'contract', 'path': '/base/gantry/nope/1', 'method': 'GET'})
    cases.append({'id': 'ct:405', 'group': 'contract', 'path': '/base/gantry/list',
                  'method': 'POST', 'body': '{}'})
    cases.append({'id': 'ct:405b', 'group': 'contract', 'path': '/base/sysutil/changeTrailInfo',
                  'method': 'GET'})
    cases.append({'id': 'ct:badjson', 'group': 'contract', 'path': '/base/sysutil/changeTrailInfo',
                  'method': 'POST', 'body': '{"trailList": ['})
    cases.append({'id': 'ct:emptyjson', 'group': 'contract', 'path': '/base/sysutil/changeTrailInfo',
                  'method': 'POST', 'body': ''})
    cases.append({'id': 'ct:arrayjson', 'group': 'contract', 'path': '/base/sysutil/changeTrailInfo',
                  'method': 'POST', 'body': '[1,2,3]'})
    cases.append({'id': 'ct:dup', 'group': 'contract',
                  'path': '/base/gantry/list?gantryCode=A&gantryCode=B&pageSize=3', 'method': 'GET'})
    cases.append({'id': 'ct:emptyparam', 'group': 'contract',
                  'path': '/base/gantry/list?gantryCode=&pageSize=3', 'method': 'GET'})
    cases.append({'id': 'ct:plus', 'group': 'contract',
                  'path': '/base/gantry/list?gantryName=%E9%87%91%E7%9B%8A&pageSize=3', 'method': 'GET'})
    cases.append({'id': 'ct:unknownparam', 'group': 'contract',
                  'path': '/base/gantry/list?zzzNotAField=1&pageSize=3', 'method': 'GET'})
    cases.append({'id': 'ct:typemismatch', 'group': 'contract',
                  'path': '/base/gantry/list?pageSize=%E4%B8%AD%E6%96%87', 'method': 'GET'})
    cases.append({'id': 'ct:trailslash', 'group': 'contract',
                  'path': '/base/gantry/list/?pageSize=3', 'method': 'GET'})
    cases.append({'id': 'ct:datefmt1', 'group': 'contract',
                  'path': '/base/snapshotflow/list?snapshottime=2025-09-10&pageSize=2', 'method': 'GET'})
    cases.append({'id': 'ct:datefmt2', 'group': 'contract',
                  'path': '/base/snapshotflow/list?snapshottime=2025/09/10&pageSize=2', 'method': 'GET'})
    cases.append({'id': 'ct:datefmt3', 'group': 'contract',
                  'path': '/base/snapshotflow/list?snapshottime=2025-09-10 12:33:00&pageSize=2',
                  'method': 'GET'})
    cases.append({'id': 'ct:datefmt4', 'group': 'contract',
                  'path': '/base/snapshotflow/list?snapshottime=garbage&pageSize=2', 'method': 'GET'})
    cases.append({'id': 'ct:datefmt5', 'group': 'contract',
                  'path': '/base/snapshotflow/list?snapshottime=2025-9-1&pageSize=2', 'method': 'GET'})
    cases.append({'id': 'ct:head-accept', 'group': 'contract', 'path': '/base/gantry/list?pageSize=1',
                  'method': 'GET', 'headers': {'Accept': 'application/xml'}})
    # Accept 协商矩阵：Java 侧 Spring 的 producible 判定 + /error 的 Whitelabel 渲染
    acc_types = ['application/xml', 'text/plain', 'application/json', '*/*', '', 'application/*+json',
                 'application/cbor', 'application/x-jackson-smile', 'application/octet-stream',
                 'application/json;q=0.9,application/xml;q=0.8', 'garbage//', 'application/js*n',
                 'application/*', 'text/*', '*/*;q=0.5', 'json', 'text/html', '*/*,text/html',
                 'text/html,application/json', 'application/json;q=0.1,text/html;q=0.9',
                 'application/xhtml+xml']
    acc_paths = ['/base/gantry/list?pageSize=1', '/no/such', '/base/feerecords/list',
                 '/base/gantry/nope']
    binary = {'application/cbor', 'application/x-jackson-smile'}
    for i, a in enumerate(acc_types):
        for j, p in enumerate(acc_paths):
            c = {'id': 'ct:acc%02d-%d' % (i, j), 'group': 'contract-accept', 'path': p,
                 'method': 'GET', 'headers': {'Accept': a}}
            if a in binary:
                c['accepted'] = {
                    'kinds': ['content-type', 'json-parse', 'raw-text', 'value', 'keys', 'len'],
                    'reason': 'Java 侧 Spring Boot 附带 CBOR/Smile 转换器，按 Accept 输出二进制；'
                              'Rust 侧只输出 JSON，状态码一致（二进制编码不在 API 契约使用范围内）'}
            cases.append(c)
    # 路径形态：连续斜杠 / 结尾斜杠 / 矩阵变量 / 大小写
    for p in ['/base/gantry/list/', '/base/gantry//list', '//base/gantry/list', '/base/gantry/18/',
              '/base/gantry//18', '/base/gantry//', '/base/gantry/', '/base/gantry',
              '/base/gantry/list;a=b', '/BASE/gantry/list', '/base/gantry/list//',
              '/base/gantry/list/?pageSize=2', '/base/snapshotflow/list/', '/base/section/1/']:
        cases.append({'id': 'ct:path:%s' % p.replace('/', '_'), 'group': 'contract-path',
                      'path': p, 'method': 'GET'})
    # 请求体 Content-Type 协商（415 / 无头 / 空体）
    for ct in ['text/plain', 'application/xml', 'application/json', 'application/json;charset=UTF-8',
               'text/json', '']:
        h = {'Content-Type': ct} if ct else None
        cases.append({'id': 'ct:body-ct:%s' % (ct or 'none'), 'group': 'contract-body',
                      'path': '/base/sysutil/changeTrailInfo', 'method': 'POST',
                      'body': '{"tracks":null,"trailList":[]}', 'headers': h})
        cases.append({'id': 'ct:body-ct-submit:%s' % (ct or 'none'), 'group': 'contract-body',
                      'path': '/api/v1/large/export/submit?startTime=2025-09-01&endTime=2025-09-02',
                      'method': 'POST', 'body': '{"a":1}', 'headers': h})
    # 大整数 / 科学计数 / 前导零：数字序列化格式差异
    for p in ['/base/gantry/list?pageSize=1&id=99999999999999999999',
              '/base/gantry/list?pageSize=1&id=1e3', '/base/gantry/list?pageSize=1&id=00018',
              '/base/gantry/00018', '/base/gantry/18 ']:
        cases.append({'id': 'ct:num:%s' % p[-20:].replace('/', '_'), 'group': 'contract-number',
                      'path': p, 'method': 'GET'})
    return cases


def main():
    H.ensure_dirs()
    tables = tables_from_inventory()
    print('tables=%d' % len(tables))
    samples = collect_samples(tables)
    stages = {
        'base': gen_base(tables, samples),
        'filters': gen_filters(tables, samples),
        'query': gen_query(samples),
        'contract': gen_contract(),
    }
    for st, cs in stages.items():
        with open(os.path.join(H.CASE_DIR, st + '.json'), 'w', encoding='utf-8') as f:
            json.dump(cs, f, ensure_ascii=False, indent=0)
        print('%-9s %4d cases' % (st, len(cs)))


if __name__ == '__main__':
    main()
