# -*- coding: utf-8 -*-
"""按变体序号归类某个 stage 的非 PASS 结果，定位差异类别。

用法: python tools/v2/stage_stats2.py dates [dates filters2 ...]
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)


def load(stage):
    p = os.path.join(ROOT, '.run', 'verify2', 'results', stage + '.jsonl')
    out = []
    with open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    stages = sys.argv[1:] or ['dates']
    for stage in stages:
        rows = load(stage)
        verdict = collections.Counter(r.get('verdict') for r in rows)
        print('== %s  n=%d  %s' % (stage, len(rows), dict(verdict)))
        by = collections.Counter()
        kinds = collections.defaultdict(collections.Counter)
        ex = {}
        for r in rows:
            if r.get('verdict') == 'PASS':
                continue
            cid = r.get('case') or r.get('id')
            m = re.match(r'^(?:dt|f2|gp):(?P<base>[^:]+):(?P<field>[^:]+):(?P<var>\S+)$', cid)
            var = m.group('var') if m else cid.split(':')[-1]
            by[var] += 1
            for d in (r.get('diffs') or []):
                kinds[var][d[0]] += 1
            ex.setdefault(var, (cid, r))
        for var in sorted(by, key=lambda v: (-by[v], str(v))):
            cid, r = ex[var]
            print('  var=%-14s n=%-4d kinds=%s' % (var, by[var], dict(kinds[var])))
            print('     e.g. %s  j=%s r=%s %s' % (
                cid, r.get('java_status'), r.get('rust_status'),
                json.dumps((r.get('diffs') or [])[:2], ensure_ascii=False)[:200]))
        groups = collections.Counter(r.get('group') for r in rows if r.get('verdict') != 'PASS')
        print('  groups:', dict(groups))


if __name__ == '__main__':
    main()
