# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.RedisConfiguration

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/RedisConfiguration.java

【Java→Python】整体说明
1) Spring 的 ``@Configuration`` + ``@EnableCaching`` + ``@Bean`` → Python 无容器，
   本类退化为“Bean 工厂集合”：每个方法名与 Java 的 @Bean 方法名一一对应，
   由启动代码显式调用并把返回值注册进 ``SpringUtils``。
2) ``RedisConnectionFactory`` / ``RedisTemplate`` / ``CacheManager`` 等
   Spring Data Redis 类型在 Python 侧没有等价物，这里提供**最小替身**：
   - ``RedisTemplate`` 直接复用 ``core.redis.RedisCache._InMemoryRedisTemplate``
     （进程内 map 模拟 Redis，保证业务代码行为可跑通）；
   - ``StringRedisSerializer`` / ``GenericJackson2JsonRedisSerializer`` 只做
     bytes ↔ str/对象 的编解码，满足 RedisCache 的鸭子类型调用；
   - ``RedisCacheManager`` 只保存默认配置，``getCache(name)`` 返回一个薄壳。
3) ``DefaultRedisScript<Long>``（Lua 限流脚本）→ Python 侧保留脚本文本与结果类型，
   执行由 ``eval_script`` 用纯 Python 复刻脚本逻辑（无 Redis 时不真正 EVAL）。
4) ``@Slf4j`` → 模块级 logging.getLogger；本类 Java 源码实际未使用 log，保留以对齐。
5) ``@SuppressWarnings({"unchecked", "rawtypes"})`` 属于编译期告警抑制，Python 无对应，忽略。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

from com.ruoyi.common.config.FastJson2JsonRedisSerializer import FastJson2JsonRedisSerializer
from com.ruoyi.common.core.redis.RedisCache import _InMemoryRedisTemplate

log = logging.getLogger(__name__)


class StringRedisSerializer:
    """org.springframework.data.redis.serializer.StringRedisSerializer 的替身。"""

    def __init__(self, charset: str = "UTF-8") -> None:
        self.charset = charset

    def serialize(self, value: Optional[str]) -> Optional[bytes]:
        return None if value is None else str(value).encode(self.charset)

    def deserialize(self, value: Optional[bytes]) -> Optional[str]:
        if value is None:
            return None
        return value.decode(self.charset) if isinstance(value, (bytes, bytearray)) else str(value)


class GenericJackson2JsonRedisSerializer:
    """org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer 的替身。

    【Java→Python】Java 版会在 JSON 中写入 "/@class" 类型信息；
    Python 侧仅在反序列化时尽量还原 dict/list，不还原具体类型（缓存对象按 dict 使用）。
    """

    def serialize(self, value: Any) -> Optional[bytes]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str).encode("UTF-8")

    def deserialize(self, value: Optional[bytes]) -> Any:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("UTF-8")
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value


class RedisTemplate(_InMemoryRedisTemplate):
    """Spring ``RedisTemplate<Object, Object>`` 的最小替身。

    【Java→Python】Java 通过 setConnectionFactory + 四个 serializer + afterPropertiesSet()
    完成初始化；Python 侧这些 setter 只记录配置，实际读写由父类（进程内 map）完成。
    """

    def __init__(self) -> None:
        super().__init__()
        self.connectionFactory: Any = None
        self.keySerializer: Any = None
        self.valueSerializer: Any = None
        self.hashKeySerializer: Any = None
        self.hashValueSerializer: Any = None

    def setConnectionFactory(self, connection_factory: Any) -> None:
        self.connectionFactory = connection_factory

    def setKeySerializer(self, serializer: Any) -> None:
        self.keySerializer = serializer

    def setValueSerializer(self, serializer: Any) -> None:
        self.valueSerializer = serializer

    def setHashKeySerializer(self, serializer: Any) -> None:
        self.hashKeySerializer = serializer

    def setHashValueSerializer(self, serializer: Any) -> None:
        self.hashValueSerializer = serializer

    def afterPropertiesSet(self) -> None:
        """Spring 的初始化回调；Python 无状态需要校验，空实现但保留调用点。"""
        return None


