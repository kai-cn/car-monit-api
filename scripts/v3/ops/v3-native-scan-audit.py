#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-native-scan-audit.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Audit a native-image classpath for MyBatis-Plus AOT scan landmines.

Background
----------
mybatis-plus-spring-boot-native-image 3.5.18 registers a reachability handler on
java.lang.invoke.SerializedLambda. When the handler fires, MybatisPlusFeature
collects every class that has a `main` method, takes each distinct
`Class.getPackageName()` as a scan root, and then walks *all* classpath entries
under that package prefix (recursively, sub-packages included). For every class
collected it calls `Class.getDeclaredMethods()`.

On a HotSpot/GraalVM host that call throws `NoClassDefFoundError` when any
method signature (parameter / return / exception type) references a type that is
absent from the build classpath. If a `main` class lives in e.g. `io.netty.util`
or `org.apache.commons.logging`, the prefix scan drags in optional-logging
adapters whose log4j 1.x types are not on the classpath, and native-image dies in
analysis with:

    Error: java.util.concurrent.ExecutionException:
        java.lang.NoClassDefFoundError: org/apache/log4j/Priority
        at com.baomidou.mybatisplus.aot.FeatureUtils.registerSerializationLambdaCapturingClass

This script predicts *every* such landmine up-front so the fix can be applied in
one shot instead of one native-image rebuild per missing type.

Usage
-----
    python3 v3-native-scan-audit.py <classpath-file> [--top N] [--json out.json]

<classpath-file> holds one classpath entry per line (produced from the
native-image `-cp` argument).

Exit code is 0 when no landmine is found, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import zipfile

# ---------------------------------------------------------------- class parsing

ACC_PUBLIC = 0x0001
ACC_STATIC = 0x0008

# Types supplied by the JDK itself; never index them.
JDK_PREFIXES = (
    "java/", "javax/", "jdk/", "sun/", "com/sun/",
    "org/w3c/", "org/xml/", "org/ietf/",
)

TYPE_IN_DESCRIPTOR = re.compile(r"L([^;]+);")


class ClassFile:
    __slots__ = ("name", "super_name", "interfaces", "field_descs",
                 "method_descs", "method_flags", "method_names")


def _read_attrs(buf: bytes, pos: int, count: int) -> int:
    for _ in range(count):
        pos += 2                       # attribute_name_index
        (length,) = struct.unpack_from(">I", buf, pos)
        pos += 4 + length
    return pos


def parse_class(buf: bytes) -> ClassFile:
    """Minimal .class parser: constant pool, this_class, fields, methods."""
    if buf[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("not a class file")

    pos = 8                            # magic + minor + major
    (cp_count,) = struct.unpack_from(">H", buf, pos)
    pos += 2

    utf8: list[str | None] = [None] * cp_count
    class_name_idx: list[int] = [0] * cp_count
    i = 1
    while i < cp_count:
        tag = buf[pos]
        pos += 1
        if tag == 1:                   # Utf8
            (length,) = struct.unpack_from(">H", buf, pos)
            pos += 2
            utf8[i] = buf[pos:pos + length].decode("utf-8", "replace")
            pos += length
        elif tag in (3, 4):            # Integer, Float
            pos += 4
        elif tag in (5, 6):            # Long, Double (two slots)
            pos += 8
            i += 1
        elif tag == 7:                 # Class
            (class_name_idx[i],) = struct.unpack_from(">H", buf, pos)
            pos += 2
        elif tag in (8, 16, 19, 20):   # String, MethodType, Module, Package
            pos += 2
        elif tag in (9, 10, 11, 12, 17, 18):   # refs, NameAndType, Dynamic
            pos += 4
        elif tag == 15:                # MethodHandle
            pos += 3
        else:
            raise ValueError(f"unknown constant pool tag {tag}")
        i += 1

    pos += 2                           # access_flags
    (this_class,) = struct.unpack_from(">H", buf, pos)
    pos += 2
    cls = ClassFile()
    cls.name = utf8[class_name_idx[this_class]] or ""

    (super_idx,) = struct.unpack_from(">H", buf, pos)
    pos += 2
    cls.super_name = utf8[class_name_idx[super_idx]] if super_idx else None

    (iface_count,) = struct.unpack_from(">H", buf, pos)
    pos += 2
    cls.interfaces = []
    for _ in range(iface_count):
        (idx,) = struct.unpack_from(">H", buf, pos)
        pos += 2
        cls.interfaces.append(utf8[class_name_idx[idx]] or "")

    def read_members(pos: int, want_methods: bool):
        (count,) = struct.unpack_from(">H", buf, pos)
        pos += 2
        descs, flags, names = [], [], []
        for _ in range(count):
            (acc,) = struct.unpack_from(">H", buf, pos)
            (name_i, desc_i, attr_count) = struct.unpack_from(">HHH", buf, pos + 2)
            pos += 8
            pos = _read_attrs(buf, pos, attr_count)
            if want_methods:
                descs.append(utf8[desc_i] or "")
                flags.append(acc)
                names.append(utf8[name_i] or "")
        return pos, descs, flags, names

    pos, cls.field_descs, _, _ = read_members(pos, False)
    pos, cls.method_descs, cls.method_flags, cls.method_names = read_members(pos, True)
    return cls


# ---------------------------------------------------------------- classpath index

def index_classpath(entries: list[str]) -> dict[str, str]:
    """Map internal class name -> location. First entry wins (classpath order)."""
    index: dict[str, str] = {}
    for entry in entries:
        if entry.endswith(".jar") or entry.endswith(".zip"):
            try:
                with zipfile.ZipFile(entry) as zf:
                    for n in zf.namelist():
                        if n.endswith(".class") and not n.startswith("META-INF/"):
                            index.setdefault(n[:-6], entry)
            except (OSError, zipfile.BadZipFile) as exc:
                print(f"warn: skip jar {entry}: {exc}", file=sys.stderr)
        elif os.path.isdir(entry):
            for root, _dirs, files in os.walk(entry):
                for f in files:
                    if f.endswith(".class"):
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, entry).replace(os.sep, "/")[:-6]
                        index.setdefault(rel, entry)
    return index


