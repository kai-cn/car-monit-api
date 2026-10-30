# -*- coding: utf-8 -*-
"""一次性修正：CommonUtil 在 Python 侧是「模块级函数集合」而非 class，
故 `from ... import CommonUtil` 应改为 `import ... as CommonUtil`，
这样调用处 `CommonUtil.isNull(...)` 与 Java 静态调用写法逐字一致。
"""
import pathlib

OLD = "from com.ruoyi.common.utils.CommonUtil import CommonUtil"
NEW = "import com.ruoyi.common.utils.CommonUtil as CommonUtil"

root = pathlib.Path(__file__).parent / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi"
changed = 0
for path in root.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if OLD not in text:
        continue
    lines = text.split("\n")
    # 删除原行，插入到 `from __future__ import annotations` 之后（标准库 import 之前）
    lines = [ln for ln in lines if ln != OLD]
    idx = lines.index("from __future__ import annotations")
    lines.insert(idx + 1, "")
    lines.insert(idx + 2, NEW)
    path.write_text("\n".join(lines), encoding="utf-8")
    changed += 1
    print("fixed:", path.name)

print("total:", changed)
