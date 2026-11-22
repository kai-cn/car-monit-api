// 来源: application.yml:12-45（dynamic-datasource + Druid + p6spy）
//       MyBatis-Plus 的 SqlSession / @Transactional
// 职责: GaussDB/PostgreSQL 连接池与事务边界。
// 对应关系:
//   Druid maxActive / minIdle / maxWait     ↔ PgPoolOptions::max_connections / min_connections / acquire_timeout
//   @Transactional                          ↔ pool.begin() / tx.commit()
//   JdbcTemplate.queryForObject             ↔ sqlx::query_scalar
//
// DIFF: Java 靠 AOP 代理开启事务，自调用会失效；Rust 必须显式 `let mut tx = db.begin().await?`，
// 事务体返回 Err 即回滚 —— 所见即所得。

use std::time::Duration;

use sqlx::postgres::{PgPoolOptions, PgRow};
use sqlx::{PgPool, Postgres, Row, Transaction};

use crate::config::MasterDatasource;
use crate::error::{AppError, AppResult};

#[derive(Clone)]
pub struct Db {
    pub pool: PgPool,
}

impl Db {
    /// 对应 SqlSessionFactory + DataSource：启动即 Ping（fail fast）。
    pub async fn connect(cfg: &MasterDatasource) -> anyhow::Result<Self> {
        let dsn = build_dsn(cfg)?;
        let pool = PgPoolOptions::new()
            .max_connections(cfg.max_open_conns.max(1))
            .min_connections(cfg.max_idle_conns)
            .acquire_timeout(Duration::from_secs(60))
            .idle_timeout(Some(Duration::from_secs(
                cfg.conn_max_lifetime_seconds.max(60),
            )))
            .connect(&dsn)
            .await
            .map_err(|e| anyhow::anyhow!("数据库 Ping 失败: {}", e))?;
        Ok(Self { pool })
    }

    /// 只创建连接池不建立连接（供路由/装配类测试使用，不需要真实数据库）。
    pub fn lazy(cfg: &MasterDatasource) -> anyhow::Result<Self> {
        let dsn = build_dsn(cfg)?;
        let pool = PgPoolOptions::new()
            .max_connections(cfg.max_open_conns.max(1))
            .connect_lazy(&dsn)
            .map_err(|e| anyhow::anyhow!("创建惰性连接池失败: {}", e))?;
        Ok(Self { pool })
    }

    pub async fn ping(&self) -> AppResult<()> {
        sqlx::query("SELECT 1").execute(&self.pool).await?;
        Ok(())
    }

    /// 对应 @Transactional：调用方拿到 tx 后自行 commit / rollback。
    pub async fn begin(&self) -> AppResult<Transaction<'_, Postgres>> {
        Ok(self.pool.begin().await?)
    }

    /// 对应 JdbcTemplate.queryForObject 的通用形态。
    pub async fn scalar_i64(&self, sql: &str) -> AppResult<i64> {
        let n: Option<i64> = sqlx::query_scalar(sql).fetch_optional(&self.pool).await?;
        Ok(n.unwrap_or(0))
    }

    pub async fn exec(&self, sql: &str) -> AppResult<u64> {
        let r = sqlx::query(sql).execute(&self.pool).await?;
        Ok(r.rows_affected())
    }

    pub async fn fetch_rows(&self, sql: &str) -> AppResult<Vec<PgRow>> {
        Ok(sqlx::query(sql).fetch_all(&self.pool).await?)
    }

    pub async fn close(&self) {
        self.pool.close().await;
    }
}

