# -*- coding: utf-8 -*-
"""阶段12：并发一致性。

单并发比对（前面 14081 例）证明不了「状态隔离」：
  - Java 的 PageHelper 把分页参数放 ThreadLocal，`startPage()` 之后任何没 clear 的路径
    都会污染**复用同一线程**的下一个请求（RuoYi 的老问题）；
  - Rust 这边是 task-local（CURRENT_PATH / OriginalPath）+ 每请求重建的字典 + 共享连接池。

做法：
  1) 先逐个用例**串行**取基线；
  2) 再把所有（用例 × 双端 × 轮次）混在一起高并发打，每个响应都必须等于自己的基线；
  3) 额外构造一组「同一端点、不同 pageNum / orderByColumn / reasonable」的交错用例 ——
     这正是 ThreadLocal 泄漏唯一能被观察到的形状。

实现细节：每个线程复用一条 HTTP/1.1 keep-alive 连接。
不要用 urllib 现连现断：32 并发下 Windows 会因 accept 队列溢出触发 SYN 重传，
实测所有请求都被记成 ~2000ms，测不出服务端真实耗时。
"""
import argparse
import collections
import concurrent.futures as cf
import http.client
import json
import os
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
import harness as H  # noqa: E402
import stability as S  # noqa: E402  复用 canonical()（去易变字段、保持顺序敏感）

ROOT = os.path.dirname(os.path.dirname(HERE))
RES_DIR = os.path.join(ROOT, '.run', 'verify2', 'results')

PREFER = [('base', 14), ('filters', 6), ('dates', 4), ('gap', 6), ('query', 6),
          ('sysutil', 6), ('contract', 2)]

_tl = threading.local()


def conn(side):
    """线程内复用连接；服务端或网络一断就重建一次。"""
    host = urllib.parse.urlparse(H.JAVA if side == 'java' else H.RUST)
    key = (side, host.netloc)
    c = getattr(_tl, 'c', None)
    if c is None or c[0] != key:
        if c is not None:
            try:
                c[1].close()
            except Exception:  # noqa: BLE001
                pass
        conn_ = http.client.HTTPConnection(host.hostname, host.port, timeout=120)
        _tl.c = (key, conn_)
    return _tl.c[1]


def request(side, case, timeout=120):
    path = case['path']
    if not path.startswith('/'):
        path = '/' + path
    path = urllib.parse.quote(path, safe='/?&=,%-.*+~@:();[]')
    body = case.get('body')
    data = body.encode('utf-8') if isinstance(body, str) else body
    hdr = {'Accept': '*/*', 'User-Agent': 'parity-harness/2', 'Connection': 'keep-alive'}
    if data is not None:
        hdr['Content-Type'] = 'application/json'
    if case.get('headers'):
        hdr.update(case['headers'])
    method = case.get('method', 'GET')
    for attempt in (0, 1):
        t0 = time.time()
        try:
            c = conn(side)
            c.request(method, path, body=data, headers=hdr)
            r = c.getresponse()
            raw = r.read()
            return {'status': r.status, 'ct': (r.getheader('Content-Type') or '').split(';')[0].strip(),
                    'canon': S.canonical(raw), 'ms': int((time.time() - t0) * 1000),
                    'err': None, 'raw_len': len(raw)}
        except Exception as exc:  # noqa: BLE001
            try:
                conn(side).close()
            except Exception:  # noqa: BLE001
                pass
            _tl.c = None
            if attempt:
                return {'status': -1, 'ct': '', 'canon': '', 'ms': int((time.time() - t0) * 1000),
                        'err': '%s: %s' % (type(exc).__name__, exc), 'raw_len': 0}
    raise AssertionError


def load(stage):
    return json.load(open(os.path.join(ROOT, '.run', 'verify2', 'cases', stage + '.json'),
                          encoding='utf-8'))


def verdicts(stage):
    p = os.path.join(RES_DIR, stage + '.jsonl')
    out = {}
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if l.strip():
                r = json.loads(l)
                out[r['case']] = r.get('verdict')
    return out


