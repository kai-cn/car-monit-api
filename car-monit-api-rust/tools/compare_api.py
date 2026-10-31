# -*- coding: utf-8 -*-
"""对比 Java(9902) 与 Rust(9911) 的只读接口响应。"""
import json
import sys
import urllib.request
import urllib.error

JAVA = 'http://127.0.0.1:9902'
RUST = 'http://127.0.0.1:9911'


def fetch(base, path, timeout=60):
    url = base + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def jload(raw):
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return raw.decode('utf-8', 'replace')


def diff(a, b, path='$', out=None, limit=8):
    """收集差异；数值允许 1e-9 相对误差。"""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if type(a) != type(b):
        # int/float 互认
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(float(a) - float(b)) <= max(1e-9, abs(float(a)) * 1e-9):
                return out
        out.append('%s type %s(%r) != %s(%r)' % (path, type(a).__name__, a, type(b).__name__, b))
        return out
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append('%s keys only-java=%s only-rust=%s' % (path, sorted(ka - kb)[:10], sorted(kb - ka)[:10]))
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


RANGE = ('2025-09-08 00:00:00', '2025-09-09 00:00:00')


def discover_plate():
    path = '/base/snapshotflow/list?pageNum=1&pageSize=1&applyTime1=%s&applyTime2=%s' % (
        RANGE[0].replace(' ', '%20'), RANGE[1].replace(' ', '%20'))
    st, raw = fetch(JAVA, path)
    try:
        v = json.loads(raw.decode('utf-8'))
        return v['rows'][0]['platenumber']
    except Exception:
        return ''


PLATE = discover_plate()
ENDPOINTS = []
for p in ['fwqjcxx', 'sfsjcxx', 'sfzjcxx']:
    ENDPOINTS += [('/base/%s/list?pageNum=1&pageSize=2' % p, 'list'),
                  ('/base/%s/listAll' % p, 'listAll')]
ENDPOINTS += [
    ('/manager/fwqclls/list?pageNum=1&pageSize=2', 'list'),
    ('/base/feeGantry/list?pageNum=1&pageSize=2', 'list'),
    ('/base/feerecords/list?pageNum=1&pageSize=2', 'list'),
    ('/base/feerecords/listToExport?pageNum=1&pageSize=2', 'listToExport'),
    ('/base/feeStationEnter/list?pageNum=1&pageSize=2', 'list'),
    ('/base/feestationexit/list?pageNum=1&pageSize=2', 'list'),
    ('/base/snapshotflow/list?pageNum=1&pageSize=5&applyTime1=%s&applyTime2=%s&platenumber=%s' % (RANGE[0].replace(' ','%20'), RANGE[1].replace(' ','%20'), PLATE), 'list'),
    ('/base/snapshotflow/listToExport?pageNum=1&pageSize=5&applyTime1=%s&applyTime2=%s&platenumber=%s' % (RANGE[0].replace(' ','%20'), RANGE[1].replace(' ','%20'), PLATE), 'listToExport'),
    ('/base/provcapture/list?pageNum=1&pageSize=2', 'list'),
    ('/base/stationcapture/list?pageNum=1&pageSize=2', 'list'),
    ('/base/gantry/list?pageNum=1&pageSize=2', 'list'),
    ('/base/gantry/listAll', 'listAll'),
    ('/base/gantryIp/list?pageNum=1&pageSize=2', 'list'),
    ('/base/vehicleweight/list?pageNum=1&pageSize=2', 'list'),
    ('/base/vehicleweight/map', 'map'),
    ('/base/section/list?pageNum=1&pageSize=2', 'list'),
    ('/base/section/listAll', 'listAll'),
    ('/base/toll/list?pageNum=1&pageSize=2', 'list'),
    ('/base/toll/listAll', 'listAll'),
    ('/base/tollStationIp/list?pageNum=1&pageSize=2', 'list'),
    ('/base/org/list?pageNum=1&pageSize=2', 'list'),
    ('/base/org/listAll', 'listAll'),
    ('/base/trailtracks/list?pageNum=1&pageSize=2', 'list'),

    ('/api/v1/large/snapshot?startTime=%s&endTime=%s&pageNum=1&pageSize=5&fuzzyFields.platenumber=%s' % (RANGE[0].replace(' ','%20'), RANGE[1].replace(' ','%20'), PLATE), 'large'),
    ('/api/v1/large/fee?startTime=2025-01-01 00:00:00&endTime=2026-12-31 23:59:59&pageNum=1&pageSize=1', 'large'),
    ('/api/v1/large/trail?startTime=2025-01-01 00:00:00&endTime=2026-12-31 23:59:59&pageNum=1&pageSize=1', 'large'),
    ('/api/v1/unified/snapshot/list?startTime=%s&endTime=%s&pageNum=1&pageSize=5&fuzzyFields.platenumber=%s' % (RANGE[0].replace(' ','%20'), RANGE[1].replace(' ','%20'), PLATE), 'unified'),
    ('/progressive/snapshotflow/list?startTime=%s&endTime=%s&pageSize=50&platenumber=%s' % (RANGE[0].replace(' ','%20'), RANGE[1].replace(' ','%20'), PLATE), 'progressive'),
    ('/progressive/feerecords/list?startTime=2025-01-01 00:00:00&endTime=2026-12-31 23:59:59&pageSize=1', 'progressive'),
    ('/progressive/trailfitting/list?startTime=2025-01-01 00:00:00&endTime=2026-12-31 23:59:59&pageSize=1', 'progressive'),
    ('/progressive/scale-level', 'scale'),
    ('/not-exist', '404'),
    ('/api/v1/large/foo?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', 'err'),
    ('/api/v1/large/snapshot?endTime=2025-11-17%2000:00:00', 'err'),
    ('/api/v1/large/carTrackQueryByCarNo?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', 'err'),
    ('/api/v1/large/stats/group?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', 'err'),
    ('/api/v1/unified/bad/list?startTime=2025-11-16%2000:00:00&endTime=2025-11-17%2000:00:00', 'err'),
    ('/api/v1/unified/snapshot/list?endTime=2025-11-17%2000:00:00', 'err'),
]


