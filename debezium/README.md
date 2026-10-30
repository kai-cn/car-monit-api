# Debezium CDC 部署指南

## 概述

本方案使用 Debezium 监听 GaussDB 数据库的 OdsRtSzdnSnapshotFlowAddcode 表数据变化，将变更数据实时同步到 Kafka，支持 car-monit-backend-new 消费者端的 MySQL 分表和 Elasticsearch 存储。

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GaussDB (源数据库)                                   │
│                         jl_data01.ods_rt_szdn_snapshot_flow_addcode         │
│                         (300G 数据, 50W 日增)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 逻辑复制 (Logical Replication)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Debezium Connector                                  │
│                         - 监听 CDC 变更                                     │
│                         - 转换消息格式                                       │
│                         - 发送至 Kafka                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Kafka Topic                                         │
│                         gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow   │
│                         (分區数: 3)                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    car-monit-backend-new (消费者)                            │
│                         │                                                    │
│                         ├── MySQL 分表 (按月)                               │
│                         │   └── ods_rt_szdn_snapshot_flow_yyyyMM           │
│                         │                                                    │
│                         └── Elasticsearch                                   │
│                             └── snapshot-flow                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 前置条件

### 1. 环境要求

- Java 8+
- Kafka 2.8+
- Kafka Connect
- GaussDB/PostgreSQL 数据库（已启用逻辑复制）

### 2. 下载 Debezium

```bash
# 下载 Debezium PostgreSQL Connector
wget https://archive.apache.org/dist/kafka/2.8.0/kafka_2.13-2.8.0.tgz
wget https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/1.9.0.Final/debezium-connector-postgres-1.9.0.Final-plugin.tar.gz

# 解压
tar -xzf kafka_2.13-2.8.0.tgz
tar -xzf debezium-connector-postgres-1.9.0.Final-plugin.tar.gz
```

## GaussDB 配置

### 1. 配置数据库参数

修改 GaussDB 配置文件（如 `postgresql.conf` 或 `gaussdb.conf`）：

```ini
# 启用逻辑复制
wal_level = logical

# 复制槽数量
max_replication_slots = 10

# WAL 发送者数量
max_wal_senders = 10

# 保留的 WAL 文件大小
wal_keep_size = 64
```

### 2. 执行复制配置脚本

连接 GaussDB 数据库，执行 SQL 脚本：

```bash
psql -h 192.168.56.10 -p 5432 -U gaussdb -d RuoYi -f debezium/sql/setup-gaussdb-replication.sql
```

脚本将完成：
- 创建复制用户（如需要）
- 创建发布 `dbz_publication_snapshot_flow`
- 配置表的 REPLICA IDENTITY

## Kafka Connect 配置

### 1. 配置 connect-distributed.properties

创建或修改 `kafka安装目录/config/connect-distributed.properties`：

```properties
bootstrap.servers=127.0.0.1:9092

group.id=connect-cluster

key.converter=org.apache.kafka.connect.json.JsonConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
key.converter.schemas.enable=false
value.converter.schemas.enable=true

offset.storage.topic=connect-offsets
offset.storage.replication.factor=1
offset.storage.partitions=3

config.storage.topic=connect-configs
config.storage.replication.factor=1

status.storage.topic=connect-status
status.storage.replication.factor=1
status.storage.partitions=3

offset.flush.interval.ms=10000

plugin.path=/path/to/debezium-connector-postgres
```

### 2. 配置 Debezium Connector

使用已创建的配置文件：

```bash
# 启动 Kafka Connect
./bin/connect-distributed.sh ./config/connect-distributed.properties

# 注册 Connector
curl -X POST -H "Content-Type: application/json" \
  --data @config/source-connector-config.json \
  http://localhost:8083/connectors

# 或使用脚本
./bin/debezium-connector.sh start
```

## 验证部署

### 1. 检查 Connector 状态

```bash
curl -s http://localhost:8083/connectors/gaussdb-snapshot-flow-source-connector/status | jq
```

预期输出：
```json
{
  "name": "gaussdb-snapshot-flow-source-connector",
  "connector": {
    "state": "RUNNING",
    "worker_id": "127.0.0.1:8083"
  },
  "tasks": [
    {
      "id": 0,
      "state": "RUNNING",
      "worker_id": "127.0.0.1:8083"
    }
  ],
  "type": "source"
}
```

### 2. 检查 Kafka Topic

```bash
# 查看创建的 Topic
./bin/kafka-topics.sh --bootstrap-server localhost:9092 --list | grep gaussdb-cdc

# 查看 Topic 详情
./bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode
```

### 3. 测试数据变更

在 GaussDB 中插入测试数据：

```sql
INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_addcode (
    big_id, datasource, cameratype, deviceid, platenumber, snapshottime
) VALUES (
    'test-' || gen_random_uuid()::text,
    'test',
    'test',
    'test',
    'TEST123',
    NOW()
);
```

