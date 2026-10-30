# -*- coding: utf-8 -*-
"""org.apache.http.util.EntityUtils

【无 Java 源文件：框架类替身】
Java 侧来自 Apache HttpComponents 的 ``org.apache.http.util.EntityUtils``。
本工程用法（EsIndexManageService.ilmPolicyExists）：
    String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);

【Java→Python 关键差异】
1) Java 的 ``HttpEntity`` 是“可重复读取的字节流 + Content-Type + Content-Length”；
   ``EntityUtils.toString(entity, charset)`` 把实体内容**读尽并关闭流**，
   再按指定字符集解码成 String。
2) Python 替身里 ``HttpEntity`` 只保存文本（见 ``org/elasticsearch/client/Response.py``
   的 ``_HttpEntity``），因此 ``toString`` 直接取出文本。
   **注意**：Java 的 ``toString`` 会消费流（二次调用得到空串），替身不做消费，
   因为原代码只调用一次，不存在语义差异。
3) Java 还有 ``toString(entity)``（默认 ISO-8859-1）重载，本工程未使用。
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["EntityUtils"]


class EntityUtils(object):
    """``EntityUtils`` 静态工具类的替身。"""

    @staticmethod
    def toString(entity: Optional[Any], charset: str = "iso-8859-1") -> str:
        """对应 ``toString(HttpEntity entity, Charset defaultCharset)``。"""
        if entity is None:
            return ""
        # 替身的 HttpEntity 以 text 属性保存已解码文本（详见 Response.py）
        text = getattr(entity, "text", None)
        if text is not None:
            return text
        content = getattr(entity, "content", None)
        if isinstance(content, bytes):
            return content.decode(charset)
        return str(content) if content is not None else ""
