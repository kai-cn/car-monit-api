# -*- coding: utf-8 -*-
"""pytest 全局夹具。

真实中间件环境隔离（P2-3）：单元测试必须与"本机是否起了真实中间件"无关——
开发者 shell 里若 export 过 ``CAR_MONIT_REDIS_URL`` / ``CAR_MONIT_ES_URL``，
不带 ``integration`` 标记的用例会被剥掉这些变量，防止替身单测意外连上真实
服务（反之，缺服务时集成测试按自身 skipif 跳过，不影响单元测试）。
"""
from __future__ import annotations

import os

import pytest

_ISOLATED_KEYS = ("CAR_MONIT_REDIS_URL", "CAR_MONIT_ES_URL")


@pytest.fixture(autouse=True)
def _isolate_real_middleware_env(request):
    if request.node.get_closest_marker("integration") is not None:
        yield
        return
    saved = {}
    for key in _ISOLATED_KEYS:
        if key in os.environ:
            saved[key] = os.environ.pop(key)
    yield
    for key, value in saved.items():
        os.environ[key] = value
