# -*- coding: utf-8 -*-
"""Live GaussDB smoke test for the mapper layer.

Usage::

    .venv\\Scripts\\python.exe tools\\verify_db.py

It runs a handful of real statements through the patched mappers -- the same
code path the HTTP endpoints use -- and prints what came back. Nothing is
written to the database.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import get_database  # noqa: E402
from app.db.registry import install_mappers  # noqa: E402
from com.ruoyi.common.utils.PageUtils import PageContext, PageUtils  # noqa: E402


def _section(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def main() -> int:
    database = get_database()
    print("jdbc url :", database.url.split("@")[-1])

    _section("connection")
    print("ping     :", database.ping())

    _section("mapper registry")
    report = install_mappers(database)
    print(report.summary())
    for item in report.missing_statements:
        print("  no statement :", item)

    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
    from com.ruoyi.base.mapper.OdsSzdnGantryMapper import OdsSzdnGantryMapper

    mapper = OdsSzdnGantryMapper()

    _section("selectOdsSzdnGantryById (single result)")
    print("missing id ->", mapper.selectOdsSzdnGantryById("__not_a_real_id__"))
    row = database.query(
        "SELECT id FROM jl_data01.ods_szdn_gantry WHERE id IS NOT NULL LIMIT 1")
    if row:
        gantry_id = row[0]["id"]
        entity = mapper.selectOdsSzdnGantryById(gantry_id)
        print("existing id ->", gantry_id, "->", entity.gantry_code, entity.gantry_name,
              "lon:", entity.lon, type(entity.lon).__name__)

    _section("selectOdsSzdnGantryList + LIKE parameter (verifies % escaping)")
    rows = mapper.selectOdsSzdnGantryList(OdsSzdnGantry(gantry_name="0"))
    print(f"gantry_name like %0% -> {len(rows)} row(s)")
    if rows:
        print("  first    :", rows[0].gantry_code, rows[0].gantry_name)

    _section("PageHelper: count + LIMIT/OFFSET")
    # PageHelper.startPage(2, 3, "gantry_code").setReasonable(true)
    # (PageHelper injects orderBy verbatim -- it does not map camelCase to a column)
    PageUtils._local.context = PageContext(page_num=2, page_size=3,
                                           order_by="gantry_code", reasonable=True)
    page_rows = mapper.selectOdsSzdnGantryList(OdsSzdnGantry())
    print(f"page 2 / size 3 -> {len(page_rows)} row(s), total = {PageUtils.get_page_total()}")
    PageUtils.clearPage()

    _section("to_timestamp + <if> nesting (cursor shard statement)")
    from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
        OdsRtSzdnSnapshotFlowAddcodeMapper,
    )

    shard = OdsRtSzdnSnapshotFlowAddcodeMapper().selectByCursorShard(
        "2024-01-01 00:00:00", "2030-01-01 00:00:00", None, None, 2)
    print(f"selectByCursorShard -> {len(shard)} row(s)")

    _section("scalar statement from @Select")
    latest = OdsRtSzdnSnapshotFlowAddcodeMapper().getMaxSnapshotTime()
    print("getMaxSnapshotTime  ->", latest, type(latest).__name__ if latest else "")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
