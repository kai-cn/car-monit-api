# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.RedisUtil

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/RedisUtil.java

【Java→Python】整体说明
1) ``@Component`` + ``@Autowired public RedisTemplate redisTemplate``
   → 构造注入（默认使用进程内的 ``_InMemoryRedisTemplate``，与 Java 的 RedisTemplate 同名 API）。
2) **方法名冲突**：Java 的 ``del(String... key)`` 在 Python 中无法命名为 ``del``
   （``del`` 是 Python 关键字），因此改名为 ``delete``；调用点需同步改名，
   这是本文件唯一“不得不改”的公开方法名。
3) ``String... / Object...`` 变长参数 → Python ``*args``；``del(String... key)`` 中
   Java 的 ``key != null && key.length > 0`` → ``args is not None and len(args) > 0``。
4) ``e.printStackTrace()`` → ``traceback.print_exc()``（输出格式不同，但“打印到 stderr
   并继续执行”的语义一致，保证了所有 catch 分支都返回默认值）。
5) ``Arrays.asList(key)`` → ``list(args)``；``Map<Object,Object>`` → ``dict``；
   ``Set<Object>`` → ``set``；``List<Object>`` → ``list``。
6) 时间单位 ``TimeUnit.SECONDS`` → 复用 ``core.redis.RedisCache.TimeUnit`` 枚举。
7) 被注释掉的 ``keys()`` / ``removeAll()``（SCAN 版本）在 Java 中是块注释，
   Python 侧同样以注释保留，不导出方法。
