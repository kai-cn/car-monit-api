# -*- coding: utf-8 -*-
"""P1-5：真实数据库集成测试（默认跳过，需显式开启）。

开启方式：``CAR_MONIT_TEST_DB=1``（并确保 application-local.yml / 环境变量
里有可达的 GaussDB 连接信息）。CI 默认不跑；接入 DB service container 后
可在 CI 中开启。
"""
from __future__ import annotations

import os

import pytest

import bootstrap  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("CAR_MONIT_TEST_DB") != "1",
                       reason="需要真实 GaussDB：设置 CAR_MONIT_TEST_DB=1 开启"),
]


def test_real_database_reachable_and_queryable() -> None:
    from app.db.engine import get_database

    rows = get_database().query("SELECT 1 AS one")
    assert rows == [{"one": 1}]


def test_real_database_jl_data01_schema_present() -> None:
    """业务 schema 存在性（TODO(V2/决策④)：生产 search_path 待确认）。"""
    from app.db.engine import get_database

    rows = get_database().query(
        "SELECT count(*) AS c FROM information_schema.schemata "
        "WHERE schema_name = 'jl_data01'")
    assert rows[0]["c"] == 1, "jl_data01 schema 不存在（决策④ 相关）"
