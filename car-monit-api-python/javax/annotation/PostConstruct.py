# -*- coding: utf-8 -*-
"""javax.annotation.PostConstruct

【无 Java 源文件：框架类替身】（``javax.annotation.PostConstruct``）
业务代码用法（ElasticsearchQueryService.init）：
    @PostConstruct
    public void init() { this.client = new RestHighLevelClient(...); }

【Java→Python 关键差异】
1) Java 的 ``@PostConstruct`` 是**运行时注解**，由容器（Spring）在依赖注入完成后
   反射调用被标注的方法；Python 没有容器，也没有等价的注解机制。
2) 本替身把注解变成**恒等装饰器**（返回原函数），作用是：
   - 保持源码里 ``@PostConstruct`` 这一行的存在（一比一还原）；
   - 不改变任何运行期行为。
3) **必须显式调用**：迁移后的类由业务代码自行 ``new``，不会自动触发 ``init``。
   工程内约定：在需要初始化的使用方（如 controller/冒烟脚本）里手动调用
   ``service.init()``，并在调用处注释说明这一差异。
"""

from __future__ import annotations

from typing import Any, Callable

__all__ = ["PostConstruct"]


def PostConstruct(func: Callable[..., Any]) -> Callable[..., Any]:
    """``@PostConstruct`` 的恒等装饰器替身（不自动执行，需显式调用）。"""
    return func
