# -*- coding: utf-8 -*-
"""按文件清单拼 Java 源码（临时工具）。用法：python _dump_list.py out.txt a.java b.java"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
IMPL = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/service/impl"
out = Path(sys.argv[1])
chunks = []
for name in sys.argv[2:]:
    path = IMPL / name
    chunks.append(f"\n===== {name} =====")
    chunks.extend(path.read_text(encoding="utf-8").splitlines())
path_out = Path(__file__).resolve().parent / out.name
path_out.write_text("\n".join(chunks), encoding="utf-8")
print(len("\n".join(chunks).splitlines()), "lines ->", path_out)
