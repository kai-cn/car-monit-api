# -*- coding: utf-8 -*-
"""V2 P1 修复回归测试（依据 docs/迁移审阅报告.md P1 清单）。

P1-1：Java ``BigDecimal`` 还原为 ``decimal.Decimal``——字段类型、DB 结果映射、
请求绑定、Jackson/fastjson2 序列化全链路十进制精确（不再丢尾零/大数精度）。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

import bootstrap  # noqa: F401


def test_domain_fields_are_decimal() -> None:
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    entity = OdsLwzxsfsjFeeRecords01()
    entity.setFee(Decimal("1.50"))
    entity.setPayfee(Decimal("12345678901234567890.12"))
    assert entity.getFee() == Decimal("1.50")
    assert entity.getPayfee() == Decimal("12345678901234567890.12")


def test_jackson_response_writes_exact_decimal_text() -> None:
    """Jackson 对 BigDecimal 输出精确十进制（保留 scale），不走 float。"""
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
    from app.web.responses import JacksonResponse
    from app.web.serializer import to_jsonable

    entity = OdsLwzxsfsjFeeRecords01()
    entity.setFee(Decimal("1.50"))
    entity.setPayfee(Decimal("12345678901234567890.12"))
    body = JacksonResponse(content=to_jsonable(entity)).body
    assert b'"fee":1.50' in body, body
    assert b'"payfee":12345678901234567890.12' in body, body


def test_fastjson_writes_exact_decimal_text() -> None:
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
    from com.alibaba.fastjson2.JSON import JSON

    entity = OdsLwzxsfsjFeeRecords01()
    entity.setFee(Decimal("1.50"))
    text = JSON.toJSONString(entity)
    assert '"fee":1.50' in text, text


def test_fastjson_json_entity_json_roundtrip_is_byte_identical() -> None:
    """H1 回归：JSON 文本 → 实体 → JSON 文本必须逐字节一致。

    覆盖两类此前会失真的形态：带 scale 的小数（``1.50`` 不能变 ``1.5``）
    与超出 double 精度的大数（不能变科学计数法）。
    """
    from com.alibaba.fastjson2.JSON import JSON
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    text = '{"fee":1.50,"payfee":12345678901234567890.12}'
    entity = JSON.parseObject(text, OdsLwzxsfsjFeeRecords01)
    assert isinstance(entity.getFee(), Decimal)
    assert str(entity.getFee()) == "1.50"          # scale 保留
    assert str(entity.getPayfee()) == "12345678901234567890.12"
    assert JSON.toJSONString(entity) == text        # 逐字节一致


def test_bigdecimal_result_type_maps_to_decimal() -> None:
    from app.db.proxy import resolve_type
    from app.db.xml_mapper import coerce_value

    assert resolve_type("java.math.BigDecimal") is Decimal
    assert resolve_type("BigDecimal") is Decimal
    assert coerce_value("1.50", Decimal) == Decimal("1.50")
    assert coerce_value(3, Decimal) == Decimal("3")


def test_request_param_binds_to_decimal_field() -> None:
    """``@RequestParam``/表单值 "1.50" -> Decimal 字段（Spring 转换器语义）。"""
    from app.web.binding import bind_value

    value = bind_value("1.50", Decimal, "fee")
    assert value == Decimal("1.50")
    assert isinstance(value, Decimal)


def test_wrapper_predicate_compares_decimal_against_float_string() -> None:
    """QueryWrapper 谓词对 Decimal 列与字符串值的比较（SnapshotFlowSync 场景）。"""
    from com.baomidou.mybatisplus.core.conditions.query.QueryWrapper import QueryWrapper

    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    entity = OdsLwzxsfsjFeeRecords01()
    entity.setFee(Decimal("1.50"))
    wrapper = QueryWrapper().ge("fee", "1.5")
    assert wrapper.toPredicate()(entity) is True
    wrapper = QueryWrapper().gt("fee", "1.50")
    assert wrapper.toPredicate()(entity) is False


# ---------------------------------------------------------------- P1-2 worker 线程数
def test_worker_threads_setting(monkeypatch) -> None:
    from app.settings import Settings

    monkeypatch.delenv("APP_SERVER_WORKER_THREADS", raising=False)
    assert Settings().worker_threads == 40  # 与 anyio 缺省一致
    monkeypatch.setenv("APP_SERVER_WORKER_THREADS", "200")
    assert Settings().worker_threads == 200
    monkeypatch.setenv("APP_SERVER_WORKER_THREADS", "0")
    assert Settings().worker_threads == 1  # 下限保护


# ---------------------------------------------------------------- P1-3 可观测性
def test_request_id_header_and_metrics_endpoint() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")  # 自动生成并回写

    inbound = client.get("/health/live", headers={"X-Request-ID": "rid-42"})
    assert inbound.headers.get("X-Request-ID") == "rid-42"  # 沿用入站值

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "app_requests_total" in text
    assert 'app_responses_total{status="200"}' in text


def test_metrics_counts_404_and_access_log(caplog) -> None:
    import logging

    from fastapi.testclient import TestClient

    from app.main import app
    from app.observability import metrics_text

    caplog.set_level(logging.INFO, logger="app.access")
    client = TestClient(app, raise_server_exceptions=False)
    client.get("/__definitely_not_a_route__")
    text = metrics_text()
    assert 'app_responses_total{status="404"}' in text
    assert any("rid=" in record.message for record in caplog.records
               if record.name == "app.access")
