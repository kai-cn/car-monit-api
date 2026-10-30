# -*- coding: utf-8 -*-
"""com.alibaba.fastjson2.JSON

【无 Java 源文件：框架类替身】
Java 侧来自 fastjson2 jar：`com.alibaba.fastjson2.JSON`。业务代码用到：
    JSON.toJSONString(obj)                     # 序列化
    JSON.parseObject(text)                     # 反序列化为 JSONObject
    JSON.parseObject(text, Entity.class)       # 反序列化为实体
    JSON.parseArray(text)                      # 反序列化为 JSONArray
    JSON.parseArray(text, TrailBo.class)       # 反序列化为 List<实体>
    JSON.toJavaObject(jsonObject, Entity.class)

【Java→Python 关键差异】
1) **`.class` 字面量**：Java 用 `OdsRtSzdnSnapshotFlowAddcode.class` 传类型；Python 直接传类对象
   `OdsRtSzdnSnapshotFlowAddcode`（转写时把所有 `Xxx.class` 改成 `Xxx`）。
2) **字段名映射**：Java 实体字段是 camelCase（bigId / applyTime1），fastjson 按属性名对齐；
   Python 实体是 snake_case（big_id / apply_time1），因此序列化时做 snake→camel，
   反序列化时做 camel→snake，这样**JSON 文本与 Java 版本逐字节一致**。
3) **Date 格式**：fastjson 默认把 Date 序列化成**毫秒时间戳**；为了让 JSON 可读、
   且能与本工程的 `yyyy-MM-dd HH:mm:ss` 解析逻辑互通，这里序列化成
   `"yyyy-MM-dd HH:mm:ss"`（反序列化两种都支持）。这是本替身与 fastjson 默认行为的
   唯一可见差异，已在 _serialize 中注明。
4) **null 字段**：fastjson 默认输出 `"field":null`；本替身**跳过 None 字段**
   （更接近 fastjson1 的默认行为，也避免生成超长 JSON）。反序列化对缺失字段一视同仁。
5) **未知字段**：fastjson 默认忽略（不报错），这里同样忽略；类型转换失败时保留原值，
   避免因为脏数据导致整个解析中断（Java 侧会抛 JSONException，属于“宽松化”处理，
   已在 _convert_value 中注明）。
"""
from __future__ import annotations

import dataclasses
import json as _json
import re
import types
import typing
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSONArray import JSONArray
from com.alibaba.fastjson2.JSONObject import JSONObject

__all__ = ["JSON"]

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def camelToSnake(name: str) -> str:
    """`bigId` → `big_id`；`datauuid` → `datauuid`（与实体字段命名规则一致）。"""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def snakeToCamel(name: str) -> str:
    """`big_id` → `bigId`；`datauuid` → `datauuid`（还原 Java 属性名）。"""
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


class JSON(object):
    """`com.alibaba.fastjson2.JSON` 的静态方法集合。"""

    # ------------------------------------------------------------------ 序列化
    @staticmethod
    def toJSONString(value: Any) -> str:
        # 【Java→Python】fastjson 输出紧凑 JSON（无空格）；ensure_ascii=False 保留中文，
        # 与 fastjson 的“不转义非 ASCII”一致。
        return _json.dumps(_serialize(value), ensure_ascii=False, separators=(",", ":"))

    # ------------------------------------------------------------------ 反序列化
    @staticmethod
    def parse(text: Any) -> Any:
        """等价 `JSON.parse(String)`：返回 Object（对象→JSONObject，数组→JSONArray）。

        【Java→Python】Java 返回的是 Object，调用方再 `instanceof JSONObject` 判断；
        这里返回 JSONObject/JSONArray/基本类型，`isinstance(data, JSONObject)` 写法不变。
        """
        if text is None:
            return None
        if isinstance(text, (JSONObject, JSONArray)):
            return text
        if isinstance(text, dict):
            return JSONObject(dict(text))
        if isinstance(text, (list, tuple)):
            return JSONArray(list(text))
        raw = _json.loads(text)
        if isinstance(raw, dict):
            return JSONObject(raw)
        if isinstance(raw, list):
            return JSONArray(raw)
        return raw

    @staticmethod
    def parseObject(text: Any, clazz: Any = None) -> Any:
        """等价 `parseObject(String)` / `parseObject(String, Class<T>)`。"""
        if text is None:
            return None
        if isinstance(text, (dict, JSONObject)):
            raw = dict(text)
        else:
            raw = _json.loads(text)
        if clazz is None:
            return JSONObject(raw) if isinstance(raw, dict) else raw
        return _convert(raw, clazz)

    @staticmethod
    def parseArray(text: Any, clazz: Any = None) -> JSONArray:
        """等价 `parseArray(String)` / `parseArray(String, Class<T>)`。"""
        if text is None:
            return JSONArray()
        raw = _json.loads(text) if isinstance(text, str) else list(text)
        if clazz is None:
            return JSONArray(raw)
        return JSONArray(_convert(item, clazz) for item in raw)

    @staticmethod
    def toJavaObject(value: Any, clazz: Any) -> Any:
        """等价 `toJavaObject(Object, Class<T>)`：JSONObject/JSONArray → 实体。"""
        if value is None:
            return None
        return _convert(value, clazz)


