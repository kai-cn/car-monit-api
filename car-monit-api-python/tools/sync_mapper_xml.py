# -*- coding: utf-8 -*-
"""把 Java 工程的 Mapper XML 同步进 Python 发布物（P0-1，见 docs/迁移审阅报告.md）。

为什么需要
----------
``app/db/registry.py`` 的 classpath 同时扫描父工程（Java 源码树）与 Python 树，
开发机上两者都在，因此 XML 永远能找到；但**独立部署 Python 目录**时父工程不存在，
22 个 XML / 54 条 statement 会全部丢失 —— Mapper 静默退回“移植期臆造实现”或抛
``Invalid bound statement``。本脚本把 XML 原样复制到 Python 树的
``pro-business-api/src/main/resources/com/ruoyi/base/mapper/xml/``，
让发布物自包含。``resources`` 目录本就在 registry 的扫描路径上，无需改代码。

用法
----
    python tools/sync_mapper_xml.py            # 同步（复制 + 删除多余副本）
    python tools/sync_mapper_xml.py --check    # 只校验一致性，漂移则 exit 1（CI 用）

等价性说明
----------
逐字节复制，不修改 XML 内容；SQL 文本与 Java 侧完全一致。
Java 侧新增/修改 XML 后必须重跑本脚本（``--check`` 漂移即红）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
#: Java 源码树（worktree/父工程）里的 XML 唯一来源
JAVA_XML_DIR = ROOT.parent / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi" / "base" / "mapper" / "xml"
#: Python 发布物内的副本（registry 已扫描 resources 根）
PACKAGE_XML_DIR = ROOT / "pro-business-api" / "src" / "main" / "resources" / "com" / "ruoyi" / "base" / "mapper" / "xml"


def collect_sources() -> list[Path]:
    return sorted(JAVA_XML_DIR.glob("*Mapper.xml")) if JAVA_XML_DIR.is_dir() else []


def sync() -> int:
    """复制 XML 到 Python 发布物，并删除发布物里的多余副本。"""
    sources = collect_sources()
    if not sources:
        print("ERROR: Java 源码树未找到任何 *Mapper.xml: %s" % JAVA_XML_DIR)
        return 1
    PACKAGE_XML_DIR.mkdir(parents=True, exist_ok=True)
    for source in sources:
        target = PACKAGE_XML_DIR / source.name
        target.write_bytes(source.read_bytes())
        print("sync  %s" % source.name)
    expected = {path.name for path in sources}
    for stale in PACKAGE_XML_DIR.glob("*Mapper.xml"):
        if stale.name not in expected:
            stale.unlink()
            print("rm    %s（Java 侧已删除）" % stale.name)
    print("done  : %d file(s) -> %s" % (len(sources), PACKAGE_XML_DIR))
    return 0


def check() -> int:
    """校验发布物副本与 Java 源逐字节一致；漂移 exit 1。"""
    sources = collect_sources()
    if not sources:
        print("ERROR: Java 源码树未找到任何 *Mapper.xml: %s" % JAVA_XML_DIR)
        return 1
    problems: list[str] = []
    for source in sources:
        target = PACKAGE_XML_DIR / source.name
        if not target.is_file():
            problems.append("缺失 %s" % source.name)
        elif target.read_bytes() != source.read_bytes():
            problems.append("漂移 %s（Java 侧已修改，需重新 sync）" % source.name)
    for stale in PACKAGE_XML_DIR.glob("*Mapper.xml"):
        if stale.name not in {p.name for p in sources}:
            problems.append("多余 %s（Java 侧已删除）" % stale.name)
    if problems:
        for item in problems:
            print("FAIL  " + item)
        print("=> 运行 python tools/sync_mapper_xml.py 重新同步")
        return 1
    print("ok    : %d packaged mapper XML(s) 与 Java 源一致" % len(sources))
    return 0


def main() -> int:
    return check() if "--check" in sys.argv else sync()


if __name__ == "__main__":
    sys.exit(main())
