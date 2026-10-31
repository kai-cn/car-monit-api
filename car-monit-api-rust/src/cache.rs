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

use std::time::Duration;

use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::config::RedisConfig;
use crate::error::{AppError, AppResult};

#[derive(Clone)]
pub struct Cache {
    conn: ConnectionManager,
}

impl Cache {
    pub async fn connect(cfg: &RedisConfig) -> anyhow::Result<Self> {
        let client = redis::Client::open(format!(
            "redis://{}:{}/{}",
            cfg.host, cfg.port, cfg.database
        ))
        .map_err(|e| anyhow::anyhow!("创建 Redis 客户端失败: {}", e))?;
        let mut conn = ConnectionManager::new(client)
            .await
            .map_err(|e| anyhow::anyhow!("连接 Redis {} 失败: {}", cfg.addr(), e))?;
        // 启动即 Ping：与 Java Lettuce 的懒连接不同，这里 fail fast
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        Ok(Self { conn })
    }

    pub async fn ping(&self) -> AppResult<()> {
        let mut conn = self.conn.clone();
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        Ok(())
    }

    pub async fn get(&self, key: &str) -> AppResult<Option<String>> {
        let mut conn = self.conn.clone();
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
        let mut conn = self.conn.clone();
        let _: () = conn.set(key, value.into()).await?;
        Ok(())
    }

    pub async fn set_ttl(
        &self,
        key: &str,
        value: impl Into<String>,
        ttl: Duration,
    ) -> AppResult<()> {
        let mut conn = self.conn.clone();
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
        let mut conn = self.conn.clone();
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
        let mut conn = self.conn.clone();
        let _: i64 = conn.del(keys).await?;
        Ok(())
    }

    pub async fn exists(&self, key: &str) -> AppResult<bool> {
        let mut conn = self.conn.clone();
        Ok(conn.exists(key).await?)
    }

    pub async fn incr(&self, key: &str, delta: i64) -> AppResult<i64> {
        let mut conn = self.conn.clone();
        Ok(conn.incr(key, delta).await?)
    }

    pub async fn expire(&self, key: &str, ttl: Duration) -> AppResult<bool> {
        let mut conn = self.conn.clone();
        Ok(conn.expire(key, ttl.as_secs() as i64).await?)
    }

    /// 对应 redisTemplate.keys(pattern)；用 SCAN 避免 KEYS 阻塞线上 Redis。
    pub async fn scan_keys(&self, pattern: &str) -> AppResult<Vec<String>> {
        let mut conn = self.conn.clone();
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
        let mut conn = self.conn.clone();
        Ok(conn.lrange(key, start, stop).await?)
    }

    pub async fn right_push(&self, key: &str, value: impl Into<String>) -> AppResult<()> {
        let mut conn = self.conn.clone();
        let _: () = conn.rpush(key, value.into()).await?;
        Ok(())
    }

    pub async fn lrem(&self, key: &str, count: isize, value: &str) -> AppResult<i64> {
        let mut conn = self.conn.clone();
        Ok(conn.lrem(key, count, value).await?)
    }

    pub async fn ltrim(&self, key: &str, start: isize, stop: isize) -> AppResult<()> {
        let mut conn = self.conn.clone();
        let _: () = conn.ltrim(key, start, stop).await?;
        Ok(())
    }

    pub async fn sadd(&self, key: &str, member: &str) -> AppResult<i64> {
        let mut conn = self.conn.clone();
        Ok(conn.sadd(key, member).await?)
    }

    pub async fn smembers(&self, key: &str) -> AppResult<Vec<String>> {
        let mut conn = self.conn.clone();
        Ok(conn.smembers(key).await?)
    }

    pub async fn get_int(&self, key: &str) -> AppResult<Option<i64>> {
        let mut conn = self.conn.clone();
        let v: Option<String> = conn.get(key).await?;
        Ok(v.and_then(|s| s.parse::<i64>().ok()))
    }
}
