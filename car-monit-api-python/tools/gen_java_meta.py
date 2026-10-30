# -*- coding: utf-8 -*-
"""Generate ``app/compat/java_meta.py`` from the Java sources.

Why: the ported Python dataclasses keep snake_case fields and only *comment*
the Java annotations, so two things cannot be recovered at runtime:

1. the exact Java property name (``gantryCaptureBO`` != ``snake_to_camel``),
2. the ``@JsonFormat`` pattern of each ``Date`` field,
3. the return type of every mapper method (single object vs ``List``) and its
   parameter names, which the proxy needs to route ``@Param`` values.

Everything is read from the Java sources, so the Python side can never drift
from the original service. Re-run after changing a domain or mapper:

    .venv\\Scripts\\python.exe tools\\gen_java_meta.py
"""
from __future__ import annotations

import pprint
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT.parent
BUSINESS_JAVA = PROJECT_ROOT / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi" / "base"
MAPPER_DIR = BUSINESS_JAVA / "mapper"
DOMAIN_DIR = BUSINESS_JAVA / "domain"
OUTPUT = ROOT / "app" / "compat" / "java_meta.py"

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
INTERFACE_RE = re.compile(r"\b(?:public\s+)?interface\s+(\w+)")
METHOD_RE = re.compile(
    r"^\s*(?:public\s+|default\s+)?"
    r"([\w$.]+(?:\s*<[^;{}]*?>)?(?:\[\])?)"   # return type
    r"\s+(\w+)\s*\(([^;]*?)\)\s*;",            # name + params
    re.M,
)
PARAM_RE = re.compile(r'(?:@Param\(\s*"([^"]+)"\s*\)\s*)?([\w$.<>\[\], ?]+?)\s+(\w+)$')
FIELD_RE = re.compile(
    r"((?:@\w+(?:\([^)]*\))?\s*)*)"           # annotations
    r"private\s+([\w.$<>, \[\]]+?)\s+(\w+)\s*(?:=[^;]*)?;",
    re.S,
)
JSON_FORMAT_RE = re.compile(r'@JsonFormat\s*\(\s*pattern\s*=\s*"([^"]+)"')
TABLE_FIELD_EXIST_FALSE_RE = re.compile(r"@TableField\s*\([^)]*\bexist\s*=\s*false")
TABLE_ID_RE = re.compile(r'@TableId\s*\([^)]*type\s*=\s*IdType\.(\w+)')
# ``@Select("SELECT ..." + "...") getMaxSnapshotTime();``
SQL_ANNOTATION_RE = re.compile(
    r'@(Select|Update|Insert|Delete)\s*\(\s*((?:"(?:[^"\\]|\\.)*"\s*\+?\s*)+)\)', re.S)
STRING_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')

_ACRONYM_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    intermediate = _ACRONYM_RE.sub(r"\1_\2", name)
    return _CAMEL_RE.sub(r"\1_\2", intermediate).lower()