def pick(total):
    out = []
    for stage, want in PREFER:
        try:
            cases = load(stage)
        except (FileNotFoundError, KeyError):
            continue
        v = verdicts(stage)
        # sysutil 的 POST 用例是无副作用的富集查询，也要进并发（覆盖请求体绑定 + task-local）
        good = [c for c in cases if v.get(c['id']) == 'PASS'
                and (c.get('method', 'GET') == 'GET'
                     or (stage == 'sysutil' and c.get('body')))]
        step = max(1, len(good) // max(1, want))
        out.extend(good[::step][:want])
    return out[:total] if total else out


def interleaved_paging():
    """同一端点、不同分页/排序参数交错 —— ThreadLocal 泄漏的诱饵。"""
    tables = ['/base/toll/list', '/base/gantry/list', '/base/snapshotflow/list',
              '/base/section/list']
    shapes = ['?pageNum=1&pageSize=3', '?pageNum=2&pageSize=3', '?pageNum=3&pageSize=5',
              '?pageNum=1&pageSize=3&orderByColumn=id&isAsc=asc',
              '?pageNum=2&pageSize=3&orderByColumn=id&isAsc=desc',
              '?pageNum=1&pageSize=3&reasonable=false',
              '?pageNum=0&pageSize=3&reasonable=false',
              '?pageNum=99&pageSize=3&reasonable=true',
              '?pageNum=1&pageSize=1&orderByColumn=t.id&isAsc=ascending']
    return [{'id': 'cx:%s%s' % (t, s), 'group': 'concurrency-selfmade', 'method': 'GET',
             'path': t + s} for t in tables for s in shapes]


def preflight(timeout=3):
    """双端必须先活着，否则立刻退出。
    教训：服务被工具超时连带杀掉后，探针曾在 120s 超时上空等 88 次（=永不结束）。"""
    for side in ('java', 'rust'):
        c = H.http_get(H.side_url(side, '/base/toll/list?pageSize=1'), timeout=timeout)
        if c[0] != 200:
            return False, '%s 预检失败 status=%s err=%s' % (side, c[0], c[4])
    return True, 'ok'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', type=int, default=44)
    ap.add_argument('--rounds', type=int, default=4)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--timeout', type=int, default=20)
    ap.add_argument('--no-selfmade', action='store_true')
    a = ap.parse_args()

    okp, msg = preflight()
    if not okp:
        print(msg)
        return 1
    print('预检通过（双端 3s 内可应答），超时上限 %ds' % a.timeout, flush=True)

    cases = pick(a.cases)
    if not a.no_selfmade:
        sm = interleaved_paging()
        ok = []
        for c in sm:                     # 只用双端本来就一致的形状当诱饵
            b1 = request('java', c, a.timeout)
            b2 = request('rust', c, a.timeout)
            if (b1['status'], b1['canon']) == (b2['status'], b2['canon']) and b1['status'] == 200:
                ok.append(c)
        cases += ok
        print('自造交错用例：可用 %d / %d' % (len(ok), len(sm)), flush=True)

    print('并发样本 %d 例；串行取基线' % len(cases), flush=True)
    base = {}
    for c in cases:
        base[c['id']] = {side: request(side, c, a.timeout) for side in ('java', 'rust')}
        time.sleep(0.01)

    jobs = [(c, side, k) for c in cases for side in ('java', 'rust') for k in range(a.rounds)]
    print('并发 %d 个请求（workers=%d，keep-alive）' % (len(jobs), a.workers), flush=True)
    bad, lat = [], collections.defaultdict(list)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(request, side, c, a.timeout): (c, side) for c, side, _ in jobs}
        done = 0
        for fu in cf.as_completed(futs):
            c, side = futs[fu]
            got = fu.result()
            lat[side].append(got['ms'])
            exp = base[c['id']][side]
            if (got['status'], got['ct'], got['canon']) != (exp['status'], exp['ct'], exp['canon']):
                diffs = []
                try:
                    if got['status'] == exp['status'] and 'json' in got['ct']:
                        diffs = H.diff_json(json.loads(exp['canon']), json.loads(got['canon']),
                                            limit=4)
                except Exception:  # noqa: BLE001
                    diffs = []
                bad.append({'case': c['id'], 'side': side, 'status': got['status'],
                            'base_status': exp['status'], 'ct': got['ct'], 'err': got['err'],
                            'diffs': diffs, 'body_head': got['canon'][:200]})
            done += 1
            if done % 100 == 0:
                print('   %d/%d 异常 %d' % (done, len(jobs), len(bad)), flush=True)
    wall = time.time() - t0

    os.makedirs(RES_DIR, exist_ok=True)
    with open(os.path.join(RES_DIR, 'concurrency.jsonl'), 'w', encoding='utf-8') as f:
        for b in bad:
            f.write(json.dumps(b, ensure_ascii=False) + '\n')

    def pct(v, q):
        v = sorted(v)
        return v[min(len(v) - 1, int(len(v) * q))] if v else 0
    print('\n请求数 %d，墙钟 %.1fs（%.1f req/s），与串行基线不一致 %d'
          % (len(jobs), wall, len(jobs) / max(wall, .001), len(bad)))
    for side in ('java', 'rust'):
        v = lat[side]
        print('  %-5s n=%d p50=%dms p95=%dms p99=%dms max=%dms'
              % (side, len(v), pct(v, .5), pct(v, .95), pct(v, .99), pct(v, .999)))
    print('  异常分布:', dict(collections.Counter(b['side'] for b in bad)))
    for b in bad[:20]:
        print('   %-42s %s status %s->%s' % (b['case'][:42], b['side'], b['base_status'],
                                             b['status']))
        print('       diffs=%s body=%s' % (json.dumps(b['diffs'], ensure_ascii=False)[:170],
                                           repr(b['body_head'])[:140]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
