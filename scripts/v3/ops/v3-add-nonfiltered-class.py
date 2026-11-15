#!/usr/bin/env python3
"""Ensure maven-resources-plugin in api pom.xml does not filter binary .class files.

Needed because the parent pom sets src/main/resources filtering=true, and the
pulsar-xz native patch ships .class files there (see v3-build-pulsar-xz-patch.py).
Idempotent; default is dry-run, pass --apply to write. Backs up before writing.
"""
import argparse
import os
import shutil
import sys

OLD = """                <artifactId>maven-resources-plugin</artifactId>
                <version>3.3.1</version>
            </plugin>"""
NEW = """                <artifactId>maven-resources-plugin</artifactId>
                <version>3.3.1</version>
                <configuration>
                    <!-- src/main/resources is filtered=true in the parent pom.
                         The pulsar-xz native patch ships binary .class files there;
                         exclude them from filtering to avoid MalformedInputException. -->
                    <nonFilteredFileExtensions>
                        <nonFilteredFileExtension>class</nonFilteredFileExtension>
                    </nonFilteredFileExtensions>
                </configuration>
            </plugin>"""
MARK = "<nonFilteredFileExtension>class</nonFilteredFileExtension>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poms", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rc = 0
    for path in args.poms:
        if not os.path.isfile(path):
            print("MISSING %s" % path); rc = 2; continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if MARK in text:
            print("ALREADY %s" % path); continue
        if OLD not in text:
            print("NO_MATCH %s" % path); rc = 3; continue
        new_text = text.replace(OLD, NEW, 1)
        if args.apply:
            backup = path + ".bak-nonfiltered"
            shutil.copy2(path, backup)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
            print("APPLIED %s (backup=%s)" % (path, os.path.basename(backup)))
        else:
            print("DRYRUN  %s" % path)
    return rc


if __name__ == "__main__":
    sys.exit(main())
