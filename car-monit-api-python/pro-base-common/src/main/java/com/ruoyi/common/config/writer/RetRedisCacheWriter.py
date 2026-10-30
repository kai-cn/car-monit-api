# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.writer.RetRedisCacheWriter

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/writer/RetRedisCacheWriter.java

【Java→Python】整体说明
1) ``RedisCacheWriter`` 是 Spring Data Redis 的缓存写入 SPI（put/get/putIfAbsent/
   remove/clean 五个核心操作 + 统计）。Python 侧保留同名方法，
   但把底层 ``RedisConnection`` 换成模块内 ``_InProcessConnection``（dict 模拟），
   使这个“重试型 cache writer”在没有真实 Redis 时也能跑通与验证。
2) ``Duration`` → ``datetime.timedelta``：
   - ``Duration.ZERO``            → ``timedelta(0)``
   - ``duration.toMillis()``      → ``int(duration.total_seconds() * 1000)``
   - ``isZero()`` / ``isNegative()`` → ``total_seconds() == 0`` / ``< 0``
3) ``Function<RedisConnection, T>`` / ``Consumer<RedisConnection>`` → Python 传可调用对象，
   分别用 ``callback(connection)`` 与 ``callback(connection)``（返回 None）调用。
4) ``Assert.notNull(x, "msg")`` → Python 抛 ``IllegalArgumentException``（自带断言方法）。
5) ``Optional.ofNullable(...).orElse(Collections.emptySet())`` → Python 用 ``or set()``。
6) ``CacheStatisticsCollector.create()`` / ``getCacheStatistics(name)``
   → 模块内 ``CacheStatisticsCollector`` / ``CacheStatistics`` 最小替身（计数命中/未命中）。
7) 原 Java 里 ``remove()`` 的分支判断 ``keyString.endsWith("*")`` 与
   ``connection.keys(key)`` 是**前缀/通配清理**，Python 用 ``fnmatch``（Redis 的 glob 语义：
   ``*`` 任意串、``?`` 单字符、``[...]`` 字符集），与 ``KEYS`` 命令一致。
