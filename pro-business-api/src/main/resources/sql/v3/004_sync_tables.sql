-- =============================================================================
-- V3 阶段一：GaussDB -> ES 同步基础设施表（Outbox / DLQ / 对账 / 位点）
--
-- 设计依据：architecture-traffic-query-design.md §5.6 / §8.3
-- 原则：
--   1. 业务事实行与 Outbox 行在同一事务写入（由 Flink/ETL 或 DBA 触发器保证）；
--   2. API 侧 relay 只读 Outbox 发 Kafka search-sync，不反向写业务表；
--   3. ES 文档 _id 幂等（big_id / cid），重复事件覆盖；
--   4. 失败重试 5 次后进 DLQ；对账按分钟桶比对 GaussDB 与 ES 行数。
--
-- 幂等：全部 CREATE ... IF NOT EXISTS，可重复执行。
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

-- -----------------------------------------------------------------------------
-- 0. 幂等索引助手（openGauss 3.0 不支持 CREATE INDEX IF NOT EXISTS）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_create_index_if_absent(
    p_table   text,
    p_index   text,
    p_columns text,
    p_where   text DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_exists int;
BEGIN
    SELECT count(*) INTO v_exists
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_index
       AND c.relkind IN ('i', 'I');
    IF v_exists = 0 THEN
        EXECUTE 'CREATE INDEX ' || quote_ident(p_index)
                || ' ON jl_data01.' || quote_ident(p_table)
                || ' (' || p_columns || ')'
                || CASE WHEN p_where IS NULL THEN '' ELSE ' WHERE ' || p_where END;
        RAISE NOTICE '[V3] 索引已创建: %.%', p_table, p_index;
    END IF;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. Outbox：待同步事件（GaussDB 提交即产生事件）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.search_sync_outbox (
    id              bigserial     PRIMARY KEY,
    event_id        varchar(64)   NOT NULL,
    table_name      varchar(64)   NOT NULL,
    pk              varchar(100)  NOT NULL,
    op              varchar(8)    NOT NULL,   -- I/U/D
    event_time      timestamp(6)  NOT NULL,
    payload         text,                      -- 展示字段 JSON；为空时 relay 按 pk 回查
    schema_version  int           NOT NULL DEFAULT 1,
    status          varchar(16)   NOT NULL DEFAULT 'PENDING', -- PENDING/SENT/FAILED
    retry_count     int           NOT NULL DEFAULT 0,
    last_error      varchar(500),
    created_at      timestamp(6)  NOT NULL DEFAULT now(),
    sent_at         timestamp(6),
    CONSTRAINT uk_search_sync_outbox_event_id UNIQUE (event_id)
);

SELECT jl_data01.v3_create_index_if_absent(
    'search_sync_outbox', 'idx_search_sync_outbox_status_id', 'status, id', NULL);

SELECT jl_data01.v3_create_index_if_absent(
    'search_sync_outbox', 'idx_search_sync_outbox_table_time', 'table_name, event_time', NULL);

COMMENT ON TABLE jl_data01.search_sync_outbox IS
    'GaussDB->ES 同步 Outbox；与事实行同事务写入，relay 消费后置 SENT';

-- -----------------------------------------------------------------------------
-- 2. DLQ：多次重试仍失败的事件（可重放）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.search_sync_dlq (
    id              bigserial     PRIMARY KEY,
    event_id        varchar(64),
    table_name      varchar(64)   NOT NULL,
    pk              varchar(100)  NOT NULL,
    op              varchar(8),
    event_time      timestamp(6),
    payload         text,
    error_message   varchar(1000),
    retry_count     int           NOT NULL DEFAULT 0,
    resolved        boolean       NOT NULL DEFAULT false,
    created_at      timestamp(6)  NOT NULL DEFAULT now(),
    resolved_at     timestamp(6)
);

SELECT jl_data01.v3_create_index_if_absent(
    'search_sync_dlq', 'idx_search_sync_dlq_unresolved', 'resolved, created_at DESC', NULL);

COMMENT ON TABLE jl_data01.search_sync_dlq IS
    'ES 同步死信：重试耗尽后落库，支持按时间桶重放';

-- -----------------------------------------------------------------------------
-- 3. 对账结果：按分钟桶比对 GaussDB 行数与 ES 文档数
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.search_sync_reconcile (
    id              bigserial     PRIMARY KEY,
    table_name      varchar(64)   NOT NULL,
    bucket_start    timestamp(6)  NOT NULL,
    bucket_end      timestamp(6)  NOT NULL,
    gauss_count     bigint        NOT NULL,
    es_count        bigint        NOT NULL,
    diff_ratio      numeric(10,6) NOT NULL,
    status          varchar(16)   NOT NULL, -- OK/DRIFT/REPAIRED/ERROR
    detail          varchar(500),
    created_at      timestamp(6)  NOT NULL DEFAULT now(),
    CONSTRAINT uk_search_sync_reconcile_bucket UNIQUE (table_name, bucket_start)
);

SELECT jl_data01.v3_create_index_if_absent(
    'search_sync_reconcile', 'idx_search_sync_reconcile_status_time', 'status, bucket_start DESC', NULL);

COMMENT ON TABLE jl_data01.search_sync_reconcile IS
    'GaussDB/ES 分钟桶对账结果；DRIFT 触发按桶回灌';

-- -----------------------------------------------------------------------------
-- 4. 同步位点：替代 Redis 水位，便于审计与重启恢复
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.search_sync_checkpoint (
    table_name      varchar(64)   PRIMARY KEY,
    last_event_id   varchar(64),
    last_event_time timestamp(6),
    updated_at      timestamp(6)  NOT NULL DEFAULT now()
);

COMMENT ON TABLE jl_data01.search_sync_checkpoint IS
    '同步位点：记录每张表已确认的最大事件，供 relay/回灌恢复';

-- -----------------------------------------------------------------------------
-- 5. 完成提示
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    RAISE NOTICE 'V3 同步基础表已就绪：search_sync_outbox / search_sync_dlq / search_sync_reconcile / search_sync_checkpoint';
    RAISE NOTICE '业务侧需保证：事实行与 outbox 行在同一事务写入；ES _id = big_id/cid。';
END $$;
