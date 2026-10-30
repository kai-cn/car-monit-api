# -*- coding: utf-8 -*-
"""Generate ``app/routes/generated.py`` from the Java controllers.

Why generate instead of hand-writing: Spring registers a route from
``@RestController`` + ``@RequestMapping`` + ``@GetMapping``/``@PostMapping``
and derives the parameter binding rules from the same annotations. A hand
written table would drift the moment a controller changes, so the table is
always produced from the Java sources -- exactly like ``tools/gen_java_meta.py``.

What is parsed
--------------
* ``@RequestMapping("<class path>")`` on the class -> route prefix
* ``@Get|Post|Put|Delete|Patch|RequestMapping`` on a method -> HTTP verb + sub path
* the method signature -> parameter list, each with its Spring source
  (``path`` / ``param`` / ``param_map`` / ``body`` / ``model``) and Java type

Comments are blanked out first, otherwise the commented-out methods at the
bottom of ``SysUtilController`` would produce phantom routes.

Re-run after touching a controller::

    .venv\\Scripts\\python.exe tools\\gen_routes.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
BUSINESS_JAVA = PROJECT_ROOT / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi" / "base"
CONTROLLER_DIR = BUSINESS_JAVA / "controller"
OUTPUT = ROOT / "app" / "routes" / "generated.py"

#: Maven source roots of the two modules (a wildcard import may come from either)
JAVA_ROOTS = [
    PROJECT_ROOT / "pro-business-api" / "src" / "main" / "java",
    PROJECT_ROOT / "pro-base-common" / "src" / "main" / "java",
]

_JAVA_SOURCES: Optional[set[str]] = None

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)(\.\*)?\s*;", re.M)
CLASS_MAPPING_RE = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?\{?\s*"([^"]*)"')
MAPPING_RE = re.compile(
    r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*(?:\(\s*(.*?)\s*\))?\s*"
    r"(?:(?:public|protected|private)\s+)?",
    re.S,
)
SIGNATURE_RE = re.compile(r"(?P<returns>[\w$.]+(?:\s*<[^;{}]*?>)?(?:\[\])?)\s+(?P<name>\w+)\s*\((?P<params>.*?)\)\s*(?:throws[^{;]*)?\{", re.S)
PATH_VALUE_RE = re.compile(r'^\s*(?:value\s*=\s*|path\s*=\s*)?\{?\s*"([^"]*)"')

SCALAR_TYPES = {
    "String": "str",
    "CharSequence": "str",
    "char": "str",
    "Character": "str",
    "int": "int",
    "Integer": "int",
    "long": "int",
    "Long": "int",
    "short": "int",
    "Short": "int",
    "byte": "int",
    "Byte": "int",
    "float": "float",
    "Float": "float",
    "double": "float",
    "Double": "float",
    "BigDecimal": "decimal",
    "boolean": "bool",
    "Boolean": "bool",
}
HTTP_VERBS = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
}


def strip_comments(text: str) -> str:
    """Blank out ``//`` and ``/* */`` while keeping every offset and newline."""
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out.append(" ")
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            out.append(" ")
            index += 1
            out.append(" ")
            index += 1
            while index < length and not (text[index] == "*" and index + 1 < length and text[index + 1] == "/"):
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            out.append(" ")
            index += 1
            out.append(" ")
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside ``<>`` or ``()``."""
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


def parse_annotation_args(args: str) -> dict[str, Any]:
    """``defaultValue = "1", required = false`` -> ``{"defaultValue": "1", ...}``."""
    result: dict[str, Any] = {}
    for chunk in split_top_level(args or ""):
        if not chunk:
            continue
        if "=" in chunk:
            key, raw = chunk.split("=", 1)
            key = key.strip()
            raw = raw.strip()
            if raw in ("true", "false"):
                result[key] = raw == "true"
            elif raw.startswith('"'):
                result[key] = raw.strip('"')
            elif raw.startswith("{") and raw.endswith("}"):
                result[key] = [item.strip().strip('"') for item in split_top_level(raw[1:-1]) if item.strip()]
            else:
                result[key] = raw
        elif chunk.startswith('"'):
            # shorthand: @GetMapping("/list") or @GetMapping({"a", "b"})
            result["value"] = chunk.strip('"')
        elif chunk.startswith("{"):
            result["value"] = [item.strip().strip('"') for item in split_top_level(chunk[1:-1]) if item.strip()]
        else:
            result.setdefault("value", chunk)
    return result


def first_path(args: dict[str, Any]) -> str:
    value = args.get("value", args.get("path", ""))
    if isinstance(value, list):
        value = value[0] if value else ""
    return value or ""


def parse_params(raw_params: str, imports: dict[str, str], package: str,
                 wildcards: list[str] | None = None) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for chunk in split_top_level(raw_params):
        if not chunk.strip():
            continue
        annotations = re.findall(r"@(\w+)\s*(?:\(([^()]*(?:\([^()]*\))?[^()]*)\))?", chunk)
        clean = re.sub(r"@\w+\s*(?:\([^()]*(?:\([^()]*\))?[^()]*\))?", " ", chunk)
        clean = " ".join(clean.split())
        clean = clean.replace("final ", "")
        match = re.match(r"(?P<type>[\w$.]+(?:\s*<.*>)?(?:\[\])?)\s+(?P<name>\w+)$", clean, re.S)
        if not match:
            raise SystemExit(f"cannot parse controller parameter: {chunk!r}")
        java_type = " ".join(match.group("type").split())
        name = match.group("name")
        annotation_map = {ann: (arg or "") for ann, arg in annotations}

        source = "model"
        java_name = name
        required = False
        default: Optional[str] = None
        if "PathVariable" in annotation_map:
            source = "path"
            args = parse_annotation_args(annotation_map["PathVariable"])
            java_name = first_path(args) or name
        elif "RequestParam" in annotation_map:
            args = parse_annotation_args(annotation_map["RequestParam"])
            named = first_path(args)
            if named:
                java_name = named
                source = "param"
            elif _is_map(java_type):
                # Spring: an unnamed Map<String,String> @RequestParam receives
                # *every* request parameter (RequestParamMapMethodArgumentResolver)
                source = "param_map"
            else:
                source = "param"
            default = args.get("defaultValue")
            required = bool(args.get("required", True)) and default is None
        elif "RequestBody" in annotation_map:
            source = "body"
            args = parse_annotation_args(annotation_map["RequestBody"])
            required = bool(args.get("required", True))
        else:
            unknown = set(annotation_map) - {"Valid", "Validated", "NotNull", "Nullable"}
            if unknown:
                raise SystemExit(f"unsupported parameter annotation {sorted(unknown)} in {chunk!r}")

        params.append({
            "name": name,
            "java_name": java_name,
            "source": source,
            "type": resolve_type(java_type, imports, package, wildcards or ()),
            "java_type": java_type,
            "required": required,
            "default": default,
        })
    return params


def _is_map(java_type: str) -> bool:
    return bool(re.match(r"^(?:java\.util\.)?(?:Map|MultiValueMap|LinkedHashMap|HashMap)\b", java_type))


def java_sources() -> set[str]:
    """Every FQCN declared by the two Java modules (``com.ruoyi.base.domain.TrailBo``).

    Needed because a controller may import a package wholesale
    (``import com.ruoyi.base.domain.*;``) and the simple name alone does not say
    which package the bean lives in.  Maven layout makes the path the FQCN.
    """
    global _JAVA_SOURCES
    if _JAVA_SOURCES is None:
        found: set[str] = set()
        for root in JAVA_ROOTS:
            if not root.is_dir():
                continue
            for path in root.rglob("*.java"):
                found.add(path.relative_to(root).with_suffix("").as_posix().replace("/", "."))
        _JAVA_SOURCES = found
    return _JAVA_SOURCES


def resolve_type(java_type: str, imports: dict[str, str], package: str,
                 wildcards: Sequence[str] = ()) -> str:
    """``OdsSzdnGantry`` -> ``com.ruoyi.base.domain.OdsSzdnGantry``."""
    compact = " ".join(java_type.split())
    if compact in SCALAR_TYPES:
        return SCALAR_TYPES[compact]
    if _is_map(compact):
        return "map"
    if compact.startswith("List<") or compact.startswith("Set<"):
        return "list"
    base = compact.split("<", 1)[0].strip()
    if base in SCALAR_TYPES:
        return SCALAR_TYPES[base]
    if "." in base:
        return base
    # Java resolution order: same package, single-type import, wildcard import.
    known = java_sources()
    local = f"{package}.{base}"
    if local in known:
        return local
    if base in imports:
        return imports[base]
    for wildcard in wildcards:
        candidate = f"{wildcard}.{base}"
        if candidate in known:
            return candidate
    return local


def parse_controller(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_text = path.read_text(encoding="utf-8")
    text = strip_comments(raw_text)
    package_match = PACKAGE_RE.search(text)
    if not package_match:
        raise SystemExit(f"no package in {path}")
    package = package_match.group(1)
    imports: dict[str, str] = {}
    wildcards: list[str] = []
    for match in IMPORT_RE.finditer(text):
        fqcn = match.group(1)
        if match.group(2):  # ``import com.ruoyi.base.domain.*;``
            wildcards.append(fqcn)
            continue
        imports[fqcn.rsplit(".", 1)[-1]] = fqcn
    class_match = re.search(r"\b(?:public\s+)?class\s+(\w+)", text)
    if not class_match:
        raise SystemExit(f"no class in {path}")
    class_name = class_match.group(1)
    fqcn = f"{package}.{class_name}"

    class_end = class_match.end()
    class_mapping = CLASS_MAPPING_RE.search(text, 0, class_end)
    base_path = class_mapping.group(1) if class_mapping else ""

    routes: list[dict[str, Any]] = []
    for mapping in MAPPING_RE.finditer(text, class_end):
        verb_name = mapping.group(1)
        args = parse_annotation_args(mapping.group(2) or "")
        sub_path = first_path(args)
        if verb_name == "Request" and not sub_path:
            # method-level @RequestMapping without a path: keep it, Spring maps
            # the class path itself
            sub_path = ""
        signature = SIGNATURE_RE.match(text, mapping.end())
        if not signature:
            continue
        returns = " ".join(signature.group("returns").split())
        method_name = signature.group("name")
        if method_name in {route["method"] for route in routes}:
            # overloaded handler would be ambiguous in Spring too
            continue
        full_path = _join_paths(base_path, sub_path)
        routes.append({
            "controller": fqcn,
            "method": method_name,
            "http": HTTP_VERBS.get(verb_name, "GET"),
            "path": full_path,
            "class_path": base_path,
            "returns": returns,
            "params": parse_params(signature.group("params"), imports, package, wildcards),
            "java": f"{_relative(path)}:{_line_of(raw_text, signature.start('name'))}",
        })
    return {"fqcn": fqcn, "class_path": base_path, "file": _relative(path)}, routes


def _join_paths(base: str, sub: str) -> str:
    if not base:
        return sub or "/"
    if not sub:
        return base
    return base.rstrip("/") + "/" + sub.lstrip("/")


def _relative(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    controllers: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    for path in sorted(CONTROLLER_DIR.glob("*Controller.java")):
        controller, controller_routes = parse_controller(path)
        controllers.append(controller)
        routes.extend(controller_routes)
    return controllers, routes


def _py(value: Any) -> str:
    """Python literal (``json.dumps`` would emit ``false``/``null``)."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None or isinstance(value, (bool, int, float)):
        return repr(value)
    raise TypeError(f"unsupported literal: {value!r}")