class DefaultRedisScript:
    """org.springframework.data.redis.core.script.DefaultRedisScript 的替身。

    限流脚本只有 GET / INCR / EXPIRE 三条命令，``eval_script`` 用纯 Python
    复刻同一段 Lua 逻辑，便于在没有真实 Redis 的情况下验证限流行为。
    """

    def __init__(self) -> None:
        self.scriptText: str = ""
        self.resultType: Any = None

    def setScriptText(self, script_text: str) -> None:
        self.scriptText = script_text

    def setResultType(self, result_type: Any) -> None:
        self.resultType = result_type

    def getResultType(self) -> Any:
        return self.resultType

    def getScriptAsString(self) -> str:
        return self.scriptText


class _Cache:
    """``org.springframework.cache.Cache`` 的最小替身（get/put/evict）。"""

    def __init__(self, name: str, config: "RedisCacheConfiguration") -> None:
        self.name = name
        self.config = config
        self._store: dict[Any, Any] = {}
        self._lock = threading.Lock()

    def getName(self) -> str:
        return self.name

    def get(self, key: Any) -> Any:
        with self._lock:
            return self._store.get(key)

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            self._store[key] = value

    def evict(self, key: Any) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class RedisCacheConfiguration:
    """``RedisCacheConfiguration`` 替身：只保留 entryTtl 与序列化器。"""

    def __init__(self) -> None:
        self.ttl_seconds: Optional[int] = None
        self.valueSerializer: Any = None

    @staticmethod
    def defaultCacheConfig() -> "RedisCacheConfiguration":
        return RedisCacheConfiguration()

    def entryTtl(self, duration: Any) -> "RedisCacheConfiguration":
        # Java: Duration → Python: datetime.timedelta（取总秒数保存）
        self.ttl_seconds = int(duration.total_seconds())
        return self

    def serializeValuesWith(self, pair: Any) -> "RedisCacheConfiguration":
        self.valueSerializer = pair
        return self


class RedisCacheManager:
    """``RedisCacheManager`` 替身：按名字创建并在内部缓存 _Cache 实例。"""

    def __init__(self, connection_factory: Any, defaults: RedisCacheConfiguration) -> None:
        self.connectionFactory = connection_factory
        self.defaults = defaults
        self._caches: dict[str, _Cache] = {}
        self._lock = threading.Lock()

    @staticmethod
    def builder(connection_factory: Any) -> "_RedisCacheManagerBuilder":
        return _RedisCacheManagerBuilder(connection_factory)

    def getCache(self, name: str) -> _Cache:
        with self._lock:
            if name not in self._caches:
                self._caches[name] = _Cache(name, self.defaults)
            return self._caches[name]


class _RedisCacheManagerBuilder:
    """``RedisCacheManager.builder(...).cacheDefaults(...).build()`` 的链式替身。"""

    def __init__(self, connection_factory: Any) -> None:
        self.connection_factory = connection_factory
        self._defaults: Optional[RedisCacheConfiguration] = None

    def cacheDefaults(self, config: RedisCacheConfiguration) -> "_RedisCacheManagerBuilder":
        self._defaults = config
        return self

    def build(self) -> RedisCacheManager:
        return RedisCacheManager(self.connection_factory,
                                 self._defaults or RedisCacheConfiguration.defaultCacheConfig())


class _SerializationPair:
    """``RedisSerializationContext.SerializationPair`` 的替身。"""

    def __init__(self, serializer: Any) -> None:
        self.serializer = serializer

    @staticmethod
    def fromSerializer(serializer: Any) -> "_SerializationPair":
        return _SerializationPair(serializer)


