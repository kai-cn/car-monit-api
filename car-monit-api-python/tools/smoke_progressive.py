# -*- coding: utf-8 -*-
"""Live smoke test for ProgressiveQueryArchitectureService.

Usage::

    .venv\\Scripts\\python.exe tools\\smoke_progressive.py

It exercises the parts that do **not** need a database first (enum helpers,
``QueryRequest.toString()``, ``QueryResult`` factories, ``judgeScaleLevel``), then
the three ``query*`` entry points.  Those hit the mapper layer, so a GaussDB outage
is reported instead of raised -- same spirit as ``tools/verify_db.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bootstrap  # noqa: E402,F401  (registers the Java-mirrored import roots)

from com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService import (  # noqa: E402
    DataScaleLevel,
    ProgressiveQueryArchitectureService,
    QueryRequest,
    QueryResult,
)


def _section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 60 - len(title)))


def main() -> int:
    _section("enum: name() / valueOf() / values() / __str__")
    print("valueOf('LEVEL_1B').name() ->", DataScaleLevel.valueOf("LEVEL_1B").name())
    print("values()                  ->", [level.name() for level in DataScaleLevel.values()])
    print("str(LEVEL_100M)           ->", str(DataScaleLevel.LEVEL_100M))
    try:
        DataScaleLevel.valueOf("LEVEL_9Z")
    except ValueError as error:
        print("valueOf('LEVEL_9Z')       -> ValueError:", error)

    _section("QueryRequest: JavaBean accessors + custom toString()")
    request = QueryRequest()
    print("default pageSize          ->", request.getPageSize())
    request.setStartTime("2024-01-01 00:00:00").setEndTime("2024-01-31 23:59:59")
    request.setPlatenumber("赣A12345").setGantryname("G01").setPageSize(200)
    print("toString()                ->", request.toString())

    _section("QueryResult factories")
    print("of([], 0, 'x')            ->", QueryResult.of([], 0, "x").getStrategy())
    placeholder = QueryResult.esPlaceholder("phase3-elasticsearch")
    print("esPlaceholder             -> data=%r total=%d strategy=%s"
          % (placeholder.getData(), placeholder.getTotal(), placeholder.getStrategy()))

    _section("judgeScaleLevel boundaries (50M / 500M)")
    service = ProgressiveQueryArchitectureService()
    for count in (0, 49_999_999, 50_000_000, 499_999_999, 500_000_000):
        print("  %12d -> %s" % (count, service.judgeScaleLevel(count)))

    _section("detectScaleLevel (Redis miss -> configured @Value)")
    print("configured optimization.scale-level ->", service.configuredScaleLevel)
    print("detectScaleLevel('zdata_trail_fitting') ->",
          service.detectScaleLevel("zdata_trail_fitting").name())

    _section("nested class access paths (Java: Service.QueryRequest)")
    print("Service.QueryRequest is QueryRequest ->",
          ProgressiveQueryArchitectureService.QueryRequest is QueryRequest)
    print("Service.DataScaleLevel is DataScaleLevel ->",
          ProgressiveQueryArchitectureService.DataScaleLevel is DataScaleLevel)
    print("Service.QueryResult is QueryResult ->",
          ProgressiveQueryArchitectureService.QueryResult is QueryResult)

    _section("query* entry points (need GaussDB)")
    for label, call in (
        ("querySnapshotFlow", service.querySnapshotFlow),
        ("queryFeeRecords", service.queryFeeRecords),
        ("queryTrailFitting", service.queryTrailFitting),
    ):
        try:
            result = call(request)
            print("  %-22s -> total=%d strategy=%s"
                  % (label, result.getTotal(), result.getStrategy()))
        except Exception as error:  # noqa: BLE001 - DB may be unreachable
            print("  %-22s -> %s: %s" % (label, type(error).__name__, error))

    _section("phase3 ES branch (needs the optional ES dependency)")
    # With no ElasticsearchQueryService the Java code falls back to phase 2;
    # inject one so the hasFuzzy / pageSize > 100 branch is really taken.
    from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
        ElasticsearchQueryService,
    )

    es_service = ProgressiveQueryArchitectureService(
        elasticsearchQueryService=ElasticsearchQueryService())
    fuzzy = es_service.querySnapshotFlowPhase3(request)  # platenumber set -> ES
    print("snapshot Flow phase3 (fuzzy)   -> total=%d strategy=%s"
          % (fuzzy.getTotal(), fuzzy.getStrategy()))

    plain = QueryRequest()
    plain.setStartTime("2024-01-01 00:00:00").setEndTime("2024-01-31 23:59:59")
    try:
        exact = es_service.querySnapshotFlowPhase3(plain)  # no fuzzy, size 20 -> phase 2
        print("snapshot Flow phase3 (exact)   -> total=%d strategy=%s"
              % (exact.getTotal(), exact.getStrategy()))
    except Exception as error:  # noqa: BLE001 - DB may be unreachable
        print("snapshot Flow phase3 (exact)   -> %s: %s"
              % (type(error).__name__, error))

    print("trailFitting phase3            ->",
          es_service.queryTrailFittingPhase3(plain).getStrategy())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
