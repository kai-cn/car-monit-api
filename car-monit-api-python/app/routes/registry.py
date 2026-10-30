# -*- coding: utf-8 -*-
"""Route registration for the 24 ``@RestController`` classes.

Migrated from: org.springframework.web.servlet.DispatcherServlet
                org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping
                org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter
                org.springframework.web.servlet.handler.AbstractHandlerMethodMapping$MatchComparator
                (``AntPatternComparator``)

The table in ``app/routes/generated.py`` is produced from the Java sources, so
this module only has to reproduce the *runtime* half of Spring MVC:

============================  ==================================================
Spring                         here
============================  ==================================================
``@RestController`` singleton  one Python instance per controller class
``RequestMappingHandlerMapping`` ``_specificity()`` ordering + Starlette router
argument resolvers             :func:`_bind_arguments`
``HttpMessageConverter``       :mod:`app.web.serializer` (Jackson shapes)
``BasicErrorController``       :mod:`app.web.errors`
``RequestContextHolder``       the ported ``ServletUtils`` stand-in
``PageHelper`` ThreadLocal     ``BaseController.startPage()`` + ``PageUtils``
============================  ==================================================

Behaviour that is reproduced on purpose
---------------------------------------
* **Path order**: ``/base/gantry/list`` wins over ``/base/gantry/{id}``.  Starlette
  matches routes in registration order while Spring sorts by specificity, so the
  table is sorted with the same comparator (fewer URI variables first, then the
  longer literal pattern).
* **``@RequestParam`` is required by default**: a missing parameter answers 400.
  ``defaultValue`` wins over ``required``, ``required = false`` passes ``None``.
* **``@RequestParam Map<String,String>`` receives every request parameter**
  (``RequestParamMapMethodArgumentResolver``), flattened to the *first* value per
  name -- see :func:`_first_values` for the bytecode-verified detail.
* **``void`` handler** writes an empty body, everything else is serialised by
  :func:`app.web.serializer.to_jsonable` -- *not* FastAPI's ``jsonable_encoder``,
  which would use the snake_case field names.
* **No ``@ControllerAdvice``** in the Java project: an uncaught exception is a 500
  produced by ``app.main``'\''s ``Exception`` handler.

Deliberate, documented differences
----------------------------------
* The servlet thread pool is bounded by the web framework (40 workers by
  default) instead of Tomcat's 200 ``max-threads``; raise it with
  ``app.server.worker-threads`` if you load test.
* ``@ModelAttribute`` binding documents nothing in ``/docs`` (Spring would list
  every property of the bean).
"""
from __future__ import annotations

import importlib
import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app.db.proxy import import_class
from app.routes.generated import ROUTES
from app.web.binding import BindingError, bind_bean, bind_json, bind_value
from app.web.errors import error_response
from app.web.responses import JacksonResponse
from app.web.serializer import to_jsonable
from com.ruoyi.common.utils.PageUtils import PageUtils
from com.ruoyi.common.utils.ServletUtils import (
    RequestContextHolder,
    _HttpServletRequest,
    _ServletRequestAttributes,
)

log = logging.getLogger(__name__)

__all__ = ["RouteInstallReport", "ControllerRegistry", "register_all"]

_PATH_VAR_RE = re.compile(r"\{[^{}]+\}")

_SCALAR_TARGETS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "decimal": Decimal,
}

_OPENAPI_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "decimal": "number",
    "map": "object",
    "list": "array",
}


