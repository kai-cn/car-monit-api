# -*- coding: utf-8 -*-
"""org.springframework.data.redis.core.StringRedisTemplate

【无 Java 源文件：框架类替身】
Java 侧来自 spring-data-redis：`org.springframework.data.redis.core.StringRedisTemplate`
（继承 RedisTemplate<String, String>，Key/Value 都按 String 序列化）。
业务代码（SnapshotFlowPulsarConsumer / DebeziumReadonlyPulsarConsumer）用到：
    redisTemplate.opsForValue()
            .setIfAbsent(key, String.valueOf(System.currentTimeMillis()),
                         ttlSeconds, TimeUnit.SECONDS);

【Java→Python 关键差异】
1) Java 的 StringRedisTemplate 与 RedisTemplate 共用同一个连接工厂，因此**共享同一份数据**；
   Python 侧同样继承 RedisTemplate 替身 → 同一个实例即同一份内存库。
   `defaultStringRedisTemplate()` 与 `defaultRedisTemplate()` 指向**同一个对象**，
   保证“一个进程一份 Redis”的语义（否则幂等 key 在两边各存一份）。
2) `opsForValue().setIfAbsent(key, value, timeout, TimeUnit)` 在 Java 返回 `Boolean`
   （可能为 null）；替身返回 bool（`_ValueOperations.setIfAbsent` 的实现）。
3) Java 的 StringRedisTemplate 对值做 UTF-8 编解码；Python 无此边界，直接存字符串。
"""
from __future__ import annotations

from typing import Any

from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate

__all__ = ["StringRedisTemplate", "defaultStringRedisTemplate"]


class StringRedisTemplate(RedisTemplate):
    """`StringRedisTemplate` 的进程内替身（与 RedisTemplate 共用同一套内存语义）。"""


def defaultStringRedisTemplate() -> Any:
    """获取共享的 StringRedisTemplate（@Autowired 的默认值）。

    【Java→Python】返回的就是进程级共享模板（P2-2 起与 RedisCache 共用同一
    真实/内存模板）：Spring 容器里两者操作同一个 Redis，适配器也必须操作同一份
    数据。真实适配（RealRedisTemplate）是鸭子类型，不参与本类的继承体系，因此
    不再做旧内存版的 ``__class__`` 换形。
    """
    return defaultRedisTemplate()
