# -*- coding: utf-8 -*-
"""check_secrets 门禁自测（复核 B-1：fail-open 与非 yml 明文识别）。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "check_secrets.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("check_secrets_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fail_open_guard_rejects_zero_files(monkeypatch) -> None:
    """扫描到 0 个文件时必须 exit 1，不能打印 no findings 后放行。"""
    tool = _load_tool()
    monkeypatch.setattr(tool, "_files", lambda: [])
    assert tool.main() == 1


def test_repo_root_untracked_plaintext_is_detected() -> None:
    """仓库根放一个未跟踪的明文样本，check_secrets 必须 exit 1。"""
    probe = ROOT / "secret_scan_probe_tmp.md"
    probe.write_text("database password: AnotherPlainPwd123\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            timeout=120)
        assert result.returncode == 1, result.stdout + result.stderr
        assert probe.name in result.stdout
    finally:
        # 本机删除会被转入回收站：先截断成 0 字节释放内容，再删空壳
        with probe.open("w", encoding="utf-8"):
            pass
        probe.unlink(missing_ok=True)
    assert not probe.exists()
