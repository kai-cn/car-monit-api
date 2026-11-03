#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JAVA -> GO 模型层代码生成器
===========================

用途
----
把 pro-business-api/src/main/java/com/ruoyi/base/domain/*.java 批量转换为
car-monit-api-go/internal/model/*.go，保证：
  1. 字段数量、JSON 字段名（Jackson 默认取字段名）、可空性一一对应；
  2. 每个字段上方带 `// JAVA: <file>:L<line>` 锚点（提示词原则 C：不允许孤立的 Go 代码）；
  3. @TableName / @TableId / @TableField(exist=false) 语义落到 gorm tag / `gorm:"-"`。

设计取舍（DIFF）
----------------
* Lombok @Data 生成的 getter/setter 在 Go 中不需要：直接导出字段即可。
* Jackson 反序列化依赖 setter；Go 依赖 json tag，故 json 名必须与 Java 字段名完全一致。
* `Date` 字段统一映射 `*time.Time`；带 `@JsonFormat(pattern = "yyyy-MM-dd")` 的映射 `*model.Day`，
  以保持 Java 侧 "2026-10-31" 而不是 RFC3339 的输出格式。
* `@TableField(exist = false)` 的字段只参与 JSON，不参与 SQL（gorm `-`）。

用法
----
    python tools/gen_models.py            # 需要 Java 源码在同级仓库路径下
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAVA_DIR = os.path.join(
    os.path.dirname(BASE),
    "pro-business-api", "src", "main", "java", "com", "ruoyi", "base", "domain",
)
OUT_DIR = os.path.join(BASE, "internal", "model")

TABLE_RE = re.compile(r'@TableName\((?:value\s*=\s*)?"([^"]+)"(?:\s*,\s*schema\s*=\s*"([^"]+)")?')
TABLE_ID_RE = re.compile(r'@TableId\((?:value\s*=\s*"([^"]+)"|(?:type\s*=\s*IdType\.\w+))')
FIELD_RE = re.compile(
    r'^\s*(?:(?:private|protected|public)\s+)?'
    r'(?:(?:static|final|transient|volatile)\s+)*'
    r'(?P<type>[A-Za-z_][\w\.]*(?:\s*<[^;=]*>)?(?:\s*\[\s*\])?)\s+'
    r'(?P<name>[A-Za-z_]\w*)\s*(?:=[^;]*)?;\s*(?://.*|/\*.*\*/)?\s*$'
)
JSONFORMAT_RE = re.compile(r'@JsonFormat\([^)]*pattern\s*=\s*"([^"]+)"')
EXCEL_RE = re.compile(r'@Excel\([^)]*name\s*=\s*"([^"]*)"')

SCALARS = {
    "String": "string",
    "Integer": "int",
    "Long": "int64",
    "Short": "int16",
    "Byte": "int8",
    "Double": "float64",
    "Float": "float32",
    "Boolean": "bool",
    "BigDecimal": "float64",
    "BigInteger": "int64",
    "Date": "time.Time",
    "Timestamp": "time.Time",
    "LocalDateTime": "time.Time",
    "Object": "any",
}
# Java 基本类型（不可为 null）→ 值类型；包装类型 → 指针，保持"null 与 0 可区分"的语义
PRIMITIVES = {"int", "long", "short", "byte", "double", "float", "boolean", "char"}


def snake(name):
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
    return s.replace("-", "_").lower()


def camel(name):
    """UPPER_HIDDEN -> UpperHidden"""
    parts = name.split("_")
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return out[:1].upper() + out[1:]


def go_type(java_type, jsonformat=None):
    """返回 (go type, 是否需要 time/model 引用)"""
    t = java_type.replace(" ", "")
    if t.startswith("List<") or t.startswith("Collection<") or t.startswith("Set<"):
        inner = t[t.index("<") + 1:t.rindex(">")]
        it, _ = go_type(inner)
        return "[]" + it.lstrip("*"), False
    if t.endswith("[]"):
        it, _ = go_type(t[:-2])
        return "[]" + it.lstrip("*"), False
    base = t.split("<")[0]
    if base in SCALARS:
        gt = SCALARS[base]
        if base in ("Date", "Timestamp", "LocalDateTime"):
            if jsonformat:
                return "*Day", True
            return "*time.Time", True
        if base == "String" or base == "Object":
            return gt, False
        if base == "Integer":
            return "*int", False
        return "*" + gt, False
    # 自定义类型（嵌套 BO / VO）
    return "*" + base, False


def parse_file(path):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    table, schema, pk = None, None, None
    class_name = None
    fields = []
    pending_jsonformat = None
    pending_excel = None
    pending_transient = False
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line = raw.strip()
        lineno = idx + 1
        idx += 1

        if line.startswith("//"):
            continue
        m = TABLE_RE.search(line)
        if m:
            table, schema = m.group(1), m.group(2)
            continue
        if "@TableId" in line:
            m = TABLE_ID_RE.search(line)
            if m and m.group(1):
                pk = m.group(1)
            continue
        if "@TableField" in line:
            if "exist" in line and "false" in line:
                pending_transient = True
            continue
        m = JSONFORMAT_RE.search(line)
        if m:
            pending_jsonformat = m.group(1)
            continue
        m = EXCEL_RE.search(line)
        if m:
            pending_excel = m.group(1)
            continue
        m = re.search(r'\bpublic\s+(?:final\s+)?class\s+(\w+)', line)
        if m:
            class_name = m.group(1)
            continue
        if line.startswith("@"):
            continue

        m = FIELD_RE.match(raw)
        if m:
            jtype, jname = m.group("type").strip(), m.group("name")
            if jname in ("serialVersionUID",):
                continue
            fields.append({
                "line": lineno,
                "type": jtype,
                "name": jname,
                "jsonformat": pending_jsonformat,
                "excel": pending_excel,
                "transient": pending_transient,
            })
        pending_jsonformat = None
        pending_excel = None
        pending_transient = False

    return {
        "file": os.path.basename(path),
        "class": class_name,
        "table": table,
        "schema": schema,
        "pk": pk,
        "fields": fields,
    }


