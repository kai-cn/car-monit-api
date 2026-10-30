# -*- coding: utf-8 -*-
"""扫描 domain 中所有“无访问修饰符”的字段（Lombok 仍会生成 getter/setter），与 Python 对照。"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(ROOT)
JAVA_DIR = os.path.join(WORKSPACE, "pro-business-api", "src", "main", "java", "com", "ruoyi", "base", "domain")
PY_DIR = os.path.join(ROOT, "pro-business-api", "src", "main", "java", "com", "ruoyi", "base", "domain")

FIELD_RE = re.compile(
    r"^\s+(?!private\b|public\b|protected\b|static\b|final\b|transient\b|volatile\b|@|return\b|new\b)"
    r"([A-Za-z_$][\w$.]*(?:\s*<[^;=()]*>)?(?:\s*\[\s*\])?)\s+([A-Za-z_$][\w$]*)\s*(?:=[^;]*)?;"
)

CLASS_RE = re.compile(r"public\s+class\s+([A-Za-z_$][\w$]*)")

results = {}
for name in sorted(os.listdir(JAVA_DIR)):
    if not name.endswith(".java"):
        continue
    path = os.path.join(JAVA_DIR, name)
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    found = []
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        # 跳过方法体、注解、注释、return/new/else 等语句
        if (not stripped or stripped.startswith("//") or stripped.startswith("*")
                or stripped.startswith("/*") or "(" in stripped or ")" in stripped
                or stripped.startswith("return") or stripped.startswith("throw")
                or stripped.startswith("else") or stripped.startswith("new")
                or stripped.startswith("for") or stripped.startswith("if")
                or stripped.startswith("while") or stripped.startswith("case")
                or stripped.startswith("import") or stripped.startswith("package")
                or stripped.startswith("public") or stripped.startswith("private")
                or stripped.startswith("protected") or stripped.startswith("static")
                or stripped.startswith("final") or stripped.startswith("@")
                or stripped.startswith("}") or stripped.startswith("{")):
            continue
        match = FIELD_RE.match(line)
        if match:
            java_type, field_name = match.group(1).strip(), match.group(2)
            # 排除明显的误判：没有分号结尾
            if not stripped.endswith(";"):
                continue
            found.append((index, java_type, field_name))

    if found:
        results[name] = (lines, found)

print("含无修饰符字段的类：", len(results))
for name, (lines, found) in results.items():
    py_path = os.path.join(PY_DIR, name[:-5] + ".py")
    py_text = ""
    if os.path.exists(py_path):
        with open(py_path, "r", encoding="utf-8") as handle:
            py_text = handle.read()
    missing = []
    for index, java_type, field_name in found:
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", field_name).lower()
        if snake not in py_text and field_name not in py_text:
            missing.append((index, java_type, field_name, snake))
    print("\n%s: 无修饰符字段 %d 个，Python 缺失 %d 个" % (name, len(found), len(missing)))
    for index, java_type, field_name, snake in missing:
        print("   L%-5s %-45s %-25s -> %s" % (index, java_type, field_name, snake))
