-- GaussDB/PostgreSQL 逻辑复制配置脚本
-- 用于配置 Debezium CDC 所需的复制槽和发布

-- 1. 创建复制用户（如果不存在）
-- 注意：需要 superuser 权限
-- CREATE USER debezium WITH REPLICATION ENCRYPTED PASSWORD 'debezium_password';

-- 2. 授予复制权限
-- ALTER USER debezium WITH REPLICATION;

-- 3. 修改 wal_level 为 logical（需要重启数据库）
-- 方式1: 临时生效（重启后失效）
-- SET wal_level = 'logical';

-- 方式2: 永久生效（需要修改 postgresql.conf 或 gaussdb.conf）
-- wal_level = 'logical'
-- max_replication_slots = 10
-- max_wal_senders = 10
-- wal_keep_size = 64

-- 4. 创建复制槽（Debezium 会自动创建，但也可以手动创建）
-- CREATE_REPLICATION_SLOT dbz_slot LOGICAL "pgoutput";

-- 5. 创建发布（Publication）- 用于指定要捕获的表
-- 为单个表创建发布
CREATE PUBLICATION dbz_publication_snapshot_flow FOR TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode;

-- 或为所有表创建发布（慎用）
-- CREATE PUBLICATION dbz_publication FOR ALL TABLES;

-- 6. 验证配置
-- 查看复制槽
-- SELECT * FROM pg_replication_slots;

-- 查看发布
-- SELECT * FROM pg_publication;

-- 查看发布与表的关系
-- SELECT * FROM pg_publication_tables;

-- 7. 如果表已经存在，需要添加到发布
-- ALTER PUBLICATION dbz_publication_snapshot_flow ADD TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode;

-- 8. 启用表级别的 REPLICA IDENTITY（用于 UPDATE/DELETE 捕获）
-- 方式1: 使用主键（推荐）
-- ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY USING INDEX pk_big_id;

-- 方式2: 使用全字段（会产生较大开销）
-- ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY FULL;

-- 方式3: 使用默认（主键或唯一索引）
-- ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY DEFAULT;

-- 9. 确保表有主键或唯一索引（Debezium 推荐）
-- 检查主键
-- SELECT COUNT(*) FROM information_schema.table_constraints 
-- WHERE constraint_name = 'pk_big_id' 
-- AND table_schema = 'jl_data01' 
-- AND table_name = 'ods_rt_szdn_snapshot_flow_addcode';

-- 如果没有主键，创建唯一索引
-- CREATE UNIQUE INDEX idx_unique_big_id ON jl_data01.ods_rt_szdn_snapshot_flow_addcode(big_id);

-- 10. 清理（如果需要删除）
-- DROP PUBLICATION dbz_publication_snapshot_flow;
-- SELECT pg_drop_replication_slot('debezium_slot_snapshot_flow');
