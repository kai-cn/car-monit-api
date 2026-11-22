// car-monit-api-rust —— pro-business-api（Java / Spring Boot）的 1:1 Rust 迁移。
// 模块划分与 Java 分层一一对应，详见 README-MIGRATION.md 的目录映射表。
pub mod cache;
pub mod config;
pub mod db;
pub mod error;
pub mod es;
pub mod handlers;
pub mod metrics;
pub mod middleware;
pub mod models;
pub mod mq;
pub mod repo;
pub mod response;
pub mod router;
pub mod scheduler;
pub mod services;
pub mod state;
pub mod utils;