def emit(spec, rel_java_path):
    cls = spec["class"]
    go_name = cls
    out = []
    out.append("package model")
    out.append("")
    out.append("// JAVA 对照: %s" % rel_java_path)
    out.append("// 类/职责: %s — %s" % (cls, ("表 %s 的实体" % spec["table"]) if spec["table"] else "DTO/VO（无独立表）"))
    out.append("// 对应 Go 文件: internal/model/%s.go" % snake(cls))
    if spec["table"]:
        out.append("// 关键映射: @TableName(value=%r, schema=%r) → TableName()/Schema()；@TableId(%s) → primaryKey；" % (
            spec["table"], spec["schema"], spec["pk"]))
    else:
        out.append("// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；")
    out.append("// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。")
    out.append("")

    need_time = any(go_type(f["type"], f["jsonformat"])[1] for f in spec["fields"])
    imports = []
    if need_time:
        imports.append('"time"')
    if imports:
        out.append("import (")
        for imp in imports:
            out.append("\t" + imp)
        out.append(")")
        out.append("")

    out.append("// %s 对应 Java 类 %s" % (go_name, cls))
    out.append("type %s struct {" % go_name)
    width = max([len(f["name"]) for f in spec["fields"]] + [8])
    for f in spec["fields"]:
        gt, _ = go_type(f["type"], f["jsonformat"])
        col = snake(f["name"])
        tag_parts = ['json:"%s"' % f["name"]]
        if spec["table"]:
            if f["transient"]:
                tag_parts.append('gorm:"-"')
            elif spec["pk"] and f["name"] == _jname_of(spec["pk"], spec["fields"]):
                tag_parts.append('gorm:"column:%s;primaryKey"' % spec["pk"])
            else:
                tag_parts.append('gorm:"column:%s"' % col)
        comment = " // JAVA L%d" % f["line"]
        if f["type"].startswith("List"):
            comment += " List<...> → slice"
        if f["jsonformat"]:
            comment += " @JsonFormat(%s) → Day" % f["jsonformat"]
        if f["excel"]:
            comment += " @Excel(%s)" % f["excel"]
        out.append("\t%-*s %-22s `%s`%s" % (width, camel(f["name"]), gt, " ".join(tag_parts), comment))
    out.append("}")
    out.append("")

    if spec["table"]:
        out.append("// TableName 对应 Java @TableName —— GORM 表名解析入口。")
        out.append("// DIFF: GORM 会把 TableName() 的返回值整体当作一个标识符加引号，写成 \"schema.table\" 会被转义成")
        out.append("//       一个带点的表名而报 42P01，因此这里只返回裸表名；需要 schema 限定名时用 TableFullName()。")
        out.append("func (%s) TableName() string {" % go_name)
        out.append('\treturn "%s"' % spec["table"])
        out.append("}")
        out.append("")
        out.append("// Schema 对应 Java @TableName(schema = ...)")
        out.append("func (%s) Schema() string {" % go_name)
        out.append('\treturn "%s"' % (spec["schema"] or ""))
        out.append("}")
        out.append("")
        out.append("// TableFullName 返回手写 SQL 中可直接内联的 schema 限定表名")
        out.append("func (%s) TableFullName() string {" % go_name)
        if spec["schema"]:
            out.append('\treturn "%s.%s"' % (spec["schema"], spec["table"]))
        else:
            out.append('\treturn "%s"' % spec["table"])
        out.append("}")
        out.append("")
    return "\n".join(out)


def _jname_of(column, fields):
    """把列名（big_id）反查回 Java 字段名（bigId）"""
    for f in fields:
        if snake(f["name"]) == column:
            return f["name"]
    return column


def main():
    if not os.path.isdir(JAVA_DIR):
        sys.exit("Java domain 目录不存在: %s" % JAVA_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for fn in sorted(os.listdir(JAVA_DIR)):
        if not fn.endswith(".java"):
            continue
        path = os.path.join(JAVA_DIR, fn)
        spec = parse_file(path)
        if not spec["class"]:
            print("skip (no class):", fn)
            continue
        rel = "pro-business-api/src/main/java/com/ruoyi/base/domain/%s" % fn
        code = emit(spec, rel)
        out_path = os.path.join(OUT_DIR, snake(spec["class"]) + ".go")
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code + "\n")
        count += 1
        print("generated %-46s ← %s (%d fields)" % (
            os.path.basename(out_path), fn, len(spec["fields"])))
    print("\n共生成 %d 个模型文件 → %s" % (count, OUT_DIR))


if __name__ == "__main__":
    main()