_ZIP_CACHE: dict[str, zipfile.ZipFile] = {}


def _zip(location: str) -> zipfile.ZipFile | None:
    zf = _ZIP_CACHE.get(location)
    if zf is None:
        try:
            zf = zipfile.ZipFile(location)
        except (OSError, zipfile.BadZipFile):
            return None
        _ZIP_CACHE[location] = zf
    return zf


def read_class(name: str, location: str) -> bytes | None:
    try:
        if os.path.isdir(location):
            with open(os.path.join(location, name + ".class"), "rb") as fh:
                return fh.read()
        zf = _zip(location)
        if zf is None:
            return None
        return zf.read(name + ".class")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


# ---------------------------------------------------------------- audit

def is_jdk_type(t: str) -> bool:
    return t.startswith(JDK_PREFIXES)


def missing_types(descs: list[str], index: dict[str, str]) -> set[str]:
    missing: set[str] = set()
    for desc in descs:
        for t in TYPE_IN_DESCRIPTOR.findall(desc):
            if t.startswith("["):
                continue
            if t in index or is_jdk_type(t):
                continue
            missing.add(t)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("classpath_file")
    ap.add_argument("--top", type=int, default=40, help="how many landmines to print")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    entries = [ln.strip() for ln in open(args.classpath_file, encoding="utf-8")
               if ln.strip()]
    index = index_classpath(entries)
    print(f"classpath entries : {len(entries)}")
    print(f"indexed classes   : {len(index)}")

    # 1. replicate CollectUtils.findMainClasses(): any public static main(String[])
    main_classes: list[str] = []
    MAIN_DESC = b"([Ljava/lang/String;)V"
    for name, loc in index.items():
        if name.endswith("module-info") or "/" not in name:
            continue
        buf = read_class(name, loc)
        if not buf or MAIN_DESC not in buf or b"main" not in buf:
            continue                # cheap pre-filter: most classes can't have main
        try:
            cf = parse_class(buf)
        except (ValueError, struct.error):
            continue
        for mname, mdesc, mflags in zip(cf.method_names, cf.method_descs, cf.method_flags):
            if (mname == "main" and mdesc == "([Ljava/lang/String;)V"
                    and mflags & ACC_PUBLIC and mflags & ACC_STATIC):
                main_classes.append(name)
                break

    scan_packages = sorted({name.rsplit("/", 1)[0] for name in main_classes})
    print(f"main classes      : {len(main_classes)}")
    print(f"scan packages     : {len(scan_packages)}")

    # 2. walk every class under those package prefixes and look for unresolvable types
    landmines: dict[str, set[str]] = {}
    scanned = 0
    for pkg in scan_packages:
        prefix = pkg + "/"
        for name, loc in index.items():
            if not name.startswith(prefix):
                continue
            scanned += 1
            buf = read_class(name, loc)
            if not buf:
                continue
            try:
                cf = parse_class(buf)
            except (ValueError, struct.error):
                continue
            miss = missing_types(cf.field_descs + cf.method_descs, index)
            if miss:
                landmines[name] = miss

    print(f"classes scanned   : {scanned}")
    print(f"landmines found   : {len(landmines)}")
    for name in sorted(landmines):
        print(f"  {name}  ->  {', '.join(sorted(landmines[name]))}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({
                "classpathEntries": len(entries),
                "indexedClasses": len(index),
                "mainClasses": main_classes,
                "scanPackages": scan_packages,
                "scannedClasses": scanned,
                "landmines": {k: sorted(v) for k, v in sorted(landmines.items())},
            }, fh, indent=2)
        print(f"json written      : {args.json_out}")

    return 1 if landmines else 0


if __name__ == "__main__":
    sys.exit(main())
