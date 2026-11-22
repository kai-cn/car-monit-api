# -*- coding: utf-8 -*-
"""Phase 2c: Spring MVC dispatcher parity.

The Java side registers 24 controllers with ``@RestController``; Spring derives
the route, the argument binding and the response from the annotations.  These
tests check the generated table and the runtime half (``app/routes/registry.py``)
without touching GaussDB: every handler used here is a local stand-in, the
controllers that need a database are only checked for *registration*.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.concurrency import run_in_threadpool

from app.routes import registry as registry_module
from app.routes.generated import ROUTES
from app.routes.registry import (
    ControllerRegistry,
    _specificity,
    register_all,
)
from app.web.responses import JacksonResponse
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.utils.PageUtils import PageUtils
from com.ruoyi.common.utils.ServletUtils import ServletUtils


@dataclass
class DemoEntity(JavaBean):
    """Stand-in for a ``com.ruoyi.base.domain`` dataclass."""

    car_no: Optional[str] = None
    page_size: Optional[int] = None
    create_time: Optional[_dt.datetime] = None


def _route(params: list[dict[str, Any]], returns: str = "Map<String, Object>",
           path: str = "/demo/{id}") -> dict[str, Any]:
    return {
        "controller": "com.ruoyi.base.controller.DemoController",
        "method": "demo",
        "http": "GET",
        "path": path,
        "class_path": "/demo",
        "returns": returns,
        "params": params,
        "java": "demo.java:1",
    }


def _client(route: dict[str, Any], handler: Any) -> TestClient:
    app = FastAPI(default_response_class=JacksonResponse)
    registry = ControllerRegistry(routes=[route])

    async def endpoint(request: Request):
        body = await request.body()
        return await run_in_threadpool(registry.invoke, route, handler, request, body)

    app.add_api_route(route["path"], endpoint, methods=[route["http"]])
    return TestClient(app)


# --------------------------------------------------------------------- table
def test_generated_table_covers_every_java_handler() -> None:
    # 【Java V3 对齐】master 24 Controller / 85 handler → V3 29 Controller / 110 handler。
    # 新增 5 个 V3 Controller（24 handler）+ LargeScaleQueryController.downloadExport（1 handler）。
    assert len(ROUTES) == 110
    # 【Java V3 对齐】5 个 V3 Controller 位于 controller/v3 子包
    assert len({route["controller"] for route in ROUTES}) == 29
    for route in ROUTES:
        assert route["path"].startswith("/")
        assert route["path"].count("{") == route["path"].count("}")
        assert route["http"] in {"GET", "POST", "PUT", "DELETE", "PATCH"}
        assert route["method"] and route["returns"]


def test_generated_paths_are_unique_per_verb() -> None:
    seen = {(route["path"], route["http"]) for route in ROUTES}
    assert len(seen) == len(ROUTES)


def test_specificity_puts_literal_paths_first() -> None:
    assert _specificity("/base/gantry/list") < _specificity("/base/gantry/{id}")
    assert (_specificity("/api/v1/unified/export/status/{taskId}")
            < _specificity("/api/v1/unified/{ds}/list"))
    assert _specificity("/base/gantry/listAll") < _specificity("/base/gantry/{id}")


def test_commented_out_java_methods_are_not_routes() -> None:
    """``SysUtilController`` keeps two ``@PostMapping`` blocks commented out."""
    paths = {route["path"] for route in ROUTES}
    assert "/base/sysutil/syncTrack" not in paths
    assert "/base/sysutil/syncSuspiciousCar" not in paths
    assert "/base/sysutil/changeTrailInfo" in paths


# ------------------------------------------------------------------ binding
def test_path_and_query_binding() -> None:
    seen: dict[str, Any] = {}

    def handler(ds: str, start_time: str, page_num: int, fuzzy: Optional[dict]) -> dict:
        seen.update(ds=ds, start_time=start_time, page_num=page_num, fuzzy=fuzzy)
        return {"ds": ds}

    route = _route([
        {"name": "ds", "java_name": "ds", "source": "path", "type": "str",
         "java_type": "String", "required": False, "default": None},
        {"name": "startTime", "java_name": "startTime", "source": "param", "type": "str",
         "java_type": "String", "required": True, "default": None},
        {"name": "pageNum", "java_name": "pageNum", "source": "param", "type": "int",
         "java_type": "int", "required": False, "default": "1"},
        {"name": "fuzzyFields", "java_name": "fuzzyFields", "source": "param_map", "type": "map",
         "java_type": "Map<String, String>", "required": False, "default": None},
    ], path="/demo/{ds}")

    response = _client(route, handler).get(
        "/demo/snapshot?startTime=2026-05-01&pageNum=3&fuzzyFields.platenumber=%E8%B5%A3A")
    assert response.status_code == 200
    assert seen["ds"] == "snapshot"
    assert seen["page_num"] == 3
    # Spring hands over *every* parameter, the prefix filter happens in the controller
    assert seen["fuzzy"]["startTime"] == "2026-05-01"
    assert seen["fuzzy"]["fuzzyFields.platenumber"] == "赣A"


def test_missing_required_parameter_is_400_with_spring_body() -> None:
    route = _route([
        {"name": "startTime", "java_name": "startTime", "source": "param", "type": "str",
         "java_type": "String", "required": True, "default": None},
    ])
    response = _client(route, lambda start_time: {}).get("/demo/1")
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == 400
    assert payload["error"] == "Bad Request"
    assert payload["path"] == "/demo/1"
    # server.error.include-message=never 不隐藏键本身：实测 Java 仍带 message，值为空串
    assert payload["message"] == ""


def test_first_parameter_value_wins_like_servlet_getParameter() -> None:
    kept: dict[str, Any] = {}

    def handler(page_num: int) -> dict:
        kept["page_num"] = page_num
        return {}

    route = _route([
        {"name": "pageNum", "java_name": "pageNum", "source": "param", "type": "int",
         "java_type": "int", "required": False, "default": None},
    ])
    _client(route, handler).get("/demo/1?pageNum=2&pageNum=9")
    assert kept["page_num"] == 2


def test_optional_parameter_without_value_is_none() -> None:
    kept: dict[str, Any] = {}

    def handler(cursor: Optional[str]) -> dict:
        kept["cursor"] = cursor
        return {}

    route = _route([
        {"name": "cursor", "java_name": "cursor", "source": "param", "type": "str",
         "java_type": "String", "required": False, "default": None},
    ], returns="TableDataInfo")
    assert _client(route, handler).get("/demo/1").status_code == 200
    assert kept["cursor"] is None


def test_number_conversion_failure_is_400() -> None:
    route = _route([
        {"name": "pageNum", "java_name": "pageNum", "source": "param", "type": "int",
         "java_type": "int", "required": False, "default": "1"},
    ])
    assert _client(route, lambda page_num: {}).get("/demo/1?pageNum=abc").status_code == 400


# ---------------------------------------------------------------- model/body
def test_model_binding_uses_java_names_and_converts_types(monkeypatch) -> None:
    monkeypatch.setattr(registry_module, "_resolve_class", lambda name: DemoEntity)
    kept: dict[str, Any] = {}

    def handler(demo: DemoEntity) -> dict:
        kept["demo"] = demo
        return {}

    route = _route([
        {"name": "demo", "java_name": "demo", "source": "model", "type": "DemoEntity",
         "java_type": "DemoEntity", "required": False, "default": None},
    ])
    _client(route, handler).get("/demo/1?carNo=赣A12345&pageSize=20&unknown=x")
    demo = kept["demo"]
    assert isinstance(demo, DemoEntity)
    assert demo.car_no == "赣A12345"
    assert demo.page_size == 20
    assert demo.create_time is None


def test_body_binding_to_entity(monkeypatch) -> None:
    monkeypatch.setattr(registry_module, "_resolve_class", lambda name: DemoEntity)
    kept: dict[str, Any] = {}

    def handler(demo: DemoEntity) -> dict:
        kept["demo"] = demo
        return {"code": 200}

    route = _route([
        {"name": "demo", "java_name": "demo", "source": "body", "type": "DemoEntity",
         "java_type": "DemoEntity", "required": True, "default": None},
    ], path="/demo/body")
    route["http"] = "POST"
    response = _client(route, handler).post("/demo/body", json={"carNo": "赣A1", "pageSize": 5})
    assert response.status_code == 200
    assert kept["demo"].car_no == "赣A1"
    assert kept["demo"].page_size == 5


def test_body_map_coerces_scalars_to_strings() -> None:
    kept: dict[str, Any] = {}

    def handler(fields: dict) -> dict:
        kept["fields"] = fields
        return {}

    route = _route([
        {"name": "fuzzyFields", "java_name": "fuzzyFields", "source": "body", "type": "map",
         "java_type": "Map<String, String>", "required": False, "default": None},
    ], path="/demo/body")
    route["http"] = "POST"
    response = _client(route, handler).post("/demo/body", json={"a": 1, "b": True, "c": "x"})
    assert response.status_code == 200
    assert kept["fields"] == {"a": "1", "b": "true", "c": "x"}


def test_missing_required_body_is_400_and_json_type_is_415() -> None:
    route = _route([
        {"name": "demo", "java_name": "demo", "source": "body", "type": "map",
         "java_type": "Map<String, String>", "required": True, "default": None},
    ], path="/demo/body")
    route["http"] = "POST"
    client = _client(route, lambda demo: {})
    assert client.post("/demo/body").status_code == 400
    assert client.post("/demo/body", content=b"x=1",
                       headers={"content-type": "application/x-www-form-urlencoded"}).status_code == 415


# -------------------------------------------------------------- responses
def test_void_handler_returns_empty_200() -> None:
    route = _route([], returns="void", path="/demo/void")
    response = _client(route, lambda: None).get("/demo/void")
    assert response.status_code == 200
    assert response.content == b""


def test_entity_response_uses_jackson_field_names() -> None:
    route = _route([], path="/demo/entity")
    entity = DemoEntity(car_no="赣A1", page_size=3)
    payload = _client(route, lambda: entity).get("/demo/entity").json()
    assert payload["carNo"] == "赣A1"
    assert payload["pageSize"] == 3
    assert payload["createTime"] is None


# --------------------------------------------------------- web context
def test_servlet_request_context_is_visible_inside_the_handler() -> None:
    kept: dict[str, Any] = {}

    def handler() -> dict:
        kept["pageNum"] = ServletUtils.getParameter("pageNum")
        kept["uri"] = ServletUtils.getRequest().getRequestURI()
        return {}

    route = _route([], path="/demo/context")
    _client(route, handler).get("/demo/context?pageNum=7")
    assert kept == {"pageNum": "7", "uri": "/demo/context"}


def test_page_helper_context_is_cleared_after_each_request() -> None:
    seen: list[Any] = []

    def handler() -> dict:
        seen.append(PageUtils._context())
        PageUtils.startPage()          # what BaseController.startPage() does
        seen.append(PageUtils._context())
        return {}

    route = _route([], path="/demo/page")
    client = _client(route, handler)
    client.get("/demo/page?pageNum=2&pageSize=5")
    client.get("/demo/page")
    assert seen[0] is None                 # nothing leaks from the previous request
    assert seen[1].page_num == 2
    assert seen[2] is None
    assert PageUtils._context() is None


# --------------------------------------------------------------- real app
def test_real_app_registers_every_available_controller() -> None:
    app = FastAPI(default_response_class=JacksonResponse)
    count = register_all(app)
    report = app.state.route_report
    assert count == report.routes
    assert report.routes + len(report.skipped) == len(ROUTES)
    assert not report.duplicates
    assert not report.missing_methods
    # the three optimization controllers still miss their service modules
    assert {name.rsplit(".", 1)[-1] for name in report.unavailable} <= {
        "LargeScaleQueryController", "ProgressiveQueryController", "UnifiedQueryController",
    }


def test_openapi_documents_path_parameters() -> None:
    app = FastAPI(default_response_class=JacksonResponse)
    register_all(app)
    schema = app.openapi()
    operation = schema["paths"]["/base/gantry/{id}"]["get"]
    assert operation["parameters"][0]["name"] == "id"
    assert operation["parameters"][0]["in"] == "path"
    assert operation["parameters"][0]["required"] is True
