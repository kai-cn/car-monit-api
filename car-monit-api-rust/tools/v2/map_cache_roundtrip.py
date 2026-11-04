# -*- coding: utf-8 -*-
"""vehicleweight/map 的缓存往返实验（只动 DB1，跑完还原）。

目的：确认 Rust 的「写缓存 → 读缓存」往返是无损的，而 Java 在同一环节会掉一天，
从而把 gap:weight-map 这条差异钉在「Java 侧 FastJSON 按本地时区解析、Jackson 按 UTC 输出」
上，而不是 Rust 的取值逻辑不同。
"""
import json
import sys

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402

U = ['18f8e2af-6ebe-4b33-8f37-a688f441de37',
     '7379e7aa-e325-449b-9728-b8f6940c77f1']
KEYS = ['DATE_BorderWeighingCapture:' + u for u in U]


def payload_check_time(d1, k):
    v = d1.cmd('GET', k)
    if not isinstance(v, bytes):
        return 'MISS'
    try:
        return json.loads(v.decode('utf-8', 'replace')).get('checkTime')
    except Exception:  # noqa: BLE001
        return 'unparseable(java `…L` 写法)'


def map_check(side):
    st, h, raw, ms, e = H.http_get(H.side_url(side, '/base/vehicleweight/map'))
    d = H.parse_json(raw) or {}
    data = d.get('data') or {}
    return {u[:8]: (data.get(u) or {}).get('checkTime') for u in U}


def main():
    d1 = H.MiniRedis(db=1)
    backup = {k: d1.cmd('GET', k) for k in KEYS}
    print('备份 DB1:', {k[-8:]: payload_check_time(d1, k) for k in KEYS})

    for k in KEYS:
        d1.cmd('DEL', k)
    print('冷缓存(回源)  rust:', map_check('rust'), '  java:', map_check('java'))
    print('  回源后 DB1:', {k[-8:]: payload_check_time(d1, k) for k in KEYS})
    print('热缓存(命中)  rust:', map_check('rust'), '  java:', map_check('java'))

    for k, v in backup.items():
        if isinstance(v, bytes):
            d1.cmd('SET', k, v)
        else:
            d1.cmd('DEL', k)
    print('还原后 DB1:', {k[-8:]: payload_check_time(d1, k) for k in KEYS})

    # 列表路径（不经缓存，直接查库）作为基准
    st, h, raw, ms, e = H.http_get(H.side_url('rust', '/base/vehicleweight/list?pageSize=200'))
    rows = (H.parse_json(raw) or {}).get('rows') or []
    want = {u[:8] for u in U}
    print('DB 基准(rust list):', {(r.get('datauuid') or '')[:8]: r.get('checkTime')
                                 for r in rows if (r.get('datauuid') or '')[:8] in want})
    st, h, raw, ms, e = H.http_get(H.side_url('java', '/base/vehicleweight/list?pageSize=200'))
    rows = (H.parse_json(raw) or {}).get('rows') or []
    print('DB 基准(java list):', {(r.get('datauuid') or '')[:8]: r.get('checkTime')
                                 for r in rows if (r.get('datauuid') or '')[:8] in want})
    d1.close()


if __name__ == '__main__':
    main()
