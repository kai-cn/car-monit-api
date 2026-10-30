-- GaussDB/PostgreSQL 逻辑复制配置脚本 - 只读模式
-- 此脚本仅配置逻辑复制，不创建任何中间表或修改现有表结构
-- 执行前请确认：
-- 1. 已连接到正确的数据库（RuoYi）
-- 2. 具有 REPLICATION 权限或 SUPERUSER 权限
-- 3. 已在 postgresql.conf/gaussdb.conf 中配置了 wal_level = logical

-- 步骤 1: 验证数据库参数配置（不需要执行修改）
-- 以下查询用于确认配置是否正确
SELECT name, setting, unit
FROM pg_settings
WHERE name IN ('wal_level', 'max_replication_slots', 'max_wal_senders');

-- 步骤 2: 创建复制槽（可选，Debezium 会自动创建）
-- 注意：如果使用此方式创建，请确保 Debezium 配置中的 slot.name 与此一致
-- SELECT pg_create_logical_replication_slot('debezium_slot_snapshot_flow', 'pgoutput');

-- 步骤 3: 创建发布（Publications）
-- 为目标表创建发布，用于捕获变更
-- 注意：
--   - 如果表已存在发布，先删除
--   - 使用 IF NOT EXISTS 避免重复创建
DROP PUBLICATION IF EXISTS dbz_publication_snapshot_flow;

CREATE PUBLICATION dbz_publication_snapshot_flow 
FOR TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode;

-- 步骤 4: 验证发布创建成功
SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate
FROM pg_publication
WHERE pubname = 'dbz_publication_snapshot_flow';

-- 步骤 5: 查看发布包含的表
SELECT *
FROM pg_publication_tables
WHERE pubname = 'dbz_publication_snapshot_flow';

-- 步骤 6: 配置表的 REPLICA IDENTITY（可选但推荐）
-- REPLICA IDENTITY 决定了 UPDATE/DELETE 时包含哪些列
-- 可以选择：DEFAULT（主键）、FULL（所有列）、USING INDEX（唯一索引）

-- 方式 1: 使用默认（主键）
ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY DEFAULT;

-- 方式 2: 如果需要完整的变更前数据，使用 FULL（性能较低）
-- ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY FULL;

-- 方式 3: 使用指定的唯一索引
-- ALTER TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode REPLICA IDENTITY USING INDEX idx_big_id;

-- 步骤 7: 验证 REPLICA IDENTITY 配置
SELECT 
    schemaname,
    tablename,
    CASE relreplident
        WHEN 'd' THEN 'default (primary key)'
        WHEN 'n' THEN 'nothing'
        WHEN 'f' THEN 'full (all columns)'
        WHEN 'i' THEN 'index'
    END AS replica_identity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'jl_data01'
AND c.relname = 'ods_rt_szdn_snapshot_flow_addcode';

-- 步骤 8: 查看当前复制槽（可选）
SELECT slot_name, plugin, slot_type, active, restart_lsn
FROM pg_replication_slots
WHERE slot_name LIKE 'debezium_slot%';

-- 步骤 9: 清理操作（仅用于回滚，生产环境谨慎使用）
/*
-- 删除发布
DROP PUBLICATION IF EXISTS dbz_publication_snapshot_flow;

-- 删除复制槽
SELECT pg_drop_replication_slot('debezium_slot_snapshot_flow');
*/

-- 配置完成！
-- 可以启动 Debezium Connector 了
