# Debezium 只读 CDC 方案 - 完整部署指南

## 📋 目录

1. [方案概述](#1-方案概述)
2. [架构对比](#2-架构对比)
3. [部署前准备](#3-部署前准备)
4. [GaussDB 配置](#4-gaussdb-配置)
5. [Kafka Connect 配置](#5-kafka-connect-配置)
6. [消费者部署](#6-消费者部署)
7. [验证测试](#7-验证测试)
8. [运维监控](#8-运维监控)

---

## 1. 方案概述

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| ✅ **零侵入** | 不修改甲方数据库，仅通过逻辑复制监听变更 |
| ✅ **只读模式** | 不需要创建任何中间表、触发器或写入操作 |
| ✅ **幂等性保证** | 基于 LSN/事务ID + Redis 实现 Exactly-Once |
| ✅ **高可靠性** | 死信队列 + 本地重试机制 |

### 1.2 核心组件

| 组件 | 职责 | 说明 |
|------|------|------|
| GaussDB | 源数据库 | 300G 数据，50W 日增 |
| Debezium Connector | CDC 监听 | 从 WAL 日志读取变更，发送到 Kafka |
| Kafka | 消息队列 | 分区数: 3，副本数: 1 |
| DebeziumReadonlyKafkaConsumer | 消费者 | 批量消费，写入 MySQL 分表和 ES |
| MySQL | 分表存储 | 按月分表 |
| Elasticsearch | 全文检索 | Bulk API 批量写入 |

---

## 2. 架构对比

### 2.1 新旧方案对比

| 维度 | 原有轮询方案 | Debezium 只读方案 |
|-----|------------|-----------------|
| **侵入性** | ❌ 需写入中间表 | ✅ 零侵入，仅读 WAL |
| **实时性** | ❌ 准实时（分钟级） | ✅ 实时（秒级） |
| **源库压力** | ❌ 高（频繁查询） | ✅ 低（仅读日志） |
| **数据完整性** | ⚠️ 可能漏 | ✅ 完整捕获 |
| **UPDATE/DELETE** | ❌ 不支持 | ✅ 完整支持 |
| **事务一致性** | ❌ 无 | ✅ 支持事务边界 |
| **幂等性** | ⚠️ 需手动实现 | ✅ 内置支持 |
| **部署复杂度** | ⚠️ 简单 | ⚠️ 中等 |

### 2.2 数据流对比

#### 旧方案

```
GaussDB ←─(轮询查询)── car-monit-api (生产者)
                              │
                              ├─写入 kafka_message_record 表
                              │
                              └─发送 Kafka → car-monit-backend-new → MySQL/ES
```

#### 新方案（推荐）

```
GaussDB (只读) ──(逻辑复制/WAL)── Debezium Connector
                                               │
                                               └─发送 Kafka → DebeziumReadonlyKafkaConsumer
                                                              │
                                                              ├─写入 MySQL 分表
                                                              └─写入 Elasticsearch
```

---

## 3. 部署前准备

### 3.1 环境要求

| 组件 | 版本要求 |
|------|---------|
| Java | 8+ |
| Kafka | 2.8+ |
| Kafka Connect | 与 Kafka 同版本 |
| Debezium PostgreSQL Connector | 1.9.0.Final |
| GaussDB/PostgreSQL | 10+ |
| 内存 | 2GB+ |

### 3.2 下载依赖

```powershell
# 下载 Kafka
Invoke-WebRequest -Uri "https://archive.apache.org/dist/kafka/2.8.0/kafka_2.13-2.8.0.tgz" -OutFile "kafka.tgz"

# 下载 Debezium PostgreSQL Connector
Invoke-WebRequest -Uri "https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgresql/1.9.0.Final/debezium-connector-postgres-1.9.0.Final-plugin.tar.gz" -OutFile "debezium.tgz"

# 解压（建议使用 7-Zip 或 tar）
tar -xzf kafka.tgz
tar -xzf debezium.tgz
```

### 3.3 目录结构

```
debezium/
├── config/
│   ├── connect-gaussdb-readonly.properties    # Debezium Connector 配置
│   └── source-connector-config.json           # REST API 配置
├── sql/
│   └── setup-gaussdb-readonly.sql             # GaussDB 配置脚本
├── bin/
│   ├── debezium-connector.sh                  # Linux 管理脚本
│   └── debezium-connector.ps1                 # Windows 管理脚本
└── README_READONLY.md                         # 详细文档
```

---

## 4. GaussDB 配置

### 4.1 验证数据库参数

首先验证 GaussDB 参数配置是否正确：

```sql
-- 检查关键参数
SELECT name, setting, unit
FROM pg_settings
WHERE name IN (
    'wal_level',
    'max_replication_slots',
    'max_wal_senders',
    'wal_keep_size'
);
```

预期结果：
- `wal_level` 应为 `logical`
- `max_replication_slots` 建议 ≥ 10
- `max_wal_senders` 建议 ≥ 10

### 4.2 修改配置（如果需要）

如果 `wal_level` 不是 `logical`，需要修改 `gaussdb.conf`：

```ini
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10
```

**⚠️ 注意：修改 `gaussdb.conf` 需要重启数据库！**

### 4.3 执行配置脚本

连接 GaussDB 并执行脚本：

```sql
-- 使用 psql 或工具连接
psql -h 192.168.56.10 -p 5432 -U gaussdb -d RuoYi -f debezium/sql/setup-gaussdb-readonly.sql
```

脚本执行内容：
1. ✅ 创建发布 `dbz_publication_snapshot_flow`
2. ✅ 配置 `REPLICA IDENTITY`
3. ✅ 验证配置

---

## 5. Kafka Connect 配置

### 5.1 配置 Kafka Connect

编辑 `kafka_2.13-2.8.0/config/connect-distributed.properties`：

```properties
bootstrap.servers=127.0.0.1:9092

group.id=debezium-connect-cluster

key.converter=org.apache.kafka.connect.json.JsonConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
key.converter.schemas.enable=false
value.converter.schemas.enable=false

offset.storage.topic=debezium-connect-offsets
offset.storage.replication.factor=1
offset.storage.partitions=3

config.storage.topic=debezium-connect-configs
config.storage.replication.factor=1

status.storage.topic=debezium-connect-status
status.storage.replication.factor=1
status.storage.partitions=3

offset.flush.interval.ms=10000

# 重要：指定 Debezium 插件路径
plugin.path=/path/to/debezium-connector-postgres/
```

### 5.2 配置 Debezium Connector

使用 [connect-gaussdb-readonly.properties](file:///D:/work/IdeaProjects/car-monit-api/debezium/config/connect-gaussdb-readonly.properties) 中的配置，或使用 Windows 管理脚本：

#### Windows 环境

```powershell
# 进入脚本目录
cd D:\work\IdeaProjects\car-monit-api\debezium\bin

# 执行管理脚本
.\debezium-connector.ps1
```

选择菜单 1：启动 Kafka Connect 并注册 Connector

#### Linux 环境

```bash
# 1. 启动 Kafka Connect
cd /path/to/kafka_2.13-2.8.0
nohup ./bin/connect-distributed.sh ./config/connect-distributed.properties > logs/connect.log 2>&1 &

# 2. 等待 30 秒后注册 Connector
cd D:/work/IdeaProjects/car-monit-api/debezium
curl -X POST -H "Content-Type: application/json" \
  --data @config/source-connector-config.json \
  http://localhost:8083/connectors
```

### 5.3 验证 Connector 状态

```powershell
# 查看状态
curl http://localhost:8083/connectors/gaussdb-snapshot-flow-connector/status
```

预期输出：
```json
{
  "name": "gaussdb-snapshot-flow-connector",
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

---

## 6. 消费者部署

### 6.1 使用新的消费者

项目已包含 [DebeziumReadonlyKafkaConsumer.java](file:///D:/work/IdeaProjects/car-monit-backend-new/ruoyi-system/src/main/java/com/ruoyi/base/kafka/consumer/DebeziumReadonlyKafkaConsumer.java)，无需额外修改。

**特性：**
- ✅ 零侵入，不依赖中间表
- ✅ 基于 LSN/事务ID 的幂等性
- ✅ 批量处理
- ✅ 手动确认偏移量
- ✅ 死信队列（可选）

### 6.2 配置文件

确保 `application.yml` 中配置正确的 Topic：

```yaml
kafka:
  topic:
    snapshot-flow: gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode
    snapshot-flow-dlq: gaussdb-cdc-deadletterqueue
```

---

## 7. 验证测试

### 7.1 查看创建的 Topic

```powershell
# Windows
kafka-topics.bat --bootstrap-server localhost:9092 --list

# Linux
./bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

预期看到：
- `gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode`
- `debezium-connect-offsets`
- `debezium-connect-configs`
- `debezium-connect-status`

### 7.2 执行测试变更

在 GaussDB 中插入测试数据：

```sql
INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_addcode (
    big_id, datasource, cameratype, deviceid, platenumber, snapshottime
) VALUES (
    'test-' || gen_random_uuid()::text,
    'test-source',
    'test-camera',
    'test-device',
    'TEST-123',
    NOW()
);
```

### 7.3 消费验证

```powershell
# Windows
kafka-console-consumer.bat --bootstrap-server localhost:9092 \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode \
  --from-beginning --property print.key=true

# Linux
./bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode \
  --from-beginning --property print.key=true
```

预期看到数据变更消息。

---

## 8. 运维监控

### 8.1 监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| Connector 状态 | RUNNING | 非 RUNNING 告警 |
| 消费延迟 | 最新 LSN 与消费 LSN 差 | > 100000 告警 |
| 失败率 | 失败记录数/总记录数 | > 5% 告警 |
| 死信队列长度 | 死信队列记录数 | > 100 告警 |
| 幂等重复数 | 重复处理记录数 | 仅供参考 |

### 8.2 消费者统计接口

```java
// 获取统计信息
DebeziumReadonlyKafkaConsumer consumer = ...;
Map<String, Integer> stats = consumer.getConsumerStats();

/*
返回值：
{
  "successCount": 1000,   // 成功数
  "failCount": 5,         // 失败数
  "retryCount": 10,       // 重试数
  "duplicateCount": 3     // 重复数（幂等跳过）
}
*/
```

### 8.3 常用操作

#### 查看 Connector 状态

```powershell
curl http://localhost:8083/connectors/gaussdb-snapshot-flow-connector/status
```

#### 暂停/恢复 Connector

```powershell
# 暂停
curl -X PUT http://localhost:8083/connectors/gaussdb-snapshot-flow-connector/pause

# 恢复
curl -X PUT http://localhost:8083/connectors/gaussdb-snapshot-flow-connector/resume
```

#### 查看日志

```powershell
# Linux
tail -f /path/to/kafka/logs/connect.log

# Windows - 使用管理脚本的菜单 6
.\debezium-connector.ps1
```

#### 删除 Connector（慎用）

```powershell
curl -X DELETE http://localhost:8083/connectors/gaussdb-snapshot-flow-connector
```

---

## 9. 回滚方案

如果需要回滚到旧方案：

```powershell
# 1. 删除 Debezium Connector
curl -X DELETE http://localhost:8083/connectors/gaussdb-snapshot-flow-connector

# 2. 停止 Kafka Connect（如果不需要）

# 3. 删除 GaussDB 配置（可选）
psql -h 192.168.56.10 -p 5432 -U gaussdb -d RuoYi -c "DROP PUBLICATION IF EXISTS dbz_publication_snapshot_flow;"
psql -h 192.168.56.10 -p 5432 -U gaussdb -d RuoYi -c "SELECT pg_drop_replication_slot('debezium_slot_snapshot_flow');"

# 4. 切换到旧消费者
```

---

## 10. 常见问题

### Q1: Debezium 连接失败？

**A:** 检查：
- GaussDB 连接参数是否正确
- 防火墙是否开放 5432 端口
- 用户是否有 REPLICATION 权限

### Q2: 消费延迟高？

**A:** 优化：
- 增加消费者并发数（`listener.concurrency`）
- 增加 `max.poll.records`
- 优化批量处理

### Q3: 出现重复数据？

**A:** 检查：
- Redis 是否正常
- 幂等键过期时间是否合理
- 消费者重启后是否正确处理

---

## 附录

### A. 文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 配置文件 | `debezium/config/connect-gaussdb-readonly.properties` | Debezium Connector 配置 |
| API 配置 | `debezium/config/source-connector-config.json` | REST API 配置 |
| SQL 脚本 | `debezium/sql/setup-gaussdb-readonly.sql` | GaussDB 配置脚本 |
| Windows 脚本 | `debezium/bin/debezium-connector.ps1` | Windows 管理工具 |
| Linux 脚本 | `debezium/bin/debezium-connector.sh` | Linux 管理工具 |
| 消费者 | `ruoyi-system/.../DebeziumReadonlyKafkaConsumer.java` | 新消费者实现 |
| 详细文档 | `debezium/README_READONLY.md` | 架构设计文档 |

### B. 相关文档

- [Debezium PostgreSQL Connector 文档](https://debezium.io/documentation/reference/1.9/connectors/postgresql.html)
- [Kafka Connect 文档](https://kafka.apache.org/documentation/#connect)

---

**方案部署完成！**
