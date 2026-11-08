// 来源: pro-base-common/src/main/java/com/ruoyi/common/core/redis/RedisCache.java
//       pro-base-common/src/main/java/com/ruoyi/common/config/RedisConfiguration.java
// 职责: Redis 门面：字符串/JSON 读写、TTL、SETNX 幂等、INCR、SCAN。
// 对应关系:
//   redisCache.getCacheObject        ↔ get / get_json
//   redisCache.setCacheObject        ↔ set / set_json
//   opsForValue().increment          ↔ incr
//   setIfAbsent(key,val,ttl,unit)    ↔ set_nx
//   redisTemplate.keys(pattern)      ↔ scan_keys（用 SCAN 替代 KEYS，避免阻塞）
//
// DIFF: Spring 用 FastJson2 序列化 Java 对象；Rust 统一存 JSON 字符串。
// 迁移期若 Java/Rust 共用同一个 key，必须约定同一序列化格式（见 README 兼容性风险）。
//
// DIFF(生产化): 启动时连不上 Redis 不再永久降级。Cache 现在持有 client 并在每次操作时
// 惰性重连（3s 超时 + 3s 失败退避），这样 Redis 晚于应用启动/短暂抖动后能自动恢复，
// readiness 也能通过 ping() 反映真实状态。

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use serde::de::DeserializeOwned;
use serde::Serialize;
use tokio::sync::RwLock;
use tracing::warn;

use crate::config::RedisConfig;
use crate::error::{AppError, AppResult};

const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
const RECONNECT_BACKOFF: Duration = Duration::from_secs(3);

/// 租约脚本：持有者续期 / 空闲时抢占，两个动作在 Redis 内原子完成。
/// 避免旧实现 GET+EXPIRE 之间的竞态（两个副本同时判定持有）。
const LEASE_LUA: &str = r#"
local cur = redis.call('GET', KEYS[1])
if cur == ARGV[1] then
  redis.call('EXPIRE', KEYS[1], ARGV[2])
  return 1
end
if not cur then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
  return 1
end
return 0
"#;

#[derive(Clone)]
pub struct Cache {
    client: redis::Client,
    conn: Arc<RwLock<Option<ConnectionManager>>>,
    last_failure: Arc<Mutex<Option<Instant>>>,
}

impl Cache {
    pub async fn connect(cfg: &RedisConfig) -> anyhow::Result<Self> {
        // PARITY: Java Lettuce 通过 redis.password 认证。此前只拼 host/port/db，
        // 有密码的 Redis 会直接连不上；这里按 redis://:password@host:port/db 构造，
        // 由 url crate 负责特殊字符转义。
        let mut url = url::Url::parse("redis://localhost")
            .map_err(|e| anyhow::anyhow!("构造 Redis URL 失败: {}", e))?;
        url.set_host(Some(cfg.host.as_str()))
            .map_err(|_| anyhow::anyhow!("非法的 Redis host: {}", cfg.host))?;
        url.set_port(Some(cfg.port))
            .map_err(|_| anyhow::anyhow!("非法的 Redis 端口: {}", cfg.port))?;
        if !cfg.password.is_empty() {
            url.set_password(Some(cfg.password.as_str()))
                .map_err(|_| anyhow::anyhow!("Redis 密码包含非法字符"))?;
        }
        url.set_path(&format!("/{}", cfg.database));
        let client = redis::Client::open(url.as_str())
            .map_err(|e| anyhow::anyhow!("创建 Redis 客户端失败: {}", e))?;
        let cache = Self {
            client,
            conn: Arc::new(RwLock::new(None)),
            last_failure: Arc::new(Mutex::new(None)),
        };
        // 启动时尝试一次；失败只告警，后续按需重连（不再永久降级）。
        if let Err(e) = cache.connection().await {
            warn!(addr = %cfg.addr(), err = %e, "Redis 暂不可用，将在后续请求中重连");
        }
        Ok(cache)
    }

    /// 取当前连接；没有则（带 3s 超时与失败退避）重连一次。
    async fn connection(&self) -> AppResult<ConnectionManager> {
        if let Some(c) = self.conn.read().await.as_ref() {
            return Ok(c.clone());
        }
        let mut guard = self.conn.write().await;
        if let Some(c) = guard.as_ref() {
            return Ok(c.clone());
        }
        if let Some(t) = *self.last_failure.lock().unwrap_or_else(|e| e.into_inner()) {
            if t.elapsed() < RECONNECT_BACKOFF {
                return Err(AppError::biz("Redis 不可用（重连退避中）"));
            }
        }
        match tokio::time::timeout(CONNECT_TIMEOUT, ConnectionManager::new(self.client.clone()))
            .await
        {
            Ok(Ok(mut cm)) => {
                let ping: Result<String, redis::RedisError> =
                    redis::cmd("PING").query_async(&mut cm).await;
                if let Err(e) = ping {
                    *self.last_failure.lock().unwrap_or_else(|x| x.into_inner()) = Some(Instant::now());
                    return Err(AppError::biz(format!("Redis PING 失败: {}", e)));
                }
                *guard = Some(cm.clone());
                *self.last_failure.lock().unwrap_or_else(|x| x.into_inner()) = None;
                Ok(cm)
            }
            Ok(Err(e)) => {
                *self.last_failure.lock().unwrap_or_else(|x| x.into_inner()) = Some(Instant::now());
                Err(AppError::biz(format!("Redis 重连失败: {}", e)))
            }
            Err(_) => {
                *self.last_failure.lock().unwrap_or_else(|x| x.into_inner()) = Some(Instant::now());
                Err(AppError::biz("Redis 重连超时"))
            }
        }
    }

    pub async fn ping(&self) -> AppResult<()> {
        let mut conn = self.connection().await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        Ok(())
    }

