CREATE TABLE IF NOT EXISTS kafka_message_record (
    id VARCHAR(64) PRIMARY KEY,
    data_id VARCHAR(64) NOT NULL,
    topic VARCHAR(255) NOT NULL,
    message_json TEXT NOT NULL,
    status INTEGER DEFAULT 0 COMMENT '0:待发送, 1:发送成功, 2:发送失败',
    retry_count INTEGER DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    send_time TIMESTAMP NULL,
    error_msg TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_kafka_message_record_status ON kafka_message_record(status);
CREATE INDEX IF NOT EXISTS idx_kafka_message_record_data_id ON kafka_message_record(data_id);
CREATE INDEX IF NOT EXISTS idx_kafka_message_record_create_time ON kafka_message_record(create_time);
