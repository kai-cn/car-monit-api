# -*- coding: utf-8 -*-
"""com.alibaba.fastjson2.JSONArray

【无 Java 源文件：框架类替身】
Java 侧来自 fastjson2 jar：`com.alibaba.fastjson2.JSONArray`（本质是有序 List<Object>）。
业务代码典型用法：
    JSONArray array = JSON.parseArray(keyValue);
    JSONObject jsonObj = (JSONObject) o;
    JSONArray imgesJsonArray = JSON.parseArray(imagesStr);
    JSONObject imageTempJosn = imgesJsonArray.getJSONObject(zz);

【Java→Python 关键差异】
1) JSONArray 继承 `list`，`size()` 方法保留（Java 风格），同时支持 Python 的 len/迭代/切片。
2) Java 的 `get(index)` 在越界时抛 IndexOutOfBoundsException → Python 的 list 抛 IndexError
   （两者都属“越界异常”，行为等价，不做转换）。
3) 元素为 dict/list 时，`get()` 返回**包装后**的 JSONObject/JSONArray，保证强转语义一致。
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["JSONArray"]


class JSONArray(list):
    """`com.alibaba.fastjson2.JSONArray` 的替身（有序 List + Java 风格方法）。"""

    @staticmethod
    def parseArray(text: Any, clazz: Any = None) -> "JSONArray":
        """等价 `JSONArray.parseArray(String)` / `parseArray(String, Class)`。"""
        from com.alibaba.fastjson2.JSON import JSON

        return JSON.parseArray(text, clazz)

    def toJSONString(self) -> str:
        from com.alibaba.fastjson2.JSON import JSON

        return JSON.toJSONString(self)

    # ------------------------------------------------------------------ 读取
    def __iter__(self):
        """【Java→Python】Java 的 `for (Object o : array)` 拿到的是 JSONObject/JSONArray；
        list 子类的默认 `__iter__` 只会返回底层 dict/list，导致 `o.getString(...)` 报错。
        这里重写为逐项 `_wrap`，与 `get(index)` 的强转语义保持一致。
        """
        from com.alibaba.fastjson2.JSONObject import _wrap

        return (_wrap(item) for item in list.__iter__(self))

    def get(self, index: int) -> Any:
        """等价 `Object get(int index)`：越界抛 IndexError。"""
        from com.alibaba.fastjson2.JSONObject import _wrap

        return _wrap(list.__getitem__(self, index))

    def getJSONObject(self, index: int) -> Any:
        from com.alibaba.fastjson2.JSONObject import JSONObject

        value = self.get(index)
        return value if isinstance(value, JSONObject) else None

    def getJSONArray(self, index: int) -> Optional["JSONArray"]:
        value = self.get(index)
        return value if isinstance(value, JSONArray) else None

    def getString(self, index: int) -> Optional[str]:
        value = self.get(index)
        if value is None:
            return None
        if isinstance(value, bool):
            return "true" if value else "false"
        return value if isinstance(value, str) else str(value)

    def getInteger(self, index: int) -> Optional[int]:
        value = self.get(index)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def getLong(self, index: int) -> Optional[int]:
        return self.getInteger(index)

    def getDouble(self, index: int) -> Optional[float]:
        value = self.get(index)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def getBoolean(self, index: int) -> Optional[bool]:
        value = self.get(index)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "y", "yes")

    def getObject(self, index: int, clazz: Any = None) -> Any:
        from com.alibaba.fastjson2.JSON import JSON

        value = self.get(index)
        if value is None or clazz is None:
            return value
        return JSON.toJavaObject(value, clazz)

    # ------------------------------------------------------------------ List 语义
    def size(self) -> int:
        return len(self)

    def isEmpty(self) -> bool:
        return len(self) == 0

    def add(self, value: Any) -> bool:
        """`boolean add(E)`：Java 的 List.add 恒返回 true。"""
        self.append(value)
        return True

    def addAll(self, values: Any) -> bool:
        before = len(self)
        self.extend(values)
        return len(self) > before

    def clear(self) -> None:
        del self[:]

    def contains(self, value: Any) -> bool:
        return value in self

    def indexOf(self, value: Any) -> int:
        try:
            return self.index(value)
        except ValueError:
            return -1

    def toJavaList(self, clazz: Any = None) -> list:
        """对应 `toJavaList(Class<T>)`：逐个转实体。"""
        from com.alibaba.fastjson2.JSON import JSON

        if clazz is None:
            return list(self)
        return [JSON.toJavaObject(item, clazz) for item in self]
