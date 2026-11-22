# -*- coding: utf-8 -*-
"""PageHelper 残留污染的范围与持续长度（A/B 对照）。

A) plant → watch            紧邻：watch 被上一次的 pageSize 截断
B) plant → 另一个分页请求 → watch：中间那个请求自带 startPage，会把残留消费掉，watch 恢复正常

结论用来写进阶段12 文档：残留只影响**同线程紧随其后的第一个 MyBatis 查询**。
"""
import http.client
import json
import sys

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402

PLANT = '/base/feerecords/list?pageSize=2'
SWALLOW = '/base/snapshotflow/list?pageSize=7'
WATCH = '/progressive/snapshotflow/list?pageSize='
JAVA, RUST = 9902, 9911


def call(port, path, conn=None):
    own = conn is None
    c = conn or http.client.HTTPConnection('127.0.0.1', port, timeout=120)
    c.request('GET', path, headers={'Connection': 'keep-alive', 'Accept': '*/*'})
    r = c.getresponse()
    raw = r.read()
    if own:
        c.close()
    try:
        d = json.loads(raw.decode('utf-8'))
        return r.status, (len(d.get('rows') or []) if isinstance(d, dict) else None)
    except Exception:  # noqa: BLE001
        return r.status, None


def main():
    n = 10
    print('A) 同连接 plant → watch（紧邻）')
    hits = []
    for i in range(n):
        c = http.client.HTTPConnection('127.0.0.1', JAVA, timeout=120)
        try:
            p = call(JAVA, PLANT, c)
            w = call(JAVA, WATCH, c)
        finally:
            c.close()
        hits.append(w[1])
        print('   #%2d plant=%s watch=%s %s' % (i, p, w, '← 污染' if w[1] not in (900, None) else ''))
    print('   watch 行数分布: %s' % {v: hits.count(v) for v in set(hits)})

    print('\nB) 同连接 plant → 中间夹一个自带 startPage 的请求 → watch')
    hits2 = []
    for i in range(n):
        c = http.client.HTTPConnection('127.0.0.1', JAVA, timeout=120)
        try:
            call(JAVA, PLANT, c)
            s = call(JAVA, SWALLOW, c)
            w = call(JAVA, WATCH, c)
        finally:
            c.close()
        hits2.append(w[1])
        print('   #%2d swallow=%s watch=%s %s' % (i, s, w, '← 污染' if w[1] not in (900, None) else ''))
    print('   watch 行数分布: %s' % {v: hits2.count(v) for v in set(hits2)})

    print('\nRust 同两种序列（应恒为 900）')
    for label, mid in (('A', None), ('B', SWALLOW)):
        got = []
        for i in range(4):
            c = http.client.HTTPConnection('127.0.0.1', RUST, timeout=120)
            try:
                call(RUST, PLANT, c)
                if mid:
                    call(RUST, mid, c)
                got.append(call(RUST, WATCH, c)[1])
            finally:
                c.close()
        print('   %s: %s' % (label, got))


if __name__ == '__main__':
    main()
