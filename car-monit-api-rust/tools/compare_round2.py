# -*- coding: utf-8 -*-
"""第二轮对比：分页、过滤、非法 ID、POST、必填校验、405。"""
import json
import sys
import urllib.request
import urllib.error
import urllib.parse

JAVA = 'http://127.0.0.1:9902'
RUST = 'http://127.0.0.1:9911'


def fetch(base, path, method='GET', body=None, timeout=60):
    url = base + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def jload(raw):
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return raw.decode('utf-8', 'replace')


def scrub(obj):
    if isinstance(obj, dict):
        for k in ('id', 'timestamp', 'taskId'):
            obj.pop(k, None)
        for v in obj.values():
            scrub(v)
    elif isinstance(obj, list):
        for v in obj:
            scrub(v)


def diff(a, b, path='$', out=None, limit=10):
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if type(a) != type(b):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(float(a) - float(b)) <= max(1e-9, abs(float(a)) * 1e-9):
                return out
        out.append('%s type %s(%r) != %s(%r)' % (path, type(a).__name__, a, type(b).__name__, b))
        return out
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append('%s keys only-java=%s only-rust=%s' % (path, sorted(ka - kb)[:8], sorted(kb - ka)[:8]))
        for k in sorted(ka & kb):
            diff(a[k], b[k], path + '.' + k, out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append('%s len %d != %d' % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diff(a[i], b[i], '%s[%d]' % (path, i), out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, float) or isinstance(b, float):
        if abs(a - b) > max(1e-9, abs(a) * 1e-9):
            out.append('%s number %r != %r' % (path, a, b))
    else:
        if a != b:
            out.append('%s %r != %r' % (path, a, b))
    return out


def get_json(path):
    st, raw = fetch(JAVA, path)
    return st, jload(raw)


def sample_list(path, key, n=1):
    st, v = get_json(path)
    try:
        rows = v.get('rows') or []
        return rows[n - 1].get(key)
    except Exception:
        return None


# 动态样本
sample = {}
st, v = get_json('/base/snapshotflow/list?pageNum=1&pageSize=1')
try:
    row = v['rows'][0]
    sample['plate'] = row.get('platenumber')
    sample['gantrycode'] = row.get('gantrycode')
    sample['gantryname'] = row.get('gantryname')
    sample['sectioncode'] = row.get('sectioncode')
    sample['sectionname'] = row.get('sectionname')
    sample['roadname'] = row.get('roadname')
    sample['tollname'] = row.get('tollname')
    sample['orgname'] = row.get('orgname')
    sample['direction'] = row.get('direction')
except Exception:
    pass

st, v = get_json('/base/gantry/list?pageNum=1&pageSize=1')
try:
    g = v['rows'][0]
    sample['g_gantry_name'] = g.get('gantryName')
    sample['g_road_code'] = g.get('roadCode')
    sample['g_section_code'] = g.get('sectionCode')
    sample['g_toll_code'] = g.get('tollCode')
    sample['g_org_code'] = g.get('orgCode')
    sample['g_hex_code'] = g.get('hexCode')
    sample['g_city_code'] = g.get('cityCode')
    sample['g_id'] = g.get('id')
except Exception:
    pass

st, v = get_json('/base/toll/list?pageNum=1&pageSize=1')
try:
    t = v['rows'][0]
    sample['toll_name'] = t.get('tollName')
    sample['toll_road'] = t.get('roadCode')
    sample['toll_code'] = t.get('tollCode')
    sample['toll_org'] = t.get('orgCode')
except Exception:
    pass

st, v = get_json('/base/trailtracks/list?pageNum=1&pageSize=1')
try:
    sample['trail_uuid'] = v['rows'][0].get('uuid')
except Exception:
    pass

CASES = []


def add(method, path, body=None):
    CASES.append((method, path, body))


# ---- 分页 ----
for p in ['fwqjcxx', 'sfsjcxx', 'sfzjcxx', 'feeGantry', 'feeStationEnter', 'feestationexit',
          'snapshotflow', 'provcapture', 'stationcapture', 'gantry', 'gantryIp', 'vehicleweight',
          'section', 'toll', 'tollStationIp', 'org', 'trailtracks']:
    add('GET', '/base/%s/list?pageNum=2&pageSize=1' % p)
    add('GET', '/base/%s/list?pageNum=1&pageSize=0' % p)
    add('GET', '/base/%s/list?pageNum=-1&pageSize=-5' % p)
add('GET', '/manager/fwqclls/list?pageNum=2&pageSize=1')

# ---- 快照过滤 ----
for q in [
    'platenumber=%s' % sample.get('plate', ''),
    'gantrycode=%s' % sample.get('gantrycode', ''),
    'gantryname=%s' % sample.get('gantryname', ''),
    'sectioncode=%s' % sample.get('sectioncode', ''),
    'sectionname=%s' % sample.get('sectionname', ''),
    'roadname=%s' % sample.get('roadname', ''),
    'tollname=%s' % sample.get('tollname', ''),
    'orgname=%s' % sample.get('orgname', ''),
    'direction=%s' % sample.get('direction', ''),
    'sectionCodeStr=%s,%s' % (sample.get('sectioncode', ''), sample.get('sectioncode', '')),
    'code=%s,%s' % (sample.get('gantrycode', ''), sample.get('gantrycode', '')),
]:
    add('GET', '/base/snapshotflow/list?pageNum=1&pageSize=5&' + urllib.parse.quote(q, safe='=&,'))

# ---- gantry / toll 过滤 ----
for q in [
    'gantryName=%s' % sample.get('g_gantry_name', ''),
    'roadCode=%s' % sample.get('g_road_code', ''),
    'sectionCode=%s' % sample.get('g_section_code', ''),
    'tollCode=%s' % sample.get('g_toll_code', ''),
    'orgCode=%s' % sample.get('g_org_code', ''),
    'hexCode=%s' % sample.get('g_hex_code', ''),
    'cityCode=%s' % sample.get('g_city_code', ''),
]:
    add('GET', '/base/gantry/list?pageNum=1&pageSize=5&' + urllib.parse.quote(q, safe='='))
for q in [
    'tollName=%s' % sample.get('toll_name', ''),
    'roadCode=%s' % sample.get('toll_road', ''),
    'tollCode=%s' % sample.get('toll_code', ''),
    'orgCode=%s' % sample.get('toll_org', ''),
]:
    add('GET', '/base/toll/list?pageNum=1&pageSize=5&' + urllib.parse.quote(q, safe='='))

# ---- 非法/不存在 ID ----
add('GET', '/base/gantryIp/abc')
add('GET', '/base/tollStationIp/abc')
add('GET', '/manager/fwqclls/abc')
add('GET', '/base/gantry/no-such-id')
add('GET', '/base/section/no-such-id')
add('GET', '/base/sysutilTest/syncSuspiciousCar2')
add('GET', '/base/sysutilTest/syncSuspiciousCar10')
add('GET', '/base/sysutilTest/separateSnapshotFlowTimeList')

# ---- POST ----
add('POST', '/base/sysutil/changeTrailInfo', {})
add('POST', '/base/sysutil/changeTrailInfo', {'trailUuid': 'x', 'trailList': [], 'tracks': {}})
add('POST', '/api/v1/large/export/submit?type=snapshot', None)
add('POST', '/api/v1/large/export/submit?type=snapshot&startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', None)
add('POST', '/api/v1/unified/snapshot/export/submit?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', {})
add('POST', '/api/v1/unified/snapshot/export/submit', {})
add('POST', '/api/v1/unified/bad/export/submit?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', {})
add('POST', '/api/v1/large/sync/repair', None)
add('POST', '/api/v1/large/sync/repair?type=snapshot', None)

# ---- 405 ----
add('POST', '/base/gantry/list')
add('GET', '/base/sysutil/changeTrailInfo')


def main():
    ok = bad = 0
    for method, path, body in CASES:
        js, jraw = fetch(JAVA, path, method, body)
        rs, rraw = fetch(RUST, path, method, body)
        j, r = jload(jraw), jload(rraw)
        scrub(j)
        scrub(r)
        label = '%s %s %s' % (method, js, path.split('?')[0])
        if js != rs:
            print('[STATUS] %s -> rust=%s' % (label, rs))
            print('   java:', str(j)[:200])
            print('   rust:', str(r)[:200])
            bad += 1
            continue
        ds = diff(j, r)
        if ds:
            print('[DIFF] %s' % label)
            for d in ds[:8]:
                print('   ', d[:300])
            bad += 1
        else:
            ok += 1
    print('\nSUMMARY ok=%d bad=%d' % (ok, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
