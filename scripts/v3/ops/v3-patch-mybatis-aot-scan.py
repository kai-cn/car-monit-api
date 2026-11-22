#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-patch-mybatis-aot-scan.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Patch MyBatis-Plus AOT scan scope in CollectUtils.class.

Problem
-------
mybatis-plus-spring-boot-native-image 3.5.18 ships `MybatisPlusFeature`, which
registers a `SerializedLambda` reachability handler. The handler calls
`CollectUtils.findMainPackages()` to decide which packages to walk, and then
invokes `Class.getDeclaredMethods()` on every class found there.

`findMainPackages()` is derived from `findMainClasses()`, which does two things:

  1. `findMainClassesFromNativeImageProperties()` - reads `-H:Class=` from every
     `META-INF/native-image/**/native-image.properties` on the classpath.
  2. `findClasses(isMainClass)` - a *full classpath* scan for any class that
     declares `public static void main(String[])`.

Step 2 is the defect for a Spring Boot fat classpath: it pulls in 100+ main
classes from Kafka, Elasticsearch, Tomcat, Pulsar's shaded commons-compress,
BouncyCastle, ... and turns their packages into recursive scan roots. Measured
on car-monit-api (JDK21): 70 scan roots, 26,912 classes scanned, 159 classes
whose method signatures reference types that are absent from the native
classpath. The first one aborts the build:

    NoClassDefFoundError: org/apache/log4j/Priority
        at com.baomidou.mybatisplus.aot.FeatureUtils.registerSerializationLambdaCapturingClass

GraalVM 25 (Mandrel 25) happens to tolerate those unresolvable signatures, so
the JDK25 branch builds; GraalVM 23.1 (Mandrel 21/17) does not.

Fix
---
The application always declares its entry point via `-H:Class` in its own
`native-image.properties` (Spring Boot generates it), so step 1 alone already
yields the correct scan root (`com.ruoyi`). This script rewrites the body of
`CollectUtils.findMainClasses()` to:

    return findMainClassesFromNativeImageProperties();

Nothing else changes: `findMainPackages()`, the MyBatis mapper/XML registration
and the MyBatis-Plus Wrapper registration all keep their original behaviour,
and lambda-capturing classes inside the application packages are still
registered through `RuntimeSerialization`.

The patched class is emitted next to the original class file tree so it can be
dropped into `target/classes` (first entry on the native-image classpath) and
shadow the jar copy.

Usage
-----
    python3 v3-patch-mybatis-aot-scan.py <native-image-jar> <out-dir> [--verify]