# ---------------------------------------------------------------------- 序列化
def _serialize(value: Any) -> Any:
    """把 Java 对象图转成可 JSON 化的 Python 原生结构。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        # 【Java→Python】fastjson 默认是毫秒数；这里用可读时间串（见模块注释第 3 条）
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Enum):
        # Java 枚举默认序列化为 name()（fastjson 行为）
        # 【Java→Python】部分替身枚举为了还原 Java 的 `Enum.name()` 把 name 定义成了**方法**
        # （如 DataReliabilityService.MessageStatus），此时 value.name 是 bound method，
        # 必须调用一次；普通 Enum 的 .name 仍是字符串属性。两种形态都要兼容。
        name_attr = value.name
        return name_attr() if callable(name_attr) else name_attr
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # 实体：只输出 dataclass 字段，字段名转回 Java 的 camelCase
        result = {}
        for field_info in dataclasses.fields(value):
            field_value = getattr(value, field_info.name, None)
            if field_value is None:
                continue  # 见模块注释第 4 条：跳过 null 字段
            result[snakeToCamel(field_info.name)] = _serialize(field_value)
        return result
    # 普通 JavaBean/POJO：按实例属性输出（跳过私有/类属性）
    if hasattr(value, "__dict__"):
        return {
            snakeToCamel(key): _serialize(item)
            for key, item in vars(value).items()
            if not key.startswith("_") and not callable(item)
        }
    return str(value)


# ---------------------------------------------------------------------- 反序列化
def _typeHints(clazz: Any) -> dict:
    """解析 dataclass 的类型注解（实体里写的是字符串注解，需要 get_type_hints 求值）。"""
    try:
        return typing.get_type_hints(clazz)
    except Exception:  # noqa: BLE001 - 注解里可能引用未导入的类，退化为“不转换”
        return {}


def _convert(value: Any, target: Any) -> Any:
    """按目标类型转换 JSON 值（对应 fastjson 的 ObjectDeserializer）。"""
    if value is None or target is None:
        return value
    if isinstance(target, str):
        # 兼容 Java 风格的类名字符串（正常转写后不会出现）
        return value

    # Optional[X] / Union[X, None] / X | None
    origin = typing.get_origin(target)
    if origin is typing.Union or origin is types.UnionType:
        candidates = [arg for arg in typing.get_args(target) if arg is not type(None)]
        return _convert(value, candidates[0]) if candidates else value

    if origin in (list, List, set, tuple):
        args = typing.get_args(target)
        item_type = args[0] if args else None
        converted = [_convert(item, item_type) for item in value]
        return tuple(converted) if origin is tuple else converted

    if origin is dict:
        args = typing.get_args(target)
        key_type, value_type = (args + (None, None))[:2]
        return {
            (_convert(key, key_type) if key_type else key): _convert(item, value_type)
            for key, item in dict(value).items()
        }

    # 实体类：dict → dataclass 实例
    if isinstance(target, type) and dataclasses.is_dataclass(target):
        return _toEntity(value, target)

    if target is datetime:
        if isinstance(value, (int, float)):
            # fastjson 的毫秒时间戳写法
            return datetime.fromtimestamp(value / 1000.0)
        if isinstance(value, datetime):
            return value
        from com.ruoyi.common.utils.DateUtils import DateUtils

        parsed = DateUtils.parseDate(value)
        return parsed if parsed is not None else value  # 解析失败保留原值（宽松化，见模块注释）

    if target is date:
        if isinstance(value, datetime):
            return value.date()
        from com.ruoyi.common.utils.DateUtils import DateUtils

        parsed = DateUtils.parseDate(value)
        return parsed.date() if parsed is not None else value

    if target is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "y", "yes")

    if target in (int, float, str):
        if isinstance(value, target):
            return value
        try:
            return target(value)
        except (TypeError, ValueError):
            # 【Java→Python】fastjson 会抛 JSONException；这里宽松处理保留原值，
            # 避免脏数据中断整批解析（如需严格，可把此处改为 raise）。
            return value

    return value


def _toEntity(raw: Any, clazz: Any) -> Any:
    """把 dict 按字段名映射成 dataclass 实体（camelCase ↔ snake_case）。"""
    if raw is None:
        return None
    if isinstance(raw, clazz):
        return raw
    if not isinstance(raw, dict):
        return raw

    hints = _typeHints(clazz)
    kwargs = {}
    for field_info in dataclasses.fields(clazz):
        java_name = snakeToCamel(field_info.name)
        if java_name in raw:
            value = raw[java_name]
        elif field_info.name in raw:
            value = raw[field_info.name]  # 兼容直接使用 snake_case 的 JSON
        else:
            continue  # fastjson：缺失字段保持默认值（null）
        kwargs[field_info.name] = _convert(value, hints.get(field_info.name))
    return clazz(**kwargs)
