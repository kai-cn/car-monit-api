# -*- coding: utf-8 -*-
"""org.elasticsearch.search.Scroll

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.Scroll``。
本工程用法（LargeScaleQueryService.executeExportScroll）：
    searchRequest.scroll(new Scroll(new TimeValue(5, TimeUnit.MINUTES)));
    scrollRequest.scroll(new Scroll(new TimeValue(5, TimeUnit.MINUTES)));

【Java→Python】关键差异
1) ``Scroll`` 只承载一个 ``TimeValue keepAlive``（游标上下文在集群侧的存活时间）；
   Java 的 ``Scroll(TimeValue keepAlive)`` / ``keepAlive()`` 在替身里同名保留。
2) Java 的 ``keepAlive`` 校验非负（负值抛 ``IllegalArgumentException``）；
   替身同样校验，抛 ``ValueError``（Python 对应物）。
3) 真实 ES 的 keepAlive 由服务端计时回收；替身的游标保存在进程内
   （``RestHighLevelClient`` 的类属性），**不做超时回收**——见该类说明。
"""

from __future__ import annotations

from typing import Any

from org.elasticsearch.core.TimeValue import TimeValue

__all__ = ["Scroll"]


class Scroll(object):
    """``Scroll`` 的替身（only keep-alive）。"""

    def __init__(self, keep_alive: TimeValue) -> None:
        # 【Java→Python】Java 用 ``keepAlive.millis() < 0`` 判非法参数
        if keep_alive is not None and keep_alive.millis() < 0:
            raise ValueError("keepAlive must be >=0")
        self._keep_alive = keep_alive

    def keepAlive(self) -> Any:
        """对应 ``TimeValue keepAlive()``。"""
        return self._keep_alive

    def __repr__(self) -> str:
        return "Scroll(keepAlive=%r)" % (self._keep_alive,)
