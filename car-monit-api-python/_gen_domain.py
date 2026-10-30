# -*- coding: utf-8 -*-
"""按 Java 源文件生成 1:1 的 Python 实体（domain 层），生成后人工复核。"""
import keyword
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/domain"
DST = BASE / "pro-business-api/src/main/java/com/ruoyi/base/domain"

CLASS_RE = re.compile(r"^\s*public\s+class\s+(\w+)([^{]*?)\s*\{?\s*$")
FIELD_RE = re.compile(
    r"^\s*(?:private|public|protected)\s+(?:static\s+final\s+)?([\w<>\[\], .?$]+?)\s+(\w+)\s*(?:=\s*(.+?))?;\s*(?://\s*(.*))?$"
)
ANN_RE = re.compile(r"^\s*@(\w+)(?:\((.*)\))?\s*$")

SIMPLE_TYPES = {
    "String": "str", "CharSequence": "str", "Object": "Any",
    "Long": "int", "Integer": "int", "Short": "int", "Byte": "int", "BigInteger": "int",
    "Double": "float", "Float": "float", "BigDecimal": "float",
    "Boolean": "bool", "boolean": "bool", "int": "int", "long": "int",
    "Date": "datetime", "Timestamp": "datetime", "LocalDateTime": "datetime",
    "LocalDate": "date", "LocalTime": "time",
}


def camel_to_snake(name: str) -> str:
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def safe_name(name: str) -> str:
    return name + "_" if keyword.iskeyword(name) else name


def _unwrap_optional(py_type: str) -> str:
    """泛型内部元素不再包 Optional（List<String> → list[str] 而非 list[Optional[str]]）。"""
    if py_type.startswith("Optional[") and py_type.endswith("]"):
        return py_type[len("Optional["):-1]
    return py_type


def map_type(java_type: str, used: set) -> str:
    t = java_type.strip()
    if t.endswith("[]"):
        used.add("Optional")
        base = map_type(t[:-2], used)
        return "Optional[bytes]" if base == "bytes" else f"Optional[list[{base}]]"
    generic = re.match(r"^(\w+)\s*<(.*)>$", t)
    if generic:
        container, args = generic.group(1), generic.group(2)
        # 处理嵌套泛型 Map<String, List<String>>：按顶层逗号切分
        depth, parts, current = 0, [], ""
        for ch in args:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current.strip())
        inner = [_unwrap_optional(map_type(p, used)) for p in parts]
        used.add("Optional")
        if container in ("List", "Set", "Collection", "Iterable"):
            used.add("list" if container != "Set" else "set")
            inner_type = inner[0] if inner else "Any"
            if container == "Set":
                return f"Optional[set[{inner_type}]]"
            return f"Optional[list[{inner_type}]]"
        if container == "Map":
            used.add("dict")
            if len(inner) == 2:
                return f"Optional[dict[{inner[0]}, {inner[1]}]]"
            return "Optional[dict[Any, Any]]"
        return "Optional[Any]"
    if t == "byte":
        used.add("Optional")
        return "Optional[int]"
    py = SIMPLE_TYPES.get(t)
    used.add("Optional")
    if py is None:
        used.add("Any")
        return "Optional[Any]"
    used.add(py)
    return f"Optional[{py}]"


def clean_comment(lines) -> str:
    texts = []
    for raw in lines:
        s = raw.strip()
        s = re.sub(r"^/\*\*?", "", s)
        s = re.sub(r"^//+", "", s)
        s = s.replace("*/", "")
        s = re.sub(r"^\*+", "", s).strip()
        if not s or s.startswith("@"):
            continue
        texts.append(s)
    text = " ".join(texts)
    text = " ".join(text.split())
    return text.replace('"', "'")


def literal(value: str):
    v = value.strip()
    if v in ("null", "NULL"):
        return "None"
    if v in ("true", "TRUE"):
        return "True"
    if v in ("false", "FALSE"):
        return "False"
    if re.fullmatch(r"-?\d+[lL]?", v):
        return v.rstrip("lL")
    if re.fullmatch(r"-?\d+\.\d+[fFdD]?", v):
        return v.rstrip("fFdD")
    if v.startswith('"') and v.endswith('"'):
        return v
    return None


def parse_metadata(annotations) -> tuple:
    """从注解中提取 @TableId / @TableField 的 metadata 描述与注释。"""
    metadata = []
    for raw in annotations:
        m = ANN_RE.match(raw)
        if not m:
            continue
        name, args = m.group(1), m.group(2) or ""
        if name == "TableId":
            value = re.search(r'value\s*=\s*"([^"]*)"', args)
            id_type = re.search(r"type\s*=\s*IdType\.(\w+)", args)
            item = []
            if value:
                item.append(f'"table_id": "{value.group(1)}"')
            if id_type:
                item.append(f'"id_type": "{id_type.group(1)}"')
            metadata.extend(item)
        elif name == "TableField":
            value = re.search(r'value\s*=\s*"([^"]*)"', args)
            exist = re.search(r"exist\s*=\s*(true|false)", args)
            item = []
            if value:
                item.append(f'"column": "{value.group(1)}"')
            if exist:
                item.append(f'"exist": {exist.group(1).capitalize()}')
            metadata.extend(item)
    return metadata


