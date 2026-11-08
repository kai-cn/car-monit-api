-- =============================================================================
-- kafka_message_record —— 真实 DDL（PostgreSQL 方言）
--
-- 来源：setup_script/sql/10_kafka_message_record.pg.sql（原 MySQL DDL 的机械转换，
-- 列名/类型/默认值/索引与实体和 Mapper XML 完全一致）。
-- 对应 kafka_message_record.sql（MySQL 原版，勿直接用于 PostgreSQL）。
-- =============================================================================

CREATE TABLE IF NOT EXISTS jl_data01.kafka_message_record (
    id           VARCHAR(64) PRIMARY KEY,
    data_id      VARCHAR(64)  NOT NULL,
    topic        VARCHAR(255) NOT NULL,
    message_json TEXT         NOT NULL,
    status       INTEGER      DEFAULT 0,
    retry_count  INTEGER      DEFAULT 0,
    create_time  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    send_time    TIMESTAMP    NULL,
    error_msg    TEXT         NULL
);

COMMENT ON TABLE  jl_data01.kafka_message_record IS 'Kafka 消息发送记录（支持失败重发）';
COMMENT ON COLUMN jl_data01.kafka_message_record.status      IS '0:待发送, 1:发送成功, 2:发送失败';
COMMENT ON COLUMN jl_data01.kafka_message_record.retry_count IS '已重试次数';
COMMENT ON COLUMN jl_data01.kafka_message_record.error_msg   IS '失败时的异常信息';

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_status
    ON jl_data01.kafka_message_record (status);

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_data_id
    ON jl_data01.kafka_message_record (data_id);

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_create_time
    ON jl_data01.kafka_message_record (create_time);
