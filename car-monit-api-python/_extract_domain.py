# -*- coding: utf-8 -*-
"""只读提取脚本：把 domain 下 Java 实体的注解/字段/方法签名紧凑打印，便于 1:1 移植。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "pro-business-api/src/main/java/com/ruoyi/base/domain"

FIELD_RE = re.compile(r"^\s*(private|public|protected)\s+(?!class)([\w<>\[\], .?]+?)\s+(\w+)\s*(=.*)?;")
METHOD_RE = re.compile(r"^\s*(public|protected|private)\s+(static\s+)?([\w<>\[\], .?]+)\s+(\w+)\s*\(([^)]*)\)\s*(\{|throws)")


def main() -> None:
    for path in sorted(ROOT.glob("*.java")):
        lines = path.read_text(encoding="utf-8").splitlines()
        print(f"\n=== {path.name} ({len(lines)} lines)")
        pending: list[str] = []
        in_class = False
        for line in lines:
            stripped = line.strip()
            if not in_class:
                if stripped.startswith("@") or stripped.startswith("public class") or \
                        stripped.startswith("public  class") or stripped.startswith("package") or \
                        (stripped.startswith("public ") and " class " in stripped):
                    if stripped.startswith("package"):
                        continue
                    print("HDR:", stripped)
                if "class " in stripped and "{" in stripped:
                    in_class = True
                    continue
                continue
            if stripped.startswith("@"):
                pending.append(stripped)
                continue
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped == "*/":
                pending.append(stripped)
                continue
            m = FIELD_RE.match(line)
            if m:
                ann = " ".join(pending)
                pending = []
                print(f"  FIELD {m.group(2).strip()} {m.group(3)} {('= ' + m.group(4)) if m.group(4) else ''}  || {ann}")
                continue
            m = METHOD_RE.match(line)
            if m:
                pending = []
                name = m.group(4)
                if name in ("toString", "equals", "hashCode", "main") or name.startswith(("get", "set", "is")):
                    print(f"  META {m.group(1)} {m.group(3)} {name}({m.group(5)})")
                else:
                    print(f"  METHOD {m.group(1)} {m.group(2) or ''}{m.group(3)} {name}({m.group(5)})")
                continue
            if stripped and not stripped.startswith(("return", "}", "{", "this.", "super.")):
                pending = []


if __name__ == "__main__":
    main()
