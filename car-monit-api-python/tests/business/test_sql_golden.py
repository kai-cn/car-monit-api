# -*- coding: utf-8 -*-
"""P1-5：SQL 渲染 golden 测试——54 条 statement 的渲染结果逐字节锁定。

与 test_phase2b 的"可渲染"断言不同，这里把**精确 SQL 文本**提交进仓库：
Java 侧 XML 或 Python 侧解释器的任何漂移都会让本测试变红。
重新生成：``CAR_MONIT_UPDATE_GOLDEN=1 python -m pytest tests/business/test_sql_golden.py``
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from app.db.registry import MapperRegistry
from app.db.xml_mapper import ParamObject

GOLDEN = Path(__file__).resolve().parent / "golden" / "sql_render.txt"


class _EmptyParams(ParamObject):
    """所有 <if> 为假、所有 <foreach> 为空列表（确定性渲染）。"""

    def __init__(self) -> None:
        super().__init__({}, None)

    def lookup(self, name: str):
        lowered = name.lower()
        if lowered.endswith("list") or lowered.endswith("ids"):
            return []
        return None


def _render_all() -> str:
    registry = MapperRegistry().load()
    lines: list[str] = []
    for full_id, statement in sorted(registry.statements.items()):
        rendered = statement.render(_EmptyParams(), registry.fragments)
        lines.append("-- %s" % full_id)
        lines.append(rendered.sql)
        lines.append("")
    return "\n".join(lines)


def test_statement_render_golden() -> None:
    actual = _render_all()
    if os.environ.get("CAR_MONIT_UPDATE_GOLDEN") == "1" or not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8", newline="\n")
        pytest.fail("golden 已重新生成（%s），请提交后重跑" % GOLDEN.name)
    expected = GOLDEN.read_text(encoding="utf-8")
    if actual != expected:
        # 给出第一处差异，便于定位
        for index, (a, b) in enumerate(zip(expected.splitlines(), actual.splitlines())):
            if a != b:
                pytest.fail("第 %d 行不一致:\n期望: %s\n实际: %s" % (index + 1, a, b))
        pytest.fail("行数不一致: 期望 %d 行 / 实际 %d 行"
                    % (len(expected.splitlines()), len(actual.splitlines())))
