# -*- coding: utf-8 -*-
"""阶段4b：有副作用端点的实测（用户已授权全部实测）。

每个端点都记录「调用前 → Java 调用后 → Rust 调用后」的状态差：
  * Redis：Java 写 DB0、Rust 写 DB1（隔离），分别统计键数量与目标键的内容长度；
  * GaussDB：共用同一份数据，用 list 接口的 total 观测行数变化（不直接连库）；
  * 响应：状态码 / Content-Type / body 前 200 字节；Java 的 sysutilTest 系列返回 void（200 空体）。
最后再跑一遍「字典依赖型」只读端点，确认刷缓存后双端仍然一致。
"""
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

OUT = os.path.join(H.RUN_DIR, 'write_probe.json')
W_START = '2025-09-01 00:00:00'
W_END = '2025-10-31 23:59:59'

TABLE_TOTALS = ['/base/snapshotflow/list', '/base/feestationexit/list', '/base/trailtracks/list',
                '/base/gantry/list', '/base/toll/list', '/base/section/list',
                '/manager/fwqclls/list', '/base/feeStationEnter/list']

WRITE_ENDPOINTS = [
    ('GET', '/base/sysutilTest/syncBaseInfo'),
    ('GET', '/base/sysutilTest/syncOdsSzdnGantry'),
    ('GET', '/base/sysutilTest/separateSnapshotFlowTimeList'),
    ('GET', '/base/sysutilTest/syncCurrentTrack'),
    ('GET', '/base/sysutilTest/syncHistroyTrack'),
] + [('GET', '/base/sysutilTest/syncSuspiciousCar%d' % i) for i in range(1, 11)] + [
    ('POST', '/api/v1/large/sync/incremental'),
    ('POST', '/api/v1/large/sync/repair'),
    ('POST', '/api/v1/large/sync/full'),
    ('POST', '/api/v1/large/export/submit?startTime=%s&endTime=%s'
     % (urllib.parse.quote(W_START), urllib.parse.quote(W_END))),
    ('POST', '/api/v1/unified/snapshot/export/submit?startTime=%s&endTime=%s'
     % (urllib.parse.quote(W_START), urllib.parse.quote(W_END))),
]

DICT_KEYS = ['car_list_jc', 'station_info', 'station_ip', 'gantry_ip', 'dev_post',
             'section_road_map', 'gantry_list', 'car_history_trail', 'car_sync_time']


def db_state(db):
    r = H.MiniRedis(db=db)
    keys = [k.decode('utf8', 'replace') for k in (r.keys('*') or [])]
    st = {'keys': len(keys)}
    for k in DICT_KEYS:
        hits = [x for x in keys if x == k or x.startswith(k + ':')]
        if not hits:
            st[k] = 0
            continue
        if hits and k not in keys:
            st[k] = 'prefix:%d' % len(hits)
        else:
            v = r.cmd('GET', k)
            st[k] = len(v) if isinstance(v, bytes) else ('type=%s' % r.cmd('TYPE', k))
    r.close()
    return st


def totals():
    out = {}
    for p in TABLE_TOTALS:
        st, h, raw, ms, e = H.http_get(H.side_url('java', p + '?pageSize=1'), timeout=90)
        d = H.parse_json(raw) or {}
        out[p.split('/')[-2]] = d.get('total')
    return out


def call(side, method, path, timeout):
    st, h, raw, ms, e = H.http_get(H.side_url(side, path), method=method,
                                   body='{}' if method == 'POST' else None, timeout=timeout)
    return {'status': st, 'ct': (h.get('content-type') or ''), 'ms': ms,
            'body': raw[:200].decode('utf-8', 'replace'), 'err': e}


def main():
    rep = {'ts': time.strftime('%F %T'), 'items': []}
    with open(os.path.join(H.RUN_DIR, 'write_progress.txt'), 'w', encoding='utf-8') as pf:
        for method, path in WRITE_ENDPOINTS:
            timeout = 600 if 'syncHistroyTrack' in path or path.endswith('/full') else 180
            before = {'db0': db_state(0), 'db1': db_state(1), 'totals': totals()}
            j = call('java', method, path, timeout)
            mid = {'db0': db_state(0), 'db1': db_state(1)}
            r = call('rust', method, path, timeout)
            after = {'db0': db_state(0), 'db1': db_state(1), 'totals': totals()}
            item = {'method': method, 'path': path, 'java': j, 'rust': r,
                    'db0_delta_java': mid['db0']['keys'] - before['db0']['keys'],
                    'db1_delta_rust': after['db1']['keys'] - mid['db1']['keys'],
                    'java_status_match': j['status'] == r['status'],
                    'totals_changed': {k: v for k, v in after['totals'].items()
                                       if v != before['totals'][k]}}
            rep['items'].append(item)
            pf.write('%s %s java=%s(%dms) rust=%s(%dms) db0+%d db1+%d %s\n' % (
                method, path, j['status'], j['ms'], r['status'], r['ms'],
                item['db0_delta_java'], item['db1_delta_rust'],
                json.dumps(item['totals_changed'], ensure_ascii=False)))
            pf.flush()
        # 刷完缓存后的字典依赖型只读复核
        recheck = []
        for p in ['/base/sysutil/getByTrailBo?locationCode=gantry:G601136060000420010',
                  '/base/sysutil/getByTrailBo?devCode=G1517360580030',
                  '/base/toll/list?pageSize=3', '/base/gantryIp/list?pageSize=3',
                  '/base/section/listAll']:
            c = {'id': p, 'path': p}
            res = H.compare(c, H.call_both(c, 120), 12)
            recheck.append({'path': p, 'verdict': res['verdict'], 'diffs': res['diffs'][:5]})
        rep['recheck'] = recheck
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        for it in rep['items']:
            print('%-5s %-52s java=%-4s rust=%-4s db0%+d db1%+d %s' % (
                it['method'], it['path'][:52], it['java']['status'], it['rust']['status'],
                it['db0_delta_java'], it['db1_delta_rust'],
                json.dumps(it['totals_changed'], ensure_ascii=False)[:60]))
        for rc in rep['recheck']:
            print('recheck %-58s %s %s' % (rc['path'][:58], rc['verdict'], str(rc['diffs'])[:90]))
        print('written', OUT)


if __name__ == '__main__':
    main()
