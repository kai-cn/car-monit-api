-- =============================================================================
-- V3 阶段一：抓拍表 snapshottime IS NULL 数据处置（备份 + 显式排除）
--
-- 背景：联调发现抓拍表有 36 行 snapshottime IS NULL。分区迁移要求时间列 NOT NULL，
--       不能静默丢弃。本脚本：
--       1) 原样备份这些行到 ods_rt_szdn_snapshot_flow_addcode_null_time_backup；
--       2) 写入 v3_migration_excluded_rows 显式标记排除（保留业务复核入口）；
--       3) 002 搬运时按排除表过滤，001 预检会输出“总数/已排除/未处理”报告。
--
-- 幂等：可重复执行；已备份/已排除的行不会重复处理。
-- 用法：psql "$PGURL" -f 000_null_time_exclusion.sql
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

-- 排除清单：所有表共用；pk 为 big_id/cid
CREATE TABLE IF NOT EXISTS jl_data01.v3_migration_excluded_rows (
    table_name   varchar(64)  NOT NULL,
    pk           varchar(100) NOT NULL,
    reason       varchar(200) NOT NULL,
    backed_up_at timestamp(6) NOT NULL DEFAULT now(),
    PRIMARY KEY (table_name, pk)
);

COMMENT ON TABLE jl_data01.v3_migration_excluded_rows IS
    'V3 分区迁移显式排除行：不删除源数据，只阻止进入影子分区表';

-- 备份表：保留原始全部列，供业务复核/清洗
DO $$
DECLARE
    v_exists   int;
    v_total    bigint;
    v_backup   bigint;
    v_excluded bigint;
BEGIN
    SELECT count(*) INTO v_exists
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = 'ods_rt_szdn_snapshot_flow_addcode_null_time_backup';

    IF v_exists = 0 THEN
        EXECUTE 'CREATE TABLE jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup '
                || 'AS SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode '
                || 'WHERE snapshottime IS NULL';
        RAISE NOTICE '[V3空值处置] 已创建备份表';
    ELSE
        EXECUTE 'INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup '
                || 'SELECT s.* FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode s '
                || 'WHERE s.snapshottime IS NULL '
                || 'AND NOT EXISTS (SELECT 1 FROM '
                || 'jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup b '
                || 'WHERE b.big_id = s.big_id)';
        RAISE NOTICE '[V3空值处置] 备份表已存在，补齐缺失行';
    END IF;

    -- 显式标记排除：不修改源表，只写排除清单
    INSERT INTO jl_data01.v3_migration_excluded_rows(table_name, pk, reason, backed_up_at)
    SELECT 'ods_rt_szdn_snapshot_flow_addcode', s.big_id,
           'snapshottime IS NULL; backed up in ods_rt_szdn_snapshot_flow_addcode_null_time_backup; requires business review',
           now()
      FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode s
     WHERE s.snapshottime IS NULL
       AND NOT EXISTS (SELECT 1 FROM jl_data01.v3_migration_excluded_rows e
                        WHERE e.table_name = 'ods_rt_szdn_snapshot_flow_addcode'
                          AND e.pk = s.big_id);

    SELECT count(*) INTO v_total
      FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode WHERE snapshottime IS NULL;
    SELECT count(*) INTO v_backup
      FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode_null_time_backup;
    SELECT count(*) INTO v_excluded
      FROM jl_data01.v3_migration_excluded_rows
     WHERE table_name = 'ods_rt_szdn_snapshot_flow_addcode';

    RAISE NOTICE '[V3空值处置报告] snapshottime NULL 总数=%, 备份行数=%, 显式排除=%, 未处理=%',
        v_total, v_backup, v_excluded, (v_total - v_excluded);
END $$;

-- 输出明细供人工复核
SELECT e.pk, e.reason, e.backed_up_at
  FROM jl_data01.v3_migration_excluded_rows e
 WHERE e.table_name = 'ods_rt_szdn_snapshot_flow_addcode'
 ORDER BY e.pk
 LIMIT 50;
