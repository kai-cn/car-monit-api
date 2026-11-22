-- =============================================================================
-- kafka_message_record —— PostgreSQL 等价版 DDL
--
-- 为什么需要这个文件？
--   仓库根目录的 kafka_message_record.sql 是 **MySQL 方言**：
--       status INTEGER DEFAULT 0 COMMENT '0:待发送, 1:发送成功, 2:发送失败'
--   PostgreSQL 不支持列定义里的内联 COMMENT，直接执行会报语法错误。
--   而实体上写的是：
--       @TableName(value = "kafka_message_record", schema = "jl_data01")
--   Mapper XML 里也全部是 jl_data01.kafka_message_record，所以这张表必须建在
--   jl_data01 下，且列名/类型要与实体和 XML 完全对得上。
--
-- 本文件做了什么 / What this file is
--   把原 MySQL DDL 做**机械方言转换**，不做任何语义修改：
--     1. 内联 COMMENT '...'  -> 列级注释改为 COMMENT ON COLUMN
--     2. 表名前补 schema     -> jl_data01.kafka_message_record（对齐 @TableName）
--     3. 索引名同样 schema 限定
--   列名、类型、默认值、可空性、主键、索引与原始文件逐项一致。
--
-- 依据（均已核对）:
--   * kafka_message_record.sql                       原 MySQL DDL
--   * com/ruoyi/base/domain/KafkaMessageRecord.java  @TableName(schema="jl_data01") + 9 个字段
--   * com/ruoyi/base/mapper/xml/KafkaMessageRecordMapper.xml
--       用到 status / retry_count / create_time / send_time / error_msg / id
--
-- 幂等 / Idempotent: 全部 IF NOT EXISTS，可重复执行。
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

-- 原 MySQL 文件里的内联注释，转换后落到列注释上
COMMENT ON TABLE  jl_data01.kafka_message_record IS 'Kafka 消息发送记录（支持失败重发）';
COMMENT ON COLUMN jl_data01.kafka_message_record.status      IS '0:待发送, 1:发送成功, 2:发送失败';
COMMENT ON COLUMN jl_data01.kafka_message_record.retry_count IS '已重试次数';
COMMENT ON COLUMN jl_data01.kafka_message_record.error_msg   IS '失败时的异常信息';

-- 索引：与原始文件的三条索引一一对应
CREATE INDEX IF NOT EXISTS idx_kafka_message_record_status
    ON jl_data01.kafka_message_record (status);

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_data_id
    ON jl_data01.kafka_message_record (data_id);

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_create_time
    ON jl_data01.kafka_message_record (create_time);
