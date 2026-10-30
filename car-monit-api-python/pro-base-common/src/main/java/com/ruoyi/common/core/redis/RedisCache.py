# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.redis.RedisCache

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisCache.java
"""
from __future__ import annotations

import copy
import fnmatch
import time
from enum import Enum
from typing import Any, Collection, Iterable, Optional


class TimeUnit(Enum):
    """java.util.concurrent.TimeUnit 的最小替身（只保留本项目用到的单位）。

    【Java→Python】Java 的 TimeUnit 是枚举，方法 toSeconds/toMillis 由枚举实现；
    Python 用 Enum + 方法还原。
    该枚举同时被 `java/util/concurrent/TimeUnit.py` 直接 re-export，
    保证 `TimeUnit.HOURS` 在两条 import 路径下是**同一个对象**（Java 只有一个类）。
    """

    NANOSECONDS = 0.000000001
    MILLISECONDS = 0.001
    SECONDS = 1
    MINUTES = 60
    HOURS = 3600
    DAYS = 86400

    def toSeconds(self, duration: int) -> int:
        return duration * self.value

    def toMillis(self, duration: int) -> int:
        return duration * self.value * 1000

    def toMinutes(self, duration: int) -> int:
        return int(duration * self.value / 60)

    def toHours(self, duration: int) -> int:
        return int(duration * self.value / 3600)

    def toDays(self, duration: int) -> int:
        return int(duration * self.value / 86400)

    def sleep(self, duration: int) -> None:
        """对应 `TimeUnit.SECONDS.sleep(5)`。

        【Java→Python】Java 的 sleep 在中断时抛 InterruptedException；
        这里同样抛出 `java.lang.InterruptedException`（延迟 import 避免循环依赖）。
        """
        from java.lang.Thread import Thread

        Thread.sleep(self.toMillis(duration))


class _ValueOperations:
    def __init__(self, store: dict[str, Any], expiries: dict[str, float]) -> None:
        self._store = store
        self._expiries = expiries

    def set(self, key: str, value: Any, timeout: Optional[int] = None,
            time_unit: Optional[TimeUnit] = None) -> None:
        # 【Java→Python】Spring Data Redis 通过序列化器把对象转成字节写入 Redis，
        # 读出来是“新对象”；这里用 deepcopy 模拟同样的序列化隔离。
        self._store[key] = copy.deepcopy(value)
        if timeout is not None and time_unit is not None:
            self._expiries[key] = time.time() + time_unit.toSeconds(timeout)

    def get(self, key: str) -> Any:
        self._check_expire(key)
        if key not in self._store:
            return None
        return copy.deepcopy(self._store[key])

    def increment(self, key: str, delta: int = 1) -> int:
        """对应 ``increment(K key, long delta)``。

        【Java→Python】Redis 的 INCRBY 在 key 不存在时按 0 处理；
        字符串值在 Redis 里会报错，这里用 int() 还原“非数字即异常”的语义。
        """
        self._check_expire(key)
        current = self._store.get(key)
        value = 0 if current is None else int(current)
        value += int(delta)
        self._store[key] = value
        return value

    def setIfAbsent(self, key: str, value: Any, timeout: Optional[int] = None,
                    time_unit: Optional[TimeUnit] = None) -> bool:
        """对应 `setIfAbsent(K key, V value[, long timeout, TimeUnit unit])`。

        【Java→Python】Redis 的 SET NX 是原子操作：已存在返回 False 且不覆盖;
        本替身在进程内单线程写入，无需额外加锁。
        """
        self._check_expire(key)
        if key in self._store:
            return False
        self.set(key, value, timeout, time_unit)
        return True

    def _check_expire(self, key: str) -> None:
        expire_at = self._expiries.get(key)
        if expire_at is not None and expire_at <= time.time():
            self._store.pop(key, None)
            self._expiries.pop(key, None)


class _ListOperations:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def rightPushAll(self, key: str, data_list: Iterable[Any]) -> int:
        target = self._store.setdefault(key, [])
        target.extend(copy.deepcopy(list(data_list)))
        return len(target)

    def range(self, key: str, start: int, end: int) -> list[Any]:
        data = self._store.get(key) or []
        # 【Java→Python】Redis 的 end=-1 表示“到末尾”，与 Python 切片语义一致；
        # 但 Redis 的区间是闭区间，Python 切片是左闭右开，故 end 需要 +1。
        if end == -1:
            return copy.deepcopy(data[start:])
        return copy.deepcopy(data[start:end + 1])

    def rightPush(self, key: str, value: Any) -> int:
        """RPUSH：从尾部插入，返回 push 后列表长度。"""
        target = self._store.setdefault(key, [])
        target.append(copy.deepcopy(value))
        return len(target)

    def leftPush(self, key: str, value: Any) -> int:
        """LPUSH：从头部插入，返回 push 后列表长度。"""
        target = self._store.setdefault(key, [])
        target.insert(0, copy.deepcopy(value))
        return len(target)

    def size(self, key: str) -> int:
        return len(self._store.get(key) or [])

    def index(self, key: str, index: int) -> Any:
        """LINDEX：越界返回 null；负数从尾部数起（Redis 语义与 Python 一致）。"""
        data = self._store.get(key) or []
        try:
            return copy.deepcopy(data[index])
        except IndexError:
            return None

    def set(self, key: str, index: int, value: Any) -> None:
        """LSET：索引越界时 Redis 抛 ERR index out of range。"""
        data = self._store.get(key) or []
        if index >= len(data) or index < -len(data):
            raise IndexError("index out of range")
        data[index] = copy.deepcopy(value)

    def remove(self, key: str, count: int, value: Any) -> int:
        """LREM：count>0 从头删、count<0 从尾删、count=0 全删；返回删除个数。"""
        data = self._store.get(key) or []
        removed = 0
        if count > 0:
            result = []
            for item in data:
                if item == value and removed < count:
                    removed += 1
                    continue
                result.append(item)
        elif count < 0:
            result = []
            for item in reversed(data):
                if item == value and removed < -count:
                    removed += 1
                    continue
                result.append(item)
            result.reverse()
        else:
            result = []
            for item in data:
                if item == value:
                    removed += 1
                    continue
                result.append(item)
        self._store[key] = result
        return removed

    def trim(self, key: str, start: int, end: int) -> None:
        """LTRIM：只保留 [start, end]（闭区间，负数从尾部数），其余删除。"""
        data = self._store.get(key) or []
        length = len(data)
        start_index = start if start >= 0 else max(0, length + start)
        end_index = end if end >= 0 else length + end  # 负数下标转正后仍为闭区间
        self._store[key] = copy.deepcopy(data[start_index:end_index + 1])

    def rightPop(self, key: str, timeout: Optional[int] = None,
                 time_unit: Optional[TimeUnit] = None) -> Any:
        """RPOP / BRPOP：非阻塞时直接弹出；带 timeout 时最多等待 timeout 秒。

        【Java→Python】BRPOP 在真实 Redis 里是阻塞命令，这里用短暂的轮询等待模拟，
        timeout=0 表示“永久阻塞”，为避免进程挂死，这里退化为“立即返回 None”。
        """
        deadline = None
        if timeout is not None and timeout > 0:
            unit = time_unit or TimeUnit.SECONDS
            deadline = time.time() + unit.toSeconds(timeout)
        while True:
            data = self._store.get(key) or []
            if data:
                return copy.deepcopy(data.pop())
            if deadline is None or time.time() >= deadline:
                return None
            time.sleep(0.01)


class _BoundSetOperations:
    def __init__(self, store: dict[str, Any], key: str) -> None:
        self._store = store
        self._key = key

    def add(self, *values: Any) -> int:
        target = self._store.setdefault(self._key, set())
        before = len(target)
        target.update(copy.deepcopy(list(values)))
        return len(target) - before


class _SetOperations:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def members(self, key: str) -> set[Any]:
        return copy.deepcopy(self._store.get(key) or set())

    def isMember(self, key: str, value: Any) -> bool:
        return value in (self._store.get(key) or set())

    def add(self, key: str, values: Any) -> int:
        """SADD：Java 传的是 Object... 数组，这里接受可迭代对象或单值。"""
        target = self._store.setdefault(key, set())
        before = len(target)
        if isinstance(values, (list, tuple, set, frozenset)):
            target.update(copy.deepcopy(list(values)))
        else:
            target.add(copy.deepcopy(values))
        return len(target) - before

    def size(self, key: str) -> int:
        return len(self._store.get(key) or set())

    def remove(self, key: str, values: Any) -> int:
        target = self._store.get(key) or set()
        if isinstance(values, (list, tuple, set, frozenset)):
            candidates = list(values)
        else:
            candidates = [values]
        removed = 0
        for value in candidates:
            if value in target:
                target.discard(value)
                removed += 1
        return removed


class _HashOperations:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def putAll(self, key: str, data_map: dict[str, Any]) -> None:
        target = self._store.setdefault(key, {})
        target.update(copy.deepcopy(data_map))

    def put(self, key: str, h_key: str, value: Any) -> None:
        target = self._store.setdefault(key, {})
        target[h_key] = copy.deepcopy(value)

    def get(self, key: str, h_key: str) -> Any:
        target = self._store.get(key) or {}
        return copy.deepcopy(target.get(h_key))

    def entries(self, key: str) -> dict[str, Any]:
        return copy.deepcopy(self._store.get(key) or {})

    def multiGet(self, key: str, h_keys: Collection[object]) -> list[Any]:
        target = self._store.get(key) or {}
        # 【Java→Python】Spring 的 multiGet 对不存在的 field 返回 null 元素（列表长度不变），
        # 这里保持同样的“None 占位”行为。
        return [copy.deepcopy(target.get(h_key)) for h_key in h_keys]

    def delete(self, key: str, h_key: str) -> int:
        target = self._store.get(key) or {}
        return 1 if target.pop(h_key, None) is not None else 0

    def hasKey(self, key: str, h_key: str) -> bool:
        return h_key in (self._store.get(key) or {})

    def increment(self, key: str, h_key: str, delta: float = 1) -> float:
        """HINCRBYFLOAT 的语义：field 不存在按 0 处理。"""
        target = self._store.setdefault(key, {})
        current = target.get(h_key)
        value = 0.0 if current is None else float(current)
        value += float(delta)
        target[h_key] = value
        return value


class _InMemoryRedisTemplate:
    """org.springframework.data.redis.core.RedisTemplate 的内存替身。

    【Java→Python】真实 Redis 里 key/value 都是字节数组，Spring 用序列化器在对象与字节之间
    转换。这里用 dict 存 Python 对象 + deepcopy 模拟“序列化隔离”：
    取出后修改不会影响缓存中的原对象，这正是 Java 侧“改副本再 set 回去”的行为基础。
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._expiries: dict[str, float] = {}

    def opsForValue(self) -> _ValueOperations:
        return _ValueOperations(self._store, self._expiries)

    def opsForList(self) -> _ListOperations:
        return _ListOperations(self._store)

    def opsForSet(self) -> _SetOperations:
        return _SetOperations(self._store)

    def opsForHash(self) -> _HashOperations:
        return _HashOperations(self._store)

    def boundSetOps(self, key: str) -> _BoundSetOperations:
        return _BoundSetOperations(self._store, key)

    def expire(self, key: str, timeout: int, unit: TimeUnit) -> bool:
        if key not in self._store:
            return False
        self._expiries[key] = time.time() + unit.toSeconds(timeout)
        return True

    def getExpire(self, key: str, unit: Optional[TimeUnit] = None) -> int:
        expire_at = self._expiries.get(key)
        if expire_at is None:
            # Redis 语义：key 存在但无过期时间返回 -1；key 不存在返回 -2
            return -1 if key in self._store else -2
        remaining = expire_at - time.time()
        # Java: getExpire(key, TimeUnit) → Python: 按单位换算（默认秒）
        seconds = unit.toSeconds(1) if unit is not None else 1
        return int(remaining / seconds)

    def hasKey(self, key: str) -> bool:
        self.opsForValue()._check_expire(key)
        return key in self._store

    def delete(self, key_or_keys: Any) -> int:
        """Java: delete(String) / delete(Collection) 两个重载，返回删除数量。"""
        if isinstance(key_or_keys, str):
            removed = 1 if self._store.pop(key_or_keys, None) is not None else 0
            self._expiries.pop(key_or_keys, None)
            return removed
        removed = 0
        for key in list(key_or_keys or []):
            if self._store.pop(key, None) is not None:
                removed += 1
            self._expiries.pop(key, None)
        return removed

    def keys(self, pattern: str) -> Optional[set[str]]:
        # Redis KEYS 返回 Set；无匹配时返回空集（不是 null）
        return {key for key in list(self._store.keys()) if fnmatch.fnmatchcase(key, pattern)}


