# -*- coding: utf-8 -*-
"""把 Mapper XML 里「只判 != null（不判 != ''）」的条件，在 filters_gen.rs 里改成按「是否传参」判断。

依据：Spring 的绑定把空串赋给 String 属性（不是 null），所以
  <if test="orgCategory != null"> and org_category = #{orgCategory}</if>
在 `?orgCategory=` 时仍然拼进 SQL（条件生效，通常 0 行）；
而 Rust 侧生成的是 `if !q.org_category.is_empty()`，空串被当没传 → 全量返回。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XML_DIR = os.path.join(os.path.dirname(ROOT), 'pro-business-api', 'src', 'main',
                       'java', 'com', 'ruoyi', 'base', 'mapper', 'xml')
GEN = os.path.join(ROOT, 'src', 'repo', 'filters_gen.rs')


def snake(name):
    return re.sub(r'(?<=[a-z0-9])([A-Z])', lambda m: '_' + m.group(1).lower(), name)


def null_only(xml_path):
    src = io.open(xml_path, encoding='utf-8', errors='replace').read()
    out = []
    for m in re.finditer(r'<if\s+test="([^"]+)"', src):
        t = m.group(1)
        if '!= null' not in t:
            continue
        if "!= ''" in t:
            continue
        if re.search(r'(like|&gt;|&lt;|>|<|\bIN\b|\bin\b)', t, re.I):
            # 区间/模糊/IN 条件另有实现，不在这次修复范围
            continue
        name = t.split('!=')[0].strip()
        if name and name not in out:
            out.append(name)
    return out


def main():
    per_entity = {}
    for fn in os.listdir(XML_DIR):
        if not fn.endswith('.xml'):
            continue
        ent = fn[:-4]
        if ent.endswith('Mapper'):
            ent = ent[:-6]
        flds = null_only(os.path.join(XML_DIR, fn))
        if flds:
            per_entity[ent] = flds

    src = io.open(GEN, encoding='utf-8').read()
    funcs = [(m.group(1), m.group(2), m.start(), m.end())
             for m in re.finditer(r'\bfn (\w*filters)\(q: &(\w+)\)[^\n]*', src)]
    # 函数体范围：从签名到下一个 `fn ` 或文件尾
    bounds = []
    for i, (name, ent, st, en) in enumerate(funcs):
        nxt = funcs[i + 1][2] if i + 1 < len(funcs) else len(src)
        bounds.append((name, ent, en, nxt))

    changed = 0
    out = src
    edits = []
    for name, ent, body_start, body_end in bounds:
        fields = per_entity.get(ent, [])
        if not fields:
            continue
        body = out[body_start:body_end]
        new_body = body
        for f in fields:
            sn = snake(f)
            for pat, rep in (('if !q.%s.is_empty() {' % sn, 'if !q.%s.is_null() {' % sn),
                             ('if !q.%s.is_empty() {' % f, 'if !q.%s.is_null() {' % f)):
                if pat in new_body:
                    new_body = new_body.replace(pat, rep, 1)
                    edits.append((ent, name, sn))
        if new_body != body:
            out = out[:body_start] + new_body + out[body_end:]
            changed += 1
    io.open(GEN, 'w', encoding='utf-8').write(out)
    print('functions touched: %d, conditions rewritten: %d' % (changed, len(edits)))
    for ent, fn, f in edits[:80]:
        print('  %-42s %-22s %s' % (ent, fn, f))


if __name__ == '__main__':
    sys.exit(main())
