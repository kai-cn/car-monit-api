-- =============================================================================
-- V3 阶段一：切换回滚
--
-- 场景 A：已执行 003_cutover.sql
--   src（当前=分区表）  -> src_v3_rollback_<ts>
--   src_legacy_<旧ts>   -> src
--
-- 场景 B：尚未切换，仅想放弃影子表
--   删除 src_v3（仅影子表），清理对应迁移进度；不影响在用源表。
--
-- 用法：
--   psql "$PGURL" -v confirm=YES -f 003_cutover_rollback.sql
--
-- 注意：场景 B 会 DROP 影子分区表；源表与数据不受影响。
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

\if :{?confirm}
\else
    \echo '请使用 -v confirm=YES 执行回滚脚本。'
    \quit
\endif

DO $$
DECLARE
    v_ts        text := to_char(now(), 'YYYYMMDD_HH24MISS');
    v_tables    text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table     text;
    v_src       text;
    v_dst       text;
    v_legacy    text;
    v_cur       text;
    v_exists    int;
    v_dropped   int := 0;
BEGIN
    IF :'confirm' <> 'YES' THEN
        RAISE EXCEPTION 'confirm 参数必须为 YES';
    END IF;

    FOREACH v_table IN ARRAY v_tables LOOP
        v_src := v_table;
        v_dst := v_table || '_v3';

        -- 查找最近一次 legacy 备份（按名称倒序）
        SELECT c.relname INTO v_cur
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01'
           AND c.relname LIKE v_table || '_legacy_%'
         ORDER BY c.relname DESC
         LIMIT 1;

        IF v_cur IS NOT NULL THEN
            -- 场景 A：切回旧表
            v_legacy := v_table || '_v3_rollback_' || v_ts;
            EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_src)
                    || ' RENAME TO ' || quote_ident(v_legacy);
            EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_cur)
                    || ' RENAME TO ' || quote_ident(v_src);
            RAISE NOTICE '[V3] 已回滚: % -> %（分区表保留为 %）', v_cur, v_src, v_legacy;
        ELSE
            -- 场景 B：删除影子表
            SELECT count(*) INTO v_exists
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'jl_data01' AND c.relname = v_dst;
            IF v_exists > 0 THEN
                EXECUTE 'DROP TABLE jl_data01.' || quote_ident(v_dst) || ' CASCADE';
                DELETE FROM jl_data01.v3_migration_progress WHERE table_name = v_table;
                v_dropped := v_dropped + 1;
                RAISE NOTICE '[V3] 已删除影子表: %', v_dst;
            ELSE
                RAISE NOTICE '[V3] 无需回滚（无 legacy、无影子表）: %', v_table;
            END IF;
        END IF;
    END LOOP;

    RAISE NOTICE '回滚脚本执行完成，删除影子表数量: %', v_dropped;
END $$;
