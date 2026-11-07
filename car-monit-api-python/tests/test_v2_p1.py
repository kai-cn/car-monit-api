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
