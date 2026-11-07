# -*- coding: utf-8 -*-
"""V2 P2 回归测试：真实 Redis 适配（单元层：编解码 + 降级语义，不依赖真实服务）。"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

import pytest

import bootstrap  # noqa: F401


# --------------------------------------------------------------------- codec
def test_codec_entity_round_trip_with_atype() -> None:
    from app.middleware.real_redis import decode, encode

    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    entity = OdsSzdnGantry()
    entity.setId("g-1")
    entity.setGantryCode("G001")
    entity.setGantryName("测试门架")
    raw = encode(entity)
    # FastJson WriteClassName 形态：@type + camelCase 字段
    assert raw.startswith(b'{"@type":"com.ruoyi.base.domain.OdsSzdnGantry"')
    assert b'"gantryCode":"G001"' in raw
    restored = decode(raw)
    assert isinstance(restored, OdsSzdnGantry)
    assert restored.getId() == "g-1"
    assert restored.getGantryCode() == "G001"
    assert restored.getGantryName() == "测试门架"


def test_codec_scalar_decimal_datetime() -> None:
    from app.middleware.real_redis import decode, encode

    assert decode(encode("abc")) == "abc"
    assert decode(encode(5)) == 5
    assert decode(encode(True)) is True
    assert decode(encode(Decimal("1.50"))) == "1.50"  # 字符串保精度（fastjson2 可还原 BigDecimal）
    stamp = _dt.datetime(2026, 1, 2, 3, 4, 5)
    assert decode(encode(stamp)) == "2026-01-02 03:04:05"
    # 实体里的 Decimal/datetime 字段经类型提示还原
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    record = OdsLwzxsfsjFeeRecords01()
    record.setFee(Decimal("1.50"))
    record.setTranstime(stamp)
    restored = decode(encode(record))
    assert isinstance(restored, OdsLwzxsfsjFeeRecords01)
    assert restored.getFee() == Decimal("1.50")
    assert restored.getTranstime() == stamp


def test_codec_non_json_passthrough() -> None:
    from app.middleware.real_redis import decode

    assert decode(b"not-json") == "not-json"
    assert decode(None) is None


# ------------------------------------------------------------------ fallback
class _BrokenClient:
    """所有命令都抛 ConnectionError 的假客户端。"""

    def __getattr__(self, name):
        def _boom(*args, **kwargs):
            import redis as redis_py

            raise redis_py.ConnectionError("connection refused (test)")

        return _boom


def test_fallback_memory_policy_trips_to_memory() -> None:
    from app.middleware.real_redis import RealRedisTemplate

    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="memory",
                                 client=_BrokenClient())
    assert template.degraded is False
    template.opsForValue().set("k", "v")  # 熔断 + 内存降级
    assert template.degraded is True
    assert template.opsForValue().get("k") == "v"  # 降级期间读写一致（内存）
    cache_keys = template.keys("*")
    assert cache_keys == {"k"}


def test_fallback_error_policy_raises() -> None:
    import redis as redis_py

    from app.middleware.real_redis import RealRedisTemplate

    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="error",
                                 client=_BrokenClient())
    with pytest.raises(redis_py.ConnectionError):
        template.opsForValue().set("k", "v")


def test_fallback_policy_env_and_runtime_default(monkeypatch) -> None:
    from app.middleware.real_redis import redis_fallback_policy

    monkeypatch.delenv("CAR_MONIT_REDIS_FALLBACK", raising=False)
    monkeypatch.delenv("CAR_MONIT_RUNTIME", raising=False)
    assert redis_fallback_policy() == "memory"  # shim 默认降级
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    assert redis_fallback_policy() == "error"  # prod 默认抛错（Java 宕机语义）
    monkeypatch.setenv("CAR_MONIT_REDIS_FALLBACK", "memory")
    assert redis_fallback_policy() == "memory"  # 显式覆盖


# ------------------------------------------------------------------- factory
def test_shared_template_factory_switches_by_env(monkeypatch) -> None:
    from app.middleware.real_redis import RealRedisTemplate
    from com.ruoyi.common.core.redis.RedisCache import (
        _InMemoryRedisTemplate,
        shared_redis_template,
    )

    monkeypatch.delenv("CAR_MONIT_REDIS_URL", raising=False)
    assert isinstance(shared_redis_template(), _InMemoryRedisTemplate)

    monkeypatch.setenv("CAR_MONIT_REDIS_URL", "redis://127.0.0.1:6379/0")
    template = shared_redis_template()
    assert isinstance(template, RealRedisTemplate)

    monkeypatch.delenv("CAR_MONIT_REDIS_URL", raising=False)
    assert isinstance(shared_redis_template(), _InMemoryRedisTemplate)  # URL 变化重建

    # RedisCache / defaultRedisTemplate / defaultStringRedisTemplate 三处同一实例
    from com.ruoyi.common.core.redis.RedisCache import RedisCache
    from org.springframework.data.redis.core.RedisTemplate import defaultRedisTemplate
    from org.springframework.data.redis.core.StringRedisTemplate import (
        defaultStringRedisTemplate,
    )

    monkeypatch.setenv("CAR_MONIT_REDIS_URL", "redis://127.0.0.1:6379/0")
    shared = shared_redis_template()
    assert RedisCache().redisTemplate is shared
    assert defaultRedisTemplate() is shared
    assert defaultStringRedisTemplate() is shared
