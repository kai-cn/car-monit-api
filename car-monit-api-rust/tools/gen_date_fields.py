# -*- coding: utf-8 -*-
"""扫描 src/models/*.rs，为每个实体生成 JavaDateFields 实现。

Java 的 `BaseController.initBinder` 给所有 `java.util.Date` 属性注册了自定义编辑器，
用 `DateUtils.parseDate`（12 种模式、要求整串匹配）解析查询参数；解析失败返回 null，
于是对应的 `<if test="x != null">` 条件根本不拼进 SQL。Rust 侧要复刻这一点，
必须知道每个实体里哪些「查询参数名」在 Java 是 Date 类型 —— 即 Day/JDateTime/JIsoDateTime。
"""
import glob
import io
import os
import re

MODEL_DIR = 'src/models'
OUT = 'src/models/java_date_fields.rs'
DATE_TYPES = ('Day', 'JDateTime', 'JIsoDateTime')


def structs(path):
    text = io.open(path, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'pub struct (\w+) \{(.*?)\n\}', text, re.S):
        name, body = m.group(1), m.group(2)
        fields = []
        pending_rename = None
        pending_skip = False
        for line in body.split('\n'):
            line = line.strip()
            r = re.match(r'#\[serde\(rename\s*=\s*"([^"]+)"', line)
            if r:
                pending_rename = r.group(1)
                if 'skip' in line:
                    pending_skip = True
                continue
            if line.startswith('#[serde(skip') and 'rename' not in line:
                pending_skip = True
                continue
            f = re.match(r'pub (r#\w+|\w+): ([^,\n]+),', line)
            if not f:
                continue
            ty = f.group(2).strip()
            rust_name = f.group(1).replace('r#', '')
            param = pending_rename or rust_name
            if ty in DATE_TYPES and not pending_skip:
                fields.append(param)
            pending_rename = None
            pending_skip = False
        out.append((name, fields))
    return out


def snake(name):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'_', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'_', s)
    return s.lower()


def main():
    lines = [
        '// 由 tools/gen_date_fields.py 自动生成，勿手改。',
        '// 每个实体的 JAVA_DATE_FIELDS = Java 侧声明为 java.util.Date 的查询参数名，',
        '// 这些参数在 Java 里走 DateUtils.parseDate 白名单，解析失败会被静默忽略。',
        'use super::JavaDateFields;',
        '',
    ]
    all_names = []
    total = 0
    for path in sorted(glob.glob(os.path.join(MODEL_DIR, '*.rs'))):
        base = os.path.basename(path)
        if base in ('mod.rs', 'java_date_fields.rs'):
            continue
        for name, fields in structs(path):
            total += 1
            all_names.append(name)
            if fields:
                quoted = ', '.join('"%s"' % f for f in fields)
                lines.append('impl JavaDateFields for %s {' % name)
                lines.append('    const JAVA_DATE_FIELDS: &[&str] = &[%s];' % quoted)
                lines.append('}')
            else:
                lines.append('impl JavaDateFields for %s {}' % name)
            lines.append('')
    if all_names:
        lines.insert(4, 'use crate::models::{%s};' % ', '.join(sorted(set(all_names))))
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print('generated %s for %d structs' % (OUT, total))


if __name__ == '__main__':
    main()
