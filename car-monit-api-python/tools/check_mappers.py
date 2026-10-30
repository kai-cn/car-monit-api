# -*- coding: utf-8 -*-
"""Print the mapper installation report (no database connection is opened).

Usage::

    .venv\\Scripts\\python.exe tools\\check_mappers.py

The report lists every mapper XML that was parsed, every statement bound to a
mapper method, and -- most important for the migration -- every mapper method
that has **no** XML statement and therefore keeps the in-memory implementation
written by the port.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.registry import get_registry  # noqa: E402


def main() -> int:
    registry = get_registry().load()
    print(f"mapper XML files : {len(registry.mapper_xmls)}")
    print(f"statements       : {len(registry.statements)}")
    print(f"sql fragments    : {len(registry.fragments) // 2}")
    print()

    for namespace in sorted(registry.mapper_xmls):
        mapper_xml = registry.mapper_xmls[namespace]
        print(f"{namespace.rsplit('.', 1)[-1]}  ({mapper_xml.resource})")
        for statement_id in sorted(mapper_xml.statements):
            statement = mapper_xml.statements[statement_id]
            print(f"    {statement.kind:<6} {statement_id}")
    print()

    report = get_registry().install()
    print(f"bound methods    : {report.patched_methods}")
    if report.missing_statements:
        print(f"without XML      : {len(report.missing_statements)}")
        for item in report.missing_statements:
            print(f"    {item}")
    if report.orphan_statements:
        print(f"orphan statements: {len(report.orphan_statements)}")
        for item in report.orphan_statements:
            print(f"    {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
