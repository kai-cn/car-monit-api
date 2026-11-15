#!/usr/bin/env python3
"""Read-only audit of the six JDK release fat jars.

Cross-platform (Windows / WSL). Uses only the stdlib zipfile central directory,
so a 200 MB jar is scanned in well under a second without extracting anything.

Usage:
  python v3-jar-audit.py
  python v3-jar-audit.py --root /mnt/d/work/IdeaProjects --out <dir>

Outputs a fixed-width text report + CSV into the evidence directory and prints
the same summary to stdout (ASCII only, safe for Windows GBK consoles).
"""
import argparse
import csv
import datetime
import os
import re
import sys
import zipfile

DEFAULT_ROOT = r"D:\work\IdeaProjects"
DEFAULT_OUT = r"D:\work\runtime-logs\v3-ops\evidence"
JDKS = ("17", "21", "25")
APPS = ("api", "backend")

DEAD_PLATFORM = re.compile(
    r"(osx|macos|darwin|windows|win32|win-x86|aarch_64|aarch64|linux-arm|"
    r"linux-aarch|s390x|ppc64|riscv)", re.I
)
DEAD_DOC = re.compile(r"(license|readme|notice|changelog|changes|about)\.", re.I)
FLINK = re.compile(r"^flink-|/flink-", re.I)


def jar_path(root, jdk, app):
    if app == "api":
        return os.path.join(root, f"car-monit-api-jdk{jdk}",
                            "pro-business-api", "target", "pro-business-api-1.0.jar")
    return os.path.join(root, f"car-monit-backend-jdk{jdk}",
                        "ruoyi-admin", "target", "ruoyi-admin.jar")


def pom_path(root, jdk, app):
    if app == "api":
        return os.path.join(root, f"car-monit-api-jdk{jdk}",
                            "pro-business-api", "pom.xml")
    return os.path.join(root, f"car-monit-backend-jdk{jdk}",
                        "ruoyi-admin", "pom.xml")


def audit(path):
    if not os.path.isfile(path):
        return None
    total = os.path.getsize(path)
    libs, docs, platforms, flink = [], [], [], []
    classes = meta = other = 0
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            n = i.filename
            cs, us = i.compress_size, i.file_size
            if n.startswith("BOOT-INF/lib/"):
                if n.endswith(".jar"):
                    libs.append((n.rsplit("/", 1)[-1], cs, us))
                    if DEAD_PLATFORM.search(n):
                        platforms.append((n.rsplit("/", 1)[-1], cs))
                    if FLINK.search(n.rsplit("/", 1)[-1]):
                        flink.append((n.rsplit("/", 1)[-1], cs))
                if DEAD_DOC.search(n.rsplit("/", 1)[-1]):
                    docs.append((n.rsplit("/", 1)[-1], cs))
            elif n.startswith("BOOT-INF/classes/"):
                classes += cs
            elif n.startswith("META-INF/"):
                meta += cs
                if DEAD_DOC.search(n.rsplit("/", 1)[-1]):
                    docs.append((n.rsplit("/", 1)[-1], cs))
            else:
                other += cs
    libs.sort(key=lambda x: -x[1])
    return {
        "total": total,
        "lib_count": len(libs),
        "lib_compressed": sum(x[1] for x in libs),
        "lib_uncompressed": sum(x[2] for x in libs),
        "classes": classes,
        "meta": meta,
        "other": other,
        "top": libs[:15],
        "dead_platform": platforms,
        "dead_docs": docs,
        "flink": flink,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    txt = os.path.join(args.out, f"jar-audit-{ts}.txt")
    csvp = os.path.join(args.out, f"jar-audit-{ts}.csv")

    rows, lines = [], []
    def emit(s=""):
        lines.append(s)
        print(s)

    emit("######## V3 RELEASE JAR AUDIT (read-only) " + ts + " ########")
    emit(f"root={args.root}")
    emit("")
    emit(f"{'APP':<9}{'JDK':<6}{'JAR_BYTES':>12}{'LIBS':>7}{'LIB_CMP':>12}"
         f"{'LIB_UNCMP':>12}{'CLASSES':>11}{'META':>10}{'DEAD_PLAT':>11}{'STALE':>7}{'FLINK':>7}")
    for j in JDKS:
        for a in APPS:
            p = jar_path(args.root, j, a)
            r = audit(p)
            if r is None:
                emit(f"{a:<9}{'jdk'+j:<6}  MISSING: {p}")
                continue
            pp = pom_path(args.root, j, a)
            stale = "YES" if (os.path.isfile(pp) and os.path.getmtime(pp) > os.path.getmtime(p)) else "no"
            emit(f"{a:<9}{'jdk'+j:<6}{r['total']:>12}{r['lib_count']:>7}"
                 f"{r['lib_compressed']:>12}{r['lib_uncompressed']:>12}{r['classes']:>11}"
                 f"{r['meta']:>10}{len(r['dead_platform']):>11}{stale:>7}"
                 f"{len(r['flink']):>7}")
            rows.append(dict(app=a, jdk=j, path=p, pom=pp,
                             jar_mtime=datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds"),
                             pom_mtime=datetime.datetime.fromtimestamp(os.path.getmtime(pp)).isoformat(timespec="seconds") if os.path.isfile(pp) else "",
                             stale=stale,
                             **{k: v for k, v in r.items()
                                if k not in ("top", "dead_platform", "dead_docs", "flink")},
                             dead_platform_count=len(r["dead_platform"]),
                             dead_docs_count=len(r["dead_docs"]),
                             flink_count=len(r["flink"])))
            if j == "17" and a == "api":
                emit("")
                emit("-- jdk17/api top 15 nested jars (compressed bytes) --")
                for name, cs, us in r["top"]:
                    emit(f"   {cs:>11}  {us:>11}  {name}")
                emit("")
                emit("-- removable candidates (non linux-x86_64 native / docs / flink) --")
                for label, items in (("platform", r["dead_platform"]),
                                     ("docs", r["dead_docs"]), ("flink", r["flink"])):
                    emit(f"   {label}: {len(items)} entries, {sum(x[1] for x in items)} bytes")
                    for name, cs in items[:10]:
                        emit(f"      {cs:>10}  {name}")
            emit("")

    emit("Interpretation:")
    emit("  * LIB_CMP dominates the jar; classes are small. Reducing image size")
    emit("    therefore means: (1) per-JDK jlink runtime, (2) shared base/JRE")
    emit("    layers, (3) removing only provably dead native/doc entries.")
    emit("  * STALE=YES means the jar is OLDER than its pom: it was packaged")
    emit("    before the slimming excludes were added. Re-packaging with the")
    emit("    CURRENT pom (no source edit) removes those libs. Verified case:")
    emit("      api jdk21/25     : +4 netty-codec-native-quic variants ~9.33 MB")
    emit("      backend jdk21/25 : calcite+groovy+aliyun-mns+linq4j ~21.45 MB")
    emit("  * DO NOT re-compress BOOT-INF/lib entries as DEFLATED: Spring Boot")
    emit("    requires nested jars to be STORED (LIB_CMP == LIB_UNCMP here).")
    emit("    Changing that breaks `java -jar` at startup.")
    emit("  * This audit never modifies any jar.")
    emit(f"report={txt}")

    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if rows:
        with open(csvp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("csv=" + csvp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
