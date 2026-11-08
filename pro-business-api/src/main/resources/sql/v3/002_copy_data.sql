-- =============================================================================
-- V3 阶段一：影子分区表数据搬运（按月、幂等、可中断续跑）
--
-- 用法（每次搬运一个月）：
--   psql "postgresql://<user>:<pwd>@<host>:5432/RuoYi" \
--        -v month=2026-01 \
--        -f 002_copy_data.sql
--
-- 说明：
--   1. 只搬运 001 创建的三张 *_v3 影子表；不改动源表。
--   2. 每月一个 INSERT ... SELECT，单独事务；失败只影响当月，可重跑。
--   3. 已完成的 (table, month) 记录在 v3_migration_progress，重跑自动跳过。
--   4. 收费表搬运后会用 SQL 规则回填派生车牌列；生产最终以 Java 解析器/Flink 为准。
--   5. 如需单独搬运某张表：-v tbl=ods_lwzxsfsj_fee_records_01
-- =============================================================================

\set ON_ERROR_STOP on

SET search_path TO jl_data01, public;

-- 幂等：确保进度表存在（001 未执行时会失败，这里兜底创建）
CREATE TABLE IF NOT EXISTS jl_data01.v3_migration_progress (
    table_name    varchar(64) NOT NULL,
    month_start   date        NOT NULL,
    rows_copied   bigint      NOT NULL DEFAULT 0,
    finished_at   timestamp(6) DEFAULT now(),
    PRIMARY KEY (table_name, month_start)
);

-- -----------------------------------------------------------------------------
-- 逐月搬运函数
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_copy_month(
    p_month  date,
    p_table  text DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_tables    text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table     text;
    v_time_col  text;
    v_pk_col    text;
    v_src       text;
    v_dst       text;
    v_cols      text;
    v_count     bigint;
    v_done      bigint;
    v_month_end date;
BEGIN
    p_month := date_trunc('month', p_month)::date;
    v_month_end := (p_month + interval '1 month')::date;

    FOREACH v_table IN ARRAY v_tables LOOP
        IF p_table IS NOT NULL AND p_table <> v_table THEN
            CONTINUE;
        END IF;

        v_time_col := CASE v_table
            WHEN 'ods_rt_szdn_snapshot_flow_addcode' THEN 'snapshottime'
            WHEN 'ods_lwzxsfsj_fee_records_01'        THEN 'transtime'
            WHEN 'zdata_trail_fitting'                THEN 'extime'
        END;

        v_pk_col := CASE v_table
            WHEN 'zdata_trail_fitting' THEN 'cid'
            ELSE 'big_id'
        END;

        v_src := 'jl_data01.' || quote_ident(v_table);
        v_dst := 'jl_data01.' || quote_ident(v_table || '_v3');

        -- 影子表必须存在（用 pg_class 判断，兼容 openGauss/gsql）
        SELECT count(*) INTO v_done
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01' AND c.relname = v_table || '_v3';
        IF v_done = 0 THEN
            RAISE EXCEPTION '影子表不存在，请先执行 001_shadow_schema.sql: %', v_dst;
        END IF;

        -- 已搬运则跳过
        SELECT count(*) INTO v_done
          FROM jl_data01.v3_migration_progress
         WHERE table_name = v_table
           AND month_start = p_month;
        IF v_done > 0 THEN
            RAISE NOTICE '[V3] 跳过已完成月份: % / %', v_table, to_char(p_month, 'YYYY-MM');
            CONTINUE;
        END IF;

        -- 只取源表列（收费表影子表额外有派生列，不能被 INSERT 列表包含）
        SELECT string_agg(quote_ident(a.attname), ', ' ORDER BY a.attnum)
          INTO v_cols
          FROM pg_attribute a
         WHERE a.attrelid = v_src::regclass
           AND a.attnum > 0
           AND NOT a.attisdropped;

        -- 按月搬运（半开区间，避免边界重复）
        EXECUTE 'INSERT INTO ' || v_dst || ' (' || v_cols || ')'
                || ' SELECT ' || v_cols || ' FROM ' || v_src
                || ' WHERE ' || quote_ident(v_time_col) || ' >= ' || quote_literal(p_month::text)
                || ' AND '   || quote_ident(v_time_col) || ' < '  || quote_literal(v_month_end::text)
                || ' AND NOT EXISTS (SELECT 1 FROM jl_data01.v3_migration_excluded_rows e '
                || 'WHERE e.table_name = ' || quote_literal(v_table)
                || ' AND e.pk = ' || quote_ident(v_pk_col) || ')';
        GET DIAGNOSTICS v_count = ROW_COUNT;

        -- 说明：收费派生车牌列不再由 SQL 兜底生成（颜色码单一事实源为 MySQL 字典 +
        -- Java 解析器/Flink）；迁移只搬原始列，派生列由后续 ETL/回灌按同一解析器补齐。

        -- openGauss 3.0 不支持 ON CONFLICT，改用 UPDATE + INSERT 保证幂等
        UPDATE jl_data01.v3_migration_progress
           SET rows_copied = v_count,
               finished_at = now()
         WHERE table_name = v_table
           AND month_start = p_month;
        IF NOT FOUND THEN
            INSERT INTO jl_data01.v3_migration_progress(table_name, month_start, rows_copied, finished_at)
            VALUES (v_table, p_month, v_count, now());
        END IF;

        RAISE NOTICE '[V3] 已搬运 % / % : % 行', v_table, to_char(p_month, 'YYYY-MM'), v_count;
    END LOOP;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 执行一个月（psql -v month=YYYY-MM）；未传变量时给出提示并退出
-- -----------------------------------------------------------------------------
\if :{?month}
\else
    \echo '请通过 -v month=YYYY-MM 指定要搬运的月份，例如：'
    \echo '  psql "$PGURL" -v month=2026-01 -f 002_copy_data.sql'
    \quit
\endif

-- 可选：-v tbl=xxx 只搬一张表
\if :{?tbl}
SELECT jl_data01.v3_copy_month(to_date(:'month', 'YYYY-MM')::date, :'tbl');
\else
SELECT jl_data01.v3_copy_month(to_date(:'month', 'YYYY-MM')::date, NULL);
\endif

-- 校验当月搬运结果（源表可能仍在写入，仅作提示）
SELECT p.table_name,
       p.month_start,
       p.rows_copied,
       p.finished_at
  FROM jl_data01.v3_migration_progress p
 WHERE p.month_start = to_date(:'month', 'YYYY-MM')::date
 ORDER BY p.table_name;

\echo '提示：逐月执行本脚本完成全部历史月份后，再执行 003_cutover.sql。'
