# -*- coding: utf-8 -*-
"""P1-5：把根目录 23 个迁移期冒烟脚本纳入 pytest 回归网（子进程隔离）。

这些脚本是迁移各阶段（t08/t09/t10）的行为断言，此前只能手工运行。
失败判定综合三种历史约定：
  * 退出码非 0（部分脚本 ``sys.exit(main())``）；
  * stdout 出现以 ``FAIL`` 开头的行（``check()`` 收集的失败）；
  * stdout 含 ``SMOKE FAILED`` 标记。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted(ROOT.glob("_smoke_*.py"))


def test_smoke_scripts_exist() -> None:
    assert len(SCRIPTS) >= 20, "迁移期冒烟脚本应至少有 20 个，实际 %d" % len(SCRIPTS)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_smoke_script_passes(script: Path, tmp_path) -> None:
    env = dict(os.environ)
    env["CAR_MONIT_RUNTIME"] = "shim"          # 替身可用（脚本全部按内存后端编写）
    env["APP_SCHEDULER_ENABLED"] = "false"
    env["OPTIMIZATION_EXPORT_DIR"] = str(tmp_path)
    env.pop("CAR_MONIT_REDIS_URL", None)       # 不做真实 Redis 穿透
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        timeout=300, env=env,
    )
    fail_lines = [line for line in result.stdout.splitlines()
                  if line.startswith("FAIL")]
    detail = ("exit=%s\nFAIL 行: %s\nstdout 尾部:\n%s\nstderr 尾部:\n%s"
              % (result.returncode, fail_lines[:5],
                 "\n".join(result.stdout.splitlines()[-15:]),
                 "\n".join(result.stderr.splitlines()[-15:])))
    assert result.returncode == 0, detail
    assert not fail_lines, detail
    assert "SMOKE FAILED" not in result.stdout, detail
