# -*- coding: utf-8 -*-
"""审阅用临时探针（不改业务代码）：收集路由/映射器安装报告供报告引用。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import bootstrap  # noqa: F401,E402  (import 时即把镜像根加入 sys.path)

from fastapi import FastAPI  # noqa: E402

from app.routes.registry import register_all  # noqa: E402
from app.db.registry import MapperRegistry  # noqa: E402
from app.routes.generated import ROUTES  # noqa: E402

app = FastAPI()
register_all(app)
report = app.state.route_report
print("=== RouteInstallReport ===")
print("controllers:", report.controllers, "routes:", report.routes)
print("unavailable:", report.unavailable)
print("skipped:", report.skipped)
print("missing_methods:", report.missing_methods)
print("signature_mismatches:", report.signature_mismatches)
print("base_path_mismatches:", report.base_path_mismatches)
print("duplicates:", report.duplicates)
print("ROUTES table size:", len(ROUTES))

print("\n=== MapperRegistry classpath roots ===")
registry = MapperRegistry()
roots = list(registry._classpath_roots())
for root in roots:
    count = len(list(root.glob("com/ruoyi/base/**/xml/*Mapper.xml"))) if root.is_dir() else 0
    print(f"{root} | is_dir={root.is_dir()} | xml={count}")

registry.load()
print("loaded xml namespaces:", len(registry.mapper_xmls))
print("loaded statements:", len(registry.statements))
install = registry.install()
print("\n=== InstallReport ===")
print("mappers:", install.mappers, "statements:", install.statements,
      "patched:", install.patched_methods)
print("missing_statements:", install.missing_statements)
print("failed_files:", install.failed_files)
print("orphan_statements:", install.orphan_statements)
print("annotated_statements:", install.annotated_statements)

# 若 XML 不可见（独立部署场景），mapper 数量会掉到多少
print("\n=== standalone simulation (root 指向空目录) ===")
empty = Path(ROOT / "tools" / "_empty_root")
empty.mkdir(exist_ok=True)
sim = MapperRegistry(root=empty)
sim.load()
print("xml:", len(sim.mapper_xmls), "statements:", len(sim.statements))
