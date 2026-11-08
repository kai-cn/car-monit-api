# -*- coding: utf-8 -*-
"""审阅用临时探针：数值/日期序列化与已知缺失 statement 的真实表现。"""
from __future__ import annotations

import json

import httpx

BASE = "http://127.0.0.1:9902"


with httpx.Client(base_url=BASE, timeout=60) as client:
    r = client.get("/base/feerecords/list", params={"pageNum": 1, "pageSize": 1})
    print("=== /base/feerecords/list ===")
    print("status:", r.status_code)
    body = r.json()
    print("total:", body.get("total"), "rows:", len(body.get("rows") or []))
    if body.get("rows"):
        first = body["rows"][0]
        keys = ["bigId", "fee", "payfee", "transfee", "balanceafter", "totalweight",
                "vehiclelength", "vehiclewidth", "vehiclehight", "transtime", "exittime"]
        print(json.dumps({k: first.get(k) for k in keys}, ensure_ascii=False, indent=2))
        print("fee raw text:", json.dumps(httpx.get(BASE + "/base/feerecords/list", params={"pageNum": 1, "pageSize": 1}).text[:1600], ensure_ascii=False)[:1600])

    print("\n=== /base/feerecords/{bigId} (no XML statement) ===")
    r2 = client.get("/base/feerecords/1")
    print("status:", r2.status_code)
    print("body:", r2.text[:220])

    print("\n=== /base/feerecords/listToExport ===")
    r3 = client.get("/base/feerecords/listToExport", params={"pageNum": 1, "pageSize": 1})
    print("status:", r3.status_code, "body:", r3.text[:300])
