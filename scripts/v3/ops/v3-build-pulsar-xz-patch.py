#!/usr/bin/env python3
"""Build a patch jar that supplies the shaded XZ/LZMA classes missing from
pulsar-client-4.2.5.jar.

Root cause
----------
pulsar-client-4.2.5.jar ships shaded commons-compress classes such as
`org.apache.pulsar.shade.org.apache.commons.compress.archivers.sevenz.LZMADecoder`
whose method signatures reference `org.apache.pulsar.shade.org.tukaani.xz.*`.
That shaded tukaani package is NOT present in the jar (verified: 0 entries).
MyBatis-Plus 3.5.18 AOT `MybatisPlusFeature` scans every class with a `main`
method as a "main class"; the shaded commons-compress `CLI` class qualifies,
so its package tree is scanned and `Class.getDeclaredMethods()` throws
`NoClassDefFoundError: org/apache/pulsar/shade/org/tukaani/xz/LZMAInputStream`,
aborting native-image analysis.

Fix
---
Take the standalone `org.tukaani:xz` jar and relocate its `org/tukaani/xz`
classes to `org/apache/pulsar/shade/org/tukaani/xz`, rewriting the class-file
constant pool so all internal/binary names point at the shaded package. The
result is a small patch jar added to the native-image classpath only.

Usage
-----
  python v3-build-pulsar-xz-patch.py <xz.jar> <out.jar> [--verify]

The transformation is pure ASCII bytes in CONSTANT_Utf8 entries, so it is
deterministic and works on any platform.
"""
import argparse
import io
import os
import struct
import sys
import zipfile

SRC_PREFIX = b"org/tukaani/xz"
DST_PREFIX = b"org/apache/pulsar/shade/org/tukaani/xz"


# ---------- minimal class-file constant-pool rewriter ----------
def _read_u2(data, off):
    return struct.unpack_from(">H", data, off)[0]


def relocate_utf8_in_class(class_bytes):
    """Return (new_bytes, replaced_count). Rewrites CONSTANT_Utf8 values only."""
    if len(class_bytes) < 10 or class_bytes[:4] != b"\xca\xfe\xba\xbe":
        return class_bytes, 0
    off = 8
    cp_count = _read_u2(class_bytes, off)
    off += 2
    out = bytearray(class_bytes[:off])
    idx = 1
    replaced = 0
    while idx < cp_count:
        tag = class_bytes[off]
        out.append(tag)
        off += 1
        if tag == 1:  # CONSTANT_Utf8
            length = _read_u2(class_bytes, off)
            off += 2
            raw = class_bytes[off:off + length]
            off += length
            new_raw = raw.replace(SRC_PREFIX, DST_PREFIX)
            if new_raw != raw:
                replaced += 1
            out.extend(struct.pack(">H", len(new_raw)))
            out.extend(new_raw)
        elif tag in (3, 4):  # Integer / Float
            out.extend(class_bytes[off:off + 4]); off += 4
        elif tag in (5, 6):  # Long / Double (two slots)
            out.extend(class_bytes[off:off + 8]); off += 8
            idx += 1
        elif tag == 15:  # MethodHandle
            out.extend(class_bytes[off:off + 3]); off += 3
        elif tag in (7, 8, 16, 19, 20):  # Class/String/MethodType/Module/Package
            out.extend(class_bytes[off:off + 2]); off += 2
        elif tag in (9, 10, 11, 12, 17, 18):  # Field/Method/IMethod/NameType/Dyn/InvDyn
            out.extend(class_bytes[off:off + 4]); off += 4
        else:
            raise ValueError("unknown constant pool tag %d at cp#%d" % (tag, idx))
        idx += 1
    out.extend(class_bytes[off:])
    return bytes(out), replaced


def build_patch(src_jar, out_jar):
    """Emit BOTH the original org/tukaani/xz package (unmodified) and the
    relocated org/apache/pulsar/shade/org/tukaani/xz package. The original
    copy is needed by unshaded commons-compress; the relocated copy is needed
    by pulsar's shaded commons-compress. Both are small and side-effect free.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_jar)), exist_ok=True)
    written = 0
    with zipfile.ZipFile(src_jar) as zin, zipfile.ZipFile(out_jar, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if not name.endswith(".class"):
                continue
            if "module-info" in name or "package-info" in name:
                continue
            if not name.startswith("org/tukaani/xz/"):
                continue
            data = zin.read(name)
            # 1) original package, byte-for-byte (for unshaded commons-compress)
            zout.writestr(name, data)
            written += 1
            # 2) relocated shaded package (for pulsar's shaded commons-compress)
            new_data, _ = relocate_utf8_in_class(data)
            dst = DST_PREFIX.decode() + "/" + name[len("org/tukaani/xz/"):]
            zout.writestr(dst, new_data)
            written += 1
    return written


def verify(out_jar):
    needles = [b"LZMAInputStream", b"LZMAOutputStream", b"LZMA2Options", b"MemoryLimitException"]
    found = {n: False for n in needles}
    total = 0
    shaded = 0
    with zipfile.ZipFile(out_jar) as z:
        for name in z.namelist():
            total += 1
            if name.startswith("org/apache/pulsar/shade/org/tukaani/xz/"):
                shaded += 1
            elif not name.startswith("org/tukaani/xz/"):
                raise AssertionError("unexpected entry: " + name)
            data = z.read(name)
            for n in needles:
                if n in data:
                    found[n] = True
    if shaded == 0:
        raise AssertionError("no shaded entries in patch jar")
    return total, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xz_jar")
    ap.add_argument("out_jar")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if not os.path.isfile(args.xz_jar):
        print("FATAL: xz jar missing: %s" % args.xz_jar, file=sys.stderr)
        return 2
    n = build_patch(args.xz_jar, args.out_jar)
    total, found = verify(args.out_jar)
    print("PATCH_OK out=%s classes=%d" % (args.out_jar, n))
    print("VERIFY total=%d %s" % (total, " ".join("%s=%s" % (k.decode(), v) for k, v in found.items())))
    if not all(found.values()):
        print("FATAL: patch jar missing required classes", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
