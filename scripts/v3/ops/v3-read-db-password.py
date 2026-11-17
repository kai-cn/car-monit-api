#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-read-db-password.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Read the local openGauss container's GS_PASSWORD without printing it anywhere.

The value is emitted on stdout ONLY, with no label, so callers can capture it:
  PowerShell: $p = (& python v3-read-db-password.py) -join ''
  Bash:       P=$(python v3-read-db-password.py)

It is never written to a file, never logged and never embedded in a command line.
Falls back to a second docker invocation form when the first returns nothing.
"""
import subprocess
import sys

DISTRO = "openEuler-24.03-LTS-SP4"
CONTAINER = "opengauss"
FORMAT = 'docker inspect opengauss --format "{{range .Config.Env}}{{println .}}{{end}}"'


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout or ""
    except Exception:
        return ""


def main():
    candidates = [
        run(["wsl.exe", "-d", DISTRO, "--", "bash", "-c", FORMAT]),
        run(["wsl.exe", "-d", DISTRO, "--", "bash", "-lc", FORMAT]),
    ]
    for out in candidates:
        for line in out.splitlines():
            if "GS_PASSWORD=" in line:
                value = line.split("GS_PASSWORD=", 1)[1].strip()
                if value:
                    print(value)
                    return 0
    print("GS_PASSWORD_NOT_FOUND", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
