# -*- coding: utf-8 -*-
"""端点覆盖率审计：把 .run/verify2/cases/*.json 里的用例回打到 Java 端点清单上。

产出：
  .run/verify2/coverage.json                 机读
  docs/verify/08-覆盖率审计.md               人读（含零覆盖/弱覆盖清单）
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
RUST_ROOT = os.path.dirname(os.path.dirname(HERE))

INV = json.load(open(os.path.join(H.RUN_DIR, 'inventory.json'), encoding='utf-8'))


def pat(p):
    segs = p.strip('/').split('/')
    return '/' + '/'.join('*' if (s.startswith('{') and s.endswith('}')) else s for s in segs)


def matches(case_path, ep_pat):
    a = pat(case_path).split('/')
    b = ep_pat.split('/')
    return len(a) == len(b) and all(x == y or x == '*' or y == '*' for x, y in zip(a, b))


def main():
    eps = []
    for r in INV['java_endpoints']:
        m = r['method'] if r['method'] != 'ANY' else 'GET'
        p = pat(r['path'])
        eps.append({'key': '%s %s' % (m, r['path']), 'method': m, 'pat': p, 'path': r['path'],
                    'controller': r['controller'], 'hits': [], 'n': 0,
                    # 字面段多的优先，否则 /base/gantry/{id}（/base/gantry/*）会抢走 /base/gantry/listAll
                    'wild': p.count('*')})
    eps.sort(key=lambda e: (e['wild'], -len(e['pat'])))

    def hit(meth, path, tag, stage):
        for e in eps:
            if e['method'] != meth:
                continue
            if matches(path, e['pat']):
                e['n'] += 1
                if len(e['hits']) < 3:
                    e['hits'].append('%s:%s' % (stage, tag))
                return True
        return False

    unmatched = []
    per_stage = {}
    for f in sorted(glob.glob(os.path.join(H.CASE_DIR, '*.json'))):
        stage = os.path.basename(f)[:-5]
        cs = json.load(open(f, encoding='utf-8'))
        per_stage[stage] = len(cs)
        for c in cs:
            if not hit(c.get('method', 'GET'), c['path'].split('?')[0], c['id'], stage):
                unmatched.append('%s:%s %s' % (stage, c['id'], c['path'].split('?')[0]))

    # 探针脚本（写端点、缓存）不走 cases 目录，单独计入
    probes = [('write_probe.json', 'write'), ('cache_probe.json', 'cache')]
    for fn, stage in probes:
        p = os.path.join(H.RUN_DIR, fn)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        n = 0
        for it in d.get('items', []):
            n += 1
            meth = it.get('method', 'GET')
            path = it.get('path', '').split('?')[0]
            # 同一端点双端各调一次，这里按「端点被覆盖」计 1
            hit(meth, path, it.get('path', '')[:40], stage)
        for it in d.get('cases', []):
            n += 1
            p2 = (it.get('path') or '').split('?')[0]
            for meth in ('GET',):
                if hit(meth, p2, it.get('kind', 'case'), stage):
                    break
        per_stage[stage] = per_stage.get(stage, 0) + n
    zero = [e for e in eps if e['n'] == 0]
    weak = [e for e in eps if 0 < e['n'] <= 2]
    out = {'per_stage': per_stage, 'endpoints': eps,
           'zero': ['%s %s' % (e['method'], e['path']) for e in zero],
           'weak': ['%s %s (%s)' % (e['method'], e['path'], e['n']) for e in weak],
           'unmatched_cases': unmatched}
    with open(os.path.join(H.RUN_DIR, 'coverage.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    L = []
    A = L.append
    A('# 阶段8 · 端点覆盖率审计')
    A('')
    A('- 生成器：`python tools/v2/coverage.py`（数据源 `.run/verify2/cases/*.json` + `inventory.json`）')
    A('- 端点总数（Java，剥注释后）：**%d**；有用例命中的：**%d**；零命中：**%d**；弱命中（≤2 例）：**%d**'
      % (len(eps), len(eps) - len(zero), len(zero), len(weak)))
    A('')
    A('## 1. 各阶段用例量')
    A('')
    A('| 阶段 | 用例数 |')
    A('|---|---|')
    for k, v in sorted(per_stage.items()):
        A('| %s | %d |' % (k, v))
    A('')
    A('## 2. 端点 → 命中用例数')
    A('')
    A('| 方法 | 路径 | 用例数 | 样例用例 |')
    A('|---|---|---|---|')
    for e in sorted(eps, key=lambda x: (x['n'], x['path'])):
        A('| %s | `%s` | %d | %s |' % (e['method'], e['path'], e['n'], ', '.join('`%s`' % h for h in e['hits'])))
    A('')
    A('## 3. 零覆盖端点（需补用例）')
    A('')
    if zero:
        for e in zero:
            A('- `%s %s`（%s）' % (e['method'], e['path'], e['controller']))
    else:
        A('无。')
    A('')
    A('## 4. 弱覆盖端点（≤2 例）')
    A('')
    if weak:
        for e in weak:
            A('- `%s %s` → %d 例（%s）' % (e['method'], e['path'], e['n'], e['controller']))
    else:
        A('无。')
    os.makedirs(os.path.join(RUST_ROOT, 'docs', 'verify'), exist_ok=True)
    dst = os.path.join(RUST_ROOT, 'docs', 'verify', '08-覆盖率审计.md')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print('zero=%d weak=%d -> %s' % (len(zero), len(weak), dst))
    for e in zero:
        print('  ZERO', e['method'], e['path'], e['controller'])
    for e in weak:
        print('  WEAK %s %s n=%d' % (e['method'], e['path'], e['n']))


if __name__ == '__main__':
    main()
