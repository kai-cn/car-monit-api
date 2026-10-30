# -*- coding: utf-8 -*-
"""把指定目录下的 java 文件拼成一个可读文本（临时工具）。"""
import sys
from pathlib import Path

folder = Path(sys.argv[1])
out = []
for path in sorted(folder.glob("*.java")):
    out.append(f"\n===== {path.name} =====")
    out.extend(path.read_text(encoding="utf-8").splitlines())
text = "\n".join(out)
Path(sys.argv[2]).write_text(text, encoding="utf-8")
print(len(text.splitlines()), "lines")
