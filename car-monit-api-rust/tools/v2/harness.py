# -*- coding: utf-8 -*-
"""双端比对内核：请求、归一化、结构化差异、结果落盘。

比对语义（与旧脚本的差异）：
  * 数字用 json.loads(parse_float=str, parse_int=str) 保留原始 token，
    因此 1.0 / 1 / 1204.550050 这类「序列化格式」差异会被当成差异上报（前端会受影响）。
  * 结构差异（键集合、类型）与取值差异分开统计，便于判断是契约问题还是数据问题。
  * 每例记录双端耗时、状态码、Content-Type、原始响应片段，方便回查。
"""
import concurrent.futures as cf
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

JAVA = os.environ.get('PARITY_JAVA', 'http://127.0.0.1:9902')
RUST = os.environ.get('PARITY_RUST', 'http://127.0.0.1:9911')
HERE = os.path.dirname(os.path.abspath(__file__))
RUST_ROOT = os.path.dirname(os.path.dirname(HERE))
RUN_DIR = os.path.join(RUST_ROOT, '.run', 'verify2')
CASE_DIR = os.path.join(RUN_DIR, 'cases')
RES_DIR = os.path.join(RUN_DIR, 'results')

# Java 每行临时生成、必然不等的字段：只比「存在性 + 类型」
VOLATILE = {'id', 'taskId', 'task_id', 'uuid', 'timestamp', 'traceId', 'requestId',
            'reportId', 'duration', 'elapsed', 'cost', 'count_ms'}
# 双端各自写入 Redis DB0/DB1 造成的时间戳类字段
SOFT_NUM_KEYS = set()


def ensure_dirs():
    for d in (CASE_DIR, RES_DIR):
        os.makedirs(d, exist_ok=True)


# ------------------------------------------------------------------ HTTP
def http_get(url, method='GET', body=None, headers=None, timeout=60):
    """返回 (status, headers_lower, raw_bytes, elapsed_ms, error_str)。"""
    hdr = {'Accept': '*/*', 'User-Agent': 'parity-harness/2'}
    data = None
    if body is not None:
        data = body.encode('utf-8') if isinstance(body, str) else body
        hdr.setdefault('Content-Type', 'application/json')
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, {k.lower(): v for k, v in dict(r.headers).items()}, raw, \
                int((time.time() - t0) * 1000), None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, {k.lower(): v for k, v in dict(e.headers).items()}, raw, \
            int((time.time() - t0) * 1000), None
    except Exception as exc:  # noqa: BLE001
        return -1, {}, b'', int((time.time() - t0) * 1000), '%s: %s' % (type(exc).__name__, exc)


def side_url(side, path):
    base = JAVA if side == 'java' else RUST
    if path.startswith('/'):
        return base + urllib.parse.quote(path, safe='/?&=,%-.*+~@:();[]')
    return base + '/' + path


def call_both(case, timeout=60, repeats=1):
    """双端各请求一次（repeats>1 时取第二次，用于观察缓存命中路径）。"""
    out = {}
    for side in ('java', 'rust'):
        url = side_url(side, case['path'])
        r = http_get(url, case.get('method', 'GET'), case.get('body'),
                     case.get('headers'), timeout)
        if repeats > 1:
            r = http_get(url, case.get('method', 'GET'), case.get('body'),
                         case.get('headers'), timeout)
        out[side] = {'status': r[0], 'headers': r[1], 'raw': r[2], 'ms': r[3], 'err': r[4]}
    return out


# ------------------------------------------------------------------ 解析
def parse_json(raw):
    try:
        return json.loads(raw.decode('utf-8'), parse_float=str, parse_int=str)
    except Exception:  # noqa: BLE001
        return None


def type_of(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, str):
        return 'string'
    if isinstance(v, (int, float)):
        return 'number'
    if isinstance(v, list):
        return 'array'
    if isinstance(v, dict):
        return 'object'
    return type(v).__name__


def is_num_token(v):
    return isinstance(v, str) and (v[:1].isdigit() or v[:1] in '-.') and _numeric(v)