class MissingRequestParameter(Exception):
    """``MissingServletRequestParameterException`` -> 400."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Required request parameter '{name}' for method parameter type "
                         f"is not present")
        self.name = name


class UnreadableBody(Exception):
    """``HttpMessageNotReadableException`` -> 400."""


class UnsupportedMediaType(Exception):
    """``HttpMediaTypeNotSupportedException`` -> 415."""


@dataclass
class RouteInstallReport:
    """What :meth:`ControllerRegistry.install` achieved (printed at startup)."""

    routes: int = 0
    controllers: int = 0
    unavailable: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing_methods: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    signature_mismatches: list[str] = field(default_factory=list)
    base_path_mismatches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.unavailable or self.missing_methods
                    or self.signature_mismatches or self.base_path_mismatches)

    def summary(self) -> str:
        return (f"{self.controllers} controller(s), {self.routes} route(s) registered"
                + (f", {len(self.unavailable)} controller(s) unavailable" if self.unavailable else ""))


def _specificity(path: str) -> tuple[int, int]:
    """``AntPatternComparator``: fewer URI variables first, then the longer pattern."""
    return len(_PATH_VAR_RE.findall(path)), -len(path)


def _first_values(request: Request) -> dict[str, list[str]]:
    """Servlet ``getParameterMap()``: every value, in request order.

    ``ServletUtils.getParameter`` returns the *first* value while Starlette's
    ``QueryParams.get`` returns the *last* one, so the raw list is kept here and
    flattened by :func:`_first_value` where a single value is expected.

    The map handed to an unnamed ``@RequestParam Map<String,String>`` argument is
    *not* the servlet map: ``RequestParamMapMethodArgumentResolver`` copies it into
    a fresh ``LinkedHashMap<String,String>``. Spring Framework 5.3.6 (the version
    Spring Boot 2.4.5 pulls in) does that in ``lambda$resolveArgument$1``::

        private static void lambda$resolveArgument$1(Map map, String key, String[] values) {
            if (values.length > 0) map.put(key, values[0]);
        }

    Every parameter therefore reaches the handler as a single ``String`` (keys
    with no value at all are omitted), and ``extractFuzzyFields`` in the two query
    controllers runs without a ``ClassCastException``. Verified with ``javap -c``
    against ``spring-web-5.3.6.jar`` in the project's own Maven repository.
    """
    parameters: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        parameters.setdefault(key, []).append(value)
    return parameters


def _first_value(values: Optional[list[str]]) -> Optional[str]:
    return values[0] if values else None


def _convert(raw: Any, param: dict[str, Any]) -> Any:
    """Convert a request value to the declared Java type of the parameter."""
    target = _SCALAR_TARGETS.get(param["type"])
    if target is None:
        return raw  # a POJO cannot come from a path/query string in this project
    return bind_value(raw, target, param["java_name"])


def _resolve_class(type_name: str) -> Optional[type]:
    if type_name in _SCALAR_TARGETS or type_name in ("map", "list"):
        return None
    return import_class(type_name)


def _string_map(payload: Any) -> dict[str, Any]:
    """Jackson's ``Map<String,String>`` coercion (scalars become strings)."""
    if payload is None:
        return None  # type: ignore[return-value]
    if not isinstance(payload, dict):
        raise UnreadableBody("Cannot deserialize value of type `java.util.LinkedHashMap`")
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None or isinstance(value, str):
            result[str(key)] = value
        elif isinstance(value, bool):
            result[str(key)] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            result[str(key)] = str(value)
        else:
            raise UnreadableBody("Cannot deserialize value of type `java.lang.String` "
                                 f"from {type(value).__name__}")
    return result


def _bind_body(param: dict[str, Any], body: bytes, request: Request) -> Any:
    if not body or not body.strip():
        if param["required"]:
            raise UnreadableBody("Required request body is missing")
        return None
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json" and not content_type.endswith("+json"):
        raise UnsupportedMediaType(content_type or "application/octet-stream")
    try:
        payload = json.loads(body)
    except ValueError as error:
        raise UnreadableBody("JSON parse error") from error
    if param["type"] == "map":
        return _string_map(payload)
    entity = _resolve_class(param["type"])
    if entity is None:
        return payload
    return bind_json(entity, payload)


def _bind_model(param: dict[str, Any], parameters: dict[str, list[str]]) -> Any:
    entity = _resolve_class(param["type"])
    flat = {key: values[0] for key, values in parameters.items() if values}
    if entity is None:
        return flat
    return bind_bean(entity, flat)


def _bind_arguments(route: dict[str, Any], request: Request, body: bytes,
                    parameters: dict[str, list[str]]) -> list[Any]:
    """Resolve the handler arguments exactly like ``InvocableHandlerMethod``."""
    arguments: list[Any] = []
    for param in route["params"]:
        source = param["source"]
        if source == "path":
            raw = request.path_params.get(param["java_name"])
            if raw is None:
                raw = request.path_params.get(param["name"])
            if raw is None:  # cannot happen: Starlette matched the path
                raise MissingRequestParameter(param["java_name"])
            arguments.append(_convert(raw, param))
        elif source == "param":
            raw = _first_value(parameters.get(param["java_name"]))
            if raw is None and param["java_name"] != param["name"]:
                raw = _first_value(parameters.get(param["name"]))
            if raw is None:
                if param["default"] is not None:
                    raw = param["default"]
                elif param["required"]:
                    raise MissingRequestParameter(param["java_name"])
                else:
                    arguments.append(None)
                    continue
            arguments.append(_convert(raw, param))
        elif source == "param_map":
            arguments.append({key: values[0] for key, values in parameters.items() if values})
        elif source == "body":
            arguments.append(_bind_body(param, body, request))
        elif source == "model":
            arguments.append(_bind_model(param, parameters))
        else:  # pragma: no cover - guarded by the generator
            raise RuntimeError(f"unknown parameter source {source!r}")
    return arguments


