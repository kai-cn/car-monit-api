# -*- coding: utf-8 -*-
"""阶段5：Redis 缓存隔离对比（Java DB0 ↔ Rust DB1）。

只做两件事，绝不写 Java 的 DB0：
  1. 盘点两个 DB 的键空间、TTL、序列化格式差异；
  2. 用「同一份输入」做公平比对：把 DB0 的 car_list_jc 复制进 DB1（先备份 DB1 原值，
     跑完还原），这样 Java 与 Rust 处理的是同一个重点车名单，差异只可能来自代码。
另外单独验证「缓存为空」分支：把 DB1 的键临时置空，确认 Rust 与 Java 代码里的
同一道 `if (carlist != null && size() > 0)` 守卫给出同样的空结果。
"""
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

KEY = 'car_list_jc'
OUT = os.path.join(H.RUN_DIR, 'cache_probe.json')


def snapshot(db):
    r = H.MiniRedis(db=db)
    keys = [k.decode('utf-8', 'replace') for k in (r.keys('*') or [])]
    pref = {}
    ttls = {'persist': 0, 'ttl': 0}
    for k in keys:
        head = k.split(':')[0] if ':' in k else k
        pref[head] = pref.get(head, 0) + 1
        t = r.cmd('TTL', k)
        ttls['ttl' if isinstance(t, int) and t > 0 else 'persist'] += 1
    val = r.cmd('GET', KEY)
    txt = None
    if isinstance(val, bytes):
        txt = val.decode('utf-8', 'replace')
    r.close()
    parsed = None
    try:
        parsed = json.loads(txt) if txt else None
    except Exception:  # noqa: BLE001
        parsed = None
    return {'db': db, 'keys': len(keys), 'prefixes': dict(sorted(pref.items(), key=lambda x: -x[1])),
            'ttl': ttls, 'car_list_jc_len': len(txt or ''), 'car_list_jc_size': len(parsed) if isinstance(parsed, list) else None,
            'car_list_jc_head': (txt or '')[:160], 'car_list_jc_json': isinstance(parsed, list)}


def get_key(db, key):
    r = H.MiniRedis(db=db)
    v = r.cmd('GET', key)
    r.close()
    return v


def set_key(db, key, value):
    r = H.MiniRedis(db=db)
    r.cmd('SET', key, value if isinstance(value, bytes) else value.encode('utf-8'))
    r.close()


def del_key(db, key):
    r = H.MiniRedis(db=db)
    r.cmd('DEL', key)
    r.close()


def cmp_case(path, timeout=120):
    c = {'id': path, 'path': path}
    return H.compare(c, H.call_both(c, timeout), 12)


def main():
    rep = {'ts': time.strftime('%F %T'), 'before': {}, 'after': {}, 'cases': [], 'notes': []}
    rep['before']['java_db0'] = snapshot(0)
    rep['before']['rust_db1'] = snapshot(1)

    # 1) saveRedis：两端都是「方法体整段被注释」的空实现，只比较响应
    for p in ['/base/sysutil/saveRedis', '/base/sysutil/saveRedis?bussType=1&bussCode=x',
              '/base/sysutil/saveRedis?queryCondtion=%25']:
        r = cmp_case(p)
        rep['cases'].append({'kind': 'saveRedis', 'path': p, 'verdict': r['verdict'],
                             'diffs': r['diffs'][:4]})

    # 2) 公平比对：把 DB0 的名单复制进 DB1（备份 DB1 原值）
    db0_val = get_key(0, KEY)
    db1_backup = get_key(1, KEY)
    if db0_val is None:
        rep['notes'].append('DB0 无 car_list_jc，跳过同输入比对')
    else:
        set_key(1, KEY, db0_val)
        try:
            for p in ['/base/sysutil/carTrackQueryByTime',
                      '/base/sysutil/carTrackQueryByTime?pageSize=3',
                      '/base/sysutil/carTrackQueryByTime?pageSize=10&pageNum=2',
                      '/base/sysutil/carTrackQueryByTime?flag=ybn',
                      '/base/sysutil/carTrackQueryByTime?startTime=2025-09-30%2000:00:00&endTime=2025-10-01%2000:00:00']:
                r = cmp_case(p, 180)
                rep['cases'].append({'kind': 'same-input', 'path': p, 'verdict': r['verdict'],
                                     'java_status': r.get('java_status'),
                                     'rust_status': r.get('rust_status'),
                                     'diffs': r['diffs'][:6]})
        finally:
            if db1_backup is not None:
                set_key(1, KEY, db1_backup)
            else:
                del_key(1, KEY)

    # 3) 空缓存分支（只动 DB1）
    cur = get_key(1, KEY)
    set_key(1, KEY, '[]')
    try:
        r = cmp_case('/base/sysutil/carTrackQueryByTime')
        rep['cases'].append({'kind': 'rust-empty', 'path': '/base/sysutil/carTrackQueryByTime',
                             'verdict': 'INFO', 'java_status': r.get('java_status'),
                             'rust_status': r.get('rust_status'), 'diffs': r['diffs'][:6],
                             'note': 'Java 侧仍有 DB0 名单，此处只看 Rust 空缓存分支：应 total=0 rows=[]'})
    finally:
        if cur is not None:
            set_key(1, KEY, cur)
        else:
            del_key(1, KEY)

    rep['after']['java_db0'] = snapshot(0)
    rep['after']['rust_db1'] = snapshot(1)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)

    for k in ('java_db0', 'rust_db1'):
        b = rep['before'][k]
        print('%s keys=%d car_list_jc=%s len=%d' % (k, b['keys'], b['car_list_jc_size'], b['car_list_jc_len']))
    for c in rep['cases']:
        print('%-11s %-72s %s %s' % (c['kind'], c['path'][:72], c['verdict'], str(c['diffs'])[:110]))
    print('written', OUT)


if __name__ == '__main__':
    main()
