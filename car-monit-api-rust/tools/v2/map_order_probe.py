# -*- coding: utf-8 -*-
"""打印 /base/vehicleweight/map 里 data 对象的键顺序（连续多次，看是否抖动）。"""
import json
import sys

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402

ORDER = {}


def hook(pairs):
    d = {}
    for k, v in pairs:
        d[k] = v
    if 'data' in d and isinstance(d['data'], dict):
        ORDER.setdefault('data_keys', []).append(list(d['data'].keys()))
    return d


def run(side, n):
    ORDER['data_keys'] = []
    for _ in range(n):
        st, h, raw, ms, e = H.http_get(H.side_url(side, '/base/vehicleweight/map'))
        json.loads(raw.decode('utf-8'), object_pairs_hook=hook)
    return ORDER['data_keys']


print('java:', run('java', 4))
print('rust:', run('rust', 4))
