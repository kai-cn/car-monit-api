# -*- coding: utf-8 -*-
"""给 JInt/JLong/JFloat/JDecimal 的 visitor 补 visit_map，接住 arbitrary_precision 的数字表示。

serde_json 开启 arbitrary_precision 后，JSON 数字以单键 map 形式喂给 visitor；
这几个类型只实现了 visit_str/visit_i64/... → 读自己写进 Redis 的 blob 时会报
`invalid type: map, expected ...`，于是每次都「反序列化失败，回源重建」。
"""
import io
import os
import re
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'src', 'models', 'mod.rs')

TYPES = ['JInt', 'JLong', 'JFloat', 'JDecimal']

TEMPLATE = '''            fn visit_map<A: serde::de::MapAccess<'de>>(self, mut map: A) -> Result<{ty}, A::Error> {{
                // arbitrary_precision 下 JSON 数字是单键 map（见 RAW_NUMBER_KEY 注释），
                // 取出原文后交给同一个 visitor 的字符串分支处理。
                match map.next_key::<String>()? {{
                    Some(k) if k == RAW_NUMBER_KEY => {{
                        let text: String = map.next_value()?;
                        self.visit_str(&text)
                    }}
                    _ => Err(serde::de::Error::invalid_type(serde::de::Unexpected::Map, &self)),
                }}
            }}
'''


def main():
    src = io.open(P, encoding='utf-8').read()
    added = 0
    for ty in TYPES:
        # 定位该类型的 Deserialize impl 区间
        m = re.search(r"impl<'de> Deserialize<'de> for %s \{" % ty, src)
        assert m, '找不到 %s 的 Deserialize impl' % ty
        start = m.start()
        end = src.index('\nimpl', start + 10)
        block = src[start:end]
        if 'RAW_NUMBER_KEY =>' in block:
            print('%s 已有 visit_map，跳过' % ty)
            continue
        anchor = 'fn visit_none<E: serde::de::Error>(self) -> Result<%s, E>' % ty
        assert anchor in block, '%s 里找不到 visit_none 锚点' % ty
        new_block = block.replace(anchor, TEMPLATE.format(ty=ty) + anchor, 1)
        src = src[:start] + new_block + src[end:]
        added += 1
        print('%s: 已插入 visit_map' % ty)
    assert added, '什么都没改'
    io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
    print('written %s (changed %d impls)' % (os.path.relpath(P), added))


if __name__ == '__main__':
    sys.exit(main())