def _numeric(s):
    try:
        float(s)
        return True
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ 差异
def diff_json(a, b, path='$', out=None, limit=40, in_rows=False):
    """结构化比较；返回差异列表 [(kind, path, java, rust)]。"""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    key = path.rsplit('.', 1)[-1]
    ta, tb = type_of(a), type_of(b)

    if key in VOLATILE and not isinstance(a, (dict, list)):
        if (a is None) != (b is None):
            out.append(('volatile-null', path, a, b))
        elif ta != tb:
            out.append(('volatile-type', path, ta, tb))
        return out

    if ta != tb:
        out.append(('type', path, ta, tb))
        return out
    if ta == 'object':
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append(('keys', path, sorted(ka - kb)[:10], sorted(kb - ka)[:10]))
        for k in sorted(ka & kb):
            diff_json(a[k], b[k], '%s.%s' % (path, k), out, limit,
                      in_rows or k in ('rows', 'data', 'list', 'trailList'))
            if len(out) >= limit:
                break
        return out
    if ta == 'array':
        if len(a) != len(b):
            out.append(('len', path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diff_json(a[i], b[i], '%s[%d]' % (path, i), out, limit, in_rows)
            if len(out) >= limit:
                break
        return out
    # 标量
    if ta == 'number' or (ta == 'string' and is_num_token(a) and is_num_token(b)):
        va, vb = str(a), str(b)
        if va != vb:
            fa, fb = float(va), float(vb)
            if abs(fa - fb) <= 1e-9 * max(1.0, abs(fa)):
                out.append(('num-format', path, va, vb))
            else:
                out.append(('value', path, va, vb))
        return out
    if a != b:
        out.append(('value', path, a, b))
    return out


def compare(case, sides, diff_limit=40):
    """单例比对结论。"""
    j, r = sides['java'], sides['rust']
    res = {'case': case['id'], 'group': case.get('group', ''), 'path': case['path'],
           'java_ms': j['ms'], 'rust_ms': r['ms']}
    problems = []
    if j['err'] or r['err']:
        res['verdict'] = 'ERROR'
        res['diffs'] = [('unreachable', '$', j['err'], r['err'])]
        res['java_status'], res['rust_status'] = j['status'], r['status']
        return res
    if j['status'] != r['status']:
        problems.append(('status', '$', j['status'], r['status']))
    ctj = (j['headers'].get('content-type') or '').split(';')[0].strip()
    ctr = (r['headers'].get('content-type') or '').split(';')[0].strip()
    if ctj != ctr:
        problems.append(('content-type', '$', ctj, ctr))
    aj, ar = j['raw'], r['raw']
    if aj.startswith(b'<html>') and ar.startswith(b'<html>'):
        # Whitelabel 错误页里的时间戳每次都不同，归一化后再比
        import re as _re
        pat = _re.compile(rb"<div id='created'>.*?</div>", _re.S)
        if pat.sub(b"<div id='created'>X</div>", aj) == pat.sub(b"<div id='created'>X</div>", ar):
            res['verdict'] = 'PASS' if not problems else 'FAIL'
            res['diffs'] = problems
            res['java_status'], res['rust_status'] = j['status'], r['status']
            return res
    if (aj == b'') != (ar == b''):
        problems.append(('empty-body', '$', len(aj), len(ar)))
    pj, pr = parse_json(aj), parse_json(ar)
    if pj is None and pr is None:
        if aj != ar:
            problems.append(('raw-text', '$', aj[:200].decode('utf-8', 'replace'),
                             ar[:200].decode('utf-8', 'replace')))
    elif pj is None or pr is None:
        problems.append(('json-parse', '$', pj is None, pr is None))
    else:
        problems.extend(diff_json(pj, pr, limit=diff_limit))
    # 容器级差异：Java 的 400 可能来自 Tomcat（HTML 错误页，Spring 还没来得及接管），
    # Rust 用 hyper + Spring 风格 JSON。状态码一致即视为可接受。
    if problems and j['status'] == r['status'] and             'text/html' in (j['headers'].get('content-type') or '') and             'json' in (r['headers'].get('content-type') or ''):
        res['verdict'] = 'ACCEPTED'
        res['accepted_reason'] = 'Tomcat 容器 HTML 错误页 vs Spring JSON 错误体（状态码一致）'
        res['diffs'] = problems
        res['java_status'], res['rust_status'] = j['status'], r['status']
        return res
    # 用例声明为「已知可接受差异」（如 Java 侧 CBOR/Smile 二进制输出）：
    # 差异类型必须全部落在白名单里，否则仍算 FAIL
    if problems and case.get('accepted'):
        allow = set(case['accepted']['kinds'])
        if {d[0] for d in problems} <= allow:
            res['verdict'] = 'ACCEPTED'
            res['accepted_reason'] = case['accepted']['reason']
            res['diffs'] = problems
            res['java_status'], res['rust_status'] = j['status'], r['status']
            return res
    res['verdict'] = 'PASS' if not problems else 'FAIL'
    res['diffs'] = problems
    res['java_status'], res['rust_status'] = j['status'], r['status']
    if problems:
        res['java_sample'] = aj[:600].decode('utf-8', 'replace')
        res['rust_sample'] = ar[:600].decode('utf-8', 'replace')
    return res


# ------------------------------------------------------------------ 运行
def run_cases(cases, workers=6, timeout=60, diff_limit=40, repeats=1):
    ensure_dirs()
    results = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, c, timeout, diff_limit, repeats): c for c in cases}
        done = 0
        for fu in cf.as_completed(futs):
            results.append(fu.result())
            done += 1
            if done % 50 == 0:
                print('   ... %d/%d' % (done, len(cases)), flush=True)
    order = {c['id']: i for i, c in enumerate(cases)}
    results.sort(key=lambda x: order.get(x['case'], 1e9))
    return results