# 【Java→Python】Spring 中 RedisTemplate 是**单例 Bean**，所有 @Autowired RedisCache 共享同一个
# Redis 连接池；若 Python 每次 RedisCache() 都新建 _InMemoryRedisTemplate，各 Service 会各持一个
# 独立内存库，缓存将互不可见（语义与 Java 不符）。因此这里提供一个进程级默认实例，
# 不传参数时一律复用它；需要隔离（如单元测试）时显式传入自己的 template。
_SHARED_REDIS_TEMPLATE = _InMemoryRedisTemplate()


class RedisCache:
    """spring redis 工具类。

    【Java→Python】
    1) @Autowired RedisTemplate → 构造注入（默认共享进程级 _SHARED_REDIS_TEMPLATE，等价于 Spring 单例）。
    2) deleteObject 的 String / Collection 两个重载 → Python 单方法内部按类型分派；
       注意 str 也是 Sequence，必须先判 str 再判集合，否则会把 key 当成字符集合逐个删。
    3) 泛型 <T> 在 Python 中由 Any 表达（Java 泛型运行时擦除，本就无校验）。
    4) 返回 Collection<String> 的 keys() → set[str]（Redis KEYS 的返回类型是 Set）。
    """

    def __init__(self, redis_template: Optional["_InMemoryRedisTemplate"] = None) -> None:
        self.redisTemplate = redis_template or _SHARED_REDIS_TEMPLATE

    def setCacheObject(self, key: str, value: Any,
                       timeout: Optional[int] = None,
                       time_unit: Optional[TimeUnit] = None) -> None:
        """对应 setCacheObject(String,T) 与 setCacheObject(String,T,Integer,TimeUnit) 两个重载。"""
        self.redisTemplate.opsForValue().set(key, value, timeout, time_unit)

    def expire(self, key: str, timeout: int, unit: Optional[TimeUnit] = None) -> bool:
        """对应 expire(String,long) 与 expire(String,long,TimeUnit) 两个重载。"""
        if unit is None:
            unit = TimeUnit.SECONDS
        return self.redisTemplate.expire(key, timeout, unit)

    def getExpire(self, key: str) -> int:
        return self.redisTemplate.getExpire(key)

    def hasKey(self, key: str) -> bool:
        return bool(self.redisTemplate.hasKey(key))

    def getCacheObject(self, key: str) -> Any:
        return self.redisTemplate.opsForValue().get(key)

    def deleteObject(self, key_or_collection: Any) -> bool:
        """对应 deleteObject(String) 与 deleteObject(Collection) 两个重载。"""
        if isinstance(key_or_collection, str):
            return bool(self.redisTemplate.delete(key_or_collection))
        return self.redisTemplate.delete(key_or_collection) > 0

    def setCacheList(self, key: str, data_list: list[Any]) -> int:
        count = self.redisTemplate.opsForList().rightPushAll(key, data_list)
        return 0 if count is None else int(count)

    def getCacheList(self, key: str) -> list[Any]:
        return self.redisTemplate.opsForList().range(key, 0, -1)

    def setCacheSet(self, key: str, data_set: set[Any]) -> _BoundSetOperations:
        set_operation = self.redisTemplate.boundSetOps(key)
        for item in data_set:
            set_operation.add(item)
        return set_operation

    def getCacheSet(self, key: str) -> set[Any]:
        return self.redisTemplate.opsForSet().members(key)

    def setCacheMap(self, key: str, data_map: Optional[dict[str, Any]]) -> None:
        if data_map is not None:
            self.redisTemplate.opsForHash().putAll(key, data_map)

    def getCacheMap(self, key: str) -> dict[str, Any]:
        return self.redisTemplate.opsForHash().entries(key)

    def setCacheMapValue(self, key: str, h_key: str, value: Any) -> None:
        self.redisTemplate.opsForHash().put(key, h_key, value)

    def getCacheMapValue(self, key: str, h_key: str) -> Any:
        return self.redisTemplate.opsForHash().get(key, h_key)

    def getMultiCacheMapValue(self, key: str, h_keys: Collection[object]) -> list[Any]:
        return self.redisTemplate.opsForHash().multiGet(key, h_keys)

    def deleteCacheMapValue(self, key: str, h_key: str) -> bool:
        return self.redisTemplate.opsForHash().delete(key, h_key) > 0

    def keys(self, pattern: str) -> Collection[str]:
        return self.redisTemplate.keys(pattern) or set()
