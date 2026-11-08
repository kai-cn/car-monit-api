# -*- coding: utf-8 -*-
"""真实 Redis 读写适配（P2-2，docs/迁移审阅报告.md）。

背景
----
此前 ``CAR_MONIT_REDIS_URL`` 只提供"未命中且标量"的**只读穿透**（_RespClient），
写永远只在进程内——是半成品。本模块把它升级为完整读写适配：设置
``CAR_MONIT_REDIS_URL``（如 ``redis://127.0.0.1:6379/0``）后，
``RedisCache`` / ``defaultRedisTemplate()`` / ``defaultStringRedisTemplate()``
共享的模板切换为 :class:`RealRedisTemplate`，全部操作走真实 Redis。

值编解码（与 Java FastJson 的互通）
------------------------------------
对标 RuoYi 的 ``FastJson2JsonRedisSerializer``：

* 标量：``str``/``int``/``float``/``bool`` 以 JSON 文本读写（Java 侧
  ``JSON.parse`` 可还原）；
* 实体（dataclass）：写为 ``{"@type": "<FQCN>", <camelCase 字段>...}``
  （等价 ``JSONWriter.Feature.WriteClassName``），读回按 ``@type`` 反射重建
  dataclass 并按字段类型恢复 datetime/Decimal；
* ``Decimal`` → 字符串（保精度；fastjson2 在有类型目标时可把字符串还原为
  BigDecimal）；
* ``datetime`` → ``yyyy-MM-dd HH:mm:ss`` 文本。**已知差异**：Java 侧 FastJson
  默认把 Date 序列化为毫秒时间戳，Python 写的是文本；Java 读取文本仍可解析
  为 Date（fastjson2 支持常见格式），如需毫秒时间戳格式属决策 D2 的细化项；
* 嵌套 list/dict 递归处理；list 内的实体重建为 dict（罕见路径，文档化限制）。

降级语义（重要）
----------------
* ``CAR_MONIT_REDIS_FALLBACK=error``（prod 模式默认）：连接失败**抛错**——
  对齐 Java 的 ``RedisConnectionFailureException`` 传播行为（查询 500）；
* ``CAR_MONIT_REDIS_FALLBACK=memory``（shim 模式默认）：首次连接失败后**熔断**，
  本模板后续读写全部落到进程内内存（保持读写一致性），每 60 秒半开重试；
  恢复后自动切回真实 Redis。**降级期间写入的数据不会回灌真实 Redis**；
* 单元测试/CI 无 Redis 时不设置 URL 即纯内存，互不影响。

线程安全：redis-py 自带连接池线程安全；熔断标志仅做尽力而为的原子性
（竞争最坏结果是多打一条日志/多一次重试）。
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import importlib
import json
import logging
import os
import typing
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import redis as redis_py

from com.ruoyi.common.core.redis.RedisCache import TimeUnit, _InMemoryRedisTemplate

from app.compat import java_meta
from app.middleware.breaker import CircuitBreaker

__all__ = ["RealRedisTemplate", "redis_fallback_policy"]

log = logging.getLogger(__name__)

_DATETIME_TEXT = "%Y-%m-%d %H:%M:%S"
#: 熔断后多久半开重试真实 Redis（秒）
_RETRY_SECONDS = 60.0


def redis_fallback_policy() -> str:
    """降级策略：``CAR_MONIT_REDIS_FALLBACK`` 显式优先；默认 prod=error / shim=memory。"""
    explicit = (os.environ.get("CAR_MONIT_REDIS_FALLBACK") or "").strip().lower()
    if explicit in ("memory", "error"):
        return explicit
    from app.runtime import is_strict

    return "error" if is_strict() else "memory"


# --------------------------------------------------------------------- codec
def _camelize(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _fqcn(cls: type) -> str:
    module, name = cls.__module__, cls.__name__
    return module if module.endswith("." + name) else module + "." + name


def _enc(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, _dt.datetime):
        return value.strftime(_DATETIME_TEXT)
    if isinstance(value, (_dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _enc_entity(value)
    if isinstance(value, dict):
        return {str(k): _enc(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_enc(v) for v in value]
    raise TypeError("Redis 适配无法序列化 %r（类型 %s）" % (value, type(value).__name__))


def _enc_entity(entity: Any) -> dict[str, Any]:
    cls = type(entity)
    fqcn = _fqcn(cls)
    field_map = java_meta.JAVA_NAMES.get(fqcn) or {}
    result: dict[str, Any] = {"@type": fqcn}
    for field in dataclasses.fields(entity):
        value = getattr(entity, field.name)
        if value is None:
            continue  # fastjson 默认不写 null 字段
        result[field_map.get(field.name) or _camelize(field.name)] = _enc(value)
    return result


def encode(value: Any) -> bytes:
    """Python 值 → FastJson 兼容字节。"""
    return json.dumps(_enc(value), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _inner(hint: Any) -> Any:
    if typing.get_origin(hint) is typing.Union:
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return args[0] if args else hint
    return hint


def _coerce(value: Any, hint: Any) -> Any:
    target = _inner(hint)
    if value is None:
        return None
    try:
        if target is _dt.datetime and isinstance(value, str):
            return _dt.datetime.fromisoformat(value)
        if target is _dt.date and isinstance(value, str):
            return _dt.date.fromisoformat(value)
        if target is Decimal and isinstance(value, (str, int, float)):
            return Decimal(str(value))
        if target is float and isinstance(value, (int, str)):
            return float(value)
        if target is int and isinstance(value, str):
            return int(value)
    except (ValueError, ArithmeticError):
        return value  # 与 MyBatis 的宽松转换一致：转不动就原样交给调用方
    return value


def _resolve_class(fqcn: str) -> Optional[type]:
    _, _, class_name = fqcn.rpartition(".")
    # 镜像树布局：类所在的模块路径就是 FQCN 本身（com/ruoyi/.../Foo.py）；
    # 兼容少数定义在包 __init__ 里的情况（module = 去掉类名的包路径）。
    for module_name in (fqcn, fqcn.rpartition(".")[0]):
        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - 反射失败按未命中处理
            continue
        cls = getattr(module, class_name, None)
        if isinstance(cls, type):
            return cls
    return None


def _rebuild(cls: type, data: dict[str, Any]) -> Any:
    field_map = java_meta.JAVA_NAMES.get(_fqcn(cls)) or {}
    try:
        hints = typing.get_type_hints(cls)
    except Exception:  # noqa: BLE001
        hints = {}
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        camel = field_map.get(field.name) or _camelize(field.name)
        if camel in data:
            kwargs[field.name] = _coerce(data[camel], hints.get(field.name))
    return cls(**kwargs)


def _dec(data: Any) -> Any:
    if isinstance(data, dict):
        fqcn = data.get("@type")
        if isinstance(fqcn, str):
            cls = _resolve_class(fqcn)
            if cls is not None and dataclasses.is_dataclass(cls):
                return _rebuild(cls, data)
        return {k: _dec(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_dec(v) for v in data]
    return data


def decode(raw: Any) -> Any:
    """FastJson 兼容字节 → Python 值；非 JSON 原样返回字符串。"""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return _dec(json.loads(raw))
    except (ValueError, TypeError):
        return raw


def _ttl_kwargs(timeout: Optional[int], time_unit: Optional[Any]) -> dict[str, Any]:
    if timeout is None:
        return {}
    millis = int(time_unit.toMillis(int(timeout))) if time_unit is not None else int(timeout) * 1000
    if millis >= 1000:
        return {"ex": max(1, millis // 1000)}
    return {"px": max(1, millis)}


def _to_seconds(timeout: int, time_unit: Optional[Any]) -> int:
    return max(1, int(time_unit.toSeconds(int(timeout))) if time_unit is not None else int(timeout))


def _iterable_or_single(values: Any) -> list[Any]:
    if isinstance(values, (list, tuple, set, frozenset)):
        return list(values)
    return [values]


# ---------------------------------------------------------------------- ops
class _RealValueOps:
    def __init__(self, template: "RealRedisTemplate") -> None:
        self._t = template

    def set(self, key: str, value: Any, timeout: Optional[int] = None,
            time_unit=None) -> None:
        payload = encode(value)
        ttl = _ttl_kwargs(timeout, time_unit)

        def real() -> None:
            self._t.client.set(key, payload, **ttl)

        def memory() -> None:
            self._t._memory.opsForValue().set(key, value, timeout, time_unit)

        self._t._run("opsForValue().set", real, memory)

    def get(self, key: str) -> Any:
        def real() -> Any:
            return decode(self._t.client.get(key))

        def memory() -> Any:
            return self._t._memory.opsForValue().get(key)

        return self._t._run("opsForValue().get", real, memory)

    def increment(self, key: str, delta: int = 1) -> int:
        def real() -> int:
            return int(self._t.client.incrby(key, int(delta)))

        def memory() -> int:
            return self._t._memory.opsForValue().increment(key, delta)

        return self._t._run("opsForValue().increment", real, memory)

    def setIfAbsent(self, key: str, value: Any, timeout: Optional[int] = None,
                    time_unit=None) -> bool:
        payload = encode(value)
        ttl = _ttl_kwargs(timeout, time_unit)

        def real() -> bool:
            return bool(self._t.client.set(key, payload, nx=True, **ttl))

        def memory() -> bool:
            return self._t._memory.opsForValue().setIfAbsent(key, value, timeout, time_unit)

        return self._t._run("opsForValue().setIfAbsent", real, memory)


class _RealListOps:
    def __init__(self, template: "RealRedisTemplate") -> None:
        self._t = template

    def rightPushAll(self, key: str, data_list: Any) -> int:
        payload = [encode(v) for v in list(data_list)]

        def real() -> int:
            return int(self._t.client.rpush(key, *payload)) if payload else int(self._t.client.llen(key))

        def memory() -> int:
            return self._t._memory.opsForList().rightPushAll(key, data_list)

        return self._t._run("opsForList().rightPushAll", real, memory)

    def rightPush(self, key: str, value: Any) -> int:
        payload = encode(value)
        return self._t._run(
            "opsForList().rightPush",
            lambda: int(self._t.client.rpush(key, payload)),
            lambda: self._t._memory.opsForList().rightPush(key, value))

    def leftPush(self, key: str, value: Any) -> int:
        payload = encode(value)
        return self._t._run(
            "opsForList().leftPush",
            lambda: int(self._t.client.lpush(key, payload)),
            lambda: self._t._memory.opsForList().leftPush(key, value))

    def range(self, key: str, start: int, end: int) -> list[Any]:
        return self._t._run(
            "opsForList().range",
            lambda: [decode(x) for x in self._t.client.lrange(key, start, end)],
            lambda: self._t._memory.opsForList().range(key, start, end))

    def size(self, key: str) -> int:
        return self._t._run(
            "opsForList().size",
            lambda: int(self._t.client.llen(key)),
            lambda: self._t._memory.opsForList().size(key))

    def index(self, key: str, index: int) -> Any:
        return self._t._run(
            "opsForList().index",
            lambda: decode(self._t.client.lindex(key, index)),
            lambda: self._t._memory.opsForList().index(key, index))

    def set(self, key: str, index: int, value: Any) -> None:
        payload = encode(value)

        def real() -> None:
            try:
                self._t.client.lset(key, index, payload)
            except redis_py.ResponseError as error:
                if "index out of range" in str(error):
                    raise IndexError("index out of range")
                raise

        def memory() -> None:
            self._t._memory.opsForList().set(key, index, value)

        self._t._run("opsForList().set", real, memory)

    def remove(self, key: str, count: int, value: Any) -> int:
        payload = encode(value)
        return self._t._run(
            "opsForList().remove",
            lambda: int(self._t.client.lrem(key, count, payload)),
            lambda: self._t._memory.opsForList().remove(key, count, value))

    def trim(self, key: str, start: int, end: int) -> None:
        self._t._run(
            "opsForList().trim",
            lambda: self._t.client.ltrim(key, start, end),
            lambda: self._t._memory.opsForList().trim(key, start, end))

    def rightPop(self, key: str, timeout: Optional[int] = None, time_unit=None) -> Any:
        """RPOP / BRPOP。timeout<=0（Java 的永久阻塞）退化为立即返回 None（与内存替身一致）。"""
        seconds = _to_seconds(timeout, time_unit) if timeout and timeout > 0 else 0

        def real() -> Any:
            if seconds:
                pair = self._t.client.brpop(key, timeout=seconds)
                return decode(pair[1]) if pair else None
            return decode(self._t.client.rpop(key))

        def memory() -> Any:
            return self._t._memory.opsForList().rightPop(key, timeout, time_unit)

        return self._t._run("opsForList().rightPop", real, memory)


class _RealSetOps:
    def __init__(self, template: "RealRedisTemplate") -> None:
        self._t = template

    def add(self, key: str, values: Any) -> int:
        payload = [encode(v) for v in _iterable_or_single(values)]
        return self._t._run(
            "opsForSet().add",
            lambda: int(self._t.client.sadd(key, *payload)),
            lambda: self._t._memory.opsForSet().add(key, values))

    def members(self, key: str) -> set[Any]:
        return self._t._run(
            "opsForSet().members",
            lambda: {decode(x) for x in self._t.client.smembers(key)},
            lambda: self._t._memory.opsForSet().members(key))

    def isMember(self, key: str, value: Any) -> bool:
        payload = encode(value)
        return self._t._run(
            "opsForSet().isMember",
            lambda: bool(self._t.client.sismember(key, payload)),
            lambda: self._t._memory.opsForSet().isMember(key, value))

    def size(self, key: str) -> int:
        return self._t._run(
            "opsForSet().size",
            lambda: int(self._t.client.scard(key)),
            lambda: self._t._memory.opsForSet().size(key))

    def remove(self, key: str, values: Any) -> int:
        payload = [encode(v) for v in _iterable_or_single(values)]
        return self._t._run(
            "opsForSet().remove",
            lambda: int(self._t.client.srem(key, *payload)),
            lambda: self._t._memory.opsForSet().remove(key, values))


class _RealBoundSetOps:
    def __init__(self, template: "RealRedisTemplate", key: str) -> None:
        self._t = template
        self._key = key

    def add(self, *values: Any) -> int:
        payload = [encode(v) for v in values]
        return self._t._run(
            "boundSetOps().add",
            lambda: int(self._t.client.sadd(self._key, *payload)),
            lambda: self._t._memory.boundSetOps(self._key).add(*values))

    def members(self) -> set[Any]:
        return self._t._run(
            "boundSetOps().members",
            lambda: {decode(x) for x in self._t.client.smembers(self._key)},
            lambda: self._t._memory.opsForSet().members(self._key))

    def isMember(self, value: Any) -> bool:
        payload = encode(value)
        return self._t._run(
            "boundSetOps().isMember",
            lambda: bool(self._t.client.sismember(self._key, payload)),
            lambda: self._t._memory.opsForSet().isMember(self._key, value))

    def remove(self, *values: Any) -> int:
        payload = [encode(v) for v in values]
        return self._t._run(
            "boundSetOps().remove",
            lambda: int(self._t.client.srem(self._key, *payload)),
            lambda: self._t._memory.opsForSet().remove(self._key, list(values)))


class _RealHashOps:
    def __init__(self, template: "RealRedisTemplate") -> None:
        self._t = template

    def putAll(self, key: str, data_map: dict[str, Any]) -> None:
        mapping = {str(k): encode(v) for k, v in (data_map or {}).items()}

        def real() -> None:
            if mapping:
                self._t.client.hset(key, mapping=mapping)

        def memory() -> None:
            self._t._memory.opsForHash().putAll(key, data_map)

        self._t._run("opsForHash().putAll", real, memory)

    def put(self, key: str, h_key: str, value: Any) -> None:
        payload = encode(value)
        self._t._run(
            "opsForHash().put",
            lambda: self._t.client.hset(key, h_key, payload),
            lambda: self._t._memory.opsForHash().put(key, h_key, value))

    def get(self, key: str, h_key: str) -> Any:
        return self._t._run(
            "opsForHash().get",
            lambda: decode(self._t.client.hget(key, h_key)),
            lambda: self._t._memory.opsForHash().get(key, h_key))

    def entries(self, key: str) -> dict[str, Any]:
        def real() -> dict[str, Any]:
            return {k.decode("utf-8"): decode(v)
                    for k, v in self._t.client.hgetall(key).items()}

        def memory() -> dict[str, Any]:
            return self._t._memory.opsForHash().entries(key)

        return self._t._run("opsForHash().entries", real, memory)

    def multiGet(self, key: str, h_keys: Any) -> list[Any]:
        wanted = [str(k) for k in h_keys]
        return self._t._run(
            "opsForHash().multiGet",
            lambda: [decode(x) for x in self._t.client.hmget(key, wanted)],
            lambda: self._t._memory.opsForHash().multiGet(key, h_keys))

    def delete(self, key: str, h_key: str) -> int:
        return self._t._run(
            "opsForHash().delete",
            lambda: int(self._t.client.hdel(key, h_key)),
            lambda: self._t._memory.opsForHash().delete(key, h_key))

    def hasKey(self, key: str, h_key: str) -> bool:
        return self._t._run(
            "opsForHash().hasKey",
            lambda: bool(self._t.client.hexists(key, h_key)),
            lambda: self._t._memory.opsForHash().hasKey(key, h_key))

    def increment(self, key: str, h_key: str, delta: float = 1) -> float:
        return self._t._run(
            "opsForHash().increment",
            lambda: float(self._t.client.hincrbyfloat(key, h_key, float(delta))),
            lambda: self._t._memory.opsForHash().increment(key, h_key, delta))


# ------------------------------------------------------------------ template
class RealRedisTemplate:
    """真实 Redis 模板（与 ``_InMemoryRedisTemplate`` 同构的鸭子类型）。

    见模块 docstring 的编解码与降级语义。构造**不建连**（redis-py 惰性连接），
    首次操作才触达服务。
    """

    def __init__(self, url: str, fallback: Optional[str] = None,
                 client: Optional[Any] = None) -> None:
        self._url = url
        self._fallback = fallback or redis_fallback_policy()
        self.client = client or redis_py.Redis.from_url(
            url, decode_responses=False,
            socket_connect_timeout=2, socket_timeout=5,
            health_check_interval=30)
        self._memory = _InMemoryRedisTemplate()
        self._breaker = CircuitBreaker(_RETRY_SECONDS)

    # ------------------------------------------------------------- dispatch
    def _run(self, description: str, real: Any, memory: Any) -> Any:
        allowed, probe = self._breaker.acquire()
        if not allowed:
            return memory()
        try:
            result = real()
        except redis_py.RedisError as error:
            if self._fallback == "error":
                if probe:
                    self._breaker.release_probe()
                raise
            # H2：失败分支无条件刷新窗口计时（包括半开探测失败）
            first = self._breaker.failure()
            log.warning("[Redis适配] %s %s，熔断降级为进程内内存（%.0fs 后半开重试；"
                        "降级期间的写入不会回灌真实 Redis）: %s",
                        description, "失败" if first else "半开探测仍失败",
                        _RETRY_SECONDS, error)
            return memory()
        except BaseException:
            if probe:
                self._breaker.release_probe()
            raise
        if self._breaker.success():
            log.info("[Redis适配] 真实 Redis 已恢复（%s）", self._url)
        return result

    @property
    def degraded(self) -> bool:
        """当前是否处于熔断降级（供健康检查/测试观察）。"""
        return self._breaker.degraded

    # ----------------------------------------------------------------- ops
    def opsForValue(self) -> _RealValueOps:
        return _RealValueOps(self)

    def opsForList(self) -> _RealListOps:
        return _RealListOps(self)

    def opsForSet(self) -> _RealSetOps:
        return _RealSetOps(self)

    def opsForHash(self) -> _RealHashOps:
        return _RealHashOps(self)

    def boundSetOps(self, key: str) -> _RealBoundSetOps:
        return _RealBoundSetOps(self, key)

    # ----------------------------------------------------------- template
    def expire(self, key: str, timeout: int, unit: Optional[Any] = None) -> bool:
        """Java 两个重载：expire(key, timeout)（秒）与 expire(key, timeout, TimeUnit)。"""
        if unit is None:
            unit = TimeUnit.SECONDS
        seconds = _to_seconds(timeout, unit)
        return self._run(
            "expire",
            lambda: bool(self.client.expire(key, seconds)),
            lambda: self._memory.expire(key, timeout, unit))

    def getExpire(self, key: str, unit: Optional[Any] = None) -> int:
        def real() -> int:
            ttl = int(self.client.ttl(key))
            if ttl < 0 or unit is None:
                return ttl
            return int(ttl / unit.toSeconds(1))

        def memory() -> int:
            return self._memory.getExpire(key, unit)

        return self._run("getExpire", real, memory)

    def hasKey(self, key: str) -> bool:
        return self._run(
            "hasKey",
            lambda: bool(self.client.exists(key)),
            lambda: self._memory.hasKey(key))

    def delete(self, key_or_keys: Any) -> int:
        if isinstance(key_or_keys, str):
            keys = [key_or_keys]
        else:
            keys = list(key_or_keys or [])

        def real() -> int:
            return int(self.client.delete(*keys)) if keys else 0

        def memory() -> int:
            return self._memory.delete(key_or_keys)

        return self._run("delete", real, memory)

    def keys(self, pattern: str) -> set[str]:
        def real() -> set[str]:
            return {k.decode("utf-8") for k in self.client.keys(pattern)}

        def memory() -> set[str]:
            return self._memory.keys(pattern)  # type: ignore[return-value]

        return self._run("keys", real, memory)
