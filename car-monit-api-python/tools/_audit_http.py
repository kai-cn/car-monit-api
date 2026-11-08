# -*- coding: utf-8 -*-
"""审阅用临时 HTTP 探针：验证真实响应契约（不改业务代码）。"""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:9902"


def show(label: str, response: httpx.Response, limit: int = 300) -> None:
    body = response.text
    print(f"\n=== {label} ===")
    print("status:", response.status_code)
    print("content-type:", response.headers.get("content-type"))
    print("body[:%d]:" % limit, body[:limit].replace("\n", "\\n"))


with httpx.Client(base_url=BASE, timeout=30) as client:
    show("GET /health", client.get("/health"), 240)
    show("GET /base/gantry/list?pageNum=2&pageSize=3", client.get("/base/gantry/list", params={"pageNum": 2, "pageSize": 3}), 400)
    r = client.get("/base/gantry/list", params={"pageNum": 2, "pageSize": 3})
    print("total:", r.json().get("total"), "rows:", len(r.json().get("rows", [])))
    print("first gantryName:", r.json()["rows"][0]["gantryName"] if r.json().get("rows") else None)
    show("GET /base/gantry/18", client.get("/base/gantry/18"), 400)
    show("GET /base/gantry/99999999", client.get("/base/gantry/99999999"), 400)
    show("GET /not-found", client.get("/not-found"), 200)
    show("GET /base/gantry/list?pageNum=abc", client.get("/base/gantry/list", params={"pageNum": "abc"}), 250)
    show("POST /base/gantry (no body / wrong media)", client.post("/base/gantry", content=b"x=1", headers={"content-type": "application/x-www-form-urlencoded"}), 200)
    show("GET /error", client.get("/error"), 200)
    show("GET /docs", client.get("/docs"), 60)
    show("GET /openapi.json", client.get("/openapi.json"), 60)
