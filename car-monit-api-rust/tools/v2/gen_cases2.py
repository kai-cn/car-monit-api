# -*- coding: utf-8 -*-
"""阶段9 用例：filters2（通配/空白/大小写/注入变体）、dates（Java 日期 pattern 全矩阵）、gap（补零覆盖与弱覆盖）。

依赖 inventory.json（Mapper `<if>` 字段 + 实体字段）与 samples.json（真实行值）。
日期字段清单来自 src/models/java_date_fields.rs（Java 侧 java.util.Date 声明的查询参数名）。
"""
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
import gen_cases as G  # noqa: E402

RUST_ROOT = os.path.dirname(os.path.dirname(HERE))
DATE_TRUST = os.path.join(RUST_ROOT, 'src', 'models', 'java_date_fields.rs')

# Java DateUtils.parsePatterns 的 12 种写法（- / . 三种分隔符 × 3 精度）+ 边界/非法写法
INJECT = ["'", "1' OR '1'='1", "%", "_", "%_%", "\\\\", "'; DROP TABLE x; --", "中文'\""]


def date_formats():
    out = []
    for sep in ('-', '/', '.'):
        for body in ('{y}{s}{m}{s}{d} {H}:{M}:{S}', '{y}{s}{m}{s}{d} {H}:{M}', '{y}{s}{m}{s}{d}',
                     '{y}{s}{mo}{s}{d}', '{y}{s}{m}{s}{d} {H}:{M}:{S}.000'):
            out.append(body.format(y='2025', m='09', d='10', mo='9', H='12', M='33', S='00', s=sep))
        out.append('2025%s09' % sep)
    out += ['2025-09-10T12:33:00', '1757462400000', '2025-09-10 12:33:00 ', '  2025-09-10  ',
            '2025-13-45', '0000-00-00', '2025-09-10 25:61:61', 'abc', '', 'null',
            '2025-09-10,2025-09-11', '20250910', '10-09-2025', '2025-09-10 12:33:00+08:00']
    return out


DATE_FORMATS = date_formats()


def date_fields_by_entity():
    src = io_read(DATE_TRUST)
    out = {}
    for m in re.finditer(r'impl JavaDateFields for (\w+)\s*\{(?:\s*const JAVA_DATE_FIELDS[^=]*=\s*&\[(.*?)\];)?', src, re.S):
        ent, body = m.group(1), m.group(2) or ''
        fields = re.findall(r'"([^"]+)"', body)
        if fields:
            out[ent] = fields
    return out


def io_read(p):
    return open(p, encoding='utf-8', errors='replace').read()


def gen_filters2(tables, samples):
    """对每个 Mapper 过滤字段再加 5 类变体：通配、纯空白、大小写、注入串、超长。"""
    cases = []
    for t in tables:
        base, rows = t['base'], samples.get(t['base'], [])
        for f in t['filters']:
            v = G.sample_value(rows, f)
            s = G.scalar_str(v) if v is not None else 'x'
            variants = {
                'wild': ['%', '_'],
                'space': [' ', '  '],
                'case': [s.upper(), s.lower()] if any(c.isalpha() for c in s) else [s],
                'long': [(s[:8] * 60)[:400]],
                'dup': None,
            }
            for kind, vals in variants.items():
                if vals is None:
                    # 同名参数出现两次：Spring 用逗号拼接后再绑定
                    cases.append({'id': 'f2:%s:%s:%s' % (base, f, kind), 'group': 'filters2-dup',
                                  'path': '%s/list?%s=%s&%s=%s&pageSize=3' % (base, f, 'a', f, 'b'),
                                  'method': 'GET', 'field': f, 'variant': kind})
                    continue
                for i, val in enumerate(vals):
                    cases.append({'id': 'f2:%s:%s:%s%d' % (base, f, kind, i), 'group': 'filters2-' + kind,
                                  'path': '%s/list?%s=%s&pageSize=3' % (base, f, urllib.parse.quote(val)),
                                  'method': 'GET', 'field': f, 'variant': kind})
            for i, val in enumerate(INJECT):
                cases.append({'id': 'f2:%s:%s:inj%d' % (base, f, i), 'group': 'filters2-inject',
                              'path': '%s/list?%s=%s&pageSize=3' % (base, f, urllib.parse.quote(val)),
                              'method': 'GET', 'field': f, 'variant': 'inject'})
    return cases


def gen_dates(tables, samples):
    """每个 java.util.Date 型查询参数 × Java 的日期 pattern 全集。"""
    dflds = date_fields_by_entity()
    cases = []
    for t in tables:
        base = t['base']
        for f in dflds.get(t['entity'], []):
            for i, val in enumerate(DATE_FORMATS):
                cases.append({'id': 'dt:%s:%s:%02d' % (base, f, i), 'group': 'dates',
                              'path': '%s/list?pageSize=2&%s=%s' % (base, urllib.parse.quote(f), urllib.parse.quote(val)),
                              'method': 'GET', 'field': f, 'fmt': val})
            # 区间两端同时给（RuoYi 的 begin/end 习惯）与重复键
            cases.append({'id': 'dt:%s:%s:range' % (base, f), 'group': 'dates-range',
                          'path': '%s/list?pageSize=2&%s=2025-09-01&%s=2025-09-30&%s=zzz'
                          % (base, f, f, f), 'method': 'GET', 'field': f})
    return cases


