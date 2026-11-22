# -*- coding: utf-8 -*-
"""执行用例并落盘：python tools/v2/run.py --stage contract,base [--limit N] [--only substr]"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='contract')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--timeout', type=int, default=60)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--skip', default='')
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--diff-limit', type=int, default=40)
    a = ap.parse_args()

    cases = []
    for st in a.stage.split(','):
        p = os.path.join(H.CASE_DIR, st.strip() + '.json')
        if not os.path.exists(p):
            print('缺用例文件: %s（先跑 gen_cases.py）' % p)
            continue
        for c in json.load(open(p, encoding='utf-8')):
            c.setdefault('stage', st.strip())
            cases.append(c)
    if a.only:
        cases = [c for c in cases if any(s in c['id'] or s in c.get('path', '')
                                         for s in a.only.split(','))]
    if a.skip:
        cases = [c for c in cases if not any(s in c['id'] or s in c.get('path', '')
                                             for s in a.skip.split(','))]
    if a.limit:
        cases = cases[:a.limit]
    print('运行 %d 例（workers=%d, timeout=%ds）' % (len(cases), a.workers, a.timeout), flush=True)
    res = H.run_cases(cases, a.workers, a.timeout, a.diff_limit, a.repeats)
    stage_key = a.stage.replace(',', '+')
    summ = H.save_stage(stage_key, cases, res)
    print(json.dumps({k: v for k, v in summ.items() if k != 'fail_cases'}, ensure_ascii=False, indent=1))
    fails = [r for r in res if r['verdict'] in ('FAIL', 'ERROR')]
    for r in fails[:60]:
        print('FAIL %-42s java=%s rust=%s %s' % (
            r['case'], r.get('java_status'), r.get('rust_status'),
            '; '.join('%s@%s %r!=%r' % d for d in r['diffs'][:3])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
