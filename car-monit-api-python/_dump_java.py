# -*- coding: utf-8 -*-
"""打印 Java 源文件，并自动修复 "中文被 GBK→UTF-8 二次编码" 造成的乱码注释。

背景：本工程部分 .java 文件里的中文注释是 "UTF-8 字节被当成 GBK 再存为 UTF-8" 的
mojibake（例如 "门架信息" 变成 "闂ㄦ灦淇℃伅"）。这里逐行尝试
`line.encode('gbk').decode('utf-8')` 还原；仅当整行可还原时才替换，正常中文行保持原样。

用法：
    python _dump_java.py <java 相对工作区的路径> [起始行] [结束行]
    python _dump_java.py --scan          # 扫描有多少文件含可还原乱码
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))
WORKSPACE = os.path.dirname(ROOT)


def fix_line(line: str) -> str:
    try:
        return line.encode("gbk").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return line


def fix_text(text: str) -> str:
    return "\n".join(fix_line(line) for line in text.split("\n"))


def read_java(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return fix_text(handle.read())


def scan() -> None:
    total = 0
    broken = 0
    for dirpath, dirnames, filenames in os.walk(WORKSPACE):
        dirnames[:] = [d for d in dirnames
                       if d not in {"target", ".git", ".idea", ".mimocode", ".vscode",
                                    "node_modules", "__pycache__", "refactor"}]
        for name in filenames:
            if not name.endswith(".java"):
                continue
            total += 1
            path = os.path.join(dirpath, name)
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            if fix_text(text) != text:
                broken += 1
                print("MOJIBAKE " + os.path.relpath(path, WORKSPACE).replace("\\", "/"))
    print("java files: %d, with restorable mojibake: %d" % (total, broken))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "--scan":
        scan()
        return 0
    path = sys.argv[1]
    if not os.path.isabs(path):
        path = os.path.join(WORKSPACE, path)
    text = read_java(path)
    lines = text.split("\n")
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    end = int(sys.argv[3]) if len(sys.argv) > 3 else len(lines)
    for index in range(start, min(end, len(lines)) + 1):
        print("%5d| %s" % (index, lines[index - 1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
