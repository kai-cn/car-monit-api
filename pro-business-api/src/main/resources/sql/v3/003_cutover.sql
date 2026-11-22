-- =============================================================================
-- V3 阶段一：影子分区表切换（窗口内执行，可回滚）
--
-- 前置条件：
--   1. 001_shadow_schema.sql 已执行；
--   2. 002_copy_data.sql 已覆盖源表所有历史月份（进度表有记录）；
--   3. 已完成行数抽检/备份；
--   4. 业务已进入停写窗口（本脚本执行期间源表不应有写入）。
--
-- 用法：
--   psql "$PGURL" -v confirm=YES -f 003_cutover.sql
--
-- 切换动作（单事务，全部成功或全部回滚）：
--   src            -> src_legacy_<ts>
--   src_v3         -> src
--
-- 回滚：执行 003_cutover_rollback.sql
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

\if :{?confirm}
\else
    \echo '危险操作：请先确认已完成备份与停写窗口，再使用 -v confirm=YES 执行。'
    \quit
\endif

DO $$
DECLARE
    v_ts       text := to_char(now(), 'YYYYMMDD_HH24MISS');
    v_tables   text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table    text;
    v_src      text;
    v_dst      text;
    v_legacy   text;
    v_exists   int;
    v_progress bigint;
    v_shadow   bigint;
BEGIN
    IF :'confirm' <> 'YES' THEN
        RAISE EXCEPTION 'confirm 参数必须为 YES';
    END IF;

    FOREACH v_table IN ARRAY v_tables LOOP
        v_src    := v_table;
        v_dst    := v_table || '_v3';
        v_legacy := v_table || '_legacy_' || v_ts;

        -- 影子表存在性
        SELECT count(*) INTO v_exists
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01' AND c.relname = v_dst;
        IF v_exists = 0 THEN
            RAISE EXCEPTION '影子表不存在，无法切换: %', v_dst;
        END IF;

        -- 迁移进度必须存在，防止未搬运就切换
        SELECT count(*) INTO v_progress
          FROM jl_data01.v3_migration_progress
         WHERE table_name = v_table;
        IF v_progress = 0 THEN
            RAISE EXCEPTION '表 % 没有任何迁移进度记录，请先执行 002_copy_data.sql', v_table;
        END IF;

        -- 影子表行数估算（用 reltuples，避免切换窗口内全表 count）
        SELECT greatest(coalesce(c.reltuples, 0), 0)::bigint INTO v_shadow
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01' AND c.relname = v_dst;
        RAISE NOTICE '[V3] % : 影子表估算 % 行, 进度月数 %', v_table, v_shadow, v_progress;

        -- 原子切换
        EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_src)
                || ' RENAME TO ' || quote_ident(v_legacy);
        EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_dst)
                || ' RENAME TO ' || quote_ident(v_src);

        RAISE NOTICE '[V3] 已切换: % -> %（原表保留为 %）', v_dst, v_src, v_legacy;
    END LOOP;

    RAISE NOTICE '============================================================';
    RAISE NOTICE '切换完成。请立即验证：';
    RAISE NOTICE '  SELECT count(*) FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode;';
    RAISE NOTICE '  SELECT count(*) FROM jl_data01.ods_lwzxsfsj_fee_records_01;';
    RAISE NOTICE '  SELECT count(*) FROM jl_data01.zdata_trail_fitting;';
    RAISE NOTICE '确认无误后再恢复业务写入；如需回滚执行 003_cutover_rollback.sql。';
    RAISE NOTICE '============================================================';
END $$;
