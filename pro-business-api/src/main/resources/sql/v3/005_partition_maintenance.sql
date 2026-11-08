-- =============================================================================
-- V3 阶段一：分区维护（预建未来分区 / 归档历史分区）
--
-- 设计依据：architecture-traffic-query-design.md §5.2
-- openGauss 3.0 实测约束（见 docs/decisions-v3.md D15）：
--   - 不支持 CREATE TABLE ... PARTITION OF ... FOR VALUES FROM/TO；
--   - 未来分区只能用 ALTER TABLE ... ADD PARTITION <name> VALUES LESS THAN (...)，
--     且新分区的上界必须大于现有最后一个分区的上界；
--   - 不支持 DETACH PARTITION，归档采用“COPY 到独立归档表 + DROP PARTITION”。
--
-- 原则：
--   - 永远提前 3 个月预建分区，禁止 default/MAXVALUE 分区；
--   - 历史数据先复制到归档表再 DROP PARTITION，绝不直接 DELETE；
--   - 所有函数幂等；归档有显式 confirm 门禁。
--
-- 用法：
--   psql "$PGURL" -f 005_partition_maintenance.sql          -- 创建函数
--   psql "$PGURL" -c "SELECT jl_data01.v3_create_future_partitions(3);"
--   psql "$PGURL" -c "SELECT jl_data01.v3_detach_old_partitions(13, 'YES');"
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

-- -----------------------------------------------------------------------------
-- 0. 判断表是否为分区父表（openGauss 父表 relkind='r'，需查 pg_partition）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_is_partitioned(p_table text) RETURNS int AS $$
DECLARE
    v_count int;
BEGIN
    SELECT count(*) INTO v_count
      FROM pg_partition p
      JOIN pg_class c ON c.oid = p.parentid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_table
       AND p.parttype = 'r';
    RETURN v_count;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. 预建未来 N 个月分区（自动识别当前生效的父表：src 或 src_v3）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_create_future_partitions(
    p_months int DEFAULT 3
) RETURNS void AS $$
DECLARE
    v_tables   text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table    text;
    v_parent   text;
    v_exists   int;
    v_month    date;
    v_end      date;
    v_month_end date;
    v_part     text;
    v_part_exists int;
    v_last_bound_text text;
    v_last_bound date;
BEGIN
    FOREACH v_table IN ARRAY v_tables LOOP
        -- 优先使用已切换的正式分区父表，否则维护影子分区父表
        SELECT jl_data01.v3_is_partitioned(v_table) INTO v_exists;
        IF v_exists > 0 THEN
            v_parent := v_table;
        ELSE
            SELECT jl_data01.v3_is_partitioned(v_table || '_v3') INTO v_exists;
            IF v_exists = 0 THEN
                RAISE NOTICE '[V3] 跳过（无分区父表）: %', v_table;
                CONTINUE;
            END IF;
            v_parent := v_table || '_v3';
        END IF;

        -- 现有最后分区上界（openGauss pg_partition.boundaries 为 text[] 上界）
        SELECT max((p.boundaries)[1]) INTO v_last_bound_text
          FROM pg_partition p
          JOIN pg_class c ON c.oid = p.parentid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'jl_data01'
           AND c.relname = v_parent
           AND p.parttype = 'p';
        IF v_last_bound_text IS NULL THEN
            RAISE NOTICE '[V3] 跳过（无分区定义）: %', v_parent;
            CONTINUE;
        END IF;
        IF v_last_bound_text !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
            RAISE NOTICE '[V3] 跳过（最后分区边界非日期，可能为 MAXVALUE）: % / %',
                v_parent, v_last_bound_text;
            CONTINUE;
        END IF;
        v_last_bound := v_last_bound_text::date;

        v_month := date_trunc('month', CURRENT_DATE)::date;
        v_end   := (date_trunc('month', CURRENT_DATE) + (p_months || ' months')::interval)::date;
        WHILE v_month < v_end LOOP
            v_month_end := (v_month + interval '1 month')::date;
            v_part := v_parent || '_p' || to_char(v_month, 'YYYYMM');

            SELECT count(*) INTO v_part_exists
              FROM pg_partition p
              JOIN pg_class c ON c.oid = p.parentid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'jl_data01'
               AND c.relname = v_parent
               AND p.parttype = 'p'
               AND p.relname = v_part;

            IF v_part_exists > 0 THEN
                RAISE NOTICE '[V3] 分区已存在，跳过: %.%', v_parent, v_part;
            ELSIF v_month_end <= v_last_bound THEN
                RAISE NOTICE '[V3] 新分区上界未超过最后分区，跳过: %.% (last=%)',
                    v_parent, v_part, v_last_bound;
            ELSE
                EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_parent)
                        || ' ADD PARTITION ' || quote_ident(v_part)
                        || ' VALUES LESS THAN (' || quote_literal(v_month_end::text) || ')';
                v_last_bound := v_month_end;
                RAISE NOTICE '[V3] 已新增分区: %.% (upper=%)', v_parent, v_part, v_month_end;
            END IF;
            v_month := v_month_end;
        END LOOP;
        RAISE NOTICE '[V3] 预建完成: % 最后上界=%', v_parent, v_last_bound;
    END LOOP;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 2. 归档历史分区：COPY 到 *_archive_YYYYMM 后 DROP PARTITION（不丢数据）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_detach_old_partitions(
    p_keep_months int DEFAULT 13,
    p_confirm     text DEFAULT 'NO'
) RETURNS int AS $$
DECLARE
    v_tables    text[] := ARRAY[
        'ods_rt_szdn_snapshot_flow_addcode',
        'ods_lwzxsfsj_fee_records_01',
        'zdata_trail_fitting'
    ];
    v_table     text;
    v_parent    text;
    v_time_col  text;
    v_exists    int;
    v_cutoff    date;
    v_part      text;
    v_ym        text;
    v_start     date;
    v_end       date;
    v_archive   text;
    v_arch_exists int;
    v_count     int := 0;