### 4. 消费验证

```bash
# 消费 Kafka 消息
./bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode \
  --from-beginning \
  --property print.key=true
```

预期消息格式：
```json
{
  "before": null,
  "after": {
    "big_id": "xxx",
    "datasource": "test",
    "platenumber": "TEST123",
    "snapshottime": 1234567890
  },
  "op": "c",
  "ts_ms": 1234567890000,
  "source": {
    "version": "1.9.0.Final",
    "connector": "postgresql",
    "name": "gaussdb-cdc",
    "ts_ms": 1234567890000,
    "snapshot": "false",
    "db": "RuoYi",
    "sequence": "[]",
    "schema": "jl_data01",
    "table": "ods_rt_szdn_snapshot_flow_addcode",
    "txId": 1234,
    "lsn": 12345678,
    "xmin": null
  },
  "transaction": null
}
```

## Debezium 消息格式说明

### 操作类型 (op)

| 值 | 说明 | 场景 |
|----|------|------|
| `c` | create | INSERT 操作 |
| `r` | read | 快照读取 |
| `u` | update | UPDATE 操作 |
| `d` | delete | DELETE 操作 |
| `t` | truncate | TRUNCATE 操作 |

### 幂等性保证

消费者使用以下策略保证幂等性：

1. **事务级幂等**（Debezium 1.9+）：
   - 使用 `transaction.id` + `total_order` 序列号
   - 全局唯一，不重复

2. **LSN 级幂等**：
   - 使用 `source.lsn` (Log Sequence Number)
   - 数据库级别的唯一标识

3. **主键级幂等**（兜底）：
   - 使用 `big_id` + 操作类型
   - 结合 Redis 缓存实现

## 性能优化

### 1. 批量处理

消费者配置：
```properties
max.poll.records=500
fetch.max.bytes=52428800
max.poll.interval.ms=300000
```

### 2. 并发消费

```properties
listener.concurrency=3
```

### 3. 分区策略

确保 Kafka Topic 分区数与并发数匹配：
```bash
./bin/kafka-topics.sh --alter \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode \
  --partitions 3 \
  --bootstrap-server localhost:9092
```

## 运维管理

### 启动

```bash
./bin/debezium-connector.sh start
```

### 停止

```bash
./bin/debezium-connector.sh stop
```

### 重启

```bash
./bin/debezium-connector.sh restart
```

### 查看状态

```bash
./bin/debezium-connector.sh status
```

### 查看日志

```bash
./bin/debezium-connector.sh logs
```

### 删除 Connector

```bash
./bin/debezium-connector.sh delete
```

## 故障排查

### 1. Connector 启动失败

检查日志：
```bash
tail -f logs/connect.log
```

常见问题：
- Kafka 连接失败
- 数据库连接失败
- 权限不足

### 2. 消息延迟

可能原因：
- 网络延迟
- 消费者处理能力不足
- Kafka 性能瓶颈

解决方案：
- 增加消费者并发数
- 调整批量处理参数
- 优化数据库查询

### 3. 数据丢失

检查点：
- 是否启用幂等性
- 手动确认是否正确
- 死信队列是否正常

## 监控告警

### 监控指标

建议监控以下指标：
- Connector 状态
- 消费延迟
- 错误率
- 死信队列长度

### 日志关键词

监控以下日志：
- `ERROR`
- `WARN` (重试)
- `acknowledge` (确认)
- `dead letter queue` (死信)

## 卸载清理

### 1. 删除 Connector

```bash
./bin/debezium-connector.sh delete
```

### 2. 删除 Kafka Topic

```bash
./bin/kafka-topics.sh --delete \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode \
  --bootstrap-server localhost:9092
```

### 3. 清理 GaussDB 复制槽

```sql
-- 删除复制槽
SELECT pg_drop_replication_slot('debezium_slot_snapshot_flow');

-- 删除发布
DROP PUBLICATION dbz_publication_snapshot_flow;
```

## 附录

### A. 相关文件路径

```
car-monit-api/
├── debezium/
│   ├── config/
│   │   ├── connect-gaussdb-distributed.properties  # Connector 配置
│   │   └── source-connector-config.json            # REST API 配置
│   ├── sql/
│   │   └── setup-gaussdb-replication.sql           # 数据库配置脚本
│   └── bin/
│       └── debezium-connector.sh                    # 管理脚本

car-monit-backend-new/
└── ruoyi-system/src/main/java/com/ruoyi/base/kafka/consumer/
    └── DebeziumSnapshotFlowKafkaConsumer.java       # 消费者实现
```

### B. 依赖版本

- Debezium Connector PostgreSQL: 1.9.0.Final
- Kafka: 2.8.0+
- Java: 8+

### C. 相关文档

- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/1.9/connectors/postgresql.html)
- [Kafka Connect](https://kafka.apache.org/documentation/#connect)
