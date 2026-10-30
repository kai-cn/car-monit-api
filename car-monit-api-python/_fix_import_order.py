# -*- coding: utf-8 -*-
"""整理 import 顺序：把 `import com.ruoyi.common.utils.CommonUtil as CommonUtil`
从标准库分组移到项目 import 分组（`from com.baomidou...` 之前），符合 isort 分组习惯。
"""
import pathlib

TARGET = "import com.ruoyi.common.utils.CommonUtil as CommonUtil"
ANCHOR = "from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl"

root = pathlib.Path(__file__).parent / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi"
changed = 0
for path in root.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if TARGET not in text:
        continue
    lines = text.split("\n")
    i = lines.index(TARGET)
    # 删除该行及其后紧跟的一个空行
    del lines[i]
    if i < len(lines) and lines[i] == "":
        del lines[i]
    lines.insert(lines.index(ANCHOR), TARGET)
    path.write_text("\n".join(lines), encoding="utf-8")
    changed += 1

print("reordered:", changed)
