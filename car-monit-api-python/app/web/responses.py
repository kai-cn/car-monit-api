# -*- coding: utf-8 -*-
"""JSON response used by every controller (Jackson ``MappingJackson2HttpMessageConverter``).

``fastapi.responses.ORJSONResponse`` is deprecated in FastAPI 0.159, so the
same behaviour is implemented on top of Starlette's ``Response`` + orjson:

* UTF-8 JSON, ``application/json`` (Spring's converter does not append a
  charset for JSON);
* non-string map keys are stringified (Jackson writes ``{"1": ...}``);
* no NaN/Infinity (Jackson rejects them too unless configured otherwise).
"""
from __future__ import annotations

from typing import Any

import orjson
from starlette.responses import Response

__all__ = ["JacksonResponse"]


class JacksonResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)
