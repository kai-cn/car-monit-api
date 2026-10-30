# -*- coding: utf-8 -*-
"""把「纯 CRUD」的 Java Mapper 接口生成等价 Python 类（临时工具）。

只处理仅含 selectXxxById / selectXxxList 两个方法的 13 个 Mapper；
含自定义 SQL 的 Mapper 由人工逐行编写以保证注释质量。
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
JAVA_DIR = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/mapper"
OUT_DIR = BASE / "pro-business-api/src/main/java/com/ruoyi/base/mapper"

SIMPLE = [
    "DwdLcztFwqjcxxMapper",
    "DwdLcztSfsjcxxMapper",
    "DwdLcztSfzjcxxMapper",
    "OdsCxztFwqcllsMapper",
    "OdsLwzxsfsjFeeGantryFusion01Mapper",
    "OdsLwzxsfsjFeeStationEnter01Mapper",
    "OdsLwzxsfsjFeeStationExit01Mapper",
    "OdsSzdnGantryMapper",
    "OdsSzdnSectionMapper",
    "OdsSzdnTollMapper",
    "OdsSzdnTollStationIpMapper",
    "OdsYhglVBaseOrgMapper",
    "ZdataLocationDictMapper",
]

IFACE_RE = re.compile(r"public interface (\w+) extends BaseMapper<(\w+)>")
METHOD_RE = re.compile(
    r"(?P<doc>/\*\*.*?\*/\s*)?(?:public\s+)?(?P<ret>[\w<>\[\]\.]+)\s+(?P<name>\w+)\s*\((?P<params>.*?)\)\s*;",
    re.S,
)

TYPE_MAP = {"String": "str", "Long": "int", "Integer": "int", "int": "int",
            "Double": "float", "BigDecimal": "float", "Date": "datetime"}


def clean_doc(block):
    lines = []
    for raw in block.replace("/**", "").replace("*/", "").splitlines():
        line = raw.strip().lstrip("*").strip()
        if not line or line.startswith("@author") or line.startswith("@date"):
            continue
        lines.append(line)
    return lines


def py_type(java_type, entity):
    java_type = java_type.strip()
    if java_type.startswith("List<"):
        return "list[" + py_type(java_type[5:-1], entity) + "]"
    if java_type in TYPE_MAP:
        return TYPE_MAP[java_type]
    if java_type == entity:
        return entity
    return "Any"


def emit(name):
    text = (JAVA_DIR / f"{name}.java").read_text(encoding="utf-8")
    iface, entity = IFACE_RE.search(text).groups()
    head, tail = text.split(f"extends BaseMapper<{entity}>", 1)
    class_doc = clean_doc(re.findall(r"/\*\*.*?\*/", head, re.S)[-1])
    # 只在 interface 体内解析方法，避免类注释被当成方法注释
    interface_body = tail.split("{", 1)[1]
    body = []
    for m in METHOD_RE.finditer(interface_body):
        params = m.group("params").strip()
        if not params:
            continue
        parts = [p.strip() for p in params.split(",")]
        ptype, pname = parts[0].split()[0], parts[0].split()[-1]
        rtype = py_type(m.group("ret"), entity)
        if m.group("ret").startswith("List<"):
            rtype = "list[" + entity + "]"
        else:
            rtype = f"Optional[{entity}]" if m.group("ret") == entity else rtype
        sig = []
        for p in parts:
            t, n = p.split()[0], p.split()[-1]
            sig.append(f"{n}: {py_type(t, entity)}")
        doc = clean_doc(m.group("doc") or "")
        brief = next((d for d in doc if not d.startswith("@")), m.group("name"))
        rest = [d for d in doc if d != brief]
        anchor = "self.selectById(" + pname + ")" if m.group("name").endswith("ById") else "self.selectList(" + pname + ")"
        lines = [
            f"    def {m.group('name')}({', '.join(['self'] + sig)}) -> {rtype}:",
            f'        """{brief}',
        ]
        if rest:
            lines.append("")
            lines.extend("        " + r for r in rest)
        lines += [
            "",
            "        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；",
            "        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。",
            '        """',
            f"        return {anchor}",
        ]
        body.append("\n".join(lines))
    joined = "\n\n".join(body)
    return f'''# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.{iface}

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/{iface}.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.{entity} import {entity}

__all__ = ["{iface}"]


class {iface}(BaseMapper[{entity}]):
    """{class_doc[0]}

    【Java→Python】
    1) `public interface {iface} extends BaseMapper<{entity}>` → 继承 BaseMapper[{entity}]；
       Java 侧实现类由 MyBatis-Plus 动态代理生成，Python 侧直接实例化。
    2) `@Repository` → Spring 容器装配；Python 侧由 SpringUtils 注册（见 config 层），
       本类保留注解语义，无运行期副作用。
    3) `List<T>` → `list[T]`；`String` → `str`；`Long` → `int`。
    4) Mapper XML 与接口同名方法一一对应，方法名保持 Java 原样作为 statement id。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__({entity})

{joined}
'''


OUT_DIR.mkdir(parents=True, exist_ok=True)
for mapper in SIMPLE:
    (OUT_DIR / f"{mapper}.py").write_text(emit(mapper), encoding="utf-8")
    print("generated", mapper)
