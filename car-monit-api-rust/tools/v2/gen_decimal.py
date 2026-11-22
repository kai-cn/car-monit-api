# -*- coding: utf-8 -*-
"""BigDecimal 过滤参数绑定专项用例（decimal 阶段）。

背景：filters_gen.rs 里数字列的等值条件走 `Cond::EqF64`（把 BigDecimal 降成 double 再绑），
而 Java/MyBatis 是 `setBigDecimal` → PostgreSQL 的 `numeric = numeric` 精确比较。
只要列的精度超过 double，两者的命中集合就可能不同（numeric→float8 的隐式转换会把
「不同的小数」折成同一个 double）。本用例集专门构造这种值。

变体设计（对每个 decimal 过滤字段）：
  exact    真实值原样
  tail     真实值 + 额外小数位（double 域等价、numeric 域不等价）★关键用例
  trunc    去掉最后一位（两个域都不等价，作对照）
  ulp      末位减 1（numeric 域不等价，double 域多半也不等价，作对照）
  wide     17~30 位大整数（超过 2^53，double 无法分辨相邻值）
  tiny     极小/次正规值
  overflow 超出 double 范围（1e400）
  sci      科学计数写法
  space    前后空格
  empty    空串（Spring 视为 null）
  junk     非数字（Java 400）
"""
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

# (base 路径, 字段名) —— 与 filters_gen.rs 里 Cond::EqF64 的 5 个点位一一对应
TARGETS = [
    ('/base/snapshotflow', 'lon'),
    ('/base/snapshotflow', 'lat'),
    ('/base/feeStationEnter', 'enweight'),
    ('/base/feeStationEnter', 'transfee'),
    ('/base/feestationexit', 'feerate'),
]


def sample_value(base, field):
    """从 Java 侧取一个字段的真实值（保留原始 JSON token 文本）。"""
    st, h, raw, ms, e = H.http_get(H.side_url('java', '%s/list?pageSize=3' % base), timeout=90)
    d = H.parse_json(raw) or {}
    for row in d.get('rows') or []:
        v = row.get(field)
        if v not in (None, '', [], {}):
            return str(v)
    return None


def variants(v):
    """基于真实值造出各类变体（v 是十进制文本）。"""
    out = {'exact': v}
    if '.' in v:
        intpart, frac = v.split('.', 1)
        out['tail'] = '%s.%s%s' % (intpart, frac, '0001')
        # ★ 关键用例：把差值压到 double 分辨率之下（1e-15 绝对量级）。
        #   只要绑定链路里还有一次 double 化，这个值就等于真实值本身 → 会命中与 exact 同样的行；
        #   而 numeric 精确比较必须 0 行。改前基线正是靠这类值暴露出错结果。
        out['eps_tail'] = '%s.%s%s' % (intpart, frac, '0' * 15 + '1')
        out['trunc'] = '%s.%s' % (intpart, frac[:-1] or '0')
        last = frac[-1]
        out['ulp'] = '%s.%s' % (intpart, frac[:-1] + (chr(ord(last) - 1) if last > '0' else '9'))
    else:
        out['tail'] = v + '.0001'
        out['eps_tail'] = v + '.000000000000001'
        out['trunc'] = v[:-1] or '0'
        out['ulp'] = str(int(v) - 1)
    out['wide'] = '9007199254740993'          # 2^53+1，double 分辨不了相邻整数
    out['wide2'] = '9007199254740992'
    out['huge'] = '123456789012345678901234567890.12345'
    out['tiny'] = '0.000000000000000000001'
    out['overflow'] = '1e400'
    out['underflow'] = '1e-400'
    out['sci'] = '1.16038e2'
    out['space'] = '  ' + v + '  '
    out['empty'] = ''
    out['junk'] = 'abc'
    out['nan'] = 'NaN'
    out['inf'] = 'Infinity'
    return out


def main():
    H.ensure_dirs()
    cases = []
    for base, field in TARGETS:
        v = sample_value(base, field)
        if v is None:
            print('!! %s.%s 取不到真实值，用固定值代替' % (base, field))
            v = '116.03808982678413' if field in ('lon',) else ('26.701453255010584' if field == 'lat' else '1')
        for kind, val in variants(v).items():
            q = '%s=%s&pageSize=3' % (field, urllib.parse.quote(val))
            cases.append({'id': 'dec:%s:%s:%s' % (base, field, kind), 'group': 'decimal',
                          'path': '%s/list?%s' % (base, q), 'method': 'GET',
                          'field': field, 'variant': kind, 'sample': v})
    with open(os.path.join(H.CASE_DIR, 'decimal.json'), 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=0)
    print('decimal cases=%d' % len(cases))
    for c in cases[:6]:
        print('  ', c['id'], '->', c['path'].split('?')[1])


if __name__ == '__main__':
    main()
