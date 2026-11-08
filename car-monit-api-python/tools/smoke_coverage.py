# -*- coding: utf-8 -*-
"""P2：把 23 个迁移期冒烟脚本的执行计入覆盖率（``coverage run --append`` 循环）。

为什么不用 pytest-cov 的子进程钩子：那需要向共享 venv 的 site-packages 写入
全局 ``.pth``（会影响该 venv 的所有使用者）；改为独立工具按需 append，
不运行时完全不介入。

用法（在 pytest --cov 之后运行，向同一份 .coverage 追加数据）：
    python -m pytest -q --cov --cov-report=
    python tools/smoke_coverage.py
    python -m coverage report
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RCFILE = str(ROOT / "pyproject.toml")


def _failed(stdout: str) -> bool:
    return ("SMOKE FAILED" in stdout
            or any(line.startswith("FAIL") for line in stdout.splitlines()))


def main() -> int:
    scripts = sorted(ROOT.glob("_smoke_*.py"))
    if not scripts:
        print("ERROR: no _smoke_*.py found under %s" % ROOT)
        return 1
    env = dict(os.environ)
    env["CAR_MONIT_RUNTIME"] = "shim"
    env["APP_SCHEDULER_ENABLED"] = "false"
    env.pop("CAR_MONIT_REDIS_URL", None)
    env.pop("CAR_MONIT_ES_URL", None)
    env.pop("CAR_MONIT_KAFKA_URL", None)
    failures: list[str] = []
    for script in scripts:
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "run", "--append",
             "--rcfile", RCFILE, str(script)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            timeout=300, env=env)
        ok = result.returncode == 0 and not _failed(result.stdout)
        print("%-4s %s" % ("ok" if ok else "FAIL", script.name))
        if not ok:
            failures.append(script.name)
            tail = "\n".join((result.stdout + result.stderr).splitlines()[-10:])
            print("     " + tail.replace("\n", "\n     "))
    print("smoke coverage: %d/%d ok" % (len(scripts) - len(failures), len(scripts)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
