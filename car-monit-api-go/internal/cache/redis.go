// Package cache 复刻 RuoYi 的 RedisCache + 幂等/计数等缓存用法。
//
// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisCache.java
//	pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisConfig.java
//	pro-base-common/src/main/java/com/ruoyi/common/config/RedisConfiguration.java
//	pro-business-api/.../service/optimization/ProgressiveQueryArchitectureService.java:105-120（table:count: 缓存）
//
// 对应 Go 文件: internal/cache/redis.go
//
// 关键映射:
//
//	RedisTemplate.opsForValue().get/set   → Client.Get / Client.Set
//	RedisTemplate.opsForValue().increment → Client.Incr
//	setIfAbsent + TTL（幂等）              → Client.SetNXWithTTL
//	@Cacheable（注解缓存）                 → 无注解等价物：在 service 里显式 Get → 回源 → Set（见 GetOrLoad）
package cache

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

// Client 是 Redis 门面。
type Client struct {
	rdb *redis.Client
}

// Options 对应 application.yml:46-59
type Options struct {
	Addr     string
	Password string
	DB       int
	PoolSize int
}

// New 建立连接并 Ping。
//
// DIFF: Spring Data Redis 用 Lettuce 连接池并做懒连接；go-redis 的 Client 本身就是并发安全的
// 连接池，无需额外池对象。启动即 Ping，让"Redis 没起来"在启动阶段暴露。
func New(ctx context.Context, o Options) (*Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     o.Addr,
		Password: o.Password,
		DB:       o.DB,
		PoolSize: o.PoolSize,
	})
	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := rdb.Ping(pingCtx).Err(); err != nil {
		return nil, fmt.Errorf("连接 Redis %s 失败: %w", o.Addr, err)
	}
	return &Client{rdb: rdb}, nil
}

// Raw 暴露底层 client（少数需要 Pipeline/Lua 的场景）
func (c *Client) Raw() *redis.Client { return c.rdb }

// Close 对应 Spring 容器关闭时的连接释放
func (c *Client) Close() error { return c.rdb.Close() }

// Get 对应 redisCache.getCacheObject(key)。
//
// DIFF: Spring 用 FastJson2/JDK 序列化，键值里是 Java 对象；Go 侧统一用 JSON 字符串存储。
// 迁移期如果两个服务共用同一个 Redis key，必须约定序列化格式，否则会解析失败（见 README「兼容性风险」）。
func (c *Client) Get(ctx context.Context, key string) (string, bool, error) {
	v, err := c.rdb.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	return v, true, nil
}

// GetText 对应 redisCache.getCacheObject(key) 且调用方期望拿到 String 的场景（如 sys_config:* 开关）。
//
// DIFF: Java 的 RedisTemplate 先反序列化再把对象交给调用方，所以 getCacheObject("sys_config:data_query")
// 得到的是裸字符串 queryall；Go 直接 GET 拿到的是底层字节，而本项目 Redis 里存的是
// FastJson2 写出的 JSON 字面量 "queryall"（带双引号）。少了这层解码，任何字符串配置都会比较失败。
func (c *Client) GetText(ctx context.Context, key string) (string, bool, error) {
	raw, ok, err := c.Get(ctx, key)
	if err != nil || !ok {
		return "", false, err
	}
	return DecodeCachedText(raw), true, nil
}

// DecodeCachedText 把 Redis 里的 JSON 字面量还原成裸字符串：
//
//	"queryall" -> queryall      （JSON 字符串）
//	queryall   -> queryall      （本来就是裸串，原样返回）
//	null       -> ""            （JSON null）
func DecodeCachedText(raw string) string {
	s := strings.TrimSpace(raw)
	if s == "" || s == "null" {
		return ""
	}
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		var out string
		if err := json.Unmarshal([]byte(s), &out); err == nil {
			return out
		}
	}
	return s
}

// GetJSON 对应 getCacheObject(key) 后直接强转目标类型。
func (c *Client) GetJSON(ctx context.Context, key string, dest any) (bool, error) {
	v, ok, err := c.Get(ctx, key)
	if err != nil || !ok {
		return false, err
	}
	if err := json.Unmarshal([]byte(v), dest); err != nil {
		return false, fmt.Errorf("反序列化缓存 %s 失败: %w", key, err)
	}
	return true, nil
}

// Set 对应 redisCache.setCacheObject(key, value)（无过期）
func (c *Client) Set(ctx context.Context, key string, value any) error {
	return c.rdb.Set(ctx, key, value, 0).Err()
}

// SetWithTTL 对应 setCacheObject(key, value, timeout, unit)
func (c *Client) SetWithTTL(ctx context.Context, key string, value any, ttl time.Duration) error {
	return c.rdb.Set(ctx, key, value, ttl).Err()
}

// SetJSON 以 JSON 字符串写入（对象场景）
func (c *Client) SetJSON(ctx context.Context, key string, value any, ttl time.Duration) error {
	b, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return c.rdb.Set(ctx, key, b, ttl).Err()
}

// Delete 对应 redisCache.deleteObject(key)
func (c *Client) Delete(ctx context.Context, keys ...string) error {
	if len(keys) == 0 {
		return nil
	}
	return c.rdb.Del(ctx, keys...).Err()
}

// Exists 对应 redisCache.hasKey(key)
func (c *Client) Exists(ctx context.Context, key string) (bool, error) {
	n, err := c.rdb.Exists(ctx, key).Result()
	return n > 0, err
}

// Incr 对应 redisTemplate.opsForValue().increment(key)
func (c *Client) Incr(ctx context.Context, key string, delta int64) (int64, error) {
	return c.rdb.IncrBy(ctx, key, delta).Result()
}

// SetNXWithTTL 对应 setIfAbsent(key, value, timeout, unit) —— 消息幂等的标准手法。
func (c *Client) SetNXWithTTL(ctx context.Context, key string, value any, ttl time.Duration) (bool, error) {
	return c.rdb.SetNX(ctx, key, value, ttl).Result()
}

// GetOrLoad 是 @Cacheable(value, key) 的手写等价物。
//
// DIFF: Spring 的 @Cacheable 由 AOP 拦截方法调用，缓存逻辑对业务透明；
// Go 没有方法拦截器，必须显式写成"先查缓存、未命中回源、写回缓存"的模板方法。
// 注意：这里不处理缓存击穿（并发回源），需要时用 singleflight 包再包一层。
func GetOrLoad(ctx context.Context, c *Client, key string, ttl time.Duration, load func(ctx context.Context) (any, error)) (any, error) {
	if v, ok, err := c.Get(ctx, key); err == nil && ok {
		return v, nil
	}
	val, err := load(ctx)
	if err != nil {
		return nil, err
	}
	if val != nil {
		_ = c.SetJSON(ctx, key, val, ttl)
	}
	return val, nil
}
