-- =============================================================================
-- 本地联调初始化：schema / 扩展 / search_path
--
-- 由 docker-compose 挂载到 /docker-entrypoint-initdb.d，仅在数据卷首次初始化时执行。
-- 角色名与 compose 中的 POSTGRES_USER 保持一致（gaussdb）；如改用其它角色，
-- 请同步修改本文件的 ALTER ROLE。
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS jl_data01;

-- 服务与 Java 侧一致，默认在 jl_data01 下解析未限定 schema 的对象。
ALTER ROLE gaussdb SET search_path = jl_data01, public;

-- 注意：pg_trgm / btree_gin 仅在执行生产索引方案（index_optimization.sql）时需要，
-- 不在本地最小环境强制创建，避免基础镜像未打包 contrib 时初始化失败。
-- 生产建库时由 DBA 按需执行：
--   CREATE EXTENSION IF NOT EXISTS pg_trgm;
--   CREATE EXTENSION IF NOT EXISTS btree_gin;
