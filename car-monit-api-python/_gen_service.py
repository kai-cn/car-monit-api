# -*- coding: utf-8 -*-
"""把 Service 接口（除 ISysUtilService）生成等价 Python ABC 接口（临时工具）。"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
JAVA_DIR = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/service"
OUT_DIR = BASE / "pro-business-api/src/main/java/com/ruoyi/base/service"
DOMAIN_DIR = BASE / "pro-business-api/src/main/java/com/ruoyi/base/domain"

SKIP = {"ISysUtilService"}
IFACE_RE = re.compile(r"public interface (\w+)(?:\s+extends\s+IService<(\w+)>)?")
METHOD_RE = re.compile(
    r"(?P<doc>/\*\*.*?\*/\s*)?(?:public\s+)?(?P<ret>[\w<>,\s\.\[\]]+?)\s+(?P<name>\w+)\s*\((?P<params>.*?)\)\s*;",
    re.S,
)
SCALAR = {"String": "str", "Long": "int", "Integer": "int", "int": "int", "long": "int",
          "boolean": "bool", "Boolean": "bool", "Double": "float", "double": "float",
          "BigDecimal": "float", "Date": "datetime", "void": "None"}
PARAM_RE = re.compile(r"@param\s+(\w+)\s*(.*)")
RETURN_RE = re.compile(r"@return\s*(.*)")


def parse_doc(block):
    """把 Javadoc 拆成 (正文行, {参数名: 描述}, 返回值描述)。"""
    brief, param_desc, return_desc = [], {}, ""
    for raw in block.replace("/**", "").replace("*/", "").splitlines():
        line = raw.strip().lstrip("*").strip()
        if not line or line.startswith("@author") or line.startswith("@date"):
            continue
        matched = PARAM_RE.match(line)
        if matched:
            param_desc[matched.group(1)] = matched.group(2).strip()
            continue
        matched = RETURN_RE.match(line)
        if matched:
            return_desc = matched.group(1).strip()
            continue
        if line.startswith("@"):
            continue
        brief.append(line)
    return brief, param_desc, return_desc


def split_top(text):
    """按顶层逗号切分（忽略泛型 <> 内的逗号）。"""
    parts, depth, current = [], 0, ""
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += ch
    if current.strip():
        parts.append(current)
    return [p.strip() for p in parts if p.strip()]


def inner(java_type, prefix):
    return java_type[len(prefix):-1].strip()


def py_type(java_type, refs):
    java_type = java_type.strip()
    if java_type.startswith("List<"):
        return f"list[{py_type(inner(java_type, 'List<'), refs)}]"
    if java_type.startswith("Map<"):
        args = split_top(inner(java_type, "Map<"))
        return f"dict[{py_type(args[0], refs)}, {py_type(args[1], refs)}]"
    if java_type in SCALAR:
        return SCALAR[java_type]
    if (DOMAIN_DIR / f"{java_type}.py").exists():
        refs.add(java_type)
        return java_type
    # 其余非实体类型（如 AjaxResult、TrailInfo）暂按 Any 处理
    return "Any"


def emit(name):
    text = (JAVA_DIR / f"{name}.java").read_text(encoding="utf-8")
    match = IFACE_RE.search(text)
    iface, entity = match.group(1), match.group(2)
    brace = text.index("{", match.end() - 1)
    head, body_text = text[:brace], text[brace + 1:]
    docs = re.findall(r"/\*\*.*?\*/", head, re.S)
    class_brief = parse_doc(docs[-1])[0] if docs else [iface]

    refs = set()
    methods = []
    for m in METHOD_RE.finditer(body_text):
        brief, param_desc, return_desc = parse_doc(m.group("doc") or "")
        sig, notes = [], []
        for param in split_top(m.group("params")):
            tokens = param.split()
            ptype, pname = tokens[0], tokens[-1]
            sig.append(f"{pname}: {py_type(ptype, refs)}")
            desc = param_desc.get(pname, "")
            notes.append(f"        :param {pname}: {desc or ptype}")
        ret_java = m.group("ret").strip()
        ret = py_type(ret_java, refs)
        if ret_java not in ("void", "boolean") and not ret_java.startswith(("List<", "Map<")) and ret in refs:
            ret = f"Optional[{ret}]"
        if ret_java != "void":
            notes.append(f"        :return: {return_desc or ret}")
        methods.append((m.group("name"), sig, ret, brief[0] if brief else m.group("name"), brief[1:], notes))

    header = [
        "# -*- coding: utf-8 -*-",
        f'"""com.ruoyi.base.service.{iface}',
        "",
        f"源文件：pro-business-api/src/main/java/com/ruoyi/base/service/{iface}.java",
        '"""',
        "from __future__ import annotations",
        "",
        "from abc import ABC, abstractmethod",
    ]
    base = f"IService[{entity}], ABC" if entity else "ABC"
    body_lines = []
    for mname, sig, ret, brief, rest, notes in methods:
        body_lines.append("    @abstractmethod")
        body_lines.append(f"    def {mname}({', '.join(['self'] + sig)}) -> {ret}:")
        body_lines.append(f'        """{brief}')
        if rest:
            body_lines.append("")
            body_lines += ["        " + d for d in rest]
        if notes:
            body_lines.append("")
            body_lines += notes
        body_lines += ["", "        【Java→Python】抽象方法：实现见对应 *ServiceImpl。", '        """', ""]

    joined_body = "\n".join(body_lines)
    typing_names = [n for n in ("Any", "Optional") if f"{n}[" in joined_body or f"-> {n}:" in joined_body]
    if typing_names:
        header += ["from typing import " + ", ".join(typing_names), ""]
    if entity:
        header.append("from com.baomidou.mybatisplus.extension.service.IService import IService")
    for ref in sorted(refs):
        header.append(f"from com.ruoyi.base.domain.{ref} import {ref}")
    header += ["", f'__all__ = ["{iface}"]', "", "", f"class {iface}({base}):", f'    """{class_brief[0]}', ""]
    header += ["    " + d if d else "" for d in class_brief[1:]]
    if class_brief[1:]:
        header.append("")
    header += [
        "    【Java→Python】",
        f"    1) `public interface {iface}{' extends IService<' + entity + '>' if entity else ''}`",
        f"       → `class {iface}({base})`：用 abc.ABC + @abstractmethod 还原 Java interface",
        "       「只声明不实现」的契约（Java 编译期检查 → Python 运行期实例化检查）。",
        "    2) `List<T>` → `list[T]`；`Map<K,V>` → `dict[K, V]`；`boolean` → `bool`；`void` → `None`；",
        "       实体返回值 → `Optional[T]`（Java 查不到时返回 null）。",
        '    """',
        "",
    ]
    return "\n".join(header + body_lines).rstrip() + "\n"


OUT_DIR.mkdir(parents=True, exist_ok=True)
count = 0
for java in sorted(JAVA_DIR.glob("I*Service.java")):
    if java.stem in SKIP:
        continue
    (OUT_DIR / f"{java.stem}.py").write_text(emit(java.stem), encoding="utf-8")
    count += 1
print("generated", count)
