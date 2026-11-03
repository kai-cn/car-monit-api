# -*- coding: utf-8 -*-
"""从源码提取两端路由清单并对照。

Java：扫 controller 目录的 @*Mapping 注解（跳过 /* */ 注释块里的）。
Go  ：扫 handler 目录的 grp.GET/POST 与 ReadOnlySpec 注册表（表驱动的要先展开）。

输出 markdown 表格，直接贴进文档，避免手抄出错。
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

JC = r"D:\work\IdeaProjects\car-monit-api\pro-business-api\src\main\java\com\ruoyi\base\controller"
GH = r"D:\work\IdeaProjects\car-monit-api\car-monit-api-go\internal\handler"

MAP_ANN = ("GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "RequestMapping")


def strip_comments(src: str) -> str:
    """去掉块注释与行注释，但保留行号结构（用等长空白替换）。"""
    out, i, n = [], 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
        elif two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif src[i] == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1
        else:
            out.append(src[i]); i += 1
    return "".join(out)


def java_routes():
    rows = []
    for fn in sorted(os.listdir(JC)):
        if not fn.endswith(".java"):
            continue
        raw = open(os.path.join(JC, fn), encoding="utf-8", errors="replace").read()
        src = strip_comments(raw)
        m = re.search(r'@RequestMapping\s*\(\s*"([^"]+)"', src)
        base = m.group(1) if m else ""
        for mm in re.finditer(r"@(%.{0,12})" % "|".join(MAP_ANN) if False else
                              r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)"
                              r"\s*(\([^)]*\))?", src):
            ann, args = mm.group(1), (mm.group(2) or "")
            if ann == "RequestMapping" and not m:
                continue
            if ann == "RequestMapping" and m and args.strip("()") == f'"{base}"':
                continue
            p = re.search(r'"([^"]*)"', args)
            sub = p.group(1) if p else ""
            method = {"GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
                      "DeleteMapping": "DELETE", "RequestMapping": "ANY"}[ann]
            # 参数签名
            tail = src[mm.end():mm.end() + 600]
            sig = re.search(r"public\s+([\w<>,\[\]\. ]+?)\s+\w+\s*\(([^)]*)\)", tail, re.S)
            ret = sig.group(1).strip() if sig else "?"
            params = re.sub(r"\s+", " ", sig.group(2)).strip() if sig else ""
            line = raw[:mm.start()].count("\n") + 1
            path = base + sub
            if sub.startswith("/{"):
                path = base + sub
            rows.append((method, path, fn.replace(".java", ""), line, ret, params,
                         "注释内" if False else ""))
    # 去重
    seen, uniq = set(), []
    for r in rows:
        if (r[0], r[1]) in seen:
            continue
        seen.add((r[0], r[1]))
        uniq.append(r)
    return uniq


# ── Go 侧 ──
SPEC_RE = re.compile(r'RegisterReadOnly(?:Numeric)?\(\s*g,\s*ReadOnlySpec\[[^\]]*\]\s*\{(.*?)\}\s*,', re.S)
NUM_RE = re.compile(r'RegisterReadOnlyNumeric')


def go_routes():
    src = open(os.path.join(GH, "base.go"), encoding="utf-8").read()
    rows = []
    for m in SPEC_RE.finditer(src):
        blk = m.group(1)
        base = re.search(r'Base:\s*"([^"]+)"', blk)
        if not base:
            continue
        idp = re.search(r'IDParam:\s*"([^"]+)"', blk)
        flags = {k: bool(re.search(k + r":\s*true", blk)) for k in
                 ("AllowAll", "AllowExport", "FlatInfo", "NumericID")}
        b = base.group(1)
        rows.append(("GET", b + "/list", "crud", flags))
        rows.append(("GET", b + "/:" + (idp.group(1) if idp else "id"), "crud", flags))
        if flags["AllowAll"]:
            rows.append(("GET", b + "/listAll", "crud", flags))
        if flags["AllowExport"]:
            rows.append(("GET", b + "/listToExport", "crud", flags))
    for extra in [("GET", "/base/vehicleweight/map"), ("GET", "/base/sysutil/saveRedis"),
                  ("GET", "/base/sysutil/carTrackQueryByCarNo"), ("GET", "/base/sysutil/carTrackQueryByTime"),
                  ("POST", "/base/sysutil/changeTrailInfo"), ("GET", "/base/sysutil/getByTrailBo"),
                  ("GET", "/base/sysutilTest/syncBaseInfo"), ("GET", "/base/sysutilTest/syncCurrentTrack"),
                  ("GET", "/base/sysutilTest/syncHistroyTrack")]:
        rows.append((extra[0], extra[1], "hand", {}))
    q = open(os.path.join(GH, "query.go"), encoding="utf-8").read()
    for mm in re.finditer(r'(large|unified|prog)\.(GET|POST)\(\s*"([^"]+)"', q):
        grp = {"large": "/api/v1/large", "unified": "/api/v1/unified", "prog": "/progressive"}[mm.group(1)]
        rows.append((mm.group(2), grp + mm.group(3), "query", {}))
    st = open(os.path.join(GH, "selftest.go"), encoding="utf-8").read()
    for i in range(1, 11):
        rows.append(("GET", f"/base/sysutilTest/syncSuspiciousCar{i}", "501桩", {}))
    rows.append(("GET", "/base/sysutilTest/syncOdsSzdnGantry", "501桩", {}))
    rows.append(("GET", "/base/sysutilTest/separateSnapshotFlowTimeList", "501桩", {}))
    if "notPorted" in st:
        pass
    seen, uniq = set(), []
    for r in rows:
        if (r[0], r[1]) in seen:
            continue
        seen.add((r[0], r[1]))
        uniq.append(r)
    return uniq


def norm_go(p):
    """把 Go 的 :param 变成 Java 的 {param} 形状，便于对齐。"""
    return re.sub(r":(\w+)$", r"{\1}", p)


def main():
    jr, gr = java_routes(), go_routes()
    gset = {norm_go(p) for _, p, _, _ in gr}
    jset = {p for _, p, *_ in jr}
    print(f"Java 端点 {len(jr)} 个，Go 端点 {len(gr)} 个（不含 /healthz /debug/pprof）\n")
    print("## Java 有、Go 无")
    for mtd, p, cls, line, ret, params, _ in jr:
        if p not in gset:
            print(f"  {mtd:6s} {p:52s} {cls:44s} L{line}  -> {ret}")
    print("\n## Go 有、Java 无")
    for mtd, p, cls, flags in gr:
        if norm_go(p) not in jset:
            print(f"  {mtd:6s} {p:52s} {cls}")
    print("\n## 全量对照表")
    print("| 方法 | 路径 | Java 类 | Java 行 | Go 状态 | Go 标志 |")
    print("|---|---|---|---|---|---|")
    for mtd, p, cls, line, ret, params, _ in jr:
        g = next((x for x in gr if norm_go(x[1]) == p), None)
        st = "有" if g else ("**缺**" if mtd == "GET" else "**缺**")
        fl = ""
        if g:
            f = g[3] or {}
            fl = ",".join(k for k, v in f.items() if v) or g[2]
        print(f"| {mtd} | `{p}` | {cls} | {line} | {st} | {fl} |")
    print("\n## Java 返回类型分布（信封判定用）")
    for ret in sorted({r[4] for r in jr}):
        n = sum(1 for r in jr if r[4] == ret)
        print(f"  {n:3d}  {ret}")


if __name__ == "__main__":
    main()