class RedisSerializationContext:
    """仅为承载 ``SerializationPair.fromSerializer(...)`` 的命名空间类。"""

    SerializationPair = _SerializationPair


class RedisConfiguration:
    """redis 配置。

    【Java→Python】Java 里 ``extends CachingConfigurerSupport`` 用于定制 cacheManager/errorHandler；
    Python 无此基类，直接以同名方法提供 Bean 工厂。
    """

    def redisTemplate(self, connection_factory: Any) -> RedisTemplate:
        """对应 ``@Bean redisTemplate(RedisConnectionFactory)``。"""
        template = RedisTemplate()
        template.setConnectionFactory(connection_factory)

        serializer = FastJson2JsonRedisSerializer(object)

        # 使用 StringRedisSerializer 来序列化和反序列化 redis 的 key 值
        template.setKeySerializer(StringRedisSerializer())
        template.setValueSerializer(serializer)

        # Hash 的 key 也采用 StringRedisSerializer 的序列化方式
        template.setHashKeySerializer(StringRedisSerializer())
        template.setHashValueSerializer(serializer)

        template.afterPropertiesSet()
        return template

    def limitScript(self) -> DefaultRedisScript:
        """对应 ``@Bean limitScript()``。"""
        redis_script = DefaultRedisScript()
        redis_script.setScriptText(self.limitScriptText())
        redis_script.setResultType(int)  # Java: Long.class → Python: int
        return redis_script

    def cacheManager(self, redis_connection_factory: Any) -> RedisCacheManager:
        """对应 ``@Bean cacheManager(RedisConnectionFactory)``。"""
        config = RedisCacheConfiguration.defaultCacheConfig() \
            .entryTtl(_duration_of_hours(1)) \
            .serializeValuesWith(
                RedisSerializationContext.SerializationPair.fromSerializer(
                    GenericJackson2JsonRedisSerializer()))
        return RedisCacheManager.builder(redis_connection_factory) \
            .cacheDefaults(config) \
            .build()

    def limitScriptText(self) -> str:
        """限流脚本（Lua 原文逐字保留）。

        【Java→Python】Java 用 "+" 拼接多行字符串；Python 用括号隐式拼接的三引号字符串，
        内容（含 \\n）保持一致，便于直接 SET 到 Redis 执行。
        """
        return (
            "local key = KEYS[1]\n"
            "local count = tonumber(ARGV[1])\n"
            "local time = tonumber(ARGV[2])\n"
            "local current = redis.call('get', key);\n"
            "if current and tonumber(current) > count then\n"
            "    return tonumber(current);\n"
            "end\n"
            "current = redis.call('incr', key)\n"
            "if tonumber(current) == 1 then\n"
            "    redis.call('expire', key, time)\n"
            "end\n"
            "return tonumber(current);"
        )


def _duration_of_hours(hours: int):
    """``Duration.ofHours(1)`` → ``datetime.timedelta``（支持 total_seconds()）。"""
    from datetime import timedelta
    return timedelta(hours=hours)


def eval_limit_script(template: Any, key: str, count: int, seconds: int) -> int:
    """用纯 Python 复刻 limitScriptText() 的 Lua 逻辑（无 Redis 时的等价实现）。

    【Java→Python】Java 由 Spring Data Redis 把脚本发送到服务端执行；
    Python 侧没有服务端脚本能力，这里按脚本语义逐行翻译，保证限流结果一致。
    """
    current = template.opsForValue().get(key)
    if current is not None and int(current) > count:
        return int(current)
    current = template.opsForValue().increment(key)
    if int(current) == 1:
        template.expire(key, seconds, _SecondsUnit())
    return int(current)


class _SecondsUnit:
    """``java.util.concurrent.TimeUnit.SECONDS`` 的壳（供 expire 识别）。"""

    name = "SECONDS"

    def toSeconds(self, duration: float) -> int:
        return int(duration)

    def __str__(self) -> str:
        return self.name
