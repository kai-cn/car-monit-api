# -*- coding: utf-8 -*-
"""Route table check (no server, no database).

Prints what ``tools/gen_routes.py`` produced, which controller modules import
cleanly, and what ``ControllerRegistry.install`` would register.  Useful right
after adding a controller::

    .venv\\Scripts\\python.exe tools\\check_routes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402

from app.db.proxy import import_class  # noqa: E402
from app.routes.generated import CONTROLLERS, ROUTES  # noqa: E402
from app.routes.registry import register_all  # noqa: E402
from app.web.responses import JacksonResponse  # noqa: E402


def _section(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def main() -> int:
    _section("generated table")
    print(f"controllers : {len(CONTROLLERS)}")
    print(f"handlers    : {len(ROUTES)}")
    kinds: dict[str, int] = {}
    for route in ROUTES:
        for param in route["params"]:
            kinds[param["source"]] = kinds.get(param["source"], 0) + 1
    print("param kinds :", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    verbs: dict[str, int] = {}
    for route in ROUTES:
        verbs[route["http"]] = verbs.get(route["http"], 0) + 1
    print("verbs       :", ", ".join(f"{k}={v}" for k, v in sorted(verbs.items())))

    _section("controllers")
    for entry in CONTROLLERS:
        klass = import_class(entry["fqcn"])
        if klass is None:
            print(f"UNAVAILABLE  {entry['fqcn']}")
            continue
        print(f"ok           {entry['fqcn']}")

    _section("registration")
    app = FastAPI(default_response_class=JacksonResponse)
    routes = register_all(app)
    report = app.state.route_report
    print(report.summary())
    print(f"routes      : {routes}")
    for name, values in (
        ("unavailable", report.unavailable),
        ("skipped", report.skipped),
        ("missing method", report.missing_methods),
        ("duplicate", report.duplicates),
        ("signature", report.signature_mismatches),
        ("BASE_PATH", report.base_path_mismatches),
    ):
        for item in values:
            print(f"{name:<13}: {item}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
