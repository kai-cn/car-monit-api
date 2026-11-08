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
    exit_code = 1 if registry.failed_files else 0
    if registry.failed_files:
        print(f"XML parse failures: {len(registry.failed_files)}")
        for item in registry.failed_files:
            print(f"    {item}")

    for namespace in sorted(registry.mapper_xmls):
        mapper_xml = registry.mapper_xmls[namespace]
        print(f"{namespace.rsplit('.', 1)[-1]}  ({mapper_xml.resource})")
        for statement_id in sorted(mapper_xml.statements):
            statement = mapper_xml.statements[statement_id]
            print(f"    {statement.kind:<6} {statement_id}")
    print()

    report = get_registry().install()
    print(f"bound methods    : {report.patched_methods}")
    if report.failed_files:
        print(f"install failures : {len(report.failed_files)}")
        for item in report.failed_files:
            print(f"    {item}")
        exit_code = 1
    if report.missing_statements:
        from app.db.registry import KNOWN_MISSING_STATEMENTS

        unexpected = [item for item in report.missing_statements
                      if item not in KNOWN_MISSING_STATEMENTS]
        print(f"without XML      : {len(report.missing_statements)} "
              f"(whitelisted: {len(report.missing_statements) - len(unexpected)})")
        for item in report.missing_statements:
            marker = "" if item in KNOWN_MISSING_STATEMENTS else "  <-- NOT WHITELISTED"
            print(f"    {item}{marker}")
        if unexpected:
            print(f"unexpected missing statements: {len(unexpected)} -> exit 1")
            exit_code = 1
    if report.orphan_statements:
        print(f"orphan statements: {len(report.orphan_statements)}")
        for item in report.orphan_statements:
            print(f"    {item}")

    # P0-1：随包 XML（pro-business-api/src/main/resources）必须与 Java 源逐字节
    # 一致，防止两树漂移；漂移/缺失时本工具 exit 1（CI 门禁）。
    import subprocess

    sync_script = Path(__file__).resolve().parent / "sync_mapper_xml.py"
    result = subprocess.run([sys.executable, str(sync_script), "--check"],
                            capture_output=True, text=True, encoding="utf-8")
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
