package com.ruoyi.common.config.writer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.data.redis.cache.CacheStatistics;
import org.springframework.data.redis.cache.CacheStatisticsCollector;
import org.springframework.data.redis.cache.RedisCacheWriter;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.RedisStringCommands.SetOption;
import org.springframework.data.redis.core.types.Expiration;
import org.springframework.lang.Nullable;
import org.springframework.util.Assert;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Collections;
import java.util.Iterator;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.function.Function;

/**
 * @Description:
 * @Author: HuangJun
 * @Date: 2022/9/3
 * @Return
 */
public class RetRedisCacheWriter implements RedisCacheWriter {
    private static final Logger log = LoggerFactory.getLogger(RetRedisCacheWriter.class);
    private final RedisConnectionFactory connectionFactory;
    private final Duration sleepTime;
    private final CacheStatisticsCollector statistics;

    public RetRedisCacheWriter(RedisConnectionFactory connectionFactory) {
        this(connectionFactory, Duration.ZERO);
    }

    public RetRedisCacheWriter(RedisConnectionFactory connectionFactory, Duration sleepTime) {
        this(connectionFactory, sleepTime, CacheStatisticsCollector.create());
    }

    public RetRedisCacheWriter(RedisConnectionFactory connectionFactory, Duration sleepTime,
                               CacheStatisticsCollector statistics) {
        Assert.notNull(connectionFactory, "ConnectionFactory must not be null!");
        Assert.notNull(sleepTime, "SleepTime must not be null!");
        this.statistics = statistics == null ? CacheStatisticsCollector.create() : statistics;
        this.connectionFactory = connectionFactory;
        this.sleepTime = sleepTime;
    }

