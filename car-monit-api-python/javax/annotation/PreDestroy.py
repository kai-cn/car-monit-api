# -*- coding: utf-8 -*-
"""javax.annotation.PreDestroy

【无 Java 源文件：框架类替身】（``javax.annotation.PreDestroy``）
业务代码用法（ElasticsearchQueryService.destroy）：
    @PreDestroy
    public void destroy() { if (client != null) client.close(); }

【Java→Python 关键差异】
1) Java 的 ``@PreDestroy`` 由容器在 Bean 销毁前反射调用；Python 无容器生命周期，
   故本替身只是**恒等装饰器**，保持源码形态，不产生运行期行为。
2) 迁移后需要显式调用 ``destroy()``（例如应用退出钩子 ``atexit.register``），
   已在调用处注释说明。
"""

from __future__ import annotations

from typing import Any, Callable

__all__ = ["PreDestroy"]


def PreDestroy(func: Callable[..., Any]) -> Callable[..., Any]:
    """``@PreDestroy`` 的恒等装饰器替身（不自动执行，需显式调用）。"""
    return func