DETAIL_KEYS = {
    '/base/fwqjcxx': 'agentPk', '/base/sfsjcxx': 'agentPk', '/base/sfzjcxx': 'agentPk',
    '/manager/fwqclls': 'bigId', '/base/feeGantry': 'bigId', '/base/feerecords': 'bigId',
    '/base/feeStationEnter': 'bigId', '/base/feestationexit': 'bigId',
    '/base/snapshotflow': 'bigId', '/base/provcapture': 'bigId', '/base/stationcapture': 'bigId',
    '/base/gantry': 'id', '/base/gantryIp': 'id', '/base/vehicleweight': 'dataSource',
    '/base/section': 'id', '/base/toll': 'id', '/base/tollStationIp': 'id',
    '/base/org': 'bigId', '/base/trailtracks': 'uuid',
}

for base, key in DETAIL_KEYS.items():
    st, raw = fetch(JAVA, base + '/list?pageNum=1&pageSize=1')
    try:
        v = json.loads(raw.decode('utf-8'))
        row = (v.get('rows') or [None])[0]
        ident = row.get(key) if row else None
        if ident not in (None, ''):
            ENDPOINTS.append(('%s/%s' % (base, ident), 'detail'))
    except Exception:
        pass

R = RANGE[0].replace(' ', '%20'), RANGE[1].replace(' ', '%20')
ENDPOINTS += [
    ('/api/v1/large/carTrackQueryByCarNo?carNo=%s&startTime=%s&endTime=%s&pageNum=1&pageSize=5' % (PLATE, R[0], R[1]), 'large'),
    ('/api/v1/large/stats/group?type=snapshot&startTime=%s&endTime=%s&groupBy=platenumber&topN=5' % R, 'large'),
    ('/api/v1/large/export/status/no-such-task', 'large'),
    ('/api/v1/unified/export/status/no-such-task', 'unified'),
    ('/progressive/scale-level', 'scale'),
    ('/base/sysutil/saveRedis', 'ajax'),
    ('/base/sysutil/getByTrailBo', 'raw'),
    ('/base/sysutilTest/syncBaseInfo', 'ajax'),
    ('/base/sysutilTest/syncCurrentTrack', 'ajax'),
    ('/base/sysutilTest/syncHistroyTrack', 'ajax'),
    ('/base/sysutilTest/syncSuspiciousCar1', 'void'),
    ('/base/sysutilTest/syncOdsSzdnGantry', 'void'),
    ('/base/sysutilTest/separateSnapshotFlowTimeList', 'void'),
]


def quote_path(p):
    return p.replace(' ', '%20')


def main():
    # 清理 Java 侧抓拍负缓存（Python/Go 迁移曾写入不兼容 JSON，会让 Java 反序列化 500）
    try:
        import subprocess
        py = '../car-monit-api-python/.venv/Scripts/python.exe'
        subprocess.run([py, '-c',
            "import redis;r=redis.Redis(host='127.0.0.1',port=6379,db=0);"
            "[r.delete('DATE_BorderWeighingCapture:'+u) for u in "
            "['18f8e2af-6ebe-4b33-8f37-a688f441de37','7379e7aa-e325-449b-9728-b8f6940c77f1']]"],
            check=False)
    except Exception as e:
        print('warmup skipped:', e)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ok = 0
    bad = 0
    for path, kind in ENDPOINTS:
        if only and only not in path:
            continue
        js, jraw = fetch(JAVA, quote_path(path))
        rs, rraw = fetch(RUST, quote_path(path))
        j = jload(jraw)
        r = jload(rraw)
        # 随机行 key / 当前时间戳不属于业务语义
        def scrub(obj):
            if isinstance(obj, dict):
                obj.pop('id', None)
                obj.pop('timestamp', None)
                for vv in obj.values():
                    scrub(vv)
            elif isinstance(obj, list):
                for vv in obj:
                    scrub(vv)
        scrub(j)
        scrub(r)
        label = '%s %s' % (js, path.split('?')[0])
        if js != rs:
            print('[STATUS] %s -> java=%s rust=%s' % (label, js, rs))
            bad += 1
            continue
        if kind == 'void':
            if isinstance(j, (dict, list)):
                scrub(j)
                scrub(r)
                ds = diff(j, r)
                if ds:
                    print('[BODY] %s' % label)
                    for d in ds[:5]:
                        print('   ', d[:300])
                    bad += 1
                else:
                    ok += 1
                continue
            if jraw.strip() != rraw.strip():
                print('[BODY] %s java=%r rust=%r' % (label, jraw[:200], rraw[:200]))
                bad += 1
            else:
                ok += 1
            continue
        ds = diff(j, r)
        # 大列表仅比较结构/首元素，差异会打印前 8 条
        if ds:
            bad += 1
            print('[DIFF] %s' % label)
            for d in ds[:8]:
                print('   ', d[:400])
        else:
            ok += 1
    print('\nSUMMARY ok=%d bad=%d' % (ok, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
