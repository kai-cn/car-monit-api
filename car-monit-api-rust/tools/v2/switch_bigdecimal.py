# -*- coding: utf-8 -*-
"""把 Java 实体里声明为 BigDecimal、Rust 模型里却用 JFloat 的字段统一换成 JDecimal。

依据：Jackson 直接输出 BigDecimal#toString()，会保留 DB 的 dscale；JFloat(f64) 会丢标度。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUST_ROOT = os.path.dirname(os.path.dirname(HERE))
JAVA_DOM = os.path.join(os.path.dirname(RUST_ROOT), 'pro-business-api', 'src', 'main', 'java',
                        'com', 'ruoyi', 'base', 'domain')
MODELS = os.path.join(RUST_ROOT, 'src', 'models')


def java_bigdecimal_fields(path):
    src = io.open(path, encoding='utf-8', errors='replace').read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)
    return set(re.findall(r'private\s+BigDecimal\s+(\w+)\s*[;=]', src))


def main():
    bd = {}
    for fn in os.listdir(JAVA_DOM):
        if fn.endswith('.java'):
            bd[fn[:-5]] = java_bigdecimal_fields(os.path.join(JAVA_DOM, fn))
    changed = []
    for fn in sorted(os.listdir(MODELS)):
        if not fn.endswith('.rs') or fn in ('mod.rs', 'java_date_fields.rs'):
            continue
        stem = fn[:-3]
        path = os.path.join(MODELS, fn)
        src = io.open(path, encoding='utf-8').read()
        cls = re.search(r'pub struct (\w+)', src)
        if not cls:
            continue
        name = cls.group(1)
        want = bd.get(name)
        if want is None:
            for k, v in bd.items():
                if k.lower() == name.lower():
                    want = v
                    break
        if not want:
            continue
        out = src
        for m in re.finditer(r'pub (\w+): JFloat,', src):
            fld = m.group(1)
            # Java 字段名 → Rust 蛇形
            snake = re.sub(r'(?<=[a-z0-9])([A-Z])', lambda x: '_' + x.group(1).lower(), fld)
            if fld in want or snake in want or fld.replace('_', '') in {w.replace('_', '') for w in want}:
                out = out.replace('pub %s: JFloat,' % fld, 'pub %s: JDecimal,' % fld)
                changed.append((fn, fld))
        if out != src:
            io.open(path, 'w', encoding='utf-8').write(out)
    print('switched %d fields' % len(changed))
    for f, fld in changed:
        print('  %-44s %s' % (f, fld))


if __name__ == '__main__':
    sys.exit(main())