    @Override
    public void put(String name, byte[] key, byte[] value, @Nullable Duration ttl) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(key, "Key must not be null!");
        Assert.notNull(value, "Value must not be null!");
        this.execute(name, (connection) -> {
            if (shouldExpireWithin(ttl)) {
                connection.set(key, value, Expiration.from(ttl.toMillis(), TimeUnit.MILLISECONDS), SetOption.upsert());
            } else {
                connection.set(key, value);
            }

            return "OK";
        });
        this.statistics.incPuts(name);
    }

    @Override
    public byte[] get(String name, byte[] key) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(key, "Key must not be null!");
        this.statistics.incGets(name);
        byte[] value = this.execute(name, connection -> connection.get(key));
        if (value == null) {
            this.statistics.incMisses(name);
        } else {
            this.statistics.incHits(name);
        }
        return value;
    }

    @Override
    public byte[] putIfAbsent(String name, byte[] key, byte[] value, @Nullable Duration ttl) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(key, "Key must not be null!");
        Assert.notNull(value, "Value must not be null!");
        this.statistics.incPuts(name);
        return this.execute(name, connection -> {
            if (this.isLockingCacheWriter()) {
                this.doLock(name, connection);
            }

            byte[] bytes;
            try {
                boolean put;
                if (shouldExpireWithin(ttl)) {
                    put = connection.set(key, value, Expiration.from(ttl), SetOption.ifAbsent());
                } else {
                    put = connection.setNX(key, value);
                }

                if (put) {
                    Object obj = null;
                    return (byte[])obj;
                }

                byte[] bytes1 = connection.get(key);
                bytes = bytes1;
            } finally {
                if (this.isLockingCacheWriter()) {
                    this.doUnlock(name, connection);
                }

            }

            return bytes;
        });
    }

    @Override
    public void remove(String name, byte[] key) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(key, "Key must not be null!");
        String keyString = new String(key);
        log.info("redis remove key:" + keyString);
        String keyIsAll = "*";
        if (keyString != null && keyString.endsWith(keyIsAll)) {
            this.execute(name, (connection) -> {
                Set<byte[]> keys = connection.keys(key);
                int delNum = 0;

                byte[] keyByte;
                for(Iterator iterator = keys.iterator(); iterator.hasNext(); delNum = (int)((long)delNum + connection.del(new byte[][]{keyByte}))) {
                    keyByte = (byte[])iterator.next();
                }

                return delNum;
            });
        } else {
            this.execute(name, connection -> connection.del(new byte[][]{key}));
        }
        this.statistics.incDeletes(name);
    }

    @Override
    public void clean(String name, byte[] pattern) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(pattern, "Pattern must not be null!");
        this.execute(name, (connection) -> {
            boolean wasLocked = false;

            try {
                if (this.isLockingCacheWriter()) {
                    this.doLock(name, connection);
                    wasLocked = true;
                }

                byte[][] keys = (byte[][])(((Set)Optional.ofNullable(connection.keys(pattern)).orElse(Collections.emptySet())).toArray(new byte[0][]));
                if (keys.length > 0) {
                    connection.del(keys);
                }
            } finally {
                if (wasLocked && this.isLockingCacheWriter()) {
                    this.doUnlock(name, connection);
                }

            }

            return "OK";
        });
    }

    void lock(String name) {
        this.execute(name, connection -> this.doLock(name, connection));
    }

    void unlock(String name) {
        this.executeLockFree(connection -> this.doUnlock(name, connection));
    }

    private Boolean doLock(String name, RedisConnection connection) {
        return connection.setNX(createCacheLockKey(name), new byte[0]);
    }

    private Long doUnlock(String name, RedisConnection connection) {
        return connection.del(new byte[][]{createCacheLockKey(name)});
    }

    boolean doCheckLock(String name, RedisConnection connection) {
        return connection.exists(createCacheLockKey(name));
    }

    private boolean isLockingCacheWriter() {
        return !this.sleepTime.isZero() && !this.sleepTime.isNegative();
    }

    private <T> T execute(String name, Function<RedisConnection, T> callback) {
        RedisConnection connection = this.connectionFactory.getConnection();

        T object;
        try {
            this.checkAndPotentiallyWaitUntilUnlocked(name, connection);
            object = callback.apply(connection);
        } finally {
            connection.close();
        }

        return object;
    }

    private void executeLockFree(Consumer<RedisConnection> callback) {
        RedisConnection connection = this.connectionFactory.getConnection();

        try {
            callback.accept(connection);
        } finally {
            connection.close();
        }

    }

    private void checkAndPotentiallyWaitUntilUnlocked(String name, RedisConnection connection) {
        if (this.isLockingCacheWriter()) {
            try {
                while(this.doCheckLock(name, connection)) {
                    Thread.sleep(this.sleepTime.toMillis());
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new PessimisticLockingFailureException(String.format("Interrupted while waiting to unlock cache %s", name), e);
            }
        }

    }

    private static boolean shouldExpireWithin(@Nullable Duration ttl) {
        return ttl != null && !ttl.isZero() && !ttl.isNegative();
    }

    private static byte[] createCacheLockKey(String name) {
        return (name + "~lock").getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Spring Data Redis 4.x（Boot 4）为 RedisCacheWriter 新增的抽象方法：
     * 按 pattern 清理某个 cache 下的所有 key，用于批量失效。
     */
    @Override
    public void clear(String name, byte[] pattern) {
        Assert.notNull(name, "Name must not be null!");
        Assert.notNull(pattern, "Pattern must not be null!");
        Long deleted = this.execute(name, (connection) -> {
            Set<byte[]> keys = connection.keys(pattern);
            if (keys == null || keys.isEmpty()) {
                return 0L;
            }
            return connection.del(keys.toArray(new byte[0][]));
        });
        this.statistics.incDeletesBy(name, deleted == null ? 0 : deleted.intValue());
    }

    /** Spring Data Redis 4.x 新增的异步检索契约：本地实现为同步 get 的已完成 Future。 */
    @Override
    public CompletableFuture<byte[]> retrieve(String name, byte[] key, Duration ttl) {
        return CompletableFuture.completedFuture(get(name, key));
    }

    /** Spring Data Redis 4.x 新增的异步写入契约：本地实现为同步 put 的已完成 Future。 */
    @Override
    public CompletableFuture<Void> store(String name, byte[] key, byte[] value, @Nullable Duration ttl) {
        put(name, key, value, ttl);
        return CompletableFuture.completedFuture(null);
    }

    /** Spring Data Redis 4.x 把 remove 拆为 evict（不等待）与 remove（默认实现）。 */
    @Override
    public void evict(String name, byte[] key) {
        remove(name, key);
    }

    @Override
    public CacheStatistics getCacheStatistics(String cacheName) {
        return this.statistics.getCacheStatistics(cacheName);
    }

    @Override
    public void clearStatistics(String name) {
        Assert.notNull(name, "Name must not be null!");
        this.statistics.reset(name);
    }

    /**
     * 返回一个持有调用方 collector 的新 writer（RedisCacheWriter 契约：不改原实例统计归属）。
     */
    @Override
    public RetRedisCacheWriter withStatisticsCollector(CacheStatisticsCollector cacheStatisticsCollector) {
        return new RetRedisCacheWriter(this.connectionFactory, this.sleepTime, cacheStatisticsCollector);
    }
}