def _dict_literal(mapping: dict[str, Any]) -> str:
    return "{" + ", ".join(f"{key!r}: {_py(item)}" for key, item in mapping.items()) + "}"


def render(controllers: list[dict[str, Any]], routes: list[dict[str, Any]]) -> str:
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""Route table generated from the Java controllers -- DO NOT EDIT.',
        "",
        "Regenerate with::",
        "",
        "    .venv\\\\Scripts\\\\python.exe tools\\\\gen_routes.py",
        "",
        f"{len(controllers)} controller(s), {len(routes)} handler method(s).",
        "",
        "``source`` mirrors Spring's argument resolution:",
        "",
        "    path      @PathVariable",
        "    param     @RequestParam (single value, first wins)",
        "    param_map @RequestParam Map<String,String> (every request parameter)",
        "    body      @RequestBody",
        "    model     unannotated POJO -> @ModelAttribute style binding",
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "__all__ = [\"CONTROLLERS\", \"ROUTES\"]",
        "",
        "CONTROLLERS: list[dict[str, Any]] = [",
    ]
    for controller in controllers:
        lines.append(f"    {_dict_literal(controller)},")
    lines.append("]")
    lines.append("")
    lines.append("ROUTES: list[dict[str, Any]] = [")
    for route in routes:
        lines.append("    {")
        for key in ("controller", "method", "http", "path", "class_path", "returns", "java"):
            lines.append(f"        {json.dumps(key)}: {_py(route[key])},")
        lines.append('        "params": [')
        for param in route["params"]:
            lines.append(f"            {_dict_literal(param)},")
        lines.append("        ],")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    controllers, routes = build()
    OUTPUT.write_text(render(controllers, routes), encoding="utf-8")
    print(f"controllers : {len(controllers)}")
    print(f"handlers    : {len(routes)}")
    by_source: dict[str, int] = {}
    for route in routes:
        for param in route["params"]:
            by_source[param["source"]] = by_source.get(param["source"], 0) + 1
    print("param kinds :", ", ".join(f"{k}={v}" for k, v in sorted(by_source.items())))
    print("written     :", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
