# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.redis.RedisSourceFactory

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisSourceFactory.java
"""
from __future__ import annotations

import logging
from typing import Optional

from com.ruoyi.common.core.redis.RedisConfig import RedisConfig

log = logging.getLogger(__name__)


class HostAndPort:
    """redis.clients.jedis.HostAndPort 的替身。"""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HostAndPort) and (self.host, self.port) == (other.host, other.port)

    def __hash__(self) -> int:
        return hash((self.host, self.port))

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


class JedisCluster:
    """redis.clients.jedis.JedisCluster 的最小替身。

    【Java→Python】
    1) 真实 JedisCluster 需要连接真实 Redis；Python 侧用注入的 dict 模拟字符串存取，
       未命中返回 None（与 Jedis 返回 null 一致）。
    2) Java 构造器 JedisCluster(Set<HostAndPort>) 在连接失败时会抛异常；
       Python 桩只在节点集合为空时抛 IllegalStateException 等价物（RuntimeError）。
    """

    def __init__(self, nodes: Optional[set[HostAndPort]] = None,
                 store: Optional[dict[str, str]] = None) -> None:
        self.nodes = nodes or set()
        self._store = store if store is not None else {}

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def set(self, key: str, value: str) -> str:
        self._store[key] = value
        return "OK"


class RedisSourceFactory:
    """创建 JedisCluster 的工厂。

    【Java→Python】implements Serializable → Python 对象默认可 pickle；
    静态 logger → 模块级 logger。
    """

    def createSource(self, redis_config: Optional[RedisConfig]) -> JedisCluster:
        if (
            redis_config is None
            or redis_config.getClusterNodes() is None
            or len(redis_config.getClusterNodes()) == 0
        ):
            log.error("Redis cluster node address 'cluster.nodes' is not configured.")
            # Java: throw new IllegalStateException(...)
            raise RuntimeError("Redis cluster node address 'cluster.nodes' is not configured.")

        jedis_cluster_nodes: set[HostAndPort] = set()
        nodes = redis_config.getClusterNodes()

        # Java: nodes.split(",") —— split 会保留中间空串，Python 的 split 行为一致
        for node in nodes.split(","):
            hp = node.strip().split(":")
            if len(hp) == 2:
                try:
                    jedis_cluster_nodes.add(HostAndPort(hp[0], int(hp[1])))
                    log.info("Added Redis node: " + node)
                except ValueError:
                    # Java: catch (NumberFormatException e)
                    log.warning("Invalid port number for Redis node: " + node + ". This node will be skipped.", exc_info=True)
            else:
                log.warning("Invalid node format (expected host:port): " + node + ". This node will be skipped.")

        try:
            jedis_cluster = JedisCluster(jedis_cluster_nodes)
            log.info("JedisCluster created successfully with nodes: " + str(jedis_cluster_nodes))
            return jedis_cluster
        except Exception:
            log.error("Failed to create JedisCluster", exc_info=True)
            raise