/// 把 JDBC URL 转成 sqlx 可用的 DSN。
///
/// DIFF: JDBC 专属参数（useUnicode / characterEncoding / tinyInt1isBit）SQLx 不认识，
/// 只保留 PostgreSQL 原生参数（sslmode / TimeZone / connect_timeout）。
pub fn build_dsn(cfg: &MasterDatasource) -> anyhow::Result<String> {
    let raw = cfg.url.trim();
    let raw = raw.strip_prefix("jdbc:").unwrap_or(raw);
    if !raw.starts_with("postgresql://") && !raw.starts_with("postgres://") {
        anyhow::bail!(
            "仅支持 postgresql:// 或 jdbc:postgresql:// 形式的 url，当前为 {:?}",
            cfg.url
        );
    }
    let u = url::Url::parse(raw).map_err(|e| anyhow::anyhow!("解析数据库 url 失败: {}", e))?;
    let host = u.host_str().unwrap_or("localhost");
    let port = u.port().unwrap_or(5432);
    let dbname = u.path().trim_start_matches('/');
    let user = if cfg.username.is_empty() {
        u.username().to_string()
    } else {
        cfg.username.clone()
    };
    let pass = if cfg.password.is_empty() {
        u.password().unwrap_or("").to_string()
    } else {
        cfg.password.clone()
    };

    let mut sslmode = "disable".to_string();
    for (k, v) in u.query_pairs() {
        if k == "sslmode" {
            sslmode = v.to_string();
        }
    }
    Ok(format!(
        "postgres://{}:{}@{}:{}/{}?sslmode={}&TimeZone=Asia/Shanghai",
        urlencode(&user),
        urlencode(&pass),
        host,
        port,
        dbname,
        sslmode
    ))
}

fn urlencode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

/// 把一行 PgRow 转成 JSON（用于三表合并查询等不方便静态建模的场景）。
/// 对应 MyBatis 的 `resultType="map"` / `call-setters-on-nulls`。
pub fn row_to_json(row: &PgRow) -> serde_json::Value {
    use serde_json::{Map, Value};
    let mut map = Map::new();
    for (i, col) in row.columns().iter().enumerate() {
        let name = <sqlx::postgres::PgColumn as sqlx::Column>::name(col);
        let type_info = <sqlx::postgres::PgColumn as sqlx::Column>::type_info(col);
        let type_name = <sqlx::postgres::PgTypeInfo as sqlx::TypeInfo>::name(type_info);
        let v = match type_name {
            "BOOL" => row
                .try_get::<Option<bool>, _>(i)
                .ok()
                .flatten()
                .map(Value::Bool),
            "INT2" => row
                .try_get::<Option<i16>, _>(i)
                .ok()
                .flatten()
                .map(|v| Value::Number(v.into())),
            "INT4" => row
                .try_get::<Option<i32>, _>(i)
                .ok()
                .flatten()
                .map(|v| Value::Number(v.into())),
            "INT8" => row
                .try_get::<Option<i64>, _>(i)
                .ok()
                .flatten()
                .map(|v| Value::Number(v.into())),
            "FLOAT4" => row
                .try_get::<Option<f32>, _>(i)
                .ok()
                .flatten()
                .and_then(|v| serde_json::Number::from_f64(v as f64).map(Value::Number)),
            "FLOAT8" => row
                .try_get::<Option<f64>, _>(i)
                .ok()
                .flatten()
                .and_then(|v| serde_json::Number::from_f64(v).map(Value::Number)),
            "NUMERIC" => row
                .try_get::<Option<bigdecimal::BigDecimal>, _>(i)
                .ok()
                .flatten()
                .and_then(|v| {
                    use bigdecimal::ToPrimitive;
                    v.to_f64()
                        .and_then(serde_json::Number::from_f64)
                        .map(Value::Number)
                }),
            "JSON" | "JSONB" => row
                .try_get::<Option<serde_json::Value>, _>(i)
                .ok()
                .flatten(),
            "TIMESTAMP" | "TIMESTAMPTZ" => row
                .try_get::<Option<chrono::DateTime<chrono::Utc>>, _>(i)
                .ok()
                .flatten()
                .map(|v| Value::String(v.to_rfc3339())),
            "DATE" => row
                .try_get::<Option<chrono::NaiveDate>, _>(i)
                .ok()
                .flatten()
                .map(|v| Value::String(v.format("%Y-%m-%d").to_string())),
            _ => row
                .try_get::<Option<String>, _>(i)
                .ok()
                .flatten()
                .map(Value::String),
        }
        .unwrap_or(Value::Null);
        map.insert(name.to_string(), v);
    }
    Value::Object(map)
}

/// 把 sqlx 错误统一成业务错误，保留原始错误链。
pub fn db_err(e: sqlx::Error) -> AppError {
    AppError::Db(e)
}
