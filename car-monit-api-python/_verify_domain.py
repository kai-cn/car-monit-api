# -*- coding: utf-8 -*-
"""校验 domain 生成结果：字段数量与 Java 源一致、可正常导入、JavaBean 访问器可用。"""
import dataclasses
import importlib
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
JAVA_DIR = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/domain"
sys.path.insert(0, str(BASE / "pro-base-common/src/main/java"))
sys.path.insert(0, str(BASE / "pro-business-api/src/main/java"))

from com.ruoyi.common.core.domain.JavaBean import camel_to_snake  # noqa: E402

FIELD_RE = re.compile(r"^\s*(?:private|public|protected)\s+(?:static\s+final\s+)?[\w<>\[\], .?$]+?\s+(\w+)\s*(?:=.*)?;")

total_java = total_py = 0
ok = True
for java in sorted(JAVA_DIR.glob("*.java")):
    names = [m.group(1) for line in java.read_text(encoding="utf-8").splitlines()
             if (m := FIELD_RE.match(line))]
    names = [n for n in names if n != "serialVersionUID"]
    module = importlib.import_module(f"com.ruoyi.base.domain.{java.stem}")
    clazz = getattr(module, java.stem)
    py_fields = [f.name for f in dataclasses.fields(clazz)]
    expected = [camel_to_snake(n) for n in names]
    total_java += len(expected)
    total_py += len(py_fields)
    if expected != py_fields:
        ok = False
        print(f"DIFF {java.stem}: java={len(expected)} py={len(py_fields)}")
        print("   only java:", [n for n in expected if n not in py_fields])
        print("   only py  :", [n for n in py_fields if n not in expected])

from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.CarParaVO import CarParaVO

entity = OdsSzdnTollStationIp()
entity.setId(7).setTollCode("G001").setTollName("某某收费站")
print("chain:", entity.getId(), entity.getTollCode(), entity.getTollName())
print("toString:", entity.toString()[:70], "...")

fee = OdsLwzxsfsjFeeRecords01()
print("fee fields:", len(dataclasses.fields(fee)), [f.name for f in dataclasses.fields(fee)][:6])
print("fee chain:", fee.setFee(12.5).setVehicleplate("赣A1").getFee(), fee.getVehicleplate())

car = CarParaVO()
print("car types:", [(f.name, f.type) for f in dataclasses.fields(car)][:4])
print(f"total java fields={total_java} py fields={total_py}", "ALL OK" if ok else "HAS DIFF")
