# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.redis.RedisConfig

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisConfig.java
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RedisConfig:
    """Redis 集群配置（Lombok @Data + @ConfigurationProperties(prefix = "rediscluster")）。

    【Java→Python】
    1) @ConfigurationProperties(prefix="rediscluster")：Spring Boot 会把
       `rediscluster.cluster-nodes` 自动绑定到 clusterNodes 字段（支持松散命名：
       cluster-nodes / clusterNodes / CLUSTER_NODES）。Python 侧没有属性绑定容器，
       因此在构造时显式传值；如需复现“松散绑定”，由配置加载器调用
       ``RedisConfig.from_properties(props)`` 完成键名归一化。
    2) @Configuration 表示这是 Spring 容器中的 Bean；Python 侧不需要注册，直接实例化。
    """

    cluster_nodes: str = ""

    def getClusterNodes(self) -> str:
        return self.cluster_nodes

    def setClusterNodes(self, value: str) -> None:
        self.cluster_nodes = value

    @staticmethod
    def from_properties(props: dict[str, object], prefix: str = "rediscluster") -> "RedisConfig":
        """模拟 Spring Boot 的松散绑定：读取 <prefix>.cluster-nodes / clusterNodes。"""
        candidates = (
            f"{prefix}.cluster-nodes",
            f"{prefix}.clusterNodes",
            f"{prefix}.CLUSTER_NODES",
        )
        for name in candidates:
            if name in props:
                return RedisConfig(cluster_nodes=str(props[name]))
        return RedisConfig()
