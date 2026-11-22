# -*- coding: utf-8 -*-
"""同输入公平比对：把 Java(DB0) 的若干缓存键原文复制到 Rust(DB1)，再跑指定用例。

用途：区分「代码差异」与「两侧缓存内容不同导致的差异」。
只写 DB1（Rust 自己的命名空间），DB1 原值会先备份、跑完还原；**不写 DB0**。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

OUT = os.path.join(H.RUN_DIR, 'same_input.json')

# (键前缀/精确键, 要比对的用例路径)
GROUPS = [
    (['DATE_BorderWeighingCapture:'], [
        '/base/vehicleweight/map',
        '/base/vehicleweight/map?pageSize=2',
    ]),
]


def snapshot(r, keys):
    out = {}
    for k in keys:
        v = r.cmd('GET', k)
        out[k] = v if isinstance(v, bytes) else None
    return out


def main():
    H.ensure_dirs()
    rep = {'ts': time.strftime('%F %T'), 'groups': []}
    for prefixes, paths in GROUPS:
        src = H.MiniRedis(db=0)
        keys = []
        for pre in prefixes:
            keys += [k.decode('utf8', 'replace') for k in (src.keys(pre + '*') or [])]
        vals = {k: src.cmd('GET', k) for k in keys}
        src.close()
        d1 = H.MiniRedis(db=1)
        backup = snapshot(d1, keys)
        loaded = 0
        for k, v in vals.items():
            if isinstance(v, bytes):
                d1.cmd('SET', k, v)
                loaded += 1
        d1.close()

        results = []
        for p in paths:
            c = {'id': p, 'path': p}
            res = H.compare(c, H.call_both(c, 120), 10)
            results.append({'path': p, 'verdict': res['verdict'],
                            'java_status': res.get('java_status'),
                            'rust_status': res.get('rust_status'),
                            'diffs': res['diffs'][:6]})
        d1 = H.MiniRedis(db=1)
        for k in keys:
            if backup.get(k) is not None:
                d1.cmd('SET', k, backup[k])
            else:
                d1.cmd('DEL', k)
        d1.close()
        rep['groups'].append({'prefixes': prefixes, 'keys_copied': loaded, 'results': results})
        print('prefixes=%s copied=%d' % (prefixes, loaded))
        for r in results:
            print('   %-34s %-9s %s' % (r['path'][:34], r['verdict'], str(r['diffs'])[:100]))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print('written', OUT)


if __name__ == '__main__':
    main()
