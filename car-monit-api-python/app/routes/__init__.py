# -*- coding: utf-8 -*-
"""Route registration for the 24 ``@RestController`` classes.

The table is generated from the Java sources by ``tools/gen_routes.py``
(``app/routes/generated.py``). Each entry records:

    controller : "com.ruoyi.base.controller.OdsSzdnGantryController"
    method     : "list"                       # Java and Python share the name
    http       : "GET"
    path       : "/base/gantry/list"          # class @RequestMapping + method
    params     : [{"name": "odsSzdnGantry", "source": "model",
                   "type": "com.ruoyi.base.domain.OdsSzdnGantry"}]

``source`` is one of: ``path`` (@PathVariable), ``body`` (@RequestBody),
``param`` (@RequestParam), ``param_map`` (@RequestParam Map), ``model``
(unannotated POJO). ``app/routes/registry.py`` turns the table into FastAPI
routes and reproduces Spring's argument resolution at runtime.
"""
from __future__ import annotations

from fastapi import FastAPI

__all__ = ["register_routes"]


def register_routes(app: FastAPI) -> int:
    """Register every generated controller route. Returns the route count."""
    from app.routes.registry import register_all

    return register_all(app)
