# -*- coding: utf-8 -*-
"""Phase 2a smoke tests: skeleton, health, error body, JSON, binding."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.web.binding import BindingError, bind_bean
from app.web.serializer import java_pattern_to_strftime, to_jsonable
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("UP", "DEGRADED")
    assert body["app"] == "car-monit-api"
    # application.yml is the single configuration source
    assert body["config"]["server.port"] == 9901
    assert body["config"]["isLocalhost"] == "local"


def test_not_found_uses_spring_error_body() -> None:
    with TestClient(app) as client:
        response = client.get("/base/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    # 实测 Java 进程的 404 响应体始终带 message 键（空串），键顺序如下
    assert list(body) == ["timestamp", "status", "error", "message", "path"]
    assert body["status"] == 404
    assert body["error"] == "Not Found"
    assert body["message"] == ""
    assert body["path"] == "/base/does-not-exist"


def test_error_endpoint_matches_basic_error_controller() -> None:
    """直接命中 /error：Spring 拿不到错误属性，固定回 HTTP 500 + status=999。"""
    with TestClient(app) as client:
        response = client.get("/error")
    assert response.status_code == 500
    body = response.json()
    # 没有 path 键：ERROR_REQUEST_URI 为 null
    assert list(body) == ["timestamp", "status", "error", "message"]
    assert body["status"] == 999
    assert body["error"] == "None"
    assert body["message"] == ""


def test_ajax_result_omits_null_data() -> None:
    assert to_jsonable(AjaxResult.success()) == {"code": 200, "msg": "操作成功"}
    assert to_jsonable(AjaxResult.success({"id": 1})) == {
        "code": 200,
        "msg": "操作成功",
        "data": {"id": 1},
    }


def test_table_data_info_field_order() -> None:
    table = TableDataInfo(rows=[], total=7)
    table.setCode(200)
    table.setMsg("查询成功")
    assert list(to_jsonable(table)) == ["total", "rows", "code", "msg"]


def test_java_date_pattern() -> None:
    assert java_pattern_to_strftime("yyyy-MM-dd HH:mm:ss") == "%Y-%m-%d %H:%M:%S"


def test_datetime_is_shifted_to_utc_like_jackson() -> None:
    # DB session is Asia/Shanghai (serverTimezone in the JDBC URL), Jackson
    # default timezone is UTC -> 10:00 +08:00 is emitted as 02:00 UTC.
    value = dt.datetime(2025, 8, 29, 10, 0, 0)
    assert to_jsonable(value) == "2025-08-29T02:00:00.000+00:00"


def test_camel_case_property_names() -> None:
    entity = OdsSzdnGantry()
    entity.gantry_code = "G01"
    payload = to_jsonable(entity)
    assert payload["gantryCode"] == "G01"
    assert payload["gantryName"] is None  # Jackson writes nulls


def test_model_attribute_binding() -> None:
    bean = bind_bean(OdsSzdnGantry, {"gantryCode": "G01", "gantry_name": "门架1", "unknown": "x"})
    assert bean.gantry_code == "G01"
    assert bean.gantry_name == "门架1"


def test_binding_failure_is_reported() -> None:
    # ZdataTrailTracks.type is an Integer, so a non-numeric value is a BindException in Spring
    try:
        bind_bean(ZdataTrailTracks, {"type": "not-a-number"})
    except BindingError as error:
        assert error.field == "type"
    else:  # pragma: no cover
        raise AssertionError("BindingError expected")
