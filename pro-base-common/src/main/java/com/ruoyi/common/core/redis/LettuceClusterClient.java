package com.ruoyi.common.core.redis;

import io.lettuce.core.RedisURI;
import io.lettuce.core.cluster.RedisClusterClient;
import io.lettuce.core.cluster.StatefulRedisClusterConnection;
import io.lettuce.core.cluster.api.sync.RedisClusterCommands;

import java.util.Set;

/** Minimal Lettuce replacement for the previously used JedisCluster read API. */
public class LettuceClusterClient implements AutoCloseable {
    private final RedisClusterClient client;
    private final StatefulRedisClusterConnection<String, String> connection;
    private final RedisClusterCommands<String, String> commands;

    public LettuceClusterClient(Set<RedisURI> nodes) {
        this.client = RedisClusterClient.create(nodes);
        this.connection = client.connect();
        this.commands = connection.sync();
    }

    public String get(String key) {
        return commands.get(key);
    }

    @Override
    public void close() {
        connection.close();
        client.shutdown();
    }
}
