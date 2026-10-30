# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.FastJson2JsonRedisSerializer

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/FastJson2JsonRedisSerializer.java

【Java→Python】整体说明
1) Java 泛型 ``FastJson2JsonRedisSerializer<T>`` + ``Class<T> clazz`` 构造参数
   → Python 没有运行期泛型，改为在构造时传入 ``clazz``（type 对象），
   序列化时用它补回 "@type"，反序列化时用它还原实体。
2) fastjson2 的 ``JSONWriter.Feature.WriteClassName`` 会把类名写成 "@type" 字段；
   Python 用 json.dumps + 手工写入 "@type" 复现（AutoType 白名单语义在下文 _check_auto_type）。
3) fastjson2 的 ``JSONReader.autoTypeFilter(whitelist)`` 是**安全白名单**：只有包名前缀命中
   白名单才允许反序列化成真实类型，否则退化成 dict。Python 用字符串前缀判断还原该行为。
4) ``new byte[0]`` → ``b""``；``bytes == null || bytes.length <= 0`` → ``not bytes_``。
"""
from __future__ import annotations

import dataclasses
import importlib
import json
from typing import Any, Optional

# Charset.forName("UTF-8") → 直接用字符串标记编码名（Python 的 str.encode 参数）
DEFAULT_CHARSET = "UTF-8"


def _type_name(obj: Any) -> str:
    """模拟 fastjson2 写出的 "@type"：Java 是包名.类名，这里统一用 Python 全限定名。"""
    cls = type(obj)
    module = getattr(cls, "__module__", "")
    return f"{module}.{cls.__qualname__}" if module else cls.__qualname__


def _to_json_compatible(obj: Any) -> Any:
    """把任意对象转成 json 可编码结构，并携带 "@type"（对应 WriteClassName）。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        result = {"@type": "java.util.HashMap"}
        for k, v in obj.items():
            result[k] = _to_json_compatible(v)
        return result
    if isinstance(obj, (list, tuple, set)):
        return [_to_json_compatible(item) for item in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {"@type": _type_name(obj)}
        for field in dataclasses.fields(obj):
            result[field.name] = _to_json_compatible(getattr(obj, field.name))
        return result
    if hasattr(obj, "__dict__"):
        result = {"@type": _type_name(obj)}
        for k, v in vars(obj).items():
            result[k] = _to_json_compatible(v)
        return result
    # 其余类型（date/datetime/Decimal）交给 json default 处理
    return obj


class FastJson2JsonRedisSerializer:
    """Redis 使用 FastJson 序列化。

    【Java→Python】
    Java 里本类 ``implements RedisSerializer<T>``，直接作为 RedisTemplate 的
    valueSerializer/hashValueSerializer；Python 侧同样只需实现
    ``serialize(value) -> bytes`` 与 ``deserialize(bytes) -> T`` 两个方法，
    RedisCache._InMemoryRedisTemplate 会按鸭子类型调用它们。
    """

    # 自动识别 json 对象白名单配置（仅允许解析的包名，范围越小越安全）
    JSON_WHITELIST_STR = ["org.springframework", "com.ruoyi"]
    # 对应 Python：运行在 refactor 目录下的模块前缀
    PY_WHITELIST_STR = ["com.ruoyi", "org.springframework"]

    def __init__(self, clazz: Any) -> None:
        super().__init__()
        self.clazz = clazz

    def serialize(self, t: Any) -> bytes:
        """对应 ``serialize(T t)``：null 返回空字节数组。"""
        if t is None:
            return b""
        # JSON.toJSONString(t, JSONWriter.Feature.WriteClassName)
        text = json.dumps(_to_json_compatible(t), ensure_ascii=False, default=str,
                          separators=(",", ":"))
        return text.encode(DEFAULT_CHARSET)

    def deserialize(self, bytes_: Optional[bytes]) -> Any:
        """对应 ``deserialize(byte[] bytes)``：空数组返回 null。"""
        if bytes_ is None or len(bytes_) <= 0:
            return None
        if isinstance(bytes_, (bytes, bytearray)):
            text = bytes_.decode(DEFAULT_CHARSET)
        else:
            # 兼容调用方直接传 str 的场景
            text = str(bytes_)
        # JSON.parseObject(str, clazz, AUTO_TYPE_FILTER)
        return self._parse_object(text)

    # ------------------------------------------------------------------ 内部实现
    @staticmethod
    def _allows(type_name: Optional[str]) -> bool:
        """等价于 fastjson2 AutoTypeFilter：包名前缀命中白名单才允许实例化。"""
        if not type_name:
            return False
        prefixes = FastJson2JsonRedisSerializer.JSON_WHITELIST_STR + \
            FastJson2JsonRedisSerializer.PY_WHITELIST_STR
        return any(type_name.startswith(prefix) for prefix in prefixes)

    def _parse_object(self, text: str) -> Any:
        data = json.loads(text)
        return self._convert(data)

    def _convert(self, data: Any) -> Any:
        if isinstance(data, list):
            return [self._convert(item) for item in data]
        if not isinstance(data, dict):
            return data

        payload = {k: self._convert(v) for k, v in data.items() if k != "@type"}
        type_name = data.get("@type")
        # 白名单校验失败 → 与 fastjson2 一样只返回普通 Map（dict），避免反序列化漏洞
        if not self._allows(type_name):
            return payload
        target = self._resolve_clazz(type_name if type_name else "")
        if target is None or not isinstance(target, type):
            return payload
        try:
            if dataclasses.is_dataclass(target):
                allowed = {f.name for f in dataclasses.fields(target)}
                return target(**{k: v for k, v in payload.items() if k in allowed})
            return target(**payload)
        except Exception:
            # 还原失败时降级为 dict（Java 侧会抛 SerializationException，这里做宽松处理并注释）
            return payload

    def _resolve_clazz(self, type_name: str) -> Any:
        """优先使用构造传入的 clazz；否则按 "@type" 反射导入（等价于 Class.forName）。"""
        if self.clazz is not None and not isinstance(self.clazz, type(None)):
            short_name = type_name.rsplit(".", 1)[-1]
            if short_name == getattr(self.clazz, "__qualname__", None) or \
                    short_name == getattr(self.clazz, "__name__", None):
                return self.clazz
        if "." not in type_name:
            return None
        module_name, _, class_name = type_name.rpartition(".")
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except Exception:
            return None
