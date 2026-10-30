# -*- coding: utf-8 -*-
"""结构对照：列出工作区中尚未在 refactor/ 下生成同名 .py 的 Java 文件。

用法：
    python _missing_files.py            # 只列缺失清单与统计
    python _missing_files.py --dirs     # 额外按目录汇总
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.dirname(__file__))
WORKSPACE = os.path.dirname(ROOT)

SKIP_DIRS = {"target", ".git", ".idea", ".mimocode", ".vscode", "node_modules",
             "__pycache__", "out", "build"}


def java_files():
    for dirpath, dirnames, filenames in os.walk(WORKSPACE):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".java"):
                yield os.path.join(dirpath, name)


def main() -> int:
    show_dirs = "--dirs" in sys.argv
    missing = []
    total = 0
    for java_path in java_files():
        rel = os.path.relpath(java_path, WORKSPACE)
        total += 1
        py_path = os.path.join(ROOT, rel[:-5] + ".py")
        if not os.path.exists(py_path):
            missing.append(rel.replace("\\", "/"))

    print("java files: %d, missing py: %d, covered: %d"
          % (total, len(missing), total - len(missing)))
    for item in sorted(missing):
        print("  MISSING " + item)

    if show_dirs:
        print("-" * 60)
        for directory, count in sorted(Counter(os.path.dirname(m) for m in missing).items()):
            print("  %-70s %d" % (directory, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
