# migrations

本目录收录 Java 侧仓库中**实际存在的** SQL：

| 文件 | 说明 |
|---|---|
| `001_kafka_message_record.pg.sql` | `jl_data01.kafka_message_record`（由 MySQL 方言机械转换） |
| `002_index_optimization.sql` | 三张大表的 B-tree/GIN/覆盖索引 |
| `003_progressive_architecture_indexes.sql` | 渐进式查询索引（含 CREATE INDEX CONCURRENTLY） |
| `004_partition_scheme.sql` | 大表分区方案 |

其余 19 张业务表是既有 GaussDB 表，Java 仓库中**没有它们的 DDL**（表结构以线上为准）。
实体字段与表/列名的一一对照见 `docs/MIGRATION-BASELINE.md` 第 3.2 节。