def generate(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    class_name, class_annotations, class_javadoc = None, [], []
    body_start = 0
    # 类声明前的注解与 Javadoc
    pending_ann, pending_doc, doc_open = [], [], False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("/**"):
            doc_open = True
        if doc_open:
            pending_doc.append(stripped)
            if stripped.endswith("*/"):
                doc_open = False
            continue
        if stripped.startswith("@"):
            pending_ann.append(stripped)
            continue
        m = CLASS_RE.match(line)
        if m:
            class_name, class_annotations, class_javadoc = m.group(1), pending_ann, pending_doc
            body_start = idx + 1
            break

    # 类体字段解析
    fields = []
    pending: list = []
    doc_open = False
    for line in lines[body_start:]:
        stripped = line.strip()
        if stripped.startswith("/*"):
            doc_open = not stripped.endswith("*/")
            pending.append(stripped)
            continue
        if doc_open:
            pending.append(stripped)
            if stripped.endswith("*/"):
                doc_open = False
            continue
        if stripped.startswith("//"):
            pending.append(stripped)
            continue
        if stripped.startswith("@"):
            pending.append(stripped)
            continue
        if stripped == "}":
            break
        m = FIELD_RE.match(line)
        if m:
            fields.append({
                "java_type": m.group(1).strip(),
                "name": m.group(2),
                "default": m.group(3),
                "trailing": m.group(4),
                "pending": list(pending),
            })
            pending = []
            continue
        if stripped:
            pending = []

    table_name = None
    for ann in class_annotations:
        m = re.search(r'@TableName\(\s*(?:value\s*=\s*)?"([^"]+)"', ann)
        if m:
            table_name = m.group(1)
    chain = any("Accessors" in a and "chain" in a for a in class_annotations)
    implements = "Custom" in text.split("\n")[body_start - 1] or \
        "implements Custom" in text.split("\n")[body_start - 1]

    used: set = set()
    field_lines: list[str] = []
    for info in fields:
        if info["name"] == "serialVersionUID":
            continue
        py_type = map_type(info["java_type"], used)
        py_name = safe_name(camel_to_snake(info["name"]))
        metadata = parse_metadata(info["pending"])
        default = literal(info["default"]) if info["default"] else None

        comments = []
        ann_comments = []
        for raw in info["pending"]:
            if raw.startswith("@"):
                ann_comments.append(raw)
                continue
            c = clean_comment([raw])
            if c:
                comments.append(c)
        if info["trailing"]:
            comments.append(info["trailing"].strip())

        java_decl = f"private {info['java_type']} {info['name']};"
        comment = " ".join(comments).replace("*/", "")
        tail = f"  # Java: {java_decl}"
        if comment:
            tail += f" // {comment}"

        if ann_comments:
            field_lines.append("    # " + " ".join(ann_comments))
        if metadata:
            meta = "{" + ", ".join(metadata) + "}"
            if default is not None:
                field_lines.append(f"    {py_name}: {py_type} = field(default={default}, metadata={meta}){tail}")
            else:
                field_lines.append(f"    {py_name}: {py_type} = field(default=None, metadata={meta}){tail}")
        else:
            value = default if default is not None else "None"
            field_lines.append(f"    {py_name}: {py_type} = {value}{tail}")
        field_lines.append("")

    # ---- 组装文件 ----
    used.add("dataclass")
    imports = ["from dataclasses import dataclass" + (", field" if any("field(" in l for l in field_lines) else "")]
    dt_types = [t for t in ("datetime", "date", "time") if t in used]
    if dt_types:
        imports.append("from datetime import " + ", ".join(sorted(dt_types)))
    typing_names = [t for t in ("Any", "Optional") if t in used]
    if typing_names:
        imports.append("from typing import " + ", ".join(typing_names))
    imports.append("")
    imports.append("from com.ruoyi.common.core.domain.JavaBean import JavaBean")
    if implements:
        imports.append("from com.ruoyi.common.core.domain.Custom import Custom")

    bases = "JavaBean, Custom" if implements else "JavaBean"

    header = [
        "# -*- coding: utf-8 -*-",
        f'"""com.ruoyi.base.domain.{class_name}',
        "",
        f"源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/{path.name}",
        '"""',
        "from __future__ import annotations",
        "",
        "\n".join(imports),
        "",
        "",
        "@dataclass",
        f"class {class_name}({bases}):",
    ]

    doc_title = clean_comment(class_javadoc) if class_javadoc else class_name
    doc_lines = [
        f'    """{doc_title}',
        "",
        "    【Java→Python】",
        "    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供",
        "       （含 @Accessors(chain = true) 的链式 setter，返回 self）。",
    ]
    if table_name:
        doc_lines.append(f'    2) @TableName("{table_name}") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。')
    else:
        doc_lines.append("    2) 无 @TableName（非表实体 / VO / DTO）。")
    doc_lines.append("    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；")
    doc_lines.append("       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。")
    if chain:
        doc_lines.append("    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。")
    doc_lines.append("    " + ('"""'))

    out = header + doc_lines
    if table_name:
        out.append(f'    TABLE_NAME = "{table_name}"  # @TableName("{table_name}")')
        out.append("")
    annotated = [f for f in fields if f["name"] != "serialVersionUID"]
    if not annotated:
        out.append("    pass")
    else:
        out.extend(field_lines)
    while out and out[-1] == "":
        out.pop()
    out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(SRC.glob("*.java")):
        code = generate(path)
        (DST / (path.stem + ".py")).write_text(code, encoding="utf-8")
        count += 1
        print("generated", path.stem + ".py", len(code.splitlines()), "lines")
    print("total", count)


if __name__ == "__main__":
    main()
