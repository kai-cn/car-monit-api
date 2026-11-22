import json
import os
import collections

RUN = os.path.join(os.getcwd(), '.run', 'verify2')


def load_cases(stage):
    return json.load(open(os.path.join(RUN, 'cases', stage + '.json'), encoding='utf-8'))


def load_results(stage):
    p = os.path.join(RUN, 'results', stage + '.jsonl')
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def main():
    for stage in ('base', 'filters', 'query', 'contract', 'sysutil'):
        cs = load_cases(stage)
        rs = load_results(stage)
        g = collections.Counter(c['group'] for c in cs)
        print('## %s: cases=%d groups=%s' % (stage, len(cs), dict(g)))
        if stage == 'filters':
            tables = collections.Counter(c['path'].split('/list')[0] for c in cs)
            fields = len({c.get('field') for c in cs if c.get('field')})
            variants = collections.Counter(c.get('variant') for c in cs if c.get('variant'))
            print('   tables=%d distinct_filter_fields=%d variants=%s' % (len(tables), fields, dict(variants)))
        if stage == 'base':
            ids = len([c for c in cs if c['id'].endswith((':listAll',)) or ':id' in c['id']])
            print('   id/listAll cases=%d' % ids)
        if rs:
            v = collections.Counter(r['verdict'] for r in rs)
            print('   results=%s' % dict(v))
            kinds = collections.Counter()
            for r in rs:
                if r['verdict'] == 'FAIL':
                    for d in r['diffs']:
                        kinds[d[0]] += 1
            if kinds:
                print('   remaining FAIL kinds=%s' % dict(kinds))
            slow = sorted(rs, key=lambda r: -(r.get('java_ms') or 0))[:3]
            print('   slowest java_ms=%s' % [r['java_ms'] for r in slow])
            slowr = sorted(rs, key=lambda r: -(r.get('rust_ms') or 0))[:3]
            print('   slowest rust_ms=%s' % [r['rust_ms'] for r in slowr])


if __name__ == '__main__':
    main()
