"""修复生成模型里未使用的 import（go build 会因 unused import 直接失败）。

生成器按 Java 文件是否出现过 Date/Timestamp 决定是否 import "time"，
但被映射成 model.Day 的字段并不需要 time 包，于是出现 "time" imported and not used。
本脚本做一次静态清理：若文件正文里没有 `time.` 引用，就删掉 `"time"` 这一行 import。
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"d:\work\IdeaProjects\car-monit-api\car-monit-api-go\internal\model"


def strip_unused(path: str) -> bool:
    src = open(path, encoding="utf-8").read()
    m = re.search(r"import \(\n(.*?)\n\)", src, re.S)
    if not m:
        return False
    block = m.group(1)
    body = src[m.end():]
    lines = block.split("\n")
    kept = []
    changed = False
    for line in lines:
        name = line.strip().strip('"')
        if not line.strip():
            kept.append(line)
            continue
        pkg = name.split("/")[-1] if "/" in name else name
        # 只处理标准库的单段包名（time / strings / fmt 等）
        if "/" not in name and not re.search(r"\b" + re.escape(pkg) + r"\.", body):
            changed = True
            continue
        kept.append(line)
    if not changed:
        return False
    new_block = "\n".join(kept)
    # 清掉空 import 组
    if not new_block.strip():
        src = src[: m.start()] + src[m.end():]
    else:
        src = src[: m.start()] + "import (\n" + new_block + "\n)" + src[m.end():]
    open(path, "w", encoding="utf-8", newline="\n").write(src)
    return True


fixed = 0
for f in sorted(glob.glob(os.path.join(ROOT, "*.go"))):
    if strip_unused(f):
        print("fixed:", os.path.basename(f))
        fixed += 1
print("total fixed:", fixed)
