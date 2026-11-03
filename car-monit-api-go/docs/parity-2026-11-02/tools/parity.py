# -*- coding: utf-8 -*-
"""Java(:9902) ↔ Go(:9903) 全接口差分工具。

设计要点
  * 用例参数尽量由 Java 的真实响应自我派生（取第一行的若干字段当过滤条件），
    这样过滤谓词是用有数据的值在测，而不是凭空编一个查不到东西的条件。
  * 比对先按主键对齐列表，再逐字段比，报出来的是「哪个字段不一致」。
  * 出现差异自动重试 3 次：两端共用一个库，调度任务在写数据，
    「两次结果不同」和「两端结果不同」必须区分开，后者才是要记录的缺陷。
  * 原始响应全部落 raw/，文档里的每个结论都能回溯到具体报文。

用法
    python parity.py --list                       # 列出用例
    python parity.py --only gantry                # 按组跑
    python parity.py --case CR-Gantry-list        # 跑单条
    python parity.py                              # 全量
    python parity.py --md out.md                  # 额外写 markdown 汇总
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

JAVA = "http://127.0.0.1:9902"
GO = "http://127.0.0.1:9903"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.normpath(os.path.join(HERE, "..", "raw"))
TIMEOUT = 60

PK_CANDIDATES = ("id", "bigId", "uuid", "agentPk", "gantryCode", "sectionCode",
                 "tollCode", "orgCode", "dataSource", "plateNo", "carNo")

# 每次请求都会变的字段，不参与等价判定
VOLATILE_NAMES = {
    "elapsed", "cost", "costms", "duration", "durationms", "timestamp",
    "servertime", "tracetime", "traceid", "requestid", "reqid", "now",
    "taskid", "filepath", "file", "url", "downloadurl", "progress",
    "executetime", "updatetime", "createtime", "createtimeend",
}


def _norm_key(k: str) -> str:
    return str(k).lower().replace("_", "")


def is_volatile(path: str, ignore=None) -> bool:
    leaf = _norm_key(path.rsplit(".", 1)[-1])
    if leaf in VOLATILE_NAMES:
        return True
    # 用例级豁免：某些表的服务端会在每次响应里重新生成 id（Java StringUtils.getUUID()），
    # 拿它当比对目标永远是"差异"，必须由用例显式声明忽略。
    return bool(ignore) and leaf in ignore


def http_call(base, method, path, params=None, body=None):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    data = None
    hdr = {"Accept": "application/json"}
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) \
            else json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return {"status": r.status, "ms": int((time.time() - t0) * 1000),
                    "raw": raw, "err": None}
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        return {"status": e.code, "ms": int((time.time() - t0) * 1000),
                "raw": raw, "err": None}
    except Exception as e:  # 连接失败、超时
        return {"status": 0, "ms": int((time.time() - t0) * 1000),
                "raw": b"", "err": type(e).__name__ + ": " + str(e)}


def parse(resp):
    if resp["err"] is not None:
        return None, "ERR " + resp["err"]
    txt = resp["raw"].decode("utf-8", "replace")
    if not txt.strip():
        return None, "<empty body>"
    try:
        return json.loads(txt), None
    except Exception:
        return None, "<not json> " + txt[:200]


def pick_pk(rows):
    if not rows or not isinstance(rows[0], dict):
        return None
    for k in PK_CANDIDATES:
        if k in rows[0]:
            return k
    return None


def rows_of(obj):
    """把响应里的行集合抽出来（TableDataInfo.rows / 裸数组 / data.rows / data）。"""
    if isinstance(obj, dict):
        if isinstance(obj.get("rows"), list):
            return obj["rows"], "rows"
        if isinstance(obj.get("data"), dict) and isinstance(obj["data"].get("rows"), list):
            return obj["data"]["rows"], "data.rows"
        if isinstance(obj.get("data"), list):
            return obj["data"], "data"
        if isinstance(obj.get("content"), list):  # ES 风格
            return obj["content"], "content"
        return None, None
    if isinstance(obj, list):
        return obj, "<root>"
    return None, None


def diff_scalar(path, jv, gv, out, scalar_ok):
    if jv == gv:
        return
    if scalar_ok and jv is None and gv in ("", [], {}):
        out.append((path, "NULLISH", jv, gv)); return
    if scalar_ok and gv is None and jv in ("", [], {}):
        out.append((path, "NULLISH", jv, gv)); return
    sj, sg = json.dumps(jv, ensure_ascii=False), json.dumps(gv, ensure_ascii=False)
    if str(jv) == str(gv):
        out.append((path, "TYPE", sj, sg)); return
    try:
        if abs(float(jv) - float(gv)) < 1e-9:   # 数值精度（BigDecimal scale）
            out.append((path, "NUMFMT", sj, sg)); return
    except Exception:
        pass
    out.append((path, "VALUE", sj, sg))


def diff_obj(path, jv, gv, out, scalar_ok, pk_override=None, ignore=None):
    if is_volatile(path, ignore):
        return
    if isinstance(jv, dict) and isinstance(gv, dict):
        for k in sorted(set(jv) | set(gv)):
            p = f"{path}.{k}" if path else k
            if is_volatile(p, ignore):
                continue
            jn, gn = k in jv, k in gv
            if jn != gn:
                out.append((p, "KEY_ABSENT", json.dumps(jv.get(k), ensure_ascii=False)[:120],
                            json.dumps(gv.get(k), ensure_ascii=False)[:120]))
                continue
            diff_obj(p, jv[k], gv[k], out, scalar_ok, pk_override, ignore)
        return
    if isinstance(jv, list) and isinstance(gv, list):
        if len(jv) != len(gv):
            out.append((path + ".<len>", "LEN", str(len(jv)), str(len(gv))))
        pk = pk_override or (pick_pk(jv) if jv else pick_pk(gv))
        if pk == "-":
            # 这张表没有可用主键（例如 vehicleweight 的 uuid 列全是 null），
            # 退化成「整行序列化后按多重集比较」：顺序无关，报的是"哪些行只在某一边出现"。
            def ser(r):
                if not isinstance(r, dict):
                    return json.dumps(r, ensure_ascii=False, sort_keys=True)
                return json.dumps({k: v for k, v in r.items()
                                   if not (ignore and _norm_key(k) in ignore)},
                                  ensure_ascii=False, sort_keys=True)
            js, gs = sorted(ser(r) for r in jv), sorted(ser(r) for r in gv)
            from collections import Counter
            jc, gc = Counter(js), Counter(gs)
            for row in sorted(set(js) | set(gs)):
                if jc[row] != gc[row]:
                    out.append((f"{path}[row]", "ROW_SET",
                                (f"x{jc[row]} " + row[:90]) if jc[row] else "-",
                                (f"x{gc[row]} " + row[:90]) if gc[row] else "-"))
            return
        if pk:
            jm = {json.dumps(r.get(pk), ensure_ascii=False): r for r in jv if isinstance(r, dict)}
            gm = {json.dumps(r.get(pk), ensure_ascii=False): r for r in gv if isinstance(r, dict)}
            for key in sorted(set(jm) | set(gm)):
                if key not in gm:
                    out.append((f"{path}[{pk}={key}]", "ONLY_JAVA", "row", "-")); continue
                if key not in jm:
                    out.append((f"{path}[{pk}={key}]", "ONLY_GO", "-", "row")); continue
                diff_obj(f"{path}[{pk}={key}]", jm[key], gm[key], out, scalar_ok, None, ignore)
        else:
            for i in range(max(len(jv), len(gv))):
                if i >= len(jv):
                    out.append((f"{path}[{i}]", "ONLY_GO", "-", json.dumps(gv[i], ensure_ascii=False)[:120])); continue
                if i >= len(gv):
                    out.append((f"{path}[{i}]", "ONLY_JAVA", json.dumps(jv[i], ensure_ascii=False)[:120], "-")); continue
                diff_obj(f"{path}[{i}]", jv[i], gv[i], out, scalar_ok, None, ignore)
        return
    if type(jv) is not type(gv) and (isinstance(jv, (dict, list)) or isinstance(gv, (dict, list))):
        out.append((path, "SHAPE", json.dumps(jv, ensure_ascii=False)[:120],
                    json.dumps(gv, ensure_ascii=False)[:120]))
        return
    diff_scalar(path, jv, gv, out, scalar_ok)


def compare(jobj, gobj, pk=None, ignore=None):
    out = []
    ig = {_norm_key(x) for x in ignore} if ignore else None
    diff_obj("", jobj, gobj, out, scalar_ok=True, pk_override=pk, ignore=ig)
    return out


def dump(case_id, side, resp, parsed):
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, f"{case_id}.{side}.http"), "w", encoding="utf-8") as f:
        f.write(f"HTTP {resp['status']}  {resp['ms']}ms  err={resp['err']}\n")
        f.write((parsed is not None and json.dumps(parsed, ensure_ascii=False, indent=1)
                 or resp["raw"].decode("utf-8", "replace")))


class Runner:
    def __init__(self, only=None):
        self.only = only
        self.results = []

    def run_case(self, case):
        cid, group = case["id"], case.get("group", "")
        if self.only and self.only.lower() not in (group.lower() + " " + cid.lower()):
            return None
        method, path = case["method"], case["path"]
        params, body = case.get("params"), case.get("body")
        best = None
        for attempt in range(3):
            rj = http_call(JAVA, method, path, params, body)
            rg = http_call(GO, method, path, params, body)
            pj, ej = parse(rj)
            pg, eg = parse(rg)
            if rj["status"] != rg["status"]:
                verdict, detail = "STATUS", f"java={rj['status']} go={rg['status']}"
            elif ej or eg:
                if ej and eg and ej == eg:
                    verdict, detail = "OK", "both non-json same"
                else:
                    verdict, detail = "SHAPE", f"java={ej or 'json'} go={eg or 'json'}"
            else:
                d = compare(pj, pg)
                if d:
                    verdict, detail = "DIFF", d
                else:
                    verdict, detail = "OK", ""
            req = method + " " + path
            if params:
                req += "?" + urllib.parse.urlencode(params)
            rec = {"id": cid, "group": group, "case": case.get("note", ""),
                   "req": req,
                   "jstatus": rj["status"], "gstatus": rg["status"],
                   "jms": rj["ms"], "gms": rg["ms"], "verdict": verdict,
                   "detail": detail, "attempt": attempt + 1}
            if best is None or (best["verdict"] == "DIFF" and verdict != "DIFF"):
                best = rec
            if verdict == "OK":
                break
        dump(cid, "java", rj, pj)
        dump(cid, "go", rg, pg)
        self.results.append(best)
        return best


def q(**kw):
    return {k: v for k, v in kw.items() if v is not None}


def cap_rows(obj, cap):
    """大列表只比前 cap 行，但先记录全长，避免把「长度差」漏成「内容差」。"""
    if not cap:
        return obj, None
    rows, where = rows_of(obj)
    if rows is None or len(rows) <= cap:
        return obj, (len(rows) if rows is not None else None)
    kept = rows[:cap]
    if isinstance(obj, dict) and where in obj:
        o2 = dict(obj)
        o2[where] = kept
        return o2, len(rows)
    if isinstance(obj, list):
        return kept, len(rows)
    return obj, len(rows)


# ─────────────────────────────── 运行器 ───────────────────────────────

def run(cases, only=None, allow_write=False, out_prefix="results"):
    results = []
    sel = [c for c in cases if (not only or only.lower() in
            (c.get("group", "") + " " + c["id"]).lower())]
    if not allow_write:
        sel = [c for c in sel if not c.get("write")]
    print(f"待跑 {len(sel)} 条用例（Java {JAVA} ↔ Go {GO}）")
    for i, case in enumerate(sel, 1):
        rec = _run_one(case)
        results.append(rec)
        v = rec["verdict"]
        mark = {"OK": ".", "DIFF": "D", "STATUS": "S", "SHAPE": "X"}.get(v, "?")
        if v != "OK" or i % 25 == 0:
            print(f"[{i:3d}/{len(sel)}] {mark} {rec['id']:38s} {v:7s} "
                  f"{str(rec['detail'])[:110]}")
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, out_prefix + ".jsonl"), "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    stat = {}
    for r in results:
        stat[r["verdict"]] = stat.get(r["verdict"], 0) + 1
    print("\n=== 汇总 ===")
    for k in ("OK", "DIFF", "STATUS", "SHAPE", "ERR"):
        if k in stat:
            print(f"  {k:7s} {stat[k]}")
    return results


def _run_one(case):
    cid, group = case["id"], case.get("group", "")
    method, path = case["method"], case["path"]
    params, body, cap = case.get("params"), case.get("body"), case.get("cap", 50)
    req = method + " " + path + ("?" + urllib.parse.urlencode(params) if params else "")
    best = None
    pk, ignore = case.get("pk"), case.get("ignore")
    for attempt in range(3):
        rj = http_call(JAVA, method, path, params, body)
        rg = http_call(GO, method, path, params, body)
        pj, ej = parse(rj)
        pg, eg = parse(rg)
        jlens = glens = None
        nondet = None
        if case.get("expect") == "status-only":
            verdict, detail = ("OK", "") if rj["status"] == rg["status"] else \
                ("STATUS", f"java={rj['status']} go={rg['status']}")
        elif rj["status"] != rg["status"]:
            verdict, detail = "STATUS", f"java={rj['status']} go={rg['status']}"
        elif ej or eg:
            verdict, detail = ("OK", "both unparsable") if ej == eg else \
                ("SHAPE", f"java={ej or 'json'} go={eg or 'json'}")
        else:
            jc, jlens = cap_rows(pj, cap)
            gc, glens = cap_rows(pg, cap)
            d = compare(jc, gc, pk, ignore)
            if jlens is not None and glens is not None and jlens != glens:
                d = [("root.<rows_len>", "LEN", str(jlens), str(glens))] + d
            if d:
                # 基准端自身是否可复现？多数 mapper XML 没有 ORDER BY，
                # 同一请求两次可能返回不同的行集合。先证明 Java 自己稳定，
                # 才能把差异归因到 Go。
                rj2 = http_call(JAVA, method, path, params, body)
                pj2, _ = parse(rj2)
                jc2, _ = cap_rows(pj2, cap)
                selfdiff = compare(jc, jc2, pk, ignore)
                if selfdiff:
                    verdict, nondet = "NONDET", len(selfdiff)
                    detail = d
                else:
                    verdict, detail = "DIFF", d
            else:
                verdict, detail = "OK", ""
        rec = {"id": cid, "group": group, "note": case.get("note", ""), "req": req,
               "jstatus": rj["status"], "gstatus": rg["status"], "jms": rj["ms"],
               "gms": rg["ms"], "verdict": verdict, "detail": detail,
               "attempt": attempt + 1, "jlens": jlens, "glens": glens, "nondet": nondet,
               "jerr": rj["err"], "gerr": rg["err"]}
        best = rec
        if verdict in ("OK", "NONDET"):
            break
    best["stable"] = (best["attempt"] == 1) or (best["verdict"] == "OK")
    dump(cid, "java", rj, pj)
    dump(cid, "go", rg, pg)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--gen", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--allow-write", action="store_true")
    ap.add_argument("--case")
    ap.add_argument("--out", default="results")
    ap.add_argument("--md")
    a = ap.parse_args()
    import suite
    if a.gen:
        suite.gen()
        return
    cases = json.load(open(suite.CASES_JSON, encoding="utf-8")) if os.path.exists(
        suite.CASES_JSON) else suite.gen()
    if a.list:
        for c in cases:
            print(f"{c['id']:44s} {c['method']:5s} {c['path']}")
        print(f"共 {len(cases)} 条")
        return
    if a.case:
        cases = [c for c in cases if c["id"] == a.case]
    res = run(cases, only=a.only, allow_write=a.allow_write, out_prefix=a.out)
    if a.md:
        write_md(res, a.md)


def write_md(res, path):
    order = {"STATUS": 0, "SHAPE": 1, "DIFF": 2, "OK": 3}
    res = sorted(res, key=lambda r: (order.get(r["verdict"], 0), r["group"], r["id"]))
    lines = ["| 用例 | 请求 | 判定 | Java | Go | 差异摘要 | 稳定 |",
             "|---|---|---|---|---|---|---|"]
    for r in res:
        d = r["detail"]
        if isinstance(d, list):
            txt = "; ".join(f"`{p}`({t})" for p, t, _, _ in [(x[0], x[1], x[2], x[3]) for x in d[:6]])
            if len(d) > 6:
                txt += f" …共 {len(d)} 项"
        else:
            txt = str(d)[:200]
        lines.append(f"| {r['id']} | `{r['req'][:70]}` | {r['verdict']} | {r['jstatus']} "
                     f"| {r['gstatus']} | {txt or '-'} | {'是' if r.get('stable') else '否(重试后一致)'} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