"""
from __future__ import annotations

import traceback
from typing import Any, Optional

from com.ruoyi.common.core.redis.RedisCache import TimeUnit, _InMemoryRedisTemplate


class RedisUtil:
    """redis 工具类。

    【Java→Python】Spring 通过字段注入把容器里的 RedisTemplate 塞进来；
    Python 用构造函数注入，默认值便于单测直接 ``RedisUtil()``。
    """

    def __init__(self, redis_template: Optional[Any] = None) -> None:
        # Java: @Autowired public RedisTemplate redisTemplate;
        self.redisTemplate = redis_template if redis_template is not None else _InMemoryRedisTemplate()

    # ------------------------------------------------------------------ 通用
    def expire(self, key: str, time: int) -> bool:
        """指定缓存失效时间（时间：秒）。"""
        try:
            if time > 0:
                self.redisTemplate.expire(key, time, TimeUnit.SECONDS)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def getExpire(self, key: str) -> int:
        """根据 key 获取过期时间（秒），返回 0 代表永久有效。

        【Java→Python】Spring 的 ``getExpire(key, TimeUnit.SECONDS)``；
        进程内实现无过期时间时返回 -1（Redis 语义），这里原样返回，不做 0 归一化。
        """
        return self.redisTemplate.getExpire(key, TimeUnit.SECONDS)

    def hasKey(self, key: str) -> bool:
        try:
            return bool(self.redisTemplate.hasKey(key))
        except Exception:
            traceback.print_exc()
            return False

    def delete(self, *key: str) -> None:
        """删除缓存（对应 Java 的 ``del(String... key)``，因 ``del`` 是 Python 关键字而改名）。"""
        if key is not None and len(key) > 0:
            if len(key) == 1:
                self.redisTemplate.delete(key[0])
            else:
                self.redisTemplate.delete(list(key))

    # ============================ String =============================
    def get(self, key: str) -> Any:
        """普通缓存获取。"""
        return None if key is None else self.redisTemplate.opsForValue().get(key)

    def set(self, key: str, value: Any, time: Optional[int] = None) -> bool:
        """普通缓存放入（两个重载合并：time 缺省表示不设过期）。"""
        try:
            if time is not None and time > 0:
                self.redisTemplate.opsForValue().set(key, value, time, TimeUnit.SECONDS)
            else:
                self.redisTemplate.opsForValue().set(key, value)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def incr(self, key: str, delta: int) -> int:
        """递增（递增因子必须大于 0）。"""
        if delta < 0:
            # Java: throw new RuntimeException("递增因子必须大于0")
            raise RuntimeError("递增因子必须大于0")
        return self.redisTemplate.opsForValue().increment(key, delta)

    def decr(self, key: str, delta: int) -> int:
        """递减（递减因子必须大于 0）。"""
        if delta < 0:
            raise RuntimeError("递减因子必须大于0")
        return self.redisTemplate.opsForValue().increment(key, -delta)

    # ================================ Map =================================
    def hget(self, key: str, item: str) -> Any:
        """HashGet。"""
        return self.redisTemplate.opsForHash().get(key, item)

    def hmget(self, key: str) -> dict:
        """获取 hashKey 对应的所有键值。"""
        return self.redisTemplate.opsForHash().entries(key)

    def hmset(self, key: str, data_map: dict, time: Optional[int] = None) -> bool:
        """HashSet（两个重载合并：time 缺省表示不设过期）。"""
        try:
            self.redisTemplate.opsForHash().putAll(key, data_map)
            if time is not None and time > 0:
                self.expire(key, time)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def hset(self, key: str, item: str, value: Any, time: Optional[int] = None) -> bool:
        """向一张 hash 表中放入数据，如果不存在将创建（两个重载合并）。"""
        try:
            self.redisTemplate.opsForHash().put(key, item, value)
            if time is not None and time > 0:
                # 注意：如果已存在的 hash 表有时间，这里将会替换原有的时间
                self.expire(key, time)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def hdel(self, key: str, *item: Any) -> None:
        """删除 hash 表中的值（item 可以是多个）。

        【Java→Python】Java 传的是 ``Object[]`` 整体给 ``delete(key, item)``；
        进程内实现按单 field 删除，因此这里循环处理（语义等价）。
        """
        for field in item:
            self.redisTemplate.opsForHash().delete(key, field)

    def hHasKey(self, key: str, item: str) -> bool:
        """判断 hash 表中是否有该项的值。"""
        return bool(self.redisTemplate.opsForHash().hasKey(key, item))

    def hincr(self, key: str, item: str, by: float) -> float:
        """hash 递增，如果不存在就会创建一个并把新增后的值返回。"""
        return self.redisTemplate.opsForHash().increment(key, item, by)

    def hdecr(self, key: str, item: str, by: float) -> float:
        """hash 递减。"""
        return self.redisTemplate.opsForHash().increment(key, item, -by)

    # ============================ set =============================
    def sGet(self, key: str) -> Optional[set]:
        """根据 key 获取 Set 中的所有值。"""
        try:
            return self.redisTemplate.opsForSet().members(key)
        except Exception:
            traceback.print_exc()
            return None

    def sHasKey(self, key: str, value: Any) -> bool:
        """根据 value 从一个 set 中查询是否存在。"""
        try:
            return bool(self.redisTemplate.opsForSet().isMember(key, value))
        except Exception:
            traceback.print_exc()
            return False

    def sSet(self, key: str, *values: Any) -> int:
        """将数据放入 set 缓存，返回成功个数。"""
        try:
            return int(self.redisTemplate.opsForSet().add(key, list(values)))
        except Exception:
            traceback.print_exc()
            return 0

    def sSetAndTime(self, key: str, time: int, *values: Any) -> int:
        """将 set 数据放入缓存（带过期时间），返回成功个数。"""
        try:
            count = self.redisTemplate.opsForSet().add(key, list(values))
            if time > 0:
                self.expire(key, time)
            return int(count)
        except Exception:
            traceback.print_exc()
            return 0

    def sGetSetSize(self, key: str) -> int:
        """获取 set 缓存的长度。"""
        try:
            return int(self.redisTemplate.opsForSet().size(key))
        except Exception:
            traceback.print_exc()
            return 0

    def setRemove(self, key: str, *values: Any) -> int:
        """移除值为 value 的（可以是多个），返回移除个数。"""
        try:
            return int(self.redisTemplate.opsForSet().remove(key, list(values)))
        except Exception:
            traceback.print_exc()
            return 0

    # =============================== list =================================
    def lGet(self, key: str, start: int, end: int) -> Optional[list]:
        """获取 list 缓存的内容（end 为 -1 代表所有值）。"""
        try:
            return self.redisTemplate.opsForList().range(key, start, end)
        except Exception:
            traceback.print_exc()
            return None

    def lGetListSize(self, key: str) -> int:
        """获取 list 缓存的长度。"""
        try:
            return int(self.redisTemplate.opsForList().size(key))
        except Exception:
            traceback.print_exc()
            return 0

    def lGetIndex(self, key: str, index: int) -> Any:
        """通过索引获取 list 中的值（负数从尾部数起）。"""
        try:
            return self.redisTemplate.opsForList().index(key, index)
        except Exception:
            traceback.print_exc()
            return None

    def lSet(self, key: str, value: Any, time: Optional[int] = None) -> bool:
        """将 list 放入缓存（四个 Java 重载合并）。

        Java 重载：
          lSet(String, Object)
          lSet(String, Object, long)
          lSet(String, List<Object>)
          lSet(String, List<Object>, long)

        【Java→Python】第二个参数是 list/tuple 时走 rightPushAll，否则走 rightPush，
        与 Java 的编译期重载选择一致；time 为 None 表示不设过期。
        """
        try:
            if isinstance(value, (list, tuple)):
                self.redisTemplate.opsForList().rightPushAll(key, value)
            else:
                self.redisTemplate.opsForList().rightPush(key, value)
            if time is not None and time > 0:
                self.expire(key, time)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def lUpdateIndex(self, key: str, index: int, value: Any) -> bool:
        """根据索引修改 list 中的某条数据。"""
        try:
            self.redisTemplate.opsForList().set(key, index, value)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def lRemove(self, key: str, count: int, value: Any) -> int:
        """移除 N 个值为 value 的元素。"""
        try:
            return int(self.redisTemplate.opsForList().remove(key, count, value))
        except Exception:
            traceback.print_exc()
            return 0

    # 以下两个方法在原 Java 中已被块注释，保留注释形态以防误用
    # private Set<String> keys(String keyPrefix) {
    #     String realKey = keyPrefix + "*";
    #     try {
    #         return redisTemplate.execute((RedisCallback<Set<String>>) connection -> {
    #             Set<String> binaryKeys = new HashSet<>();
    #             Cursor<byte[]> cursor = connection.scan(
    #                 ScanOptions.scanOptions().match(realKey).count(Integer.MAX_VALUE).build());
    #             while (cursor.hasNext()) {
    #                 binaryKeys.add(new String(cursor.next()));
    #             }
    #             return binaryKeys;
    #         });
    #     } catch (Throwable e) {
    #         e.printStackTrace();
    #     }
    #     return null;
    # }
    #
    # public void removeAll(String keyPrefix) {
    #     try {
    #         Set<String> keys = keys(keyPrefix);
    #         redisTemplate.delete(keys);
    #     } catch (Throwable e) {
    #         e.printStackTrace();
    #     }
    # }

    # ---------------------------------- redis 消息队列 ----------------------------------
    def lpush(self, key: str, value: Any) -> bool:
        """存值（从左侧写入队列）。"""
        try:
            self.redisTemplate.opsForList().leftPush(key, value)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def rpop(self, key: str) -> Any:
        """取值 - rpop：非阻塞式。"""
        try:
            return self.redisTemplate.opsForList().rightPop(key)
        except Exception:
            traceback.print_exc()
            return None

    def brpop(self, key: str, timeout: int, timeUnit: TimeUnit) -> Any:
        """取值 - brpop：阻塞式（推荐使用）。

        超时时间单位支持 DAYS/HOURS/MINUTES/SECONDS/MILLISECONDS。

        【Java→Python】Python 的 TimeUnit 只实现了本项目用到的单位；
        阻塞语义在进程内实现中退化为“带截止时间的轮询”，超时会返回 None。
        """
        try:
            return self.redisTemplate.opsForList().rightPop(key, timeout, timeUnit)
        except Exception:
            traceback.print_exc()
            return None
