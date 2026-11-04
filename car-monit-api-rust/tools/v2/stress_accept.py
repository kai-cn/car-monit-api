# -*- coding: utf-8 -*-
"""阶段12 前置：accept 层压力测试。

背景：第一轮 32 并发的并发一致性探针跑完后，Rust 服务出现「进程在但 9911 不再监听」，
需要用可控实验区分三种可能：
  A. 连接风暴把 accept 循环打死（真实健壮性问题）；
  B. 探针自己的连接方式（每线程 keep-alive、空闲挂着）触发服务端上限；
  C. 工具超时把整个进程树连带杀掉（环境副作用，不是被测代码的问题）。

做法：固定时长内高频新建连接 + 少量长连接挂着，然后立刻串行验证服务是否还能应答，
并对比日志里 `请求完成` 的增量（如果服务端真的在处理，日志必须涨）。

用法: python tools/v2/stress_accept.py --seconds 25 --workers 32 --idle-keepalive 16
"""
import argparse
import http.client
import json
import os
import random
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, '.run', 'rust-9911.log')

PATHS = [
    '/base/toll/list?pageSize=3',
    '/base/gantry/list?pageSize=3&pageNum=2',
    '/base/section/list?pageSize=5',
    '/base/org/list?pageSize=2',
    '/healthz',
    '/base/toll/1',
    '/api/v1/progressive/stats?groupBy=plateColor',
]


def count_served():
    n = 0
    with open(LOG, 'rb') as f:
        for line in f:
            if '请求完成'.encode('utf-8') in line:
                n += 1
    return n


def one_quick(side, path):
    host = '127.0.0.1'
    port = 9902 if side == 'java' else 9911
    t = time.time()
    try:
        with urllib.request.urlopen('http://%s:%d%s' % (host, port, urllib.parse.quote(path)),
                                    timeout=8) as r:
            r.read()
            return r.status, int((time.time() - t) * 1000)
    except Exception as e:  # noqa: BLE001
        return -1, int((time.time() - t) * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=25)
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--idle-keepalive', type=int, default=16, help='打开后闲置不用的长连接数')
    a = ap.parse_args()

    before = count_served()
    ok = fail = 0
    lock = threading.Lock()
    stop = threading.Event()
    worst = [0]

    def worker():
        nonlocal ok, fail
        while not stop.is_set():
            st, ms = one_quick('rust', random.choice(PATHS))
            with lock:
                if st in (200, 404, 400):
                    ok += 1
                else:
                    fail += 1
                worst[0] = max(worst[0], ms)

    print('基线：日志里 请求完成 计数 = %d' % before)
    print('压 %ds：新建连接 %d 并发 + %d 条空闲 keep-alive' % (a.seconds, a.workers,
                                                              a.idle_keepalive))
    t0 = time.time()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(a.workers)]
    for t in threads:
        t.start()
    held = []
    for _ in range(a.idle_keepalive):
        try:
            c = http.client.HTTPConnection('127.0.0.1', 9911, timeout=5)
            c.connect()          # 只建连、不发请求 —— 模拟探针里挂着的 keep-alive 连接
            held.append(c)
        except Exception as e:  # noqa: BLE001
            print('  建长连接失败:', e)
    while time.time() - t0 < a.seconds:
        time.sleep(1)
    stop.set()
    for t in threads:
        t.join(timeout=10)
    mid_ok, mid_fail = ok, fail
    for c in held:
        try:
            c.close()
        except Exception:  # noqa: BLE001
            pass
    print('  压测期间：成功 %d，失败/超时 %d，最慢 %dms，空闲长连接 %d 条全部建上'
          % (mid_ok, mid_fail, worst[0], len(held)))

    # 立刻串行验一遍
    print('压测后串行 10 次：')
    for i in range(10):
        st, ms = one_quick('rust', '/healthz')
        print('   #%2d rust=%s %sms' % (i, st, ms))
        if st == -1:
            break
    for i in range(3):
        print('   java 对照 #%d %s' % (i, one_quick('java', '/base/toll/list?pageSize=1')))

    after = count_served()
    print('日志 请求完成 增量 = %d（压测成功数 %d）→ 服务端确实在处理' % (after - before, mid_ok))
    return 0


if __name__ == '__main__':
    main()
