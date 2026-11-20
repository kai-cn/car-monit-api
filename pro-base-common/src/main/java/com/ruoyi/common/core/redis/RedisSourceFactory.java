package com.ruoyi.common.core.redis;

import io.lettuce.core.RedisURI;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;

@Service
public class RedisSourceFactory implements Serializable {
    private static final long serialVersionUID = 1L;
    private static final Logger logger = LoggerFactory.getLogger(RedisSourceFactory.class);

    public LettuceClusterClient createSource(RedisConfig redisConfig) {
        if (redisConfig == null || redisConfig.getClusterNodes() == null || redisConfig.getClusterNodes().isEmpty()) {
            logger.error("Redis cluster node address 'cluster.nodes' is not configured.");
            throw new IllegalStateException("Redis cluster node address 'cluster.nodes' is not configured.");
        }

        Set<RedisURI> nodes = new HashSet<>();
        for (String node : redisConfig.getClusterNodes().split(",")) {
            String[] hp = node.trim().split(":");
            if (hp.length == 2) {
                try {
                    nodes.add(RedisURI.create(hp[0], Integer.parseInt(hp[1])));
                    logger.info("Added Redis node: " + node);
                } catch (NumberFormatException e) {
                    logger.warn("Invalid port number for Redis node: " + node + ". This node will be skipped.", e);
                }
            } else {
                logger.warn("Invalid node format (expected host:port): " + node + ". This node will be skipped.");
            }
        }
        if (nodes.isEmpty()) {
            throw new IllegalStateException("No valid Redis cluster nodes configured.");
        }

        try {
            LettuceClusterClient client = new LettuceClusterClient(nodes);
            logger.info("Lettuce cluster client created successfully with nodes: " + nodes);
            return client;
        } catch (Exception e) {
            logger.error("Failed to create Lettuce cluster client", e);
            throw e;
        }
    }
}
