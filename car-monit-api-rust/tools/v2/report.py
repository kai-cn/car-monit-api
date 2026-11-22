# -*- coding: utf-8 -*-
"""把 .run/verify2/results/*.jsonl 渲染成 Markdown 片段。

用法:
  python tools/v2/report.py --stage contract+base --out docs/verify/_frag_base.md [--top 40]
  python tools/v2/report.py --all --json   # 机器可读汇总（供总报告引用）
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402


def load(stage):
    p = os.path.join(H.RES_DIR, stage + '.jsonl')
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def kind_of(diffs):
    return ','.join(sorted({d[0] for d in diffs})) if diffs else ''


def render(stage, top=40):
    rows = load(stage)
    if not rows:
        return '_（无 %s 的结果）_' % stage
    total = len(rows)
    passed = [r for r in rows if r['verdict'] == 'PASS']
    accepted = [r for r in rows if r['verdict'] == 'ACCEPTED']
    failed = [r for r in rows if r['verdict'] not in ('PASS', 'ACCEPTED')]
    by_group = collections.Counter(r['group'] for r in rows)
    fail_group = collections.Counter(r['group'] for r in failed)
    kinds = collections.Counter(kind_of(r['diffs']) for r in failed)

    L = []
    L.append('### 阶段 `%s` 结果' % stage)
    L.append('')
    L.append('| 指标 | 值 |')
    L.append('|---|---|')
    L.append('| 用例数 | %d |' % total)
    L.append('| 通过 | %d (%.1f%%) |' % (len(passed), 100.0 * len(passed) / max(1, total)))
    L.append('| 已知可接受差异 | %d |' % len(accepted))
    L.append('| 不一致 | %d |' % len(failed))
    L.append('| 差异类型分布 | %s |' % (', '.join('%s×%d' % (k or '-', v)
                                                  for k, v in kinds.most_common()) or '-'))
    L.append('')
    L.append('| 分组 | 用例 | 不一致 |')
    L.append('|---|---|---|')
    for g, n in sorted(by_group.items()):
        L.append('| %s | %d | %d |' % (g, n, fail_group.get(g, 0)))
    L.append('')
    if failed:
        L.append('#### 不一致明细（前 %d 条）' % top)
        L.append('')
        L.append('| 用例 | Java | Rust | 差异类型 | 首个差异 |')
        L.append('|---|---|---|---|---|')
        for r in failed[:top]:
            d = (r.get('diffs') or [['-', '-', None, None]])[0]
            frag = '`%s` java=%s rust=%s' % (d[1], json.dumps(d[2], ensure_ascii=False)[:60],
                                             json.dumps(d[3], ensure_ascii=False)[:60])
            L.append('| `%s` | %s | %s | %s | %s |' % (
                r['case'], r.get('java_status'), r.get('rust_status'), kind_of(r['diffs']), frag))
        L.append('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    stages = ([f[:-6] for f in sorted(os.listdir(H.RES_DIR)) if f.endswith('.jsonl')]
              if a.all else [s for s in a.stage.split(',') if s])
    if a.json:
        summary = {}
        for st in stages:
            rows = load(st)
            summary[st] = {'total': len(rows),
                           'pass': sum(1 for r in rows if r['verdict'] == 'PASS'),
                           'accepted': sum(1 for r in rows if r['verdict'] == 'ACCEPTED'),
                           'fail': sum(1 for r in rows if r['verdict'] not in ('PASS', 'ACCEPTED')),
                           'kinds': dict(collections.Counter(kind_of(r['diffs']) for r in rows
                                                             if r['verdict'] not in ('PASS', 'ACCEPTED')))}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return 0
    text = '\n\n'.join(render(st, a.top) for st in stages)
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print('written %s' % a.out)
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