def _one(c, timeout, diff_limit, repeats):
    try:
        return compare(c, call_both(c, timeout, repeats), diff_limit)
    except Exception as exc:  # noqa: BLE001
        return {'case': c['id'], 'group': c.get('group', ''), 'path': c['path'],
                'verdict': 'ERROR', 'diffs': [('harness', '$', None, repr(exc))]}


# ------------------------------------------------------------------ 落盘 / 汇总
def save_stage(stage, cases, results):
    ensure_dirs()
    with open(os.path.join(CASE_DIR, stage + '.json'), 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RES_DIR, stage + '.jsonl'), 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return summarize(stage, results)


def summarize(stage, results):
    tot = len(results)
    by = {}
    for r in results:
        by.setdefault(r['verdict'], []).append(r)
    kinds = {}
    for r in results:
        for k, p, a, b in r.get('diffs', []):
            kinds.setdefault(k, 0)
            kinds[k] += 1
    return {'stage': stage, 'total': tot,
            'pass': len(by.get('PASS', [])), 'fail': len(by.get('FAIL', [])),
            'accepted': len(by.get('ACCEPTED', [])),
            'error': len(by.get('ERROR', [])), 'diff_kinds': kinds,
            'fail_cases': [r['case'] for r in by.get('FAIL', []) + by.get('ERROR', [])][:400]}


def qs(params):
    if not params:
        return ''
    return '?' + urllib.parse.urlencode([(k, v) for k, v in params.items() if v is not None])


# ------------------------------------------------------------------ 迷你 Redis 客户端（无第三方依赖）
class MiniRedis:
    """够用即可：RESP 协议、支持 SELECT db / SCAN / GET / TTL / DBSIZE / FLUSHDB。"""

    def __init__(self, host='127.0.0.1', port=6379, db=0, password=None):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.buf = b''
        if password:
            self.cmd('AUTH', password)
        self.cmd('SELECT', str(db))
        self.db = db

    def cmd(self, *args):
        out = ('*%d\r\n' % len(args)).encode()
        for a in args:
            b = a if isinstance(a, bytes) else str(a).encode('utf-8')
            out += b'$%d\r\n%s\r\n' % (len(b), b)
        self.sock.sendall(out)
        return self._read()

    def _readline(self):
        while b'\r\n' not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError('redis closed')
            self.buf += chunk
        line, self.buf = self.buf.split(b'\r\n', 1)
        return line

    def _read(self):
        line = self._readline()
        t, rest = line[:1], line[1:]
        if t == b'+':
            return rest.decode()
        if t == b'-':
            return RuntimeError(rest.decode())
        if t == b':':
            return int(rest)
        if t == b'$':
            n = int(rest)
            if n == -1:
                return None
            while len(self.buf) < n + 2:
                self.buf += self.sock.recv(65536)
            val, self.buf = self.buf[:n], self.buf[n + 2:]
            return val
        if t == b'*':
            n = int(rest)
            return [self._read() for _ in range(n)] if n >= 0 else None
        raise ValueError('bad RESP %r' % line)

    def keys(self, pattern='*'):
        return self.cmd('KEYS', pattern) or []

    def close(self):
        try:
            self.sock.close()
        except Exception:  # noqa: BLE001
            pass
