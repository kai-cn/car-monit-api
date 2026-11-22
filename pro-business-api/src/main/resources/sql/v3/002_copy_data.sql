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
-- 强制重搬前置：p_force=true 时清空影子表该月份（用于源表修正后重算）
-- 仅影响 *_v3 影子表，不触碰源表；p_force=false 时直接返回。
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_clear_month_if(
    p_month date,
    p_table text,
    p_force boolean
) RETURNS void AS $$
DECLARE
    v_tables   text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table    text;
    v_time_col text;
    v_dst      text;
    v_count    bigint;
    v_month_end date;
BEGIN
    IF NOT p_force THEN
        RETURN;
    END IF;
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
        v_dst := 'jl_data01.' || quote_ident(v_table || '_v3');
        EXECUTE 'DELETE FROM ' || v_dst
                || ' WHERE ' || quote_ident(v_time_col) || ' >= ' || quote_literal(p_month::text)
                || ' AND '   || quote_ident(v_time_col) || ' < '  || quote_literal(v_month_end::text);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE '[V3] 强制重搬已清空 % / % : % 行', v_table, to_char(p_month, 'YYYY-MM'), v_count;
    END LOOP;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 按任意时间窗搬运算（P1-9：切换前 final delta）

--
-- 与 v3_copy_month 的区别：
--   1. 时间窗可精确到秒，用于切换前把“上次整月搬运之后新增的行”补齐；
--   2. 目标表按主键去重（NOT EXISTS），重复执行不会产生重复行；
--   3. p_force=true 时先删除目标表该时间窗再重搬（用于源表修正后重算当前月）。
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_copy_range(
    p_start timestamp,
    p_end   timestamp,
    p_table text    DEFAULT NULL,
    p_force boolean DEFAULT false
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
    v_exists    int;
BEGIN
    IF p_start IS NULL OR p_end IS NULL OR p_start >= p_end THEN
        RAISE EXCEPTION '时间窗非法: start=% end=%', p_start, p_end;
    END IF;

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

        SELECT count(*) INTO v_exists
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01' AND c.relname = v_table || '_v3';
        IF v_exists = 0 THEN
            RAISE EXCEPTION '影子表不存在，请先执行 001_shadow_schema.sql: %', v_dst;
        END IF;

        SELECT string_agg(quote_ident(a.attname), ', ' ORDER BY a.attnum)
          INTO v_cols
          FROM pg_attribute a
         WHERE a.attrelid = v_src::regclass
           AND a.attnum > 0
           AND NOT a.attisdropped;

        IF p_force THEN
            EXECUTE 'DELETE FROM ' || v_dst
                    || ' WHERE ' || quote_ident(v_time_col) || ' >= ' || quote_literal(p_start::text)
                    || ' AND '   || quote_ident(v_time_col) || ' < '  || quote_literal(p_end::text);
        END IF;

        EXECUTE 'INSERT INTO ' || v_dst || ' (' || v_cols || ')'
                || ' SELECT s.' || replace(v_cols, ', ', ', s.')
                || ' FROM ' || v_src || ' s '
                || ' WHERE s.' || quote_ident(v_time_col) || ' >= ' || quote_literal(p_start::text)
                || ' AND s.'   || quote_ident(v_time_col) || ' < '  || quote_literal(p_end::text)
                || ' AND NOT EXISTS (SELECT 1 FROM ' || v_dst || ' d'
                || ' WHERE d.' || quote_ident(v_pk_col) || ' = s.' || quote_ident(v_pk_col) || ')';
        GET DIAGNOSTICS v_count = ROW_COUNT;

        RAISE NOTICE '[V3] delta 搬运 % : % ~ % , 新增 % 行 (force=%)',
            v_table, p_start, p_end, v_count, p_force;
    END LOOP;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 执行方式（二选一）：
--   A. 整月搬运：   -v month=YYYY-MM [-v tbl=xxx] [-v force=YES]
--   B. final delta：-v delta_start='YYYY-MM-DD HH24:MI:SS'
--                   -v delta_end='YYYY-MM-DD HH24:MI:SS' [-v tbl=xxx]
--
-- delta 模式用于 003_cutover 停写窗口内补齐“最后一次整月搬运之后新增的行”，
-- 按主键去重，可重复执行；force=YES 用于源表修正后强制重搬当前月。
-- -----------------------------------------------------------------------------
\if :{?force}
\else
    \set force NO
\endif

\if :{?delta_start}
    \if :{?delta_end}
    \else
        \echo 'delta 模式必须同时提供 -v delta_end=YYYY-MM-DD HH24:MI:SS'
        \quit
    \endif
    \if :{?tbl}
    SELECT jl_data01.v3_copy_range(
        CAST(:'delta_start' AS timestamp), CAST(:'delta_end' AS timestamp), :'tbl', false);
    \else
    SELECT jl_data01.v3_copy_range(
        CAST(:'delta_start' AS timestamp), CAST(:'delta_end' AS timestamp), NULL, false);
    \endif
    \echo 'delta 搬运完成。请核对时间窗内源表与影子表 count 后再执行 003_cutover.sql。'
\else
    \if :{?month}
    \else
        \echo '请通过 -v month=YYYY-MM 指定要搬运的月份，或使用 delta_start/delta_end 做 final delta，例如：'
        \echo '  psql "$PGURL" -v month=2026-01 -f 002_copy_data.sql'
        \echo '  psql "$PGURL" -v delta_start="2026-01-31 00:00:00" -v delta_end="2026-02-01 00:00:00" -f 002_copy_data.sql'
        \quit
    \endif

    \if :{?tbl}
    SELECT jl_data01.v3_clear_month_if(
        to_date(:'month', 'YYYY-MM')::date, :'tbl', (:'force' = 'YES'));
    SELECT jl_data01.v3_copy_month(to_date(:'month', 'YYYY-MM')::date, :'tbl');
    \else
    SELECT jl_data01.v3_clear_month_if(
        to_date(:'month', 'YYYY-MM')::date, NULL, (:'force' = 'YES'));
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

    \echo '提示：逐月执行本脚本完成全部历史月份后，切换前再用 delta 模式补一次 final delta，然后执行 003_cutover.sql。'
\endif
