# -*- coding: utf-8 -*-
"""找出 Java 侧所有会留下 PageHelper 残留的端点（泄漏源清单）。

受害者统一用 `/base/gantry/listAll`：它自己不分页，正常必然返回全表（本机 1526 行）。
只要它拿到 2 行，就说明同一线程上有一个没被消费的 startPage 残留。

每个 plant 跑 T 轮：plant → listAll（同一条连接），统计 listAll 被截断的比例；
再用「新连接单独发 listAll」作对照，确认基准行数。
"""
import http.client
import json
import sys
import time

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402

VICTIM = '/base/gantry/listAll'
PLANTS = [
    ('feerecords/list 500(缺 Mapper)', '/base/feerecords/list?pageSize=2'),
    ('feerecords/listToExport 500', '/base/feerecords/listToExport?pageSize=2'),
    ('feerecords/{id} 500', '/base/feerecords/1'),
    ('toll/list 500(非法 orderBy)', '/base/toll/list?pageSize=2&orderByColumn='
                                   + '1%3Bdrop%20table%20x'),
    ('toll/list 500(orderBy 超长)', '/base/toll/list?pageSize=2&orderByColumn='
                                    + 'a' * 600),
    ('feestationexit/list 500(数字列绑 BigDecimal 失败)',
     '/base/feestationexit/list?pageSize=2&feerate=' + '9' * 40),
    ('对照：正常分页请求（应无残留）', '/base/gantry/list?pageSize=2'),
]
ROUNDS = 8


def call(conn, path):
    conn.request('GET', path, headers={'Connection': 'keep-alive', 'Accept': '*/*'})
    r = conn.getresponse()
    raw = r.read()
    try:
        d = json.loads(raw.decode('utf-8'))
    except Exception:  # noqa: BLE001
        return r.status, None
    # listAll 直接返回顶层数组；其它端点是 {rows:[...]}
    if isinstance(d, list):
        return r.status, len(d)
    if isinstance(d, dict):
        if 'data' in d and isinstance(d['data'], list):
            return r.status, len(d['data'])
        if 'rows' in d and isinstance(d['rows'], list):
            return r.status, len(d['rows'])
    return r.status, None


def baseline():
    c = http.client.HTTPConnection('127.0.0.1', 9902, timeout=120)
    try:
        return call(c, VICTIM)
    finally:
        c.close()


def main():
    st, full = baseline()
    print('基准：新连接单独发 %-24s -> status=%s rows=%s' % (VICTIM, st, full))
    print('判定：rows < %s 即视为被上一个请求的 startPage 残留截断\n' % full)

    for name, plant in PLANTS:
        trunc = 0
        statuses = {}
        for _ in range(ROUNDS):
            c = http.client.HTTPConnection('127.0.0.1', 9902, timeout=120)
            try:
                ps, _pn = call(c, plant)
                vs, vn = call(c, VICTIM)
            finally:
                c.close()
            statuses[ps] = statuses.get(ps, 0) + 1
            if vn is not None and vn < full:
                trunc += 1
            time.sleep(0.02)
        print('   %-46s plant状态=%-18s 受害者被截断 %d/%d %s'
              % (name, ','.join(str(k) for k in statuses), trunc, ROUNDS,
                 '← 泄漏源' if trunc else '干净'))

    print('\nRust 同清单（受害者必须恒为 %s 行）' % full)
    for name, plant in PLANTS:
        vals = []
        for _ in range(3):
            c = http.client.HTTPConnection('127.0.0.1', 9911, timeout=120)
            try:
                call(c, plant)
                vals.append(call(c, VICTIM)[1])
            finally:
                c.close()
        print('   %-46s %s' % (name, vals))


if __name__ == '__main__':
    main()
