# Debezium 只读 CDC 架构设计

## 核心原则

✅ **只读原则**：仅读取甲方 GaussDB，不做任何写入操作
✅ **零侵入**：不创建任何中间表、触发器或存储过程
✅ **纯 CDC**：基于 PostgreSQL/GaussDB 逻辑复制实现
✅ **幂等性**：基于 Debezium LSN/事务ID 保证 Exactly-Once

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           甲方 GaussDB 数据库 (只读，零侵入)                                  │
│           jl_data01.ods_rt_szdn_snapshot_flow_addcode                         │
│           (300G 数据, 50W 日增)                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 逻辑复制 (Logical Replication) - 只读
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│         Debezium Connector (纯读取模式)                                       │
│         ┌──────────────────────────────────────────────────────────┐        │
│         │ SMT (Single Message Transform) 消息转换                  │        │
│         │ - 过滤冗余字段                                           │        │
│         │ - 扁平化消息                                             │        │
│         │ - 简化格式                                               │        │
│         └──────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│         Kafka Topic                                                          │
│         gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow                      │
│         (分区数: 3, 副本数: 1)                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│         car-monit-backend-new (消费者)                                       │
│         ┌──────────────────────────────────────────────────────────┐        │
│         │ 幂等性处理 (Redis + LSN/事务ID)                           │        │
│         │ ┌──────────────────────────────────────────────────┐   │        │
│         │ │ 1. 基于 LSN 幂等检查                              │   │        │
│         │ │ 2. 解析消息 -> 实体映射                           │   │        │
│         │ │ 3. 批量写入 MySQL 分表 (按月)                     │   │        │
│         │ │ 4. 批量写入 Elasticsearch                        │   │        │
│         │ │ 5. 手动确认偏移量                                 │   │        │
│         │ └──────────────────────────────────────────────────┘   │        │
│         └──────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
           ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
           │  MySQL 分表   │  │ Elasticsearch │  │  死信队列     │
           │ (按月分表)    │  │ (Bulk API)    │  │ (失败重试)    │
           └───────────────┘  └───────────────┘  └───────────────┘
```

## 方案优势

### 1. 零侵入甲方数据库

| 操作 | 是否需要 | 说明 |
|-----|---------|------|
| 创建中间表 | ❌ 否 | 不需要 |
| 创建触发器 | ❌ 否 | 不需要 |
| 写入操作 | ❌ 否 | 不需要 |
| 修改现有表 | ❌ 否 | 不需要 |
| 配置逻辑复制 | ✅ 是 | 标准 PostgreSQL/GaussDB 功能，只是开启 |

### 2. 性能优势

- **低负载**：仅读取 WAL 日志，不产生额外查询
- **实时性**：秒级延迟，无需定时轮询
- **完整数据**：捕获 INSERT/UPDATE/DELETE 所有变更
- **顺序保证**：同一记录的变更按顺序处理

## 消息格式设计

### 原始 Debezium 格式（经过 SMT 简化）

```json
{
  "big_id": "xxx",
  "datasource": "test",
  "platenumber": "京A12345",
  "cameratype": "camera-001",
  "deviceid": "device-001",
  "gantrycode": "gantry-001",
  "gantryname": "门架1号",
  "roadcode": "road-001",
  "roadname": "北京-上海",
  "sectioncode": "section-001",
  "sectionname": "路段1",
  "tollcode": "toll-001",
  "tollname": "收费站1",
  "orgcode": "org-001",
  "orgname": "机构1",
  "direction": 1,
  "hexcode": "xxx",
  "pileno": "xxx",
  "lon": 116.40,
  "lat": 39.90,
  "deviceip": "192.168.1.100",
  "siteid": 1,
  "laneid": 1,
  "snapshottimeunix": 1716700800000,
  "snapshottime": "2024-05-26 10:00:00",
  "receivedtimeunix": 1716700800000,
  "receivedtime": "2024-05-26 10:00:00",
  "platenumber": "京A12345",
  "platecolor": "blue",
  "platecolorcode": 1,
  "platetype": "small",
  "platetypecode": 1,
  "plateconfidence": 95,
  "carbrand": "BMW",
  "carcolor": "black",
  "carcolorcode": 2,
  "cartype": "sedan",
  "cartypecode": 1,
  "cardirection": "north",
  "snappicturepath": "/path/to/image.jpg",
  "loadtime": "2024-05-26 10:00:00",
  "gradelevel": 1,
  "datauuid": "xxx-yyy-zzz",
  "reserve3": "xxx",
  
  "__op": "c",
  "__ts_ms": 1716700800000,
  "__lsn": "12345678/12345678"
}
```

### Kafka Header 元数据

```json
{
  "debezium-operation": "c",
  "debezium-source-table": "jl_data01.ods_rt_szdn_snapshot_flow_addcode",
  "debezium-lsn": "12345678/12345678",
  "debezium-txid": "1234",
  "debezium-ts-ms": "1716700800000"
}
```

## 幂等性实现

### 策略一：基于 LSN（推荐）

```java
// 幂等键 = lsn + op
String lsn = debeziumMessage.getSource().getLsn();
String op = debeziumMessage.getOp();
String idempotentKey = "lsn:" + lsn + ":op:" + op;

if (redisUtil.exists(idempotentKey)) {
    // 已处理，跳过
    return;
}
// 处理逻辑...
redisUtil.setEx(idempotentKey, 1, TimeUnit.DAYS);
```

### 策略二：基于事务 ID

```java
// 幂等键 = tx_id + sequence
String txId = debeziumMessage.getSource().getTxId();
String idempotentKey = "tx:" + txId;
```

## 配置示例

### SMT 配置

```properties
transforms=unwrap,addSourceInfo,flatten,filter
transforms.unwrap.type=io.debezium.transforms.ExtractNewRecordState
transforms.unwrap.drop.tombstones=true
transforms.unwrap.delete.handling.mode=drop
transforms.unwrap.add.source.fields=lsn,txId
transforms.unwrap.operation.header=true

transforms.addSourceInfo.type=org.apache.kafka.connect.transforms.InsertHeader
transforms.addSourceInfo.headers=__lsn:source.lsn,__ts_ms:source.ts_ms,__op:op

transforms.flatten.type=org.apache.kafka.connect.transforms.Flatten
transforms.flatten.delimiter=_

transforms.filter.type=org.apache.kafka.connect.transforms.Filter
```