BEGIN
    IF upper(p_confirm) <> 'YES' THEN
        RAISE EXCEPTION '归档会 DROP PARTITION（先复制到归档表），请使用 confirm=YES';
    END IF;

    v_cutoff := (date_trunc('month', CURRENT_DATE) - (p_keep_months || ' months')::interval)::date;

    FOREACH v_table IN ARRAY v_tables LOOP
        SELECT jl_data01.v3_is_partitioned(v_table) INTO v_exists;
        IF v_exists > 0 THEN
            v_parent := v_table;
        ELSE
            SELECT jl_data01.v3_is_partitioned(v_table || '_v3') INTO v_exists;
            IF v_exists = 0 THEN
                RAISE NOTICE '[V3] 跳过（无分区父表）: %', v_table;
                CONTINUE;
            END IF;
            v_parent := v_table || '_v3';
        END IF;

        v_time_col := CASE v_table
            WHEN 'ods_rt_szdn_snapshot_flow_addcode' THEN 'snapshottime'
            WHEN 'ods_lwzxsfsj_fee_records_01'        THEN 'transtime'
            WHEN 'zdata_trail_fitting'                THEN 'extime'
        END;

        FOR v_part IN
            SELECT p.relname
              FROM pg_partition p
              JOIN pg_class c ON c.oid = p.parentid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'jl_data01'
               AND c.relname = v_parent
               AND p.parttype = 'p'
             ORDER BY p.relname
        LOOP
            v_ym := substring(v_part from '([0-9]{6})$');
            IF v_ym IS NULL THEN
                CONTINUE;
            END IF;
            v_start := to_date(v_ym || '01', 'YYYYMMDD');
            v_end   := (v_start + interval '1 month')::date;
            IF v_start >= v_cutoff THEN
                CONTINUE;
            END IF;

            v_archive := v_parent || '_archive_' || v_ym;
            SELECT count(*) INTO v_arch_exists
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'jl_data01' AND c.relname = v_archive;
            IF v_arch_exists > 0 THEN
                RAISE NOTICE '[V3] 归档表已存在，跳过: %', v_archive;
                CONTINUE;
            END IF;

            -- openGauss 3.0 无 DETACH：先按分区范围 COPY 到独立归档表，再 DROP 分区
            EXECUTE 'CREATE TABLE jl_data01.' || quote_ident(v_archive)
                    || ' AS SELECT * FROM jl_data01.' || quote_ident(v_parent)
                    || ' WHERE ' || quote_ident(v_time_col) || ' >= ' || quote_literal(v_start::text)
                    || ' AND ' || quote_ident(v_time_col) || ' < ' || quote_literal(v_end::text);
            EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(v_parent)
                    || ' DROP PARTITION ' || quote_ident(v_part);
            v_count := v_count + 1;
            RAISE NOTICE '[V3] 已归档分区: % -> %（%）', v_part, v_archive, v_ym;
        END LOOP;
    END LOOP;

    RAISE NOTICE '[V3] 归档分区总数: %（保留最近 % 个月热数据）', v_count, p_keep_months;
    RETURN v_count;
END $$ LANGUAGE plpgsql;

DO $$
BEGIN
    RAISE NOTICE '分区维护函数已就绪：v3_create_future_partitions / v3_detach_old_partitions';
    RAISE NOTICE '建议每月初执行一次预建；归档需业务确认后手动执行。';
END $$;
