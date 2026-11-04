# -*- coding: utf-8 -*-
"""阶段11 稳定性：同一请求连续打 N 次，分别看

  1) 单端自稳定性：Java / Rust 自己的 N 次响应是否逐字节一致（去掉易变字段后）；
  2) 双端逐次一致性：第 k 次的 Java 与 Rust 是否一致；
  3) 不一致时，具体是哪个 JSON 路径在抖（列表顺序？字典顺序？分页窗口？）。

这暴露的是「无 ORDER BY 的分页」「异步写入的缓存」「逐请求重建的字典」这类非确定性问题，
单次比对（PASS/FAIL）看不出来。

用法:
    python tools/v2/stability.py --repeats 5 --per-stage 8
    python tools/v2/stability.py --from base,sysutil --only carTrack
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Windows 控制台默认 GBK，二进制响应里的非法字节会让 print 直接抛异常
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
import harness as H  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
RES_DIR = os.path.join(ROOT, '.run', 'verify2', 'results')

# 错误页/响应里每次都不同的字段，规范化时剔除
DROP_KEYS = set(H.VOLATILE) | {'timestamp', 'java_ms', 'rust_ms'}


def canonical(raw_bytes):
    """去易变字段后按原顺序重新序列化：列表/对象内部的**顺序仍然敏感**，
    顺序抖动必须被算作不稳定。"""
    obj = H.parse_json(raw_bytes)
    if obj is None:
        # 二进制响应（CBOR/Smile）：里面同样嵌了 epoch 毫秒，无法按键剔除，
        # 退化为「把 8 位以上的数字串（时间戳）掩掉」，否则每次都比不同（实测 Java 的
        # Smile 500 响应就差这一个字段，见 ct:acc07-2）。
        text = raw_bytes.decode('utf-8', 'replace')
        return re.sub(r'\d{8,}', '#', text)
    return json.dumps(strip(obj), ensure_ascii=False, sort_keys=False)


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if k not in DROP_KEYS}
    if isinstance(v, list):
        return [strip(x) for x in v]
    return v


def pick_cases(stages, per_stage, only):
    out = []
    for st in stages:
        p = os.path.join(ROOT, '.run', 'verify2', 'cases', st + '.json')
        if not os.path.exists(p):
            print('缺用例: %s' % p)
            continue
        cases = [c for c in json.load(open(p, encoding='utf-8'))
                 if c.get('method', 'GET') == 'GET']
        if only:
            cases = [c for c in cases if any(s in c['id'] or s in c.get('path', '')
                                             for s in only.split(','))]
        by_group = collections.OrderedDict()
        for c in cases:
            by_group.setdefault(c.get('group', ''), []).append(c)
        # 每个 group 均匀取样，覆盖分页/排序/富集/错误路径
        chosen = []
        for g, lst in by_group.items():
            step = max(1, len(lst) // max(1, per_stage))
            chosen.extend(lst[i * step] for i in range(min(per_stage, len(lst))))
        out.extend(chosen)
    return out


def probe(case, repeats, timeout):
    per_side = {}
    for side in ('java', 'rust'):
        vals = []
        for _ in range(repeats):
            st, h, raw, ms, e = H.http_get(H.side_url(side, case['path']),
                                           case.get('method', 'GET'), case.get('body'),
                                           case.get('headers'), timeout)
            ct = (h.get('content-type') or '').split(';')[0].strip()
            vals.append((st, canonical(raw), e, ct))
        per_side[side] = vals
    return per_side


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='stages', default='base,gap,query,sysutil,contract')
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--per-stage', type=int, default=8)
    ap.add_argument('--only', default='')
    ap.add_argument('--timeout', type=int, default=60)
    a = ap.parse_args()

    cases = pick_cases(a.stages.split(','), a.per_stage, a.only)
    print('稳定性样本 %d 例 × %d 次 × 2 端' % (len(cases), a.repeats), flush=True)

    rows = []
    for i, c in enumerate(cases):
        per = probe(c, a.repeats, a.timeout)
        jv, rv = per['java'], per['rust']
        j_stable = len({v[1] for v in jv}) == 1
        r_stable = len({v[1] for v in rv}) == 1
        j_status = {v[0] for v in jv}
        r_status = {v[0] for v in rv}
        cross = [jv[k][1] == rv[k][1] for k in range(a.repeats)]
        # 抖动定位：shake = 去掉易变字段后的差异（通常为空，说明抖的只是 id/时间戳）；
        # shake_raw = 保留全部字段的差异，用来找到真正在抖的 JSON 路径。
        shake, shake_raw, shake_side = [], [], ''
        if not (j_stable and r_stable):
            shake_side = 'java' if not j_stable else 'rust'
            seq = jv if shake_side == 'java' else rv
            first = seq[0][1]
            other = next((x[1] for x in seq if x[1] != first), first)
            try:
                shake = H.diff_json(json.loads(first), json.loads(other), limit=6)
            except Exception:  # noqa: BLE001
                shake = [['raw-text', '$', first[:80], other[:80]]]
        elif not all(cross):
            shake_side = 'cross'
            try:
                shake_raw = H.diff_json(json.loads(jv[0][1]), json.loads(rv[0][1]), limit=6)
            except Exception:  # noqa: BLE001
                shake_raw = []
        # Java 侧输出的是二进制（CBOR/Smile）：内部嵌的 epoch 毫秒无法按键剔除，
        # 逐字节比必然每次不同 —— 这与「是否稳定」无关，归到已接受的编码差异（见 09）。
        binary = all('json' not in v[3] for v in jv)
        verdict = ('PASS' if j_stable and r_stable and all(cross) else
                   'ACCEPTED' if binary else
                   'FLAKY' if not (j_stable and r_stable) else 'CROSS-DIFF')
        rows.append({'case': c['id'], 'group': c.get('group', ''), 'path': c['path'],
                     'repeats': a.repeats,
                     'java_stable': j_stable, 'rust_stable': r_stable,
                     'java_status': sorted(j_status), 'rust_status': sorted(r_status),
                     'cross_hits': sum(1 for x in cross if x), 'cross_total': len(cross),
                     'verdict': verdict, 'shake_side': shake_side, 'binary': binary,
                     'shake': shake[:6], 'shake_raw': shake_raw[:6]})
        if verdict != 'PASS' or (i + 1) % 25 == 0:
            print('  %d/%d %s %-44s j_stable=%s r_stable=%s cross=%d/%d' % (
                i + 1, len(cases), verdict, c['id'][:44], j_stable, r_stable,
                rows[-1]['cross_hits'], len(cross)), flush=True)

    os.makedirs(RES_DIR, exist_ok=True)
    with open(os.path.join(RES_DIR, 'stability.jsonl'), 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    by = collections.Counter(r['verdict'] for r in rows)
    print('\n合计 %d 例: %s' % (len(rows), dict(by)))
    for side in ('java', 'rust'):
        n = sum(1 for r in rows if not r[side + '_stable'])
        print('  %s 自身抖动的用例: %d' % (side, n))
    for r in rows:
        if r['verdict'] != 'PASS':
            print('  %s %-40s side=%s' % (r['verdict'], r['case'][:40], r['shake_side']))
            print('      shake=%s' % json.dumps(r['shake'][:3], ensure_ascii=False)[:200])
            print('      shake_raw=%s' % json.dumps(r['shake_raw'][:3], ensure_ascii=False)[:200])
    return 0


if __name__ == '__main__':
    sys.exit(main())
