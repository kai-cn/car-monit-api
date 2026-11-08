package scheduler

// 分布式租约锁 —— 让定时任务在**多副本部署**时只有一个实例真正执行。
//
// 背景（报告 02 R5）：调度器本身没有分布式语义，多副本时每个实例都会跑
// syncTrack / 增量同步 / 补偿等写共享状态的 job。当前部署基线是单副本
// （deploy/k8s.yaml 用 replicas: 1 + Recreate 固化），所以默认**关闭**本锁：
// 关闭时行为与 V1 完全一致，单副本部署零影响。
//
// 开启方式（configs/config.yaml）：
//
//	scheduler:
//	  distributed-lock:
//	    enabled: true
//	    key-prefix: "scheduler:lock:"   # 可保留默认
//	    ttl: 300s                       # 单次租约有效期，需 > 最慢 job 的常规耗时
//
// 语义（与 Spring 侧 @Scheduled 的 poolSize 模型正交）：
//   - 每次触发前尝试 SET NX PX 抢占 `<prefix><jobName>`；
//   - 抢到才执行，抢不到说明别的副本正在跑，本次触发直接跳过（不排队、不重试）；
//   - 执行期间每 ttl/3 续约一次（仅当 token 仍是自己的），执行结束后 compare-and-delete；
//   - 抢锁失败与续约失败都只影响"这一次是否执行"，不会让调度协程退出。
//
// 失效场景（必须知道）：
//   1. **续约失败**（Redis 抖断/主从切换）→ 租约到期后别的副本可再次执行，
//      可能出现同一 job 短暂并发。此时日志会打 `[定时任务] 租约续期失败`，需告警。
//   2. **job 执行时间远超 ttl** 且续约正常时是安全的；但若进程被 SIGKILL，
//      租约要等 ttl 自然过期才释放（最多空转 ttl 时长的触发）。
//   3. Redis 不可用：`enabled: true` 时所有 job 都抢不到锁 → **全部不执行**。
//      这是一个"宁可漏跑也不重复跑"的取舍；对可靠性敏感的部署应保证 Redis 可用，
//      或改用 DB 实现（本包把 Locker 抽象成接口，替换实现即可）。
//
// 验证方法：
//   - 单副本：`enabled: true` 后行为应与关闭时一致（每个 job 照常执行）；
//   - 双副本：同一时刻只有一台日志里出现 `[定时任务] 开始执行 job=syncCurrentTrack`；
//   - Redis 侧可 `GET scheduler:lock:syncCurrentTrack` 观察租约键，执行结束后应消失。

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

// Locker 是"任务级分布式租约"的最小接口。
//
// TryLock 返回：
//   - release：拿锁成功时非 nil，调用方必须 defer 调用（幂等）；
//   - ok：true 表示抢到；
//   - err：非 nil 说明锁后端不可用（调用方应视为"没抢到"并记录告警）。
type Locker interface {
	TryLock(ctx context.Context, key string, ttl time.Duration) (release func(), ok bool, err error)
}

// LockConfig 是分布式锁配置（对应 configs 的 scheduler.distributed-lock 段）。
type LockConfig struct {
	Enabled   bool
	KeyPrefix string
	TTL       time.Duration
}

// DefaultLockConfig 返回默认值：关闭、前缀 scheduler:lock:、TTL 300s。
func DefaultLockConfig() LockConfig {
	return LockConfig{Enabled: false, KeyPrefix: "scheduler:lock:", TTL: 5 * time.Minute}
}

// Normalized 补齐空值，保证开启锁时不会因为缺省字段而失效。
func (c LockConfig) Normalized() LockConfig {
	if c.KeyPrefix == "" {
		c.KeyPrefix = "scheduler:lock:"
	}
	if c.TTL <= 0 {
		c.TTL = 5 * time.Minute
	}
	// 续约间隔取 TTL/3，但要 >= 1s，避免 TTL 极小时把 Redis 打爆。
	if c.TTL < 3*time.Second {
		c.TTL = 3 * time.Second
	}
	return c
}

// renewInterval 返回续约间隔。
func (c LockConfig) renewInterval() time.Duration {
	d := c.TTL / 3
	if d < time.Second {
		d = time.Second
	}
	return d
}

// redisLocker 是 Locker 的 Redis 实现（SET NX PX + token 校验续约/释放）。
type redisLocker struct {
	rdb       *redis.Client
	keyPrefix string
	ttl       time.Duration
}

// NewRedisLocker 用 cache 客户端的底层 *redis.Client 构造锁实现。
func NewRedisLocker(rdb *redis.Client, cfg LockConfig) Locker {
	cfg = cfg.Normalized()
	return &redisLocker{rdb: rdb, keyPrefix: cfg.KeyPrefix, ttl: cfg.TTL}
}

// releaseScript：只有 token 匹配才删除，避免替别人解锁。
var releaseScript = redis.NewScript(`
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0`)

// renewScript：只有 token 匹配才续期，避免续到别人的租约上。
var renewScript = redis.NewScript(`
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("pexpire", KEYS[1], ARGV[2])
end
return 0`)

func (l *redisLocker) TryLock(ctx context.Context, key string, ttl time.Duration) (func(), bool, error) {
	if l == nil || l.rdb == nil {
		return nil, false, errors.New("scheduler: 锁后端未初始化")
	}
	if ttl <= 0 {
		ttl = l.ttl
	}
	fullKey := l.keyPrefix + key
	token := uuid.NewString()

	ok, err := l.rdb.SetNX(ctx, fullKey, token, ttl).Result()
	if err != nil {
		return nil, false, fmt.Errorf("scheduler: 抢锁失败(%s): %w", key, err)
	}
	if !ok {
		return nil, false, nil
	}

	// 续约协程：执行期间保持租约；ctx 取消（进程关闭）时退出。
	renewCtx, cancelRenew := context.WithCancel(context.WithoutCancel(ctx))
	var once sync.Once
	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[定时任务] 租约续期协程 panic", "job", key, "panic", r)
			}
		}()
		ticker := time.NewTicker(l.ttl / 3)
		defer ticker.Stop()
		for {
			select {
			case <-renewCtx.Done():
				return
			case <-ticker.C:
				// 续约用独立短超时：锁后端抖动不应拖住任务本身。
				rctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 2*time.Second)
				n, rerr := renewScript.Run(rctx, l.rdb, []string{fullKey}, token, int64(l.ttl/time.Millisecond)).Int()
				cancel()
				if rerr != nil {
					slog.Warn("[定时任务] 租约续期失败（锁后端不可用，租约到期后可能被其他副本抢占）",
						"job", key, "err", rerr)
					continue
				}
				if n == 0 {
					slog.Warn("[定时任务] 租约已不属于本实例（可能已过期被抢占）", "job", key)
					return
				}
			}
		}
	}()

	release := func() {
		once.Do(func() {
			cancelRenew()
			rctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 2*time.Second)
			defer cancel()
			if _, err := releaseScript.Run(rctx, l.rdb, []string{fullKey}, token).Result(); err != nil {
				// 释放失败不影响业务，租约会在 ttl 后自然过期；但要让运维看得见。
				slog.Warn("[定时任务] 释放租约失败（将由 TTL 自然过期）", "job", key, "err", err)
			}
		})
	}
	return release, true, nil
}
