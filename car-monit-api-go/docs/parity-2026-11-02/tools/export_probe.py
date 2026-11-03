# -*- coding: utf-8 -*-
"""导出类接口实测（会写文件，不碰 /large/sync/*，避免覆盖 Java 写入的 ES 文档）。

流程：submit → 轮询 status 直到终态 → 比对状态机字段；
文件本身两端目录与命名不同（Java /data/export、Go ./data/export/<taskID>/），
所以只比「行数与表头」，不比字节。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

JAVA, GO = "http://127.0.0.1:9902", "http://127.0.0.1:9903"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")

# 用一个必然没有数据的时间窗，避免真的导出百万行
T1 = "2020-01-01 00:00:00"
T2 = "2020-01-01 00:01:00"


def call(base, method, path, params=None, body=None):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, type(e).__name__ + ": " + str(e)


def poll(base, path_tpl, task_id, limit=24):
    """轮询到终态或超时，返回最后一次状态与观测到的状态序列。"""
    seen = []
    last = None
    for _ in range(limit):
        st, txt = call(base, "GET", path_tpl.format(task_id))
        try:
            o = json.loads(txt)
        except Exception:
            o = {"_raw": txt[:200]}
        seen.append((st, o.get("status") or o.get("state") or o.get("code")))
        last = o
        if str(o.get("status", "")).upper() in ("COMPLETED", "SUCCESS", "FAILED", "DONE", "ERROR"):
            break
        if o.get("finished") is True:
            break
        time.sleep(2.5)
    return last, seen


def run_one(name, submit_path, submit_params, status_tpl, body=None):
    rec = {"case": name, "submit": submit_path}
    for label, base in (("java", JAVA), ("go", GO)):
        st, txt = call(base, "POST", submit_path, submit_params, body)
        try:
            o = json.loads(txt)
        except Exception:
            o = {"_raw": txt[:300]}
        tid = o.get("taskId") or o.get("data") or o.get("id") or ""
        rec[label] = {"submit_status": st, "submit_body": o, "taskId": tid}
        if tid:
            last, seen = poll(base, status_tpl, tid)
            rec[label]["final"] = last
            rec[label]["states"] = [s for _, s in seen]
    return rec


def main():
    os.makedirs(RAW, exist_ok=True)
    cases = [
        {"case": "large-export",
         "submit": "/api/v1/large/export/submit",
         "params": {"type": "snapshot", "startTime": T1, "endTime": T2},
         "status": "/api/v1/large/export/status/{}", "body": None},
        {"case": "unified-snapshot-export",
         "submit": "/api/v1/unified/snapshot/export/submit",
         "params": {"startTime": T1, "endTime": T2},
         "status": "/api/v1/unified/export/status/{}", "body": None},
        {"case": "unified-fee-export",
         "submit": "/api/v1/unified/fee/export/submit",
         "params": {"startTime": T1, "endTime": T2},
         "status": "/api/v1/unified/export/status/{}",
         "body": {"platenumber": "赣A12345"}},
    ]
    out = []
    for c in cases:
        r = run_one(c["case"], c["submit"], c["params"], c["status"], c["body"])
        out.append(r)
        j, g = r.get("java", {}), r.get("go", {})
        print(f"\n### {c['case']}")
        print(f"  Java submit={j.get('submit_status')} taskId={str(j.get('taskId'))[:24]} "
              f"states={j.get('states')}")
        print(f"  Go   submit={g.get('submit_status')} taskId={str(g.get('taskId'))[:24]} "
              f"states={g.get('states')}")
        print(f"  Java final keys={sorted((j.get('final') or {}).keys())}")
        print(f"  Go   final keys={sorted((g.get('final') or {}).keys())}")
        print(f"  Java final={json.dumps(j.get('final'), ensure_ascii=False)[:260]}")
        print(f"  Go   final={json.dumps(g.get('final'), ensure_ascii=False)[:260]}")
    with open(os.path.join(RAW, "export-probe.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n→ raw/export-probe.json")


if __name__ == "__main__":
    main()
