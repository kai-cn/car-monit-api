package com.ruoyi.common.core.redis;

import java.io.Serializable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import redis.clients.jedis.HostAndPort;
import redis.clients.jedis.JedisCluster;

import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;

public class RedisSourceFactory implements Serializable {


    private static final long serialVersionUID = 1L;

    private static final Logger logger = LoggerFactory.getLogger(RedisSourceFactory.class);

    public static JedisCluster createSource(RedisConfig redisConfig) {
        if (redisConfig == null || redisConfig.getClusterNodes() == null || redisConfig.getClusterNodes().isEmpty()) {
            logger.error("Redis cluster node address 'cluster.nodes' is not configured.");
            throw new IllegalStateException("Redis cluster node address 'cluster.nodes' is not configured.");
        }

        Set<HostAndPort> jedisClusterNodes = new HashSet<HostAndPort>();
        String nodes = redisConfig.getClusterNodes();

        for (String node : nodes.split(",")) {
            String[] hp = node.trim().split(":");
            if (hp.length == 2) {
                try {
                    jedisClusterNodes.add(new HostAndPort(hp[0], Integer.parseInt(hp[1])));
                    logger.info("Added Redis node: " + node);
                } catch (NumberFormatException e) {
                    logger.warn("Invalid port number for Redis node: " + node + ". This node will be skipped.", e);
                }
            } else {
                logger.warn("Invalid node format (expected host:port): " + node + ". This node will be skipped.");
            }
        }

        try {
            JedisCluster jedisCluster = new JedisCluster(jedisClusterNodes);
            logger.info("JedisCluster created successfully with nodes: " + jedisClusterNodes);
            return jedisCluster;
        } catch (Exception e) {
            logger.error("Failed to create JedisCluster", e);
            throw e;
        }
    };
}
