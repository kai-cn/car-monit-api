# -*- coding: utf-8 -*-
"""org.springframework.data.redis.core.RedisTemplate

【无 Java 源文件：框架类替身】
Java 侧来自 spring-data-redis jar：`org.springframework.data.redis.core.RedisTemplate<K, V>`。
业务代码通过 `@Autowired private RedisTemplate redisTemplate;` 注入，然后调用：
    redisTemplate.opsForValue().set(key, value[, timeout, TimeUnit])
    redisTemplate.opsForValue().get(key)
    redisTemplate.opsForValue().increment(key, delta)
    redisTemplate.opsForList().rightPush(key, value) / range(key, 0, -1) / trim(key, -1000, -1)
    redisTemplate.opsForSet().add(key, value) / members(key)
    redisTemplate.expire(key, 2, TimeUnit.DAYS)
    redisTemplate.hasKey(key) / delete(key[, ...]) / keys(pattern)

【Java→Python 关键差异】
1) 同 RedisCache：`RedisTemplate` 在 Spring 里是**单例 Bean**，所有服务共享同一份数据；
   这里用模块级 `_DEFAULT_TEMPLATE` 还原“同一个 Redis 连接”的语义。若各服务各自 new，
   A 服务写入的缓存 B 服务读不到，与原系统行为不符。
2) 底层实现直接复用 `com.ruoyi.common.core.redis.RedisCache._InMemoryRedisTemplate`
   （dict + deepcopy 模拟序列化），避免两套内存 Redis 语义不一致。
   类名以下划线开头是因为它原本是 RedisCache 的内部替身；这里通过继承暴露成
   与 Java 同名的 `RedisTemplate`。
3) Java 泛型 `RedisTemplate<String, Object>` 在 Python 中无运行时意义，省略。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.common.core.redis.RedisCache import _InMemoryRedisTemplate

__all__ = ["RedisTemplate", "defaultRedisTemplate"]


class RedisTemplate(_InMemoryRedisTemplate):
    """`RedisTemplate<K,V>` 的进程内替身（一个实例即一份“Redis 库”）。"""


# 进程级单例：等价 Spring 容器里唯一的 RedisTemplate Bean
_DEFAULT_TEMPLATE: Optional[RedisTemplate] = None


def defaultRedisTemplate() -> RedisTemplate:
    """获取共享的 RedisTemplate（@Autowired 的默认值）。"""
    global _DEFAULT_TEMPLATE
    if _DEFAULT_TEMPLATE is None:
        _DEFAULT_TEMPLATE = RedisTemplate()
    return _DEFAULT_TEMPLATE