    pub async fn get(&self, key: &str) -> AppResult<Option<String>> {
        let mut conn = self.connection().await?;
        Ok(conn.get(key).await?)
    }

    pub async fn get_json<T: DeserializeOwned>(&self, key: &str) -> AppResult<Option<T>> {
        match self.get(key).await? {
            Some(raw) => serde_json::from_str(&raw)
                .map(Some)
                .map_err(|e| AppError::biz(format!("反序列化缓存 {} 失败: {}", key, e))),
            None => Ok(None),
        }
    }

    pub async fn set(&self, key: &str, value: impl Into<String>) -> AppResult<()> {
        let mut conn = self.connection().await?;
        let _: () = conn.set(key, value.into()).await?;
        Ok(())
    }

    pub async fn set_ttl(
        &self,
        key: &str,
        value: impl Into<String>,
        ttl: Duration,
    ) -> AppResult<()> {
        let mut conn = self.connection().await?;
        let _: () = conn.set_ex(key, value.into(), ttl.as_secs().max(1)).await?;
        Ok(())
    }

    pub async fn set_json<T: Serialize>(
        &self,
        key: &str,
        value: &T,
        ttl: Duration,
    ) -> AppResult<()> {
        let s = serde_json::to_string(value)?;
        if ttl.is_zero() {
            self.set(key, s).await
        } else {
            self.set_ttl(key, s, ttl).await
        }
    }

    /// 对应 setIfAbsent：返回 true 表示本次写入成功（即首次出现，幂等基石）。
    pub async fn set_nx(
        &self,
        key: &str,
        value: impl Into<String>,
        ttl: Duration,
    ) -> AppResult<bool> {
        let mut conn = self.connection().await?;
        let set: Option<String> = redis::cmd("SET")
            .arg(key)
            .arg(value.into())
            .arg("NX")
            .arg("EX")
            .arg(ttl.as_secs().max(1))
            .query_async(&mut conn)
            .await?;
        Ok(set.is_some())
    }

    pub async fn del(&self, keys: &[String]) -> AppResult<()> {
        if keys.is_empty() {
            return Ok(());
        }
        let mut conn = self.connection().await?;
        let _: i64 = conn.del(keys).await?;
        Ok(())
    }

    pub async fn exists(&self, key: &str) -> AppResult<bool> {
        let mut conn = self.connection().await?;
        Ok(conn.exists(key).await?)
    }

    pub async fn incr(&self, key: &str, delta: i64) -> AppResult<i64> {
        let mut conn = self.connection().await?;
        Ok(conn.incr(key, delta).await?)
    }

    pub async fn expire(&self, key: &str, ttl: Duration) -> AppResult<bool> {
        let mut conn = self.connection().await?;
        Ok(conn.expire(key, ttl.as_secs() as i64).await?)
    }

    /// 对应 redisTemplate.keys(pattern)；用 SCAN 避免 KEYS 阻塞线上 Redis。
    pub async fn scan_keys(&self, pattern: &str) -> AppResult<Vec<String>> {
        let mut conn = self.connection().await?;
        let mut cursor: u64 = 0;
        let mut keys = Vec::new();
        loop {
            let (next, batch): (u64, Vec<String>) = redis::cmd("SCAN")
                .arg(cursor)
                .arg("MATCH")
                .arg(pattern)
                .arg("COUNT")
                .arg(1000)
                .query_async(&mut conn)
                .await?;
            keys.extend(batch);
            cursor = next;
            if cursor == 0 {
                break;
            }
        }
        Ok(keys)
    }

    /// 对应 redisCache.getCacheList / rightPushAll（用于轨迹缓存）。
    pub async fn list_range(&self, key: &str, start: isize, stop: isize) -> AppResult<Vec<String>> {
        let mut conn = self.connection().await?;
        Ok(conn.lrange(key, start, stop).await?)
    }

    pub async fn right_push(&self, key: &str, value: impl Into<String>) -> AppResult<()> {
        let mut conn = self.connection().await?;
        let _: () = conn.rpush(key, value.into()).await?;
        Ok(())
    }

    pub async fn lrem(&self, key: &str, count: isize, value: &str) -> AppResult<i64> {
        let mut conn = self.connection().await?;
        Ok(conn.lrem(key, count, value).await?)
    }

    pub async fn ltrim(&self, key: &str, start: isize, stop: isize) -> AppResult<()> {
        let mut conn = self.connection().await?;
        let _: () = conn.ltrim(key, start, stop).await?;
        Ok(())
    }

    pub async fn sadd(&self, key: &str, member: &str) -> AppResult<i64> {
        let mut conn = self.connection().await?;
        Ok(conn.sadd(key, member).await?)
    }

    pub async fn smembers(&self, key: &str) -> AppResult<Vec<String>> {
        let mut conn = self.connection().await?;
        Ok(conn.smembers(key).await?)
    }

    /// 单实例租约：Lua 原子完成「持有者续期 / 空闲时抢占 / 他人持有则失败」。
    /// 用于多副本部署时只让一个副本执行定时任务（替代 Java 单机 @Scheduled 的隐含前提）。
    pub async fn acquire_lease(&self, key: &str, token: &str, ttl: Duration) -> AppResult<bool> {
        let mut conn = self.connection().await?;
        let acquired: i32 = redis::Script::new(LEASE_LUA)
            .key(key)
            .arg(token)
            .arg(ttl.as_secs().max(1))
            .invoke_async(&mut conn)
            .await?;
        Ok(acquired == 1)
    }

    pub async fn get_int(&self, key: &str) -> AppResult<Option<i64>> {
        let mut conn = self.connection().await?;
        let v: Option<String> = conn.get(key).await?;
        Ok(v.and_then(|s| s.parse::<i64>().ok()))
    }
}
