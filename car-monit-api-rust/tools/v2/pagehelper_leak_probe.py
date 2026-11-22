# -*- coding: utf-8 -*-
"""证明 Java 侧 PageHelper ThreadLocal 残留会污染「同一个 Tomcat 工作线程上的下一个请求」。

机制假设：
  RuoYi 的 BaseController.startPage() 把分页参数放进 PageHelper 的 ThreadLocal，
  正常由紧随其后的 MyBatis 查询消费并清除。若那条查询没执行（参数校验先抛异常、
  或走了不查库的分支），ThreadLocal 就留在池化线程上；下一个被调度到该线程的请求
  会莫名被上一次的分页参数截断。

验证方式：在**一条 keep-alive 连接**上先后发两个请求（同线程），
  制造残留的请求：/base/snapshotflow/list?pageSize=2&orderByColumn=<非法> —— startPage 已执行、
                                    查询前 orderBy 校验抛 500；
  观察的请求：/progressive/snapshotflow/list?pageSize=  —— 该端点自己不分页，应该 900 行。
对照组：同样的观察请求换一条新连接发（大概率换线程），应为 900 行。
"""
import http.client
import json
import sys
import urllib.parse

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402

# 候选「制造残留」的请求：都是 startPage() 已经执行、但紧随其后的 MyBatis 查询没跑成的形状
PLANTS = {
    # 缺 Mapper XML：startPage() 之后 selectList 抛 BindingException → 页面无人消费
    'feerecords-500': '/base/feerecords/list?pageSize=2',
    # orderBy 非法：PageHelper 在查询里才校验 orderBy，异常发生在查询内部，页面可能已清除
    'bad-order': '/base/snapshotflow/list?pageSize=2&orderByColumn=' + urllib.parse.quote('1;drop table x'),
    # 正常分页请求（对照组，应当自己把页面消费掉）
    'normal': '/base/snapshotflow/list?pageSize=2',
}
PLANT = PLANTS['feerecords-500']
WATCH = '/progressive/snapshotflow/list?pageSize='


def call(conn, path):
    conn.request('GET', path, headers={'Connection': 'keep-alive', 'Accept': '*/*'})
    r = conn.getresponse()
    raw = r.read()
    try:
        d = json.loads(raw.decode('utf-8'))
        n = len(d.get('rows') or []) if isinstance(d, dict) else None
        tot = d.get('total') if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        n, tot = None, None
    return r.status, n, tot


def fresh(path):
    c = http.client.HTTPConnection('127.0.0.1', 9902, timeout=60)
    try:
        return call(c, path)
    finally:
        c.close()


def main():
    print('对照：新连接单独发 watch ->', fresh(WATCH))
    for name, plant in PLANTS.items():
        print('对照：新连接单独发 %-14s ->' % name, fresh(plant))

    for name, plant in PLANTS.items():
        print('\n同一连接（同线程）：%-14s 之后立刻 watch' % name)
        hits = 0
        for i in range(8):
            c = http.client.HTTPConnection('127.0.0.1', 9902, timeout=60)
            try:
                p = call(c, plant)
                w = call(c, WATCH)
                tagged = '← 被残留分页截断' if w[1] not in (900, None) else ''
                print('   #%d plant=%s  watch=%s %s' % (i, p, w, tagged))
                if w[1] not in (900, None):
                    hits += 1
            finally:
                c.close()
        print('   残留命中 %d/8' % hits)

    print('\n反向对照：先 watch 再 plant（watch 不该受影响）')
    c = http.client.HTTPConnection('127.0.0.1', 9902, timeout=60)
    try:
        print('   watch=%s plant=%s watch2=%s' % (call(c, WATCH), call(c, PLANT), call(c, WATCH)))
    finally:
        c.close()

    print('\nRust 同场景（应当始终是 900）:')
    for name, path in (('plant', PLANT), ('watch', WATCH)):
        st, h, raw, ms, e = H.http_get(H.side_url('rust', path))
        try:
            d = json.loads(raw.decode('utf-8'))
            print('   %-6s %s rows=%s total=%s' % (name, st, len(d.get('rows') or []), d.get('total')))
        except Exception:  # noqa: BLE001
            print('   %-6s %s %r' % (name, st, (raw or b'')[:60]))


if __name__ == '__main__':
    main()