"""
from __future__ import annotations

import fnmatch
import logging
import threading
import time
from datetime import timedelta
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class IllegalArgumentException(Exception):
    """``java.lang.IllegalArgumentException`` 的替身（Assert.notNull 抛出）。"""


class PessimisticLockingFailureException(Exception):
    """``org.springframework.dao.PessimisticLockingFailureException`` 的替身。"""


class _Assert:
    """``org.springframework.util.Assert`` 的最小替身，仅实现 notNull。"""

    @staticmethod
    def notNull(obj: Any, message: str) -> None:
        if obj is None:
            raise IllegalArgumentException(message)


class Duration:
    """``java.time.Duration`` 的最小替身（内部持有 timedelta）。

    【Java→Python】Python 标准库的 ``timedelta`` 已能表达全部需求，
    这里保留 Duration 的名字只是为了让 ``Duration.ZERO`` 这类调用点可逐字对照。
    """

    ZERO = None  # 在类体末尾赋值，避免前向引用问题

    def __init__(self, value: timedelta) -> None:
        self.value = value

    @staticmethod
    def ofMillis(millis: int) -> "Duration":
        return Duration(timedelta(milliseconds=millis))

    @staticmethod
    def ofSeconds(seconds: float) -> "Duration":
        return Duration(timedelta(seconds=seconds))

    def toMillis(self) -> int:
        return int(self.value.total_seconds() * 1000)

    def isZero(self) -> bool:
        return self.value.total_seconds() == 0

    def isNegative(self) -> bool:
        return self.value.total_seconds() < 0

    def __str__(self) -> str:
        return str(self.value)


Duration.ZERO = Duration(timedelta(0))


class SetOption:
    """``RedisStringCommands.SetOption`` 的替身：upsert / ifAbsent 两个选项。"""

    @staticmethod
    def upsert() -> str:
        return "UPSERT"

    @staticmethod
    def ifAbsent() -> str:
        return "IF_ABSENT"


class Expiration:
    """``org.springframework.data.redis.core.types.Expiration`` 的替身。"""

    def __init__(self, milliseconds: int) -> None:
        self.milliseconds = milliseconds

    @staticmethod
    def from_millis(milliseconds: int, time_unit: Optional[Any] = None) -> "Expiration":
        """``Expiration.from(long, TimeUnit)`` → Python 直接用毫秒数。

        【Java→Python】方法名不得不改：``from`` 是 Python 关键字，
        无法作为函数名，故改名为 ``from_millis``（调用点已同步）。
        """
        if time_unit is not None and hasattr(time_unit, "toMillis"):
            milliseconds = time_unit.toMillis(milliseconds)
        return Expiration(int(milliseconds))

    def getExpirationTimeInMilliseconds(self) -> int:
        return self.milliseconds


class CacheStatistics:
    """``org.springframework.data.redis.cache.CacheStatistics`` 的替身（只读快照）。"""

    def __init__(self, hits: int, misses: int, puts: int, deletes: int) -> None:
        self.hits = hits
        self.misses = misses
        self.puts = puts
        self.deletes = deletes

    def getHits(self) -> int:
        return self.hits

    def getMisses(self) -> int:
        return self.misses

    def getPuts(self) -> int:
        return self.puts

    def getDeletes(self) -> int:
        return self.deletes


class _CacheStatisticsCollector:
    """``CacheStatisticsCollector`` 替身：按 cacheName 累加 hit/miss/put/delete。"""

    def __init__(self) -> None:
        self._stats: dict[str, list[int]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def create() -> "_CacheStatisticsCollector":
        return _CacheStatisticsCollector()

    def _bucket(self, name: str) -> list[int]:
        return self._stats.setdefault(name, [0, 0, 0, 0])

    def incHits(self, name: str) -> None:
        with self._lock:
            self._bucket(name)[0] += 1

    def incMisses(self, name: str) -> None:
        with self._lock:
            self._bucket(name)[1] += 1

    def incPuts(self, name: str) -> None:
        with self._lock:
            self._bucket(name)[2] += 1

    def incDeletes(self, name: str) -> None:
        with self._lock:
            self._bucket(name)[3] += 1

    def getCacheStatistics(self, name: str) -> CacheStatistics:
        with self._lock:
            hits, misses, puts, deletes = self._bucket(name)
            return CacheStatistics(hits, misses, puts, deletes)

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


class _InProcessConnection:
    """``RedisConnection`` 的最小替身：key/value 均为 bytes，带 TTL。"""

    def __init__(self, store: dict[bytes, tuple[bytes, Optional[float]]],
                 lock: threading.RLock) -> None:
        self._store = store
        self._lock = lock
        self._closed = False

    # ---------------------------------------------------------------- 命令
    def set(self, key: bytes, value: bytes, expiration: Optional[Expiration] = None,
            option: Optional[str] = None) -> Optional[bool]:
        """对应 ``set(byte[], byte[] [, Expiration, SetOption])`` 重载。"""
        with self._lock:
            if option == SetOption.ifAbsent() and self._alive(key):
                return None  # Redis SET NX 失败返回 null
            expire_at = None
            if expiration is not None and expiration.getExpirationTimeInMilliseconds() > 0:
                expire_at = time.time() + expiration.getExpirationTimeInMilliseconds() / 1000.0
            self._store[key] = (value, expire_at)
            return True

    def setNX(self, key: bytes, value: bytes) -> bool:
        with self._lock:
            if self._alive(key):
                return False
            self._store[key] = (value, None)
            return True

    def get(self, key: bytes) -> Optional[bytes]:
        with self._lock:
            return self._get_alive(key)

    def keys(self, pattern: bytes) -> set[bytes]:
        with self._lock:
            pattern_str = pattern.decode("UTF-8") if isinstance(pattern, (bytes, bytearray)) else str(pattern)
            matched: set[bytes] = set()
            for key in list(self._store.keys()):
                if self._get_alive(key) is None:
                    continue
                key_str = key.decode("UTF-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
                if fnmatch.fnmatchcase(key_str, pattern_str):
                    matched.add(key)
            return matched

    def delete(self, keys: Any) -> int:
        """对应 ``del(byte[]... keys)``：Python 形参接受 bytes 或 bytes 列表。

        【Java→Python】方法名不得不改：``del`` 是 Python 关键字；
        ``connection.del(...)`` 的调用点已全部改为 ``connection.delete(...)``。
        """
        with self._lock:
            if isinstance(keys, (bytes, bytearray)):
                keys = [keys]
            deleted = 0
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    deleted += 1
            return deleted

    def exists(self, key: bytes) -> bool:
        with self._lock:
            return self._alive(key)

    def close(self) -> None:
        self._closed = True

    # ---------------------------------------------------------------- 内部
    def _alive(self, key: bytes) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return False
        expire_at = entry[1]
        if expire_at is not None and expire_at <= time.time():
            del self._store[key]
            return False
        return True

    def _get_alive(self, key: bytes) -> Optional[bytes]:
        if not self._alive(key):
            return None
        return self._store[key][0]


class RedisConnectionFactory:
    """``RedisConnectionFactory`` 替身：所有连接共享同一个 dict 存储。"""

    def __init__(self) -> None:
        self._store: dict[bytes, tuple[bytes, Optional[float]]] = {}
        self._lock = threading.RLock()

    def getConnection(self) -> _InProcessConnection:
        return _InProcessConnection(self._store, self._lock)


class RetRedisCacheWriter:
    """带重试/加锁能力的 Redis 缓存写入器。

    【Java→Python】两个构造重载（一个参数 / 两个参数）合并为一个，
    ``sleep_time`` 缺省为 ``Duration.ZERO``，与 Java 的委托构造一致。
    """

    def __init__(self, connection_factory: RedisConnectionFactory,
                 sleep_time: Optional[Duration] = None) -> None:
        self.statistics = _CacheStatisticsCollector.create()
        _Assert.notNull(connection_factory, "ConnectionFactory must not be null!")
        if sleep_time is None:
            sleep_time = Duration.ZERO
        _Assert.notNull(sleep_time, "SleepTime must not be null!")
        self.connectionFactory = connection_factory
        self.sleepTime = sleep_time

    # ------------------------------------------------------------------ 写入
    def put(self, name: str, key: bytes, value: bytes,
            ttl: Optional[Duration]) -> None:
        _Assert.notNull(name, "Name must not be null!")
        _Assert.notNull(key, "Key must not be null!")
        _Assert.notNull(value, "Value must not be null!")

        def callback(connection: _InProcessConnection) -> str:
            if self.shouldExpireWithin(ttl):
                connection.set(key, value,
                               Expiration.from_millis(ttl.toMillis(), _MillisecondsUnit()),
                               SetOption.upsert())
            else:
                connection.set(key, value)
            return "OK"

        self.execute(name, callback)
        self.statistics.incPuts(name)

    def get(self, name: str, key: bytes) -> Optional[bytes]:
        _Assert.notNull(name, "Name must not be null!")
        _Assert.notNull(key, "Key must not be null!")
        value = self.execute(name, lambda connection: connection.get(key))
        if value is None:
            self.statistics.incMisses(name)
        else:
            self.statistics.incHits(name)
        return value

    def putIfAbsent(self, name: str, key: bytes, value: bytes,
                    ttl: Optional[Duration]) -> Optional[bytes]:
        _Assert.notNull(name, "Name must not be null!")
        _Assert.notNull(key, "Key must not be null!")
        _Assert.notNull(value, "Value must not be null!")

        def callback(connection: _InProcessConnection) -> Optional[bytes]:
            if self.isLockingCacheWriter():
                self.doLock(name, connection)
            try:
                if self.shouldExpireWithin(ttl):
                    put = connection.set(key, value, Expiration.from_millis(ttl.toMillis()),
                                         SetOption.ifAbsent())
                    put = bool(put)
                else:
                    put = connection.setNX(key, value)

                if put:
                    # Java: Object obj = null; return (byte[]) obj;
                    return None
                return connection.get(key)
            finally:
                if self.isLockingCacheWriter():
                    self.doUnlock(name, connection)

        return self.execute(name, callback)

    def remove(self, name: str, key: bytes) -> None:
        _Assert.notNull(name, "Name must not be null!")
        _Assert.notNull(key, "Key must not be null!")
        key_string = key.decode("UTF-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
        log.info("redis remove key:%s", key_string)
        key_is_all = "*"
        if key_string is not None and key_string.endswith(key_is_all):
            def callback_batch(connection: _InProcessConnection) -> int:
                keys = connection.keys(key)
                del_num = 0
                for key_byte in keys:
                    del_num += connection.delete([key_byte])
                return del_num

            self.execute(name, callback_batch)
        else:
            self.execute(name, lambda connection: connection.delete([key]))
        self.statistics.incDeletes(name)

    def clean(self, name: str, pattern: bytes) -> None:
        _Assert.notNull(name, "Name must not be null!")
        _Assert.notNull(pattern, "Pattern must not be null!")

        def callback(connection: _InProcessConnection) -> str:
            was_locked = False
            try:
                if self.isLockingCacheWriter():
                    self.doLock(name, connection)
                    was_locked = True

                keys = list(connection.keys(pattern) or set())
                if len(keys) > 0:
                    connection.delete(keys)
            finally:
                if was_locked and self.isLockingCacheWriter():
                    self.doUnlock(name, connection)
            return "OK"

        self.execute(name, callback)

    # ------------------------------------------------------------------ 锁
    def lock(self, name: str) -> None:
        self.execute(name, lambda connection: self.doLock(name, connection))

    def unlock(self, name: str) -> None:
        self.executeLockFree(lambda connection: self.doUnlock(name, connection))

    def doLock(self, name: str, connection: _InProcessConnection) -> bool:
        return connection.setNX(self.createCacheLockKey(name), b"")

    def doUnlock(self, name: str, connection: _InProcessConnection) -> int:
        return connection.delete([self.createCacheLockKey(name)])

    def doCheckLock(self, name: str, connection: _InProcessConnection) -> bool:
        return connection.exists(self.createCacheLockKey(name))

    def isLockingCacheWriter(self) -> bool:
        return not self.sleepTime.isZero() and not self.sleepTime.isNegative()

    # ------------------------------------------------------------------ 执行骨架
    def execute(self, name: str, callback: Callable[[_InProcessConnection], Any]) -> Any:
        connection = self.connectionFactory.getConnection()
        try:
            self.checkAndPotentiallyWaitUntilUnlocked(name, connection)
            return callback(connection)
        finally:
            connection.close()

    def executeLockFree(self, callback: Callable[[_InProcessConnection], Any]) -> None:
        connection = self.connectionFactory.getConnection()
        try:
            callback(connection)
        finally:
            connection.close()

    def checkAndPotentiallyWaitUntilUnlocked(self, name: str,
                                             connection: _InProcessConnection) -> None:
        if self.isLockingCacheWriter():
            try:
                while self.doCheckLock(name, connection):
                    # Thread.sleep(millis) → time.sleep(seconds)
                    time.sleep(self.sleepTime.toMillis() / 1000.0)
            except KeyboardInterrupt as e:
                # InterruptedException → Python 无该异常；线程中断语义用 InterruptedError 表达
                raise PessimisticLockingFailureException(
                    f"Interrupted while waiting to unlock cache {name}", e)

    # ------------------------------------------------------------------ 静态工具
    @staticmethod
    def shouldExpireWithin(ttl: Optional[Duration]) -> bool:
        return ttl is not None and not ttl.isZero() and not ttl.isNegative()

    @staticmethod
    def createCacheLockKey(name: str) -> bytes:
        return f"{name}~lock".encode("UTF-8")

    # ------------------------------------------------------------------ 统计
    def getCacheStatistics(self, cache_name: str) -> CacheStatistics:
        return self.statistics.getCacheStatistics(cache_name)

    def clearStatistics(self, name: str) -> None:
        # Java 原实现为空方法（清空统计的语义未落地），保持空实现
        return None

    def withStatisticsCollector(self, cache_statistics_collector: Any) -> "RetRedisCacheWriter":
        # Java 原实现直接 return null（缺陷：链式调用会 NPE），保持原样返回 None
        return None  # type: ignore[return-value]


class _MillisecondsUnit:
    """``TimeUnit.MILLISECONDS`` 的壳：Expiration.from 里用于“不换算”。"""

    def toMillis(self, value: float) -> int:
        return int(value)
