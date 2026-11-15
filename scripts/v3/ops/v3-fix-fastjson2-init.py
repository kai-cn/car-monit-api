#!/usr/bin/env python3
"""
Propagate the fastjson2 native-image initialization fix to all six JDK branches.

Root cause (measured on 2026-11-15):
  fastjson2 2.0.66 ships META-INF/native-image/com.alibaba.fastjson2/fastjson2/
  native-image.properties which marks JSONFactory / JDKUtils / TypeUtils /
  ObjectWriterImplMap (22 classes) as --initialize-at-build-time.  Those class
  initializers call sun.misc.Unsafe.objectFieldOffset(); GraalVM cannot recompute
  the resulting field offsets ("RecomputeFieldValue.FieldOffset ... failed"),
  so the image heap contains offsets computed for the build-time JVM layout.
  At run time the GC walks that heap (AlignedChunkRememberedSet.walkObjects)
  and segfaults.  Adding MORE build-time rules (whole package, or per-class
  iteration) only hides the compile-time errors and keeps the corrupted heap.

Fix:
  * drop every project-supplied --initialize-at-build-time=com.alibaba.fastjson2* rule
  * exclude the jar's own native-image.properties via --exclude-config
  * force the whole com.alibaba.fastjson2 package to run-time initialization
    (a classpath-regex based exclusion keeps the rule portable across Windows
     and Linux runners; no absolute path is baked into the pom)

Usage:
  python v3-fix-fastjson2-init.py            # dry run, prints the planned diff
  python v3-fix-fastjson2-init.py --apply    # modify six poms + backup
  python v3-fix-fastjson2-init.py --verify   # only check current state
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_ROOT = Path(r"D:\work\IdeaProjects")
DEFAULT_BACKUP = Path(r"D:\work\runtime-logs\v3-ops\backup")
POMS = [
    "car-monit-api-jdk25/pro-business-api/pom.xml",
    "car-monit-api-jdk21/pro-business-api/pom.xml",
    "car-monit-api-jdk17/pro-business-api/pom.xml",
    "car-monit-backend-jdk25/ruoyi-admin/pom.xml",
    "car-monit-backend-jdk21/ruoyi-admin/pom.xml",
    "car-monit-backend-jdk17/ruoyi-admin/pom.xml",
]

# Kept as separate <buildArg> elements: native-maven-plugin passes each one as
# one argv token, so --exclude-config gets its two required arguments.
NEW_ARGS = [
    "--exclude-config",
    ".*fastjson2.*[.]jar",
    "^/META-INF/native-image/",
    "--initialize-at-run-time=com.alibaba.fastjson2",
]
BAD_PREFIX = "--initialize-at-build-time=com.alibaba.fastjson2"
LINE_RE = re.compile(r"^(\s*)<buildArg>(.*?)</buildArg>\s*$")


def transform(text: str):
    lines = text.splitlines(keepends=True)
    out, removed, insert_at, indent = [], [], None, "                        "
    for line in lines:
        m = LINE_RE.match(line.rstrip("\r\n"))
        if m:
            indent, value = m.group(1), m.group(2).strip()
            if value.startswith(BAD_PREFIX):
                removed.append(value)
                if insert_at is None:
                    insert_at = len(out)
                continue
        out.append(line)
    if insert_at is None:
        return text, removed, 0
    block = "".join(f"{indent}<buildArg>{a}</buildArg>\n" for a in NEW_ARGS)
    out.insert(insert_at, block)
    return "".join(out), removed, len(NEW_ARGS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--backup", default=str(DEFAULT_BACKUP))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    root, backup = Path(args.root), Path(args.backup)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    rc = 0
    for rel in POMS:
        p = root / rel
        if not p.exists():
            print(f"MISSING {p}")
            rc = 1
            continue
        text = p.read_text(encoding="utf-8")
        has_bad = BAD_PREFIX in text
        has_fix = NEW_ARGS[0] in text and NEW_ARGS[-1] in text
        print(f"=== {rel} bad_rules={has_bad} fix_present={has_fix}")
        if args.verify:
            if has_bad or not has_fix:
                rc = 1
            continue
        new_text, removed, added = transform(text)
        if not removed:
            print("  no fastjson2 build-time rule to remove; skipping")
            if not has_fix:
                rc = 1
            continue
        for r in removed:
            print(f"  - {r}")
        for a in NEW_ARGS:
            print(f"  + {a}")
        try:
            ET.fromstring(new_text)
        except ET.ParseError as e:
            print(f"  XML_INVALID {e}")
            rc = 1
            continue
        if args.apply:
            dst = backup / f"pom-fastjson2-{stamp}" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            p.write_text(new_text, encoding="utf-8")
            print(f"  APPLIED backup={dst}")
        else:
            print("  DRY-RUN (use --apply)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
