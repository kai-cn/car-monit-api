#!/usr/bin/env python3
"""Port the proven JDK25 native-maven-plugin configuration to other Boot4 branches.

Usage: python3 v3-port-jdk25-native-config.py <pom> [<pom> ...]

Only the <configuration> block following <artifactId>native-maven-plugin</artifactId>
is replaced. Source of truth is the JDK25 api pom (working native build).
"""
import re
import sys
from pathlib import Path

SRC = Path("/mnt/d/work/IdeaProjects/car-monit-api-jdk25/pro-business-api/pom.xml")
PAT = re.compile(
    r"(<artifactId>native-maven-plugin</artifactId>\s*)(<configuration>.*?</configuration>)",
    re.S,
)

src_text = SRC.read_text(encoding="utf-8")
m = PAT.search(src_text)
if not m:
    raise SystemExit(f"FATAL: native plugin config not found in {SRC}")
block = m.group(2)

for arg in sys.argv[1:]:
    p = Path(arg)
    text = p.read_text(encoding="utf-8")
    if not PAT.search(text):
        raise SystemExit(f"FATAL: native plugin config not found in {p}")
    new, n = PAT.subn(lambda mm: mm.group(1) + block, text, count=1)
    if n != 1:
        raise SystemExit(f"FATAL: replacement failed for {p}")
    p.write_text(new, encoding="utf-8")
    print(f"PORTED {p}")