def gen_gap():
    cases = []
    # 1) 零覆盖：/base/vehicleweight/map
    #    已知差异（见 09-已知差异根因.md）：Java 的 map 路径把缓存里的日期字符串按 JVM 本地时区
    #    解析成 Date，再由 Jackson 以 UTC 输出 → 比 Rust 早一天；同表的 list 路径（直接来自 DB）
    #    双端完全一致（base/filters 阶段已验证）。照抄这个时区往返会把 list 也带偏。
    map_reason = {
        'kinds': ['value', 'keys', 'type'],
        'reason': 'Java 缓存回读时区往返缺陷（Date→UTC）导致日期早一天；Rust 与 DB 原值一致'}
    cases.append({'id': 'gap:weight-map', 'group': 'gap-misc', 'path': '/base/vehicleweight/map',
                  'method': 'GET', 'accepted': map_reason})
    for q in ('', '?pageSize=2'):
        cases.append({'id': 'gap:weight-map%s' % (q or '-bare'), 'group': 'gap-misc',
                      'path': '/base/vehicleweight/map' + q, 'method': 'GET',
                      'accepted': map_reason})
    # 2) 导出状态：未知 / 畸形 taskId（提交→轮询的真实链路在 gap_probe.py 里）
    for ep in ('/api/v1/large/export/status', '/api/v1/unified/export/status'):
        for tid in ('nonexistent-task-id', '', '0', '%27', 'a' * 200, '12345', '%', '.'):
            cases.append({'id': 'gap:status:%s:%s' % (ep.split('/')[2], tid[:8] or 'empty'),
                          'group': 'gap-export-status',
                          'path': '%s/%s' % (ep, urllib.parse.quote(tid, safe='')), 'method': 'GET'})
    # 3) 弱覆盖：progressive 三个表的深度组合
    for tbl in ('snapshotflow', 'feerecords', 'trailfitting'):
        for q in ('', '?pageSize=3', '?pageSize=0', '?pageSize=-1', '?cursor=2025-09-05%2012:00:00',
                  '?platenumber=%E8%B5%A3A&pageSize=3', '?roadname=%E6%98%86%E4%B8%9A',
                  '?gantryname=%E9%97%A8%E6%9E%B6&sectionname=x&orgname=y&tollname=z',
                  '?startTime=2025-09-01&endTime=2025-09-10&pageSize=5',
                  '?startTime=2025-09-01&endTime=2025-09-10&pageSize=2&pageNum=3',
                  '?startTime=%20&endTime=%20', '?pageSize=999999'):
            cases.append({'id': 'gap:prog:%s:%s' % (tbl, q[:36].replace('&', '_').replace('?', '')),
                          'group': 'gap-progressive', 'path': '/progressive/%s/list%s' % (tbl, q),
                          'method': 'GET'})
    cases.append({'id': 'gap:scale', 'group': 'gap-progressive', 'path': '/progressive/scale-level', 'method': 'GET'})
    for q in ('?type=fee', '?type=trail', '?type=SNAPSHOT', '?type=', '?groupBy=platenumber&topN=3',
              '?groupBy=platenumber&topN=0', '?groupBy=platenumber&countField=cnt'):
        cases.append({'id': 'gap:stats:%s' % q[1:20].replace('&', '_').replace('=', ''),
                      'group': 'gap-stats',
                      'path': '/api/v1/large/stats/group?startTime=2025-09-01&endTime=2025-09-30' + q,
                      'method': 'GET'})
    # 4) 排序列的真列名（每张表挑一个真实列，含多列与点号写法）
    for col in ('t.id', 'id,name', 'id asc', 'ID', 'id,', '=id', 'id--', 'id/*x*/'):
        cases.append({'id': 'gap:sort:%s' % col.replace('/', '_').replace(',', '+'), 'group': 'gap-sort',
                      'path': '/base/gantry/list?pageSize=3&orderByColumn=%s&isAsc=asc'
                      % urllib.parse.quote(col), 'method': 'GET'})
    return cases


def main():
    H.ensure_dirs()
    tables = G.tables_from_inventory()
    samples = G.collect_samples(tables)
    stages = {'filters2': gen_filters2(tables, samples),
              'dates': gen_dates(tables, samples),
              'gap': gen_gap()}
    for st, cs in stages.items():
        with open(os.path.join(H.CASE_DIR, st + '.json'), 'w', encoding='utf-8') as f:
            json.dump(cs, f, ensure_ascii=False, indent=0)
        print('%-9s %5d cases' % (st, len(cs)))


if __name__ == '__main__':
    main()
