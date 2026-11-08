# -*- coding: utf-8 -*-
"""P2-2：真实 Redis 集成测试（默认跳过）。

开启方式（本机 Redis 已起在 6379）：
    CAR_MONIT_TEST_REDIS=1 CAR_MONIT_REDIS_URL=redis://127.0.0.1:6379/15 \
      python -m pytest tests/business/test_integration_redis.py -q

CI 的 integration job 由 service container 提供服务并注入同组环境变量。
"""
from __future__ import annotations

import datetime as _dt
import os
from decimal import Decimal

import pytest

import bootstrap  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("CAR_MONIT_TEST_REDIS") != "1",
                       reason="需要真实 Redis：设置 CAR_MONIT_TEST_REDIS=1 开启"),
]

REDIS_URL = os.environ.get("CAR_MONIT_REDIS_URL", "redis://127.0.0.1:6379/15")
KEY_PREFIX = "car-monit-test:p2:"


@pytest.fixture()
def template():
    from app.middleware.real_redis import RealRedisTemplate

    instance = RealRedisTemplate(REDIS_URL, fallback="error")
    yield instance
    keys = instance.keys(KEY_PREFIX + "*")
    if keys:
        instance.client.delete(*keys)


def test_string_value_round_trip_and_ttl(template) -> None:
    key = KEY_PREFIX + "str"
    template.opsForValue().set(key, "hello")
    assert template.opsForValue().get(key) == "hello"

    template.opsForValue().set(key, "temp", timeout=30)
    ttl = template.getExpire(key)
    assert 0 < ttl <= 30

    assert template.opsForValue().increment(KEY_PREFIX + "counter", 5) == 5
    assert template.opsForValue().increment(KEY_PREFIX + "counter") == 6

    assert template.opsForValue().setIfAbsent(key, "x") is False  # 已存在
    assert template.opsForValue().setIfAbsent(KEY_PREFIX + "nx", "y", timeout=10) is True

    assert template.delete(key) == 1
    assert template.opsForValue().get(key) is None


def test_entity_round_trip_is_fastjson_compatible(template) -> None:
    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    key = KEY_PREFIX + "entity"
    entity = OdsSzdnGantry()
    entity.setId("g-42")
    entity.setGantryCode("G42")
    entity.setGantryName("集成测试门架")
    template.opsForValue().set(key, entity)

    # 原始字节即 FastJson WriteClassName 形态（Java 侧可直接反序列化）
    raw = template.client.get(key)
    assert raw.startswith(b'{"@type":"com.ruoyi.base.domain.OdsSzdnGantry"')

    restored = template.opsForValue().get(key)
    assert isinstance(restored, OdsSzdnGantry)
    assert restored.getId() == "g-42"
    assert restored.getGantryCode() == "G42"


def test_decimal_and_datetime_fields_survive_round_trip(template) -> None:
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    key = KEY_PREFIX + "fee"
    record = OdsLwzxsfsjFeeRecords01()
    record.setBigId("fee-1")
    record.setFee(Decimal("123.45"))
    record.setTranstime(_dt.datetime(2026, 6, 1, 12, 30, 0))
    template.opsForValue().set(key, record)

    restored = template.opsForValue().get(key)
    assert isinstance(restored, OdsLwzxsfsjFeeRecords01)
    assert restored.getFee() == Decimal("123.45")
    assert restored.getTranstime() == _dt.datetime(2026, 6, 1, 12, 30, 0)


def test_list_set_hash_operations(template) -> None:
    lkey, skey, hkey = KEY_PREFIX + "list", KEY_PREFIX + "set", KEY_PREFIX + "hash"

    assert template.opsForList().rightPushAll(lkey, ["a", "b", "c"]) == 3
    template.opsForList().leftPush(lkey, "z")
    assert template.opsForList().range(lkey, 0, -1) == ["z", "a", "b", "c"]
    assert template.opsForList().rightPop(lkey) == "c"
    assert template.opsForList().remove(lkey, 1, "a") == 1
    template.opsForList().trim(lkey, 0, 0)
    assert template.opsForList().range(lkey, 0, -1) == ["z"]

    assert template.opsForSet().add(skey, ["m1", "m2"]) == 2
    assert template.opsForSet().isMember(skey, "m1") is True
    assert template.opsForSet().size(skey) == 2
    assert template.opsForSet().members(skey) == {"m1", "m2"}
    bound = template.boundSetOps(skey)
    assert bound.add("m3") == 1
    assert bound.members() == {"m1", "m2", "m3"}

    template.opsForHash().putAll(hkey, {"f1": "v1", "f2": 7})
    template.opsForHash().put(hkey, "f3", "v3")
    assert template.opsForHash().get(hkey, "f1") == "v1"
    assert template.opsForHash().entries(hkey) == {"f1": "v1", "f2": 7, "f3": "v3"}
    assert template.opsForHash().multiGet(hkey, ["f1", "missing"]) == ["v1", None]
    assert template.opsForHash().hasKey(hkey, "f2") is True
    assert template.opsForHash().delete(hkey, "f3") == 1
    assert template.opsForHash().increment(hkey, "cnt", 2.5) == 2.5


def test_expire_and_keys_pattern(template) -> None:
    key = KEY_PREFIX + "exp"
    template.opsForValue().set(key, "v")
    assert template.hasKey(key) is True
    assert template.expire(key, 60) is True
    assert 0 < template.getExpire(key) <= 60
    found = template.keys(KEY_PREFIX + "exp*")
    assert key in found
    template.delete([key])
    assert template.hasKey(key) is False


def test_redis_cache_facade_over_real_template(monkeypatch, template) -> None:
    """业务入口（RedisCache）+ 共享工厂在真实 Redis 上的完整链路。"""
    from com.ruoyi.common.core.redis.RedisCache import RedisCache

    monkeypatch.setenv("CAR_MONIT_REDIS_URL", REDIS_URL)
    cache = RedisCache()
    cache.setCacheObject(KEY_PREFIX + "facade", "v1", timeout=60)
    assert cache.getCacheObject(KEY_PREFIX + "facade") == "v1"
    assert cache.hasKey(KEY_PREFIX + "facade") is True
    assert cache.deleteObject(KEY_PREFIX + "facade") is True
    assert cache.getCacheObject(KEY_PREFIX + "facade") is None