def _is_void(returns: str) -> bool:
    return returns.replace(" ", "") == "void"


def _respond(route: dict[str, Any], result: Any) -> Response:
    if _is_void(route["returns"]):
        # A void handler writes nothing; Spring sends 200 with an empty body
        return Response(status_code=200)
    return JacksonResponse(content=to_jsonable(result))


def _openapi_extra(route: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Describe the Spring parameters in ``/docs`` (FastAPI cannot see them)."""
    parameters: list[dict[str, Any]] = []
    request_body: Optional[dict[str, Any]] = None
    for param in route["params"]:
        json_type = _OPENAPI_TYPES.get(param["type"], "string")
        if param["source"] == "path":
            parameters.append({"name": param["java_name"], "in": "path", "required": True,
                               "schema": {"type": json_type}})
        elif param["source"] == "param":
            schema: dict[str, Any] = {"type": json_type}
            if param["default"] is not None:
                schema["default"] = _openapi_default(param["default"], json_type)
            parameters.append({"name": param["java_name"], "in": "query",
                               "required": bool(param["required"]), "schema": schema})
        elif param["source"] == "param_map":
            parameters.append({"name": f"{param['java_name']}.*", "in": "query",
                               "required": False, "schema": {"type": "string"},
                               "description": "every request parameter is passed through"})
        elif param["source"] == "body":
            request_body = {"required": bool(param["required"]),
                            "content": {"application/json": {"schema": {"type": "object"}}}}
    extra: dict[str, Any] = {}
    if parameters:
        extra["parameters"] = parameters
    if request_body:
        extra["requestBody"] = request_body
    return extra or None


def _openapi_default(value: str, json_type: str) -> Any:
    try:
        if json_type == "integer":
            return int(value)
        if json_type == "number":
            return float(value)
        if json_type == "boolean":
            return str(value).lower() == "true"
    except (TypeError, ValueError):
        return value
    return value


class ControllerRegistry:
    """Instantiates the controllers once (``@RestController`` = singleton)."""

    def __init__(self, routes: Optional[list[dict[str, Any]]] = None) -> None:
        self.routes = ROUTES if routes is None else routes
        self.controllers: dict[str, Any] = {}
        self._report = RouteInstallReport()

    # ------------------------------------------------------------------ install
    def install(self, app: FastAPI) -> RouteInstallReport:
        report = self._report
        seen: set[tuple[str, str]] = set()
        # Spring sorts the mappings by specificity; the router matches in order
        ordered = sorted(enumerate(self.routes, start=1),
                         key=lambda pair: (_specificity(pair[1]["path"]), pair[0]))
        for index, route in ordered:
            controller = self._controller(route, report)
            if controller is None:
                report.skipped.append(f"{route['http']} {route['path']}")
                continue
            handler = getattr(controller, route["method"], None)
            if not callable(handler):
                report.missing_methods.append(f"{route['controller']}#{route['method']}")
                log.error("%s#%s does not exist on the Python controller",
                          route["controller"], route["method"])
                continue
            self._check_signature(route, handler, report)
            key = (route["path"] or "/", route["http"])
            if key in seen:
                report.duplicates.append(f"{route['http']} {route['path']}")
                log.warning("duplicate mapping %s %s (%s)", route["http"], route["path"],
                            route["controller"])
                continue
            seen.add(key)
            app.add_api_route(
                route["path"] or "/",
                _make_endpoint(self, route, handler),
                methods=[route["http"]],
                name=f"{route['controller'].rsplit('.', 1)[-1]}.{route['method']}.{index}",
                response_class=JacksonResponse,
                tags=[_tag_of(route)],
                summary=f"{route['controller'].rsplit('.', 1)[-1]}#{route['method']}",
                openapi_extra=_openapi_extra(route),
            )
            report.routes += 1
        return report

    # ------------------------------------------------------------------ invoke
    def invoke(self, route: dict[str, Any], handler: Callable[..., Any],
               request: Request, body: bytes) -> Response:
        """Run one handler in a worker thread with the Spring context installed."""
        parameters = _first_values(request)
        attributes = _ServletRequestAttributes(_HttpServletRequest(
            parameters=parameters,
            headers={key: value for key, value in request.headers.items()},
            request_uri=request.url.path,
        ))
        RequestContextHolder.setRequestAttributes(attributes)
        PageUtils.clearPage()
        try:
            arguments = _bind_arguments(route, request, body, parameters)
            result = handler(*arguments)
            return _respond(route, result)
        except (BindingError, MissingRequestParameter, UnreadableBody) as error:
            log.debug("%s %s -> 400 (%s)", route["http"], request.url.path, error)
            return error_response(400, request.url.path)
        except UnsupportedMediaType as error:
            log.debug("%s %s -> 415 (%s)", route["http"], request.url.path, error)
            return error_response(415, request.url.path)
        finally:
            # PageHelper's interceptor does the same in afterCompletion
            PageUtils.clearPage()
            RequestContextHolder.resetRequestAttributes()

    # ------------------------------------------------------------------ helpers
    def _controller(self, route: dict[str, Any], report: RouteInstallReport) -> Any:
        fqcn = route["controller"]
        if fqcn in self.controllers:
            return self.controllers[fqcn]
        controller = None
        klass = import_class(fqcn)
        if klass is None:
            report.unavailable.append(fqcn)
            log.error("cannot import controller %s%s", fqcn, _import_reason(fqcn))
        else:
            try:
                controller = klass()
            except Exception as error:  # noqa: BLE001 - a controller needs a no-arg ctor
                report.unavailable.append(fqcn)
                log.error("cannot instantiate %s: %s", fqcn, error)
            else:
                report.controllers += 1
                self._check_base_path(route, klass, report)
        self.controllers[fqcn] = controller
        return controller

    @staticmethod
    def _check_base_path(route: dict[str, Any], klass: type, report: RouteInstallReport) -> None:
        declared = getattr(klass, "BASE_PATH", None)
        expected = route["class_path"]
        if declared is not None and declared != expected:
            report.base_path_mismatches.append(
                f"{klass.__name__}: BASE_PATH={declared!r} but @RequestMapping({expected!r})")
            log.warning("%s: BASE_PATH=%r differs from @RequestMapping(%r)",
                        klass.__name__, declared, expected)

    @staticmethod
    def _check_signature(route: dict[str, Any], handler: Callable[..., Any],
                         report: RouteInstallReport) -> None:
        try:
            signature = inspect.signature(handler)
        except (TypeError, ValueError):  # pragma: no cover - builtins
            return
        positional = [p for p in signature.parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                      and p.name != "self"]
        if len(positional) != len(route["params"]):
            report.signature_mismatches.append(
                f"{route['controller'].rsplit('.', 1)[-1]}#{route['method']}: "
                f"Java {len(route['params'])} parameter(s), Python {len(positional)}")
            log.warning("%s#%s: Java declares %d parameter(s) but Python declares %d",
                        route["controller"], route["method"],
                        len(route["params"]), len(positional))


def _tag_of(route: dict[str, Any]) -> str:
    return route["controller"].rsplit(".", 1)[-1].removesuffix("Controller")


def _import_reason(fqcn: str) -> str:
    """Surface the underlying ``ImportError`` (``import_class`` swallows it)."""
    try:
        importlib.import_module(fqcn)
    except Exception as error:  # noqa: BLE001 - reported, never raised
        return f": {type(error).__name__}: {error}"
    return ""


def _make_endpoint(registry: ControllerRegistry, route: dict[str, Any],
                   handler: Callable[..., Any]) -> Callable[[Request], Any]:
    """Bodies must be read on the event loop; the handler runs in a worker thread."""
    async def endpoint(request: Request) -> Response:
        body = await request.body()
        return await run_in_threadpool(registry.invoke, route, handler, request, body)

    endpoint.__name__ = f"{_tag_of(route)}_{route['method']}"
    endpoint.__doc__ = f"# Java: {route['controller']}#{route['method']} ({route['java']})"
    return endpoint


def register_all(app: FastAPI) -> int:
    """Register every generated route. Returns the number of routes added."""
    registry = ControllerRegistry()
    report = registry.install(app)
    log.info("route registry: %s", report.summary())
    for item in report.unavailable:
        log.error("controller unavailable (module not ported yet): %s", item)
    for item in report.missing_methods:
        log.error("handler missing on the Python controller: %s", item)
    for item in report.signature_mismatches:
        log.error("parameter count mismatch: %s", item)
    for item in report.base_path_mismatches:
        log.error("BASE_PATH mismatch: %s", item)
    app.state.route_report = report
    app.state.controller_registry = registry
    return report.routes