"""

from __future__ import annotations

import argparse
import io
import os
import struct
import sys
import zipfile

TARGET_METHOD = "findMainClasses"
TARGET_DESC = "()Ljava/util/Set;"
DELEGATE_NAME = "findMainClassesFromNativeImageProperties"
DELEGATE_DESC = "()Ljava/util/Set;"
CLASS_ENTRY = "com/baomidou/mybatisplus/aot/CollectUtils.class"

# opcodes
ALOAD_0 = 0x2A
INVOKEVIRTUAL = 0xB6
ARETURN = 0xB0


def u2(buf: bytes, pos: int) -> int:
    return struct.unpack_from(">H", buf, pos)[0]


def u4(buf: bytes, pos: int) -> int:
    return struct.unpack_from(">I", buf, pos)[0]


class ConstantPool:
    def __init__(self, buf: bytes):
        self.utf8: dict[int, str] = {}
        self.class_name_idx: dict[int, int] = {}
        self.nat: dict[int, tuple[int, int]] = {}
        self.methodref: dict[int, tuple[int, int]] = {}

        pos = 8
        self.count = u2(buf, pos)
        pos += 2
        self.start = pos
        i = 1
        while i < self.count:
            tag = buf[pos]
            pos += 1
            if tag == 1:
                length = u2(buf, pos)
                pos += 2
                self.utf8[i] = buf[pos:pos + length].decode("utf-8", "replace")
                pos += length
            elif tag in (3, 4):
                pos += 4
            elif tag in (5, 6):
                pos += 8
                i += 1
            elif tag == 7:
                self.class_name_idx[i] = u2(buf, pos)
                pos += 2
            elif tag in (8, 16, 19, 20):
                pos += 2
            elif tag == 12:
                self.nat[i] = (u2(buf, pos), u2(buf, pos + 2))
                pos += 4
            elif tag in (9, 10, 11):
                cls_idx, nat_idx = u2(buf, pos), u2(buf, pos + 2)
                if tag == 10:
                    self.methodref[i] = (cls_idx, nat_idx)
                pos += 4
            elif tag in (17, 18):
                pos += 4
            elif tag == 15:
                pos += 3
            else:
                raise ValueError(f"unknown constant pool tag {tag}")
            i += 1
        self.end = pos

    def class_name(self, class_idx: int) -> str | None:
        name_idx = self.class_name_idx.get(class_idx)
        return self.utf8.get(name_idx) if name_idx else None

    def find_methodref(self, owner: str, name: str, desc: str) -> int | None:
        for idx, (cls_idx, nat_idx) in self.methodref.items():
            if self.class_name(cls_idx) != owner:
                continue
            n_idx, d_idx = self.nat.get(nat_idx, (None, None))
            if self.utf8.get(n_idx) == name and self.utf8.get(d_idx) == desc:
                return idx
        return None

    def find_utf8(self, value: str) -> int | None:
        for idx, text in self.utf8.items():
            if text == value:
                return idx
        return None


def patch_class(buf: bytes) -> tuple[bytes, dict]:
    if buf[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("not a class file")

    cp = ConstantPool(buf)
    pos = cp.end

    access = u2(buf, pos)
    pos += 2
    this_class = u2(buf, pos)
    pos += 2
    super_class = u2(buf, pos)
    pos += 2
    iface_count = u2(buf, pos)
    pos += 2 + iface_count * 2

    # ---- fields (copy verbatim)
    field_count = u2(buf, pos)
    pos += 2
    for _ in range(field_count):
        attr_count = u2(buf, pos + 6)
        pos += 8
        for _ in range(attr_count):
            pos += 2
            pos += 4 + u4(buf, pos)

    # ---- methods
    method_count = u2(buf, pos)
    methods_count_offset = pos
    pos += 2

    owner = cp.class_name(this_class)
    code_name_idx = cp.find_utf8("Code")
    if code_name_idx is None:
        raise ValueError("no Code attribute name in constant pool")

    target_start = target_end = None
    target_attrs_count_offset = None
    for _ in range(method_count):
        m_start = pos
        m_access, m_name_idx, m_desc_idx, m_attr_count = struct.unpack_from(">HHHH", buf, pos)
        pos += 8
        name = cp.utf8.get(m_name_idx)
        desc = cp.utf8.get(m_desc_idx)
        for _ in range(m_attr_count):
            pos += 2
            pos += 4 + u4(buf, pos)
        if name == TARGET_METHOD and desc == TARGET_DESC:
            target_start, target_end, target_attrs_count_offset = m_start, pos, m_start + 6
    if target_start is None:
        raise ValueError(f"method {TARGET_METHOD}{TARGET_DESC} not found")

    delegate_idx = cp.find_methodref(owner, DELEGATE_NAME, DELEGATE_DESC)
    if delegate_idx is None:
        raise ValueError(f"methodref {DELEGATE_NAME}{DELEGATE_DESC} not found on {owner}")

    # ---- build new Code attribute: return findMainClassesFromNativeImageProperties();
    code = bytes([ALOAD_0, INVOKEVIRTUAL]) + struct.pack(">H", delegate_idx) + bytes([ARETURN])
    payload = struct.pack(">HHI", 1, 1, len(code)) + code + struct.pack(">HH", 0, 0)
    code_attr = struct.pack(">HI", code_name_idx, len(payload)) + payload

    method_head = buf[target_start:target_attrs_count_offset]
    new_method = method_head + struct.pack(">H", 1) + code_attr
    new_buf = buf[:target_start] + new_method + buf[target_end:]

    info = {
        "owner": owner,
        "delegateMethodref": delegate_idx,
        "origMethodBytes": target_end - target_start,
        "newMethodBytes": len(new_method),
        "origSize": len(buf),
        "newSize": len(new_buf),
    }
    return new_buf, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jar")
    ap.add_argument("out_dir")
    ap.add_argument("--verify", action="store_true",
                    help="re-parse the patched class to prove it is well formed")
    args = ap.parse_args()

    with zipfile.ZipFile(args.jar) as zf:
        original = zf.read(CLASS_ENTRY)

    patched, info = patch_class(original)
    print(f"owner            : {info['owner']}")
    print(f"delegate methodref: #{info['delegateMethodref']}")
    print(f"method bytes      : {info['origMethodBytes']} -> {info['newMethodBytes']}")
    print(f"class bytes       : {info['origSize']} -> {info['newSize']}")

    if args.verify:
        cp = ConstantPool(patched)
        pos = cp.end + 2 + 2 + 2 + 2
        pos += u2(patched, pos - 2) * 2
        field_count = u2(patched, pos)
        pos += 2
        for _ in range(field_count):
            attr_count = u2(patched, pos + 6)
            pos += 8
            for _ in range(attr_count):
                pos += 2
                pos += 4 + u4(patched, pos)
        method_count = u2(patched, pos)
        pos += 2
        found = False
        for _ in range(method_count):
            m_access, m_name_idx, m_desc_idx, m_attr_count = struct.unpack_from(">HHHH", patched, pos)
            pos += 8
            if cp.utf8.get(m_name_idx) == TARGET_METHOD and cp.utf8.get(m_desc_idx) == TARGET_DESC:
                found = True
                attr_name = u2(patched, pos)
                attr_len = u4(patched, pos + 2)
                body = patched[pos + 6:pos + 6 + attr_len]
                max_stack, max_locals, code_len = struct.unpack_from(">HHI", body, 0)
                code = body[8:8 + code_len]
                print(f"verify           : Code name_idx={attr_name} len={attr_len} "
                      f"max_stack={max_stack} max_locals={max_locals} code_len={code_len}")
                print(f"verify           : code={code.hex()}")
                expected = bytes([ALOAD_0, INVOKEVIRTUAL]) + struct.pack(">H", info["delegateMethodref"]) + bytes([ARETURN])
                assert code == expected, "bytecode mismatch"
                assert attr_len == 8 + code_len + 4, "attribute length mismatch"
                print("verify           : OK (delegates to findMainClassesFromNativeImageProperties)")
                pos += 2 + 4 + attr_len
                continue
            for _ in range(m_attr_count):
                pos += 2
                pos += 4 + u4(patched, pos)
        assert found, "patched method lost"

    out_path = os.path.join(args.out_dir, CLASS_ENTRY)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(patched)
    print(f"written          : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
