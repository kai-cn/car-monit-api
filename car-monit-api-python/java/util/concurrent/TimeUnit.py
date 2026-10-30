# -*- coding: utf-8 -*-
"""java.util.concurrent.TimeUnit

【无 Java 源文件：框架类替身】
业务代码大量出现 `TimeUnit.SECONDS.sleep(5)`、`redisTemplate.expire(key, 2, TimeUnit.DAYS)`。

【Java→Python 关键差异】
本文件**不重复定义枚举**，而是直接 re-export `com.ruoyi.common.core.redis.RedisCache.TimeUnit`：
Java 里 TimeUnit 只有一个类，任何 import 路径拿到的都是同一批枚举常量；
若这里另建一个同名 Enum，`redisTemplate.expire(..., TimeUnit.HOURS)` 的类型判断
（isinstance / 相等比较）就会因“两个不同的类”而失效。做法是让两条 import 路径
指向**同一个对象**，最大程度还原 Java 的“单一份类”语义。
"""
from com.ruoyi.common.core.redis.RedisCache import TimeUnit  # noqa: F401  (同名 re-export)

__all__ = ["TimeUnit"]
