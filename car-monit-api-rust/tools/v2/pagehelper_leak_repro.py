# -*- coding: utf-8 -*-
"""Java PageHelper 线程残留的可控复现（不依赖「同连接恰好同线程」的运气）。

思路：残留是**线程级**的，会一直留到该线程上跑起下一个 MyBatis 查询为止。
所以不必在同一连接里紧挨着发 plant/victim，而是
  阶段0 先测受害者基线（N 次，全新连接）；
  阶段1 用 N 条连接各发一次 plant（往 N 个 worker 线程上铺残留）；
  阶段2 立刻测受害者 N 次 —— 落到被污染线程的那些会被截断；
  阶段3 再测 N 次 —— 残留被逐个消费掉，截断数应当衰减。

受害者选择 `/progressive/snapshotflow/list?pageSize=`：
  它自己不分页（controller 里没有 startPage()），正常必然返回全量 900 行，
  而且它经 MyBatis 查询，所以会被线程上的残留分页命中。
"""
import collections
import concurrent.futures as cf
import http.client
import json
import sys
import time

sys.path.insert(0, 'tools/v2')
import harness as H  # noqa: E402
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

PORT = {'java': 9902, 'rust': 9911}
PLANT = '/base/feerecords/list?pageSize=2'
VICTIM = '/progressive/snapshotflow/list?pageSize='
N = 30


def get(port, path, timeout=60):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        c.request('GET', path, headers={'Connection': 'close', 'Accept': '*/*'})
        r = c.getresponse()
        raw = r.read()
    finally:
        try:
            c.close()
        except Exception:  # noqa: BLE001
            pass
    try:
        d = json.loads(raw.decode('utf-8'))
        return r.status, (len(d.get('rows') or []) if isinstance(d, dict) else None), \
            (d.get('total') if isinstance(d, dict) else None)
    except Exception:  # noqa: BLE001
        return r.status, None, None


def sweep(port, path, n, workers=10):
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda _: get(port, path), range(n)))


def main():
    print('受害者基线应当恒为全量行数；被残留分页污染时变成 plant 的 pageSize（2）\n')
    for side in ('java', 'rust'):
        port = PORT[side]
        b = sweep(port, VICTIM, N)
        c0 = collections.Counter(x[1] for x in b)
        print('[%s] 阶段0 基线 N=%d 行数分布: %s' % (side, N, dict(c0)))

        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            plants = list(ex.map(lambda _: get(port, PLANT), range(N)))
        pc = collections.Counter(x[0] for x in plants)
        print('[%s] 阶段1 铺 %d 个 plant（状态分布 %s）' % (side, N, dict(pc)))

        t0 = time.time()
        v1 = sweep(port, VICTIM, N)
        c1 = collections.Counter(x[1] for x in v1)
        trunc1 = sum(v for k, v in c1.items() if k is not None and k != max(c0))
        print('[%s] 阶段2 立刻测受害者: %s  → 被截断 %d/%d（%.0f%%）'
              % (side, dict(c1), trunc1, N, 100.0 * trunc1 / N))
        full = max(c0)
        polluted = [x for x in v1 if x[1] is not None and x[1] != full]
        if polluted:
            print('[%s]   被截断响应的 (status, rows, total) 抽样: %s'
                  % (side, polluted[:4]))
            print('[%s]   ↑ total 仍是全量 %s，只有 rows 变少，客户端看不出异常' % (side, full))

        v2 = sweep(port, VICTIM, N)
        c2 = collections.Counter(x[1] for x in v2)
        trunc2 = sum(v for k, v in c2.items() if k is not None and k != max(c0))
        print('[%s] 阶段3 再测一轮      : %s  → 被截断 %d/%d（衰减）  耗时 %.1fs\n'
              % (side, dict(c2), trunc2, N, time.time() - t0))

    print('对照：同一时间直接单独发受害者（新连接，无 plant）')
    for side in ('java', 'rust'):
        print('  [%s] %s' % (side, collections.Counter(x[1] for x in sweep(PORT[side], VICTIM, 10))))


if __name__ == '__main__':
    main()
