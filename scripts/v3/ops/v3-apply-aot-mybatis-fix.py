#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-apply-aot-mybatis-fix.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Propagate the Spring Boot 4 AOT / MyBatis-Plus mapper fix to all six worktrees.

Source of truth: car-monit-api-jdk25/pro-business-api/.../NativeMapperSqlSessionFactoryRegistrar.java
The class is package-agnostic; only the `package` declaration is rewritten per target.

Targets:
  api     jdk{17,21,25}  -> <root>/pro-business-api/src/main/java/com/ruoyi/base/config
  backend jdk{17,21,25}  -> ruoyi-framework/src/main/java/com/ruoyi/framework/config

Idempotent: existing files are overwritten with the canonical source.
"""
import os
import sys

ROOT = r"D:\work\IdeaProjects"
SOURCE = os.path.join(
    ROOT, "car-monit-api-jdk25", "pro-business-api", "src", "main", "java",
    "com", "ruoyi", "base", "config", "NativeMapperSqlSessionFactoryRegistrar.java",
)
NAME = "NativeMapperSqlSessionFactoryRegistrar.java"


def main():
    src = open(SOURCE, encoding="utf-8").read()
    body = src.split("\n", 1)[1] if src.startswith("package ") else src
    # strip the original package line, keep everything after it
    lines = src.splitlines(True)
    idx = next(i for i, l in enumerate(lines) if l.startswith("package "))
    tail = "".join(lines[idx + 1:])

    ok = 0
    for app in ("api", "backend"):
        for jdk in ("17", "21", "25"):
            if app == "api":
                pkg = "com.ruoyi.base.config"
                rel = os.path.join("pro-business-api", "src", "main", "java",
                                   "com", "ruoyi", "base", "config")
            else:
                pkg = "com.ruoyi.framework.config"
                rel = os.path.join("ruoyi-framework", "src", "main", "java",
                                   "com", "ruoyi", "framework", "config")
            dst_dir = os.path.join(ROOT, "car-monit-%s-jdk%s" % (app, jdk), rel)
            if not os.path.isdir(dst_dir):
                print("SKIP (dir missing): " + dst_dir)
                continue
            dst = os.path.join(dst_dir, NAME)
            content = "package %s;\n%s" % (pkg, tail)
            # keep the Javadoc pointer valid in every worktree
            previous = open(dst, encoding="utf-8").read() if os.path.isfile(dst) else None
            open(dst, "w", encoding="utf-8", newline="\n").write(content)
            state = "unchanged" if previous == content else ("updated" if previous else "created")
            print("%-9s jdk%-3s %-9s %s" % (app, jdk, state, dst))
            ok += 1
    print("targets_ok=%d" % ok)
    return 0 if ok == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
