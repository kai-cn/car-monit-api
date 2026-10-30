# -*- coding: utf-8 -*-
"""Live HTTP smoke test against a running server (no database needed).

Usage::

    .venv\\Scripts\\python.exe tools\\smoke_http.py [base_url]
"""
from __future__ import annotations

import sys

import httpx


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9902"
    with_db = "--db" in sys.argv
    with httpx.Client(base_url=base, timeout=30.0) as client:
        print("== unknown path -> Spring 404 body")
        response = client.get("/nope")
        print(" ", response.status_code, response.text)

        print("== @PathVariable Long conversion failure -> 400")
        response = client.get("/manager/fwqclls/abc")
        print(" ", response.status_code, response.text)

        print("== literal route wins over {dataSource}")
        response = client.get("/base/vehicleweight/map")
        print(" ", response.status_code, response.text[:160])

        print("== @RequestBody required, sent empty -> 400")
        response = client.post("/base/sysutil/changeTrailInfo")
        print(" ", response.status_code, response.text)

        print("== @RequestBody wrong content type -> 415")
        response = client.post("/base/sysutil/changeTrailInfo", content=b"a=1",
                               headers={"content-type": "application/x-www-form-urlencoded"})
        print(" ", response.status_code, response.text)

        print("== method not allowed on an existing path -> 405")
        response = client.post("/base/gantry/{id}".replace("{id}", "x"))
        print(" ", response.status_code, response.text)

        print("== openapi")
        schema = client.get("/openapi.json").json()
        print("  paths:", len(schema["paths"]))
        operation = schema["paths"]["/base/gantry/{id}"]["get"]
        print("  /base/gantry/{id} parameters:", operation.get("parameters"))

        print("== /health")
        response = client.get("/health")
        print(" ", response.status_code, response.text[:900])

        if with_db:
            print("== GET /base/gantry/list (needs GaussDB)")
            response = client.get("/base/gantry/list")
            print(" ", response.status_code, response.text[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
