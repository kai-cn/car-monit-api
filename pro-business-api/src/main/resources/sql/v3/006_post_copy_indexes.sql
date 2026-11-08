-- =============================================================================
-- V3 阶段一：搬运完成后创建分区索引（在 003_cutover.sql 之前执行）
--
-- 为什么单独一个脚本：
--   8 亿行搬运期间持续维护索引会显著拖慢导入；影子表在搬运阶段不承载查询，
--   因此先搬数据，再统一建 (time DESC, pk)、组织维度、车牌复合索引。
--
-- 幂等：索引已存在则跳过；父表不支持分区索引时自动退化为逐分区建索引。
-- 用法：
--   psql "$PGURL" -f 006_post_copy_indexes.sql
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

-- -----------------------------------------------------------------------------
-- 通用索引创建：openGauss 3.0 不支持 CREATE INDEX IF NOT EXISTS；
-- 分区表索引必须显式声明 LOCAL（否则与主键全局索引在分区键上冲突：
-- "Global and local partition index should not be on same column"）。
-- 这里先用 pg_class 判断索引是否已存在，幂等创建。
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_create_index_any(
    p_table   text,
    p_index   text,
    p_columns text
) RETURNS void AS $$
DECLARE
    v_exists int;
BEGIN
    SELECT count(*) INTO v_exists
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_index
       AND c.relkind IN ('i', 'I');
    IF v_exists > 0 THEN
        RAISE NOTICE '[V3] 索引已存在，跳过: %.%', p_table, p_index;
        RETURN;
    END IF;

    EXECUTE 'CREATE INDEX ' || quote_ident(p_index)
            || ' ON jl_data01.' || quote_ident(p_table)
            || ' (' || p_columns || ') LOCAL';
    RAISE NOTICE '[V3] 索引已创建（LOCAL）: %.%', p_table, p_index;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. 抓拍流水
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_index_any(
    'ods_rt_szdn_snapshot_flow_addcode_v3',
    'idx_v3_ods_rt_szdn_snapshot_flow_addcode_time',
    'snapshottime DESC, big_id');

SELECT jl_data01.v3_create_index_any(
    'ods_rt_szdn_snapshot_flow_addcode_v3',
    'idx_v3_ods_rt_szdn_snapshot_flow_addcode_org_time',
    'orgcode, snapshottime DESC');

SELECT jl_data01.v3_create_index_any(
    'ods_rt_szdn_snapshot_flow_addcode_v3',
    'idx_v3_ods_rt_szdn_snapshot_flow_addcode_plate_time',
    'platenumber, snapshottime DESC');

-- -----------------------------------------------------------------------------
-- 2. 收费流水（派生车牌列 + 颜色）
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_index_any(
    'ods_lwzxsfsj_fee_records_01_v3',
    'idx_v3_ods_lwzxsfsj_fee_records_01_time',
    'transtime DESC, big_id');

-- 收费表无 orgcode 列（维度经 ods_szdn_gantry 关联），组织维度索引改用 gantryid
SELECT jl_data01.v3_create_index_any(
    'ods_lwzxsfsj_fee_records_01_v3',
    'idx_v3_ods_lwzxsfsj_fee_records_01_gantry_time',
    'gantryid, transtime DESC');

SELECT jl_data01.v3_create_index_any(
    'ods_lwzxsfsj_fee_records_01_v3',
    'idx_v3_ods_lwzxsfsj_fee_records_01_plate_time',
    'plate_core, plate_color_code, transtime DESC');

-- -----------------------------------------------------------------------------
-- 3. 轨迹表
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_index_any(
    'zdata_trail_fitting_v3',
    'idx_v3_zdata_trail_fitting_time',
    'extime DESC, cid');

SELECT jl_data01.v3_create_index_any(
    'zdata_trail_fitting_v3',
    'idx_v3_zdata_trail_fitting_plate_time',
    'envehicleid, extime DESC');

-- -----------------------------------------------------------------------------
-- 4. 更新统计信息（让切换后计划器立即使用新索引）
-- -----------------------------------------------------------------------------
ANALYZE jl_data01.ods_rt_szdn_snapshot_flow_addcode_v3;
ANALYZE jl_data01.ods_lwzxsfsj_fee_records_01_v3;
ANALYZE jl_data01.zdata_trail_fitting_v3;

DO $$
BEGIN
    RAISE NOTICE '索引创建与 ANALYZE 完成。下一步执行 003_cutover.sql。';
END $$;