def _split_params(text: str) -> list[str]:
    """Split a parameter list on top-level commas (generics and annotations contain commas)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "<(":
            depth += 1
        elif char in ">)":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if "".join(current).strip():
        parts.append("".join(current))
    return [part.strip() for part in parts]


def parse_mappers() -> dict:
    mappers: dict[str, dict] = {}
    for path in sorted(MAPPER_DIR.glob("*.java")):
        text = path.read_text(encoding="utf-8")
        package_match = PACKAGE_RE.search(text)
        interface_match = INTERFACE_RE.search(text)
        if not package_match or not interface_match:
            continue
        fqcn = f"{package_match.group(1)}.{interface_match.group(1)}"
        methods: dict[str, dict] = {}
        for match in METHOD_RE.finditer(text):
            returns, name, raw_params = match.group(1), match.group(2), match.group(3)
            params = []
            for raw in _split_params(raw_params):
                param_match = PARAM_RE.match(raw)
                if not param_match:
                    continue
                params.append([param_match.group(3), param_match.group(2).strip(), param_match.group(1)])
            methods[name] = {"returns": returns.strip(), "params": params}
        mappers[fqcn] = methods
    return mappers


def parse_annotated_statements() -> dict:
    """``@Select`` / ``@Update`` SQL written on the mapper interface itself."""
    statements: dict[str, dict] = {}
    for path in sorted(MAPPER_DIR.glob("*.java")):
        text = path.read_text(encoding="utf-8")
        package_match = PACKAGE_RE.search(text)
        interface_match = INTERFACE_RE.search(text)
        if not package_match or not interface_match:
            continue
        fqcn = f"{package_match.group(1)}.{interface_match.group(1)}"
        entries: dict[str, dict] = {}
        for match in SQL_ANNOTATION_RE.finditer(text):
            kind = match.group(1).lower()
            sql = "".join(STRING_LITERAL_RE.findall(match.group(2)))
            sql = sql.replace('\\"', '"').replace("\\n", "\n").strip()
            signature = re.search(r"\b(\w+)\s*\(", text[match.end():])
            if not signature or not sql:
                continue
            entries[signature.group(1)] = {"kind": kind, "sql": sql}
        if entries:
            statements[fqcn] = entries
    return statements


def parse_domains() -> tuple[dict, dict]:
    formats: dict[str, dict[str, str]] = {}
    names: dict[str, dict[str, str]] = {}
    for path in sorted(DOMAIN_DIR.glob("*.java")):
        text = path.read_text(encoding="utf-8")
        package_match = PACKAGE_RE.search(text)
        class_match = re.search(r"\b(?:public\s+)?class\s+(\w+)", text)
        if not package_match or not class_match:
            continue
        fqcn = f"{package_match.group(1)}.{class_match.group(1)}"
        class_formats: dict[str, str] = {}
        class_names: dict[str, str] = {}
        for match in FIELD_RE.finditer(text):
            annotations, _java_type, java_name = match.group(1), match.group(2), match.group(3)
            field_name = camel_to_snake(java_name)
            class_names[field_name] = java_name
            format_match = JSON_FORMAT_RE.search(annotations or "")
            if format_match:
                class_formats[field_name] = format_match.group(1)
        if class_names:
            names[fqcn] = class_names
        if class_formats:
            formats[fqcn] = class_formats
    return formats, names


def main() -> None:
    mappers = parse_mappers()
    annotated = parse_annotated_statements()
    formats, names = parse_domains()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        handle.write('# -*- coding: utf-8 -*-\n')
        handle.write('"""Java metadata extracted from the original sources.\n\n')
        handle.write("GENERATED FILE -- do not edit. Regenerate with:\n")
        handle.write("    .venv\\\\Scripts\\\\python.exe tools\\\\gen_java_meta.py\n\n")
        handle.write("* ``MAPPERS``      : mapper interface methods (return type + @Param names)\n")
        handle.write("* ``ANNOTATED_STATEMENTS``: ``@Select``/``@Update`` SQL on the interface\n")
        handle.write("* ``JSON_FORMATS``: @JsonFormat(pattern) per domain field\n")
        handle.write("* ``JAVA_NAMES``  : snake_case field -> Java property name\n")
        handle.write('"""\n')
        handle.write("from __future__ import annotations\n\n")
        for name, value in (("MAPPERS", mappers),
                            ("ANNOTATED_STATEMENTS", annotated),
                            ("JSON_FORMATS", formats),
                            ("JAVA_NAMES", names)):
            handle.write(f"{name} = " + pprint.pformat(value, width=118, sort_dicts=True) + "\n\n")
    print(f"wrote {OUTPUT}")
    print(f"  mappers     : {len(mappers)}")
    print(f"  annotated   : {sum(len(v) for v in annotated.values())}")
    print(f"  domain name : {len(names)}")
    print(f"  json format : {len(formats)}")


if __name__ == "__main__":
    main()
