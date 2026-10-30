# -*- coding: utf-8 -*-
"""com.alibaba.fastjson2.JSONObject

【无 Java 源文件：框架类替身】
Java 侧来自 fastjson2 jar：`com.alibaba.fastjson2.JSONObject`（继承 JSON 的静态方法）。
业务代码典型用法：
    JSONObject messageObj = JSONObject.parseObject(messageJson);
    JSONObject sourceObj = messageObj.getJSONObject("source");
    String s = obj.getString("op");
    JSONObject json = new JSONObject();

【Java→Python 关键差异】
1) fastjson2 的 JSONObject 本质是**有序 Map<String,Object>**（LinkedHashMap 语义）；
   Python 直接继承 `dict`（3.7+ 默认保持插入顺序），并补齐 Java 风格方法。
2) Java 的 `get()` 返回 Object，嵌套对象是 JSONObject/JSONArray；
   Python 的 dict 存的是原生 dict/list，这里在 get() 时**按需包装**成
   JSONObject/JSONArray，保证 `isinstance(x, JSONObject)` 判断与 Java 一致。
3) Java 的 `getString()` 会把数字/布尔转成字符串（`String.valueOf`），
   `getInteger()` 会把字符串转数字；这里逐一还原（转换失败返回 None，对应 Java 返回 null）。
4) `JSONObject.parseObject(...)` 是 Java 里「静态方法继承」的写法；Python 用 staticmethod 转发给 JSON。
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["JSONObject"]


def _wrap(value: Any) -> Any:
    """把原生 dict/list 包装成 JSONObject/JSONArray（对应 fastjson 的嵌套类型）。"""
    from com.alibaba.fastjson2.JSONArray import JSONArray

    if isinstance(value, JSONObject) or isinstance(value, JSONArray):
        return value
    if isinstance(value, dict):
        return JSONObject(value)
    if isinstance(value, list):
        return JSONArray(value)
    return value


class JSONObject(dict):
    """`com.alibaba.fastjson2.JSONObject` 的替身（有序 Map + 类型转换方法）。"""

    # ------------------------------------------------------------------ 构造
    @staticmethod
    def parseObject(text: Any, clazz: Any = None) -> Any:
        """等价 `JSONObject.parseObject(String)` / `parseObject(String, Class)`。"""
        from com.alibaba.fastjson2.JSON import JSON

        return JSON.parseObject(text, clazz)

    def toJSONString(self) -> str:
        from com.alibaba.fastjson2.JSON import JSON

        return JSON.toJSONString(self)

    def toJavaObject(self, clazz: Any) -> Any:
        """等价 `JSONObject#toJavaObject(Class<T>)`：把当前对象映射成实体。

        【Java→Python】Java 是实例方法（`((JSONObject) dataObj).toJavaObject(Xxx.class)`），
        这里委托给 JSON.toJavaObject（与静态写法等价）。
        """
        from com.alibaba.fastjson2.JSON import JSON

        return JSON.toJavaObject(self, clazz)

    # ------------------------------------------------------------------ 读取
    def get(self, key: Any, default: Any = None) -> Any:
        """Java 的 `Object get(String key)`：缺失返回 null（Python None）。"""
        return _wrap(dict.get(self, key, default))

    def getString(self, key: Any) -> Optional[str]:
        value = dict.get(self, key)
        if value is None:
            return None
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        return str(value)

    def getInteger(self, key: Any) -> Optional[int]:
        value = dict.get(self, key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def getIntValue(self, key: Any, default_value: int = 0) -> int:
        """`getIntValue(key)`：缺失按 0 处理（Java 返回 int 基本类型）。"""
        value = self.getInteger(key)
        return default_value if value is None else value

    def getLong(self, key: Any) -> Optional[int]:
        # 【Java→Python】Java 的 Long 与 Python int 同为任意精度/64 位整数，无需区分
        return self.getInteger(key)

    def getDouble(self, key: Any) -> Optional[float]:
        value = dict.get(self, key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def getBoolean(self, key: Any) -> Optional[bool]:
        value = dict.get(self, key)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "y", "yes")

    def getBooleanValue(self, key: Any) -> bool:
        value = self.getBoolean(key)
        return False if value is None else value

    def getDate(self, key: Any) -> Optional[Any]:
        """`Date getDate(String key)`：把值解析成日期。

        【Java→Python】Java 返回 `java.util.Date`；Python 侧统一用 `datetime`
        表达（与实体里 `Date` 字段的转写保持一致）。
        支持三种输入，覆盖 fastjson 的 `getDate` 行为：
          - 已是 datetime/date → 直接返回；
          - 数字 → 按**毫秒时间戳**解释（fastjson 默认把 Date 序列化成毫秒）；
          - 字符串 → 走 `DateUtils.parseDate`（与 fastjson 的多种 pattern 解析等价）。
        解析失败返回 None（Java 抛 JSONException，业务侧用 try/catch 兜底，
        两者在 `date != null ? ... : now` 的判断下结果一致）。
        """
        from datetime import date, datetime

        value = dict.get(self, key)
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value / 1000.0)

        from com.ruoyi.common.utils.DateUtils import DateUtils

        return DateUtils.parseDate(value)

    def getJSONObject(self, key: Any) -> Optional["JSONObject"]:
        value = self.get(key)
        return value if isinstance(value, JSONObject) else None

    def getJSONArray(self, key: Any) -> Any:
        from com.alibaba.fastjson2.JSONArray import JSONArray

        value = self.get(key)
        return value if isinstance(value, JSONArray) else None

    def getObject(self, key: Any, clazz: Any = None) -> Any:
        """`getObject(String, Class<T>)`：把嵌套 JSON 转成实体。"""
        from com.alibaba.fastjson2.JSON import JSON

        value = self.get(key)
        if value is None or clazz is None:
            return value
        return JSON.toJavaObject(value, clazz)

    def getOrDefault(self, key: Any, default_value: Any) -> Any:
        return self.get(key, default_value)

    # ------------------------------------------------------------------ Map 语义
    def containsKey(self, key: Any) -> bool:
        return key in self

    def containsValue(self, value: Any) -> bool:
        return value in self.values()

    def put(self, key: Any, value: Any) -> Any:
        previous = self.get(key)
        self[key] = value
        return previous

    def putAll(self, other: dict) -> None:
        self.update(other)

    def size(self) -> int:
        return len(self)

    def isEmpty(self) -> bool:
        return len(self) == 0

    def keySet(self) -> set:
        return set(self.keys())

    def entrySet(self) -> list:
        return list(self.items())

    def remove(self, key: Any) -> Any:
        return self.pop(key, None)

    def clone(self) -> "JSONObject":
        return JSONObject(self)
