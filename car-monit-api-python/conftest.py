# -*- coding: utf-8 -*-
"""pytest bootstrap: register the Java-mirrored import roots."""
import os

# P0-2：测试固定运行在 shim 模式（替身可用）；prod 模式的守卫行为由
# tests/test_v2_p0.py 用 monkeypatch / 子进程专门验证。
os.environ.setdefault("CAR_MONIT_RUNTIME", "shim")

import bootstrap  # noqa: F401,E402
