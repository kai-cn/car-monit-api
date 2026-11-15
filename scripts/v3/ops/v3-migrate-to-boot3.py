#!/usr/bin/env python3
"""Migrate a car-monit-api branch from Spring Boot 4 (Jackson 3) to Spring Boot 3.5.x.

Why
---
Spring Boot 4 refuses to start a GraalVM native image that is not built on Java 25
(`NativeImageRequirementsException`). For the JDK17/JDK21 native lines we therefore
need a Spring Boot 3.5.x branch, which is the last line that supports Java 17/21
natively.

What it changes
---------------
pom.xml (parent):
  * spring-boot-starter-parent   4.1.2  -> 3.5.6
  * druid-spring-boot-4-starter        -> druid-spring-boot-3-starter
  * mybatis-plus-spring-boot4-starter  -> mybatis-plus-spring-boot3-starter
  * dynamic-datasource-spring-boot4-starter -> ...-spring-boot3-starter
  * pagehelper-spring-boot-starter    4.1.1 -> 2.1.0
  * dynamic-datasource.version        4.6.0 -> 4.3.0

module poms:
  * spring-boot-starter-webmvc -> spring-boot-starter-web (Boot 4 split artifact)
  * the three *-boot-4 starters above

java sources:
  * tools.jackson.* (Jackson 3) -> com.fasterxml.jackson.* (Jackson 2)

Usage
-----
    python3 v3-migrate-to-boot3.py <repo-dir> [--apply]

Without --apply it only reports what would change.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

POM_RULES = [
    ("<version>4.1.2</version>", "<version>3.5.6</version>"),
    ("druid-spring-boot-4-starter", "druid-spring-boot-3-starter"),
    ("mybatis-plus-spring-boot4-starter", "mybatis-plus-spring-boot3-starter"),
    ("dynamic-datasource-spring-boot4-starter", "dynamic-datasource-spring-boot3-starter"),
    ("spring-boot-starter-webmvc", "spring-boot-starter-web"),
    # Boot 4 split these out of the core; Boot 3 has the aop starter and a plain
    # spring-kafka artifact published under org.springframework.kafka.
    ("<groupId>org.springframework.boot</groupId>\n"
     "            <artifactId>spring-boot-starter-kafka</artifactId>",
     "<groupId>org.springframework.kafka</groupId>\n"
     "            <artifactId>spring-kafka</artifactId>"),
    ("spring-boot-starter-aspectj", "spring-boot-starter-aop"),
    ("<pagehelper.boot.version>4.1.1</pagehelper.boot.version>",
     "<pagehelper.boot.version>2.1.0</pagehelper.boot.version>"),
    ("<dynamic-datasource.version>4.6.0</dynamic-datasource.version>",
     "<dynamic-datasource.version>4.3.0</dynamic-datasource.version>"),
]

JAVA_IMPORT_RULES = [
    (re.compile(r"\borg\.springframework\.boot\.webmvc\b"), None),  # no-op marker
    (re.compile(r"\btools\.jackson\.databind\b"), "com.fasterxml.jackson.databind"),
    (re.compile(r"\btools\.jackson\.core\b"), "com.fasterxml.jackson.core"),
    (re.compile(r"\btools\.jackson\.annotation\b"), "com.fasterxml.jackson.annotation"),
]


def iter_files(root: str, suffixes: tuple[str, ...]):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("target", ".git", ".workbuddy")]
        for name in files:
            if name.endswith(suffixes):
                yield os.path.join(base, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print(f"FATAL: not a directory: {repo}", file=sys.stderr)
        return 3

    pom_changes = 0
    for path in iter_files(repo, ("pom.xml",)):
        text = open(path, encoding="utf-8").read()
        new = text
        for old, rep in POM_RULES:
            if old in new:
                count = new.count(old)
                new = new.replace(old, rep)
                print(f"  pom {os.path.relpath(path, repo)}: {old} -> {rep} (x{count})")
                pom_changes += count
        if new != text and args.apply:
            open(path, "w", encoding="utf-8", newline="\n").write(new)

    java_changes = 0
    touched = []
    for path in iter_files(repo, (".java",)):
        text = open(path, encoding="utf-8").read()
        new = text
        for pattern, rep in JAVA_IMPORT_RULES:
            if rep is None:
                continue
            new = pattern.sub(rep, new)
        if new != text:
            java_changes += 1
            touched.append(os.path.relpath(path, repo))
            if args.apply:
                open(path, "w", encoding="utf-8", newline="\n").write(new)

    print(f"\npom replacements : {pom_changes}")
    print(f"java files       : {java_changes}")
    for t in touched:
        print("  ", t)
    print("applied" if args.apply else "dry-run (pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
