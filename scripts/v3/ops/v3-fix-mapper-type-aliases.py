#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-fix-mapper-type-aliases.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Replace short MyBatis type aliases in Mapper XML with fully-qualified names.

Why (verified 2026-11-15 on the Spring Boot 4 / Mandrel native image):
  mybatis-plus `type-aliases-package` is resolved at runtime by scanning the
  classpath for .class files. GraalVM native images have no .class files, so the
  scan silently registers nothing and every short alias in a Mapper XML fails with
  `Could not resolve type alias 'Xxx' -> ClassNotFoundException`.
  Using fully-qualified names removes the implicit scan entirely: it works on
  both JVM and native, and makes startup deterministic.

This script is idempotent: already-qualified aliases contain '.' and are ignored.
A timestamped backup of every modified XML is written under BACKUP_ROOT.

Usage:
  python v3-fix-mapper-type-aliases.py            # report only (dry-run)
  python v3-fix-mapper-type-aliases.py --apply    # rewrite + backup
"""
import collections
import datetime
import glob
import os
import re
import shutil
import sys

BASE = r"D:\work\IdeaProjects"
BACKUP_ROOT = r"D:\work\runtime-logs\v3-ops\backup"
BRANCHES = [
    "car-monit-api-jdk17", "car-monit-api-jdk21", "car-monit-api-jdk25",
    "car-monit-backend-jdk17", "car-monit-backend-jdk21", "car-monit-backend-jdk25",
]
BUILTIN = {
    "String", "Long", "Integer", "Map", "Object", "Boolean", "Date", "BigDecimal",
    "List", "HashMap", "Double", "Float", "Short", "Byte", "ArrayList", "Collection",
    "Iterator", "BigInteger", "Set", "Void", "Number", "Character", "C",
}
ATTR = re.compile(r'(resultType|parameterType|type)\s*=\s*(["\'])([A-Z][A-Za-z0-9_]*)\2')
PKG = re.compile(r'^\s*package\s+([\w.]+);', re.M)


def java_index(root):
    idx = collections.defaultdict(list)
    for p in glob.glob(os.path.join(root, "**", "*.java"), recursive=True):
        if os.sep + "target" + os.sep in p:
            continue
        try:
            head = open(p, encoding="utf-8", errors="replace").read(600)
        except OSError:
            continue
        m = PKG.search(head)
        if m:
            name = os.path.basename(p)[:-5]
            idx[name].append(m.group(1) + "." + name)
    return idx


def xml_files(root):
    out = []
    for p in glob.glob(os.path.join(root, "**", "*Mapper.xml"), recursive=True):
        norm = p.replace("\\", "/")
        if "/target/" in norm or "/car-monit-api-python/" in norm:
            continue
        out.append(p)
    return out


def main():
    apply = "--apply" in sys.argv
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(BACKUP_ROOT, "mapper-xml-" + stamp)
    total_files = total_repl = 0
    unmapped = set()

    for branch in BRANCHES:
        root = os.path.join(BASE, branch)
        idx = java_index(root)
        files = xml_files(root)
        mapping, nf, nr = {}, 0, 0
        for p in files:
            text = open(p, encoding="utf-8", errors="replace").read()
            aliases = {m.group(3) for m in ATTR.finditer(text)
                       if m.group(3) not in BUILTIN}
            for a in aliases:
                if a in idx:
                    mapping[a] = sorted(idx[a], key=len)[0]
                else:
                    unmapped.add((branch, a))

            def repl(m):
                fq = mapping.get(m.group(3))
                return f'{m.group(1)}={m.group(2)}{fq}{m.group(2)}' if fq else m.group(0)

            new = ATTR.sub(repl, text)
            if new != text:
                nr += sum(1 for m in ATTR.finditer(text) if m.group(3) in mapping)
                nf += 1
                if apply:
                    rel = os.path.relpath(p, root)
                    dst = os.path.join(backup, branch, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(p, dst)
                    open(p, "w", encoding="utf-8", newline="\n").write(new)
        total_files += nf
        total_repl += nr
        print("%-30s xml=%-4d mapped_aliases=%-3d files_to_change=%-3d replacements=%d"
              % (branch, len(files), len(mapping), nf, nr))

    print("SUMMARY mode=%s files=%d replacements=%d backup=%s"
          % ("APPLY" if apply else "DRY-RUN", total_files, total_repl,
             backup if apply else "<none>"))
    if unmapped:
        print("UNMAPPED (ignored, builtin-like or not found):", sorted(unmapped)[:20])
    return 0


if __name__ == "__main__":
    sys.exit(main())
