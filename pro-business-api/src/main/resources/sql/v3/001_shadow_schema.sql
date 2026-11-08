-- =============================================================================
-- V3 阶段一：三张核心表按月分区 —— 影子表建表脚本（幂等）
--
-- 目标表：
--   jl_data01.ods_rt_szdn_snapshot_flow_addcode  (时间键 snapshottime，主键 big_id)
--   jl_data01.ods_lwzxsfsj_fee_records_01        (时间键 transtime，主键 big_id)
--   jl_data01.zdata_trail_fitting                (时间键 extime，主键 cid)
--
-- 安全策略（见 docs/decisions-v3.md D1）：
--   1. 不原地修改在用表；创建 *_v3 影子分区表，全部列从源表动态克隆。
--   2. 本脚本只做 DDL（建影子表/分区/索引/派生列），不搬运数据。
--   3. 数据搬运见 002_copy_data.sql，按月执行、可中断可续跑。
--   4. 切换见 003_cutover.sql；回滚见 003_cutover_rollback.sql。
--   5. 所有对象带 IF NOT EXISTS 语义，可重复执行。
--
-- 执行方式：
--   psql "postgresql://<user>:<pwd>@<host>:5432/RuoYi" -f 001_shadow_schema.sql
--   建议先在测试 schema / 数据库副本上演练。
-- =============================================================================

\set ON_ERROR_STOP on

SET search_path TO jl_data01, public;

-- -----------------------------------------------------------------------------
-- 0. 迁移进度表：按月记录已搬运的表，供 002 续跑与 003 切换前校验
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.v3_migration_progress (
    table_name    varchar(64) NOT NULL,
    month_start   date        NOT NULL,
    rows_copied   bigint      NOT NULL DEFAULT 0,
    finished_at   timestamp(6) DEFAULT now(),
    PRIMARY KEY (table_name, month_start)
);

COMMENT ON TABLE jl_data01.v3_migration_progress IS
    'V3 分区迁移进度：按月幂等记录，避免重复搬运';

-- 显式排除清单（000 会写入；此处兜底创建，保证预检能给出明确报告）
CREATE TABLE IF NOT EXISTS jl_data01.v3_migration_excluded_rows (
    table_name   varchar(64)  NOT NULL,
    pk           varchar(100) NOT NULL,
    reason       varchar(200) NOT NULL,
    backed_up_at timestamp(6) NOT NULL DEFAULT now(),
    PRIMARY KEY (table_name, pk)
);

-- -----------------------------------------------------------------------------
-- 1. 通用函数：建影子分区表（仅建结构 + 分区 + 关键索引）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_create_shadow_partitioned(
    p_src_table          text,
    p_dst_table          text,
    p_time_col           text,
    p_pk_col             text,
    p_fillfactor         int,
    p_precreate_months   int
) RETURNS void AS $$
DECLARE
    v_src_rel      text;
    v_cols         text;
    v_parts        text;
    v_start_month  date;
    v_end_month    date;
    v_month        date;
    v_month_end    date;
    v_exists       int;
    v_null_time_count bigint;
    v_null_pk_count   bigint;
    v_excluded_count  bigint;
    v_unaccounted     bigint;
BEGIN
    v_src_rel := quote_ident('jl_data01') || '.' || quote_ident(p_src_table);

    -- 源表存在性检查
    SELECT count(*) INTO v_exists
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_src_table
       AND c.relkind IN ('r', 'p');
    IF v_exists = 0 THEN
        RAISE EXCEPTION '源表不存在: %', v_src_rel;
    END IF;

    -- 影子表已存在则跳过
    SELECT count(*) INTO v_exists
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_dst_table;
    IF v_exists > 0 THEN
        RAISE NOTICE '影子表已存在，跳过: %', p_dst_table;
        RETURN;
    END IF;

    -- NULL 前置校验/报告：时间列 NULL 必须先备份并显式排除（000_null_time_exclusion.sql），
    -- 不允许静默丢弃；主键 NULL 无法按 pk 排除，直接中止。
    EXECUTE 'SELECT count(*) FROM ' || v_src_rel
            || ' WHERE ' || quote_ident(p_time_col) || ' IS NULL'
       INTO v_null_time_count;
    EXECUTE 'SELECT count(*) FROM ' || v_src_rel
            || ' WHERE ' || quote_ident(p_pk_col) || ' IS NULL'
       INTO v_null_pk_count;
    IF v_null_pk_count > 0 THEN
        RAISE EXCEPTION '源表 % 存在主键 NULL % 行，无法按 pk 备份/排除，请先清洗主键',
            v_src_rel, v_null_pk_count;
    END IF;

    IF v_null_time_count > 0 THEN
        EXECUTE 'SELECT count(*) FROM ' || v_src_rel || ' s WHERE s.'
                || quote_ident(p_time_col) || ' IS NULL AND EXISTS ('
                || 'SELECT 1 FROM jl_data01.v3_migration_excluded_rows e '
                || 'WHERE e.table_name = ' || quote_literal(p_src_table)
                || ' AND e.pk = s.' || quote_ident(p_pk_col) || ')'
           INTO v_excluded_count;
        v_unaccounted := v_null_time_count - v_excluded_count;
        RAISE NOTICE '[V3迁移预检] %: 时间列 NULL 总数=%, 已备份并显式排除=%, 未处理=%',
            p_src_table, v_null_time_count, v_excluded_count, v_unaccounted;
        IF v_unaccounted > 0 THEN
            RAISE EXCEPTION '源表 % 仍有 % 行时间列 NULL 未处置；请先执行 000_null_time_exclusion.sql 备份并标记排除',
                p_src_table, v_unaccounted;
        END IF;
    ELSE
        RAISE NOTICE '[V3迁移预检] %: 时间列 NULL=0，无排除行', p_src_table;
    END IF;

    -- 从源表动态克隆全部列定义（保留 varchar 长度 / numeric 精度 / text[] 等）
    SELECT string_agg(
               quote_ident(a.attname) || ' ' || format_type(a.atttypid, a.atttypmod),
               ', ' ORDER BY a.attnum)
      INTO v_cols
      FROM pg_attribute a
     WHERE a.attrelid = v_src_rel::regclass
       AND a.attnum > 0
       AND NOT a.attisdropped;

    IF v_cols IS NULL THEN
        RAISE EXCEPTION '无法读取源表列定义: %', v_src_rel;
    END IF;

    -- 分区范围：源表最早月 ~ 最晚月 + 预建月数；空表从当前月起
    EXECUTE 'SELECT date_trunc(''month'', min(' || quote_ident(p_time_col) || '))::date FROM ' || v_src_rel
       INTO v_start_month;
    IF v_start_month IS NULL THEN
        v_start_month := date_trunc('month', CURRENT_DATE)::date;
    END IF;

    EXECUTE 'SELECT date_trunc(''month'', max(' || quote_ident(p_time_col) || '))::date FROM ' || v_src_rel
       INTO v_end_month;
    IF v_end_month IS NULL THEN
        v_end_month := date_trunc('month', CURRENT_DATE)::date;
    END IF;
    IF v_end_month < date_trunc('month', CURRENT_DATE)::date THEN
        v_end_month := date_trunc('month', CURRENT_DATE)::date;
    END IF;

    -- 建影子分区表：分区表唯一约束必须包含分区键，主键用 (pk, time)
    -- openGauss 3.0 实测约束（见 decisions-v3.md D15）：
    --   1) PARTITION BY RANGE 后必须紧跟至少一个 PARTITION 定义，不能先建空分区表；
    --   2) 分区必须在 CREATE TABLE 内用 VALUES LESS THAN 声明；
    --   3) 不支持 CREATE TABLE ... PARTITION OF ... FOR VALUES FROM/TO；
    --   4) 不支持在 PARTITION BY 后追加 WITH (fillfactor)。
    -- 因此这里一次性构建“历史月 ~ 预建月”的完整分区列表；未来月由
    -- 005_partition_maintenance.sql 用 ALTER TABLE ... ADD PARTITION 追加。
    v_month := v_start_month;
    v_parts := '';
    WHILE v_month <= (v_end_month + (p_precreate_months || ' months')::interval)::date LOOP
        v_month_end := (v_month + interval '1 month')::date;
        v_parts := v_parts
                || CASE WHEN v_parts = '' THEN '' ELSE ', ' END
                || 'PARTITION ' || quote_ident(p_dst_table || '_p' || to_char(v_month, 'YYYYMM'))
                || ' VALUES LESS THAN (' || quote_literal(v_month_end::text) || ')';
        v_month := v_month_end;
    END LOOP;

    EXECUTE 'CREATE TABLE jl_data01.' || quote_ident(p_dst_table) || ' ('
            || v_cols
            || ', PRIMARY KEY (' || quote_ident(p_pk_col) || ', ' || quote_ident(p_time_col) || '))'
            || ' PARTITION BY RANGE (' || quote_ident(p_time_col) || ') ('
            || v_parts || ')';

    -- 分区键 / 主键 NOT NULL（父表设置，自动继承到分区）
    EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(p_dst_table)
            || ' ALTER COLUMN ' || quote_ident(p_time_col) || ' SET NOT NULL';
    EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(p_dst_table)
            || ' ALTER COLUMN ' || quote_ident(p_pk_col) || ' SET NOT NULL';

    -- 说明：时间/组织/车牌索引统一在 006_post_copy_indexes.sql 中、数据搬运完成后创建，
    -- 避免 8 亿行搬运期间持续维护索引；影子表搬运阶段不承载查询，无需索引。

    -- 自动清理参数（大分区表降低阈值，设计 §2.5）
    BEGIN
        EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(p_dst_table)
                || ' SET (autovacuum_vacuum_scale_factor = 0.02,'
                || ' autovacuum_analyze_scale_factor = 0.01)';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '[V3] 设置 autovacuum 参数失败（可忽略）: %', SQLERRM;
    END;

    RAISE NOTICE '[V3] 影子分区表已创建: %, 分区 % ~ %',
        p_dst_table, v_start_month, v_end_month;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1.1 通用函数：列不存在时新增（兼容 openGauss 不支持 ADD COLUMN IF NOT EXISTS 的情况）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_add_column_if_absent(
    p_table   text,
    p_column  text,
    p_type    text,
    p_default text DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_exists int;
BEGIN
    SELECT count(*) INTO v_exists
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'jl_data01'
       AND c.relname = p_table
       AND a.attname = p_column
       AND a.attnum > 0
       AND NOT a.attisdropped;
    IF v_exists = 0 THEN
        EXECUTE 'ALTER TABLE jl_data01.' || quote_ident(p_table)
                || ' ADD COLUMN ' || quote_ident(p_column) || ' ' || p_type
                || CASE WHEN p_default IS NULL THEN '' ELSE ' DEFAULT ' || p_default END;
        RAISE NOTICE '[V3] 已新增列 %.%', p_table, p_column;
    END IF;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 2. 抓拍流水：43 列，时间 snapshottime，主键 big_id
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_shadow_partitioned(
    'ods_rt_szdn_snapshot_flow_addcode',
    'ods_rt_szdn_snapshot_flow_addcode_v3',
    'snapshottime',
    'big_id',
    100,
    3
);

-- 精确车牌索引统一在 006_post_copy_indexes.sql 中创建（避免搬运期维护索引）

-- -----------------------------------------------------------------------------
-- 3. 收费流水：136 列，时间 transtime，主键 big_id
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_shadow_partitioned(
    'ods_lwzxsfsj_fee_records_01',
    'ods_lwzxsfsj_fee_records_01_v3',
    'transtime',
    'big_id',
    100,
    3
);

-- 派生车牌列（设计 §5.1.6 / decisions D4）
SELECT jl_data01.v3_add_column_if_absent(
    'ods_lwzxsfsj_fee_records_01_v3', 'plate_core', 'varchar(32)', NULL);
SELECT jl_data01.v3_add_column_if_absent(
    'ods_lwzxsfsj_fee_records_01_v3', 'plate_color_code', 'smallint', '-1');
SELECT jl_data01.v3_add_column_if_absent(
    'ods_lwzxsfsj_fee_records_01_v3', 'plate_color_raw', 'varchar(16)', NULL);
SELECT jl_data01.v3_add_column_if_absent(
    'ods_lwzxsfsj_fee_records_01_v3', 'plate_raw', 'varchar(100)', NULL);
SELECT jl_data01.v3_add_column_if_absent(
    'ods_lwzxsfsj_fee_records_01_v3', 'plate_parse_status', 'varchar(16)', '''unparsed''');

ALTER TABLE jl_data01.ods_lwzxsfsj_fee_records_01_v3
    ALTER COLUMN plate_color_code SET NOT NULL;

-- 车牌复合索引统一在 006_post_copy_indexes.sql 中创建（避免搬运期维护索引）

COMMENT ON COLUMN jl_data01.ods_lwzxsfsj_fee_records_01_v3.plate_core IS
    '派生：车牌核心（去除 _颜色码 后缀）';
COMMENT ON COLUMN jl_data01.ods_lwzxsfsj_fee_records_01_v3.plate_color_code IS
    '派生：颜色枚举码；0..N 以 dict_plate_color 为准，-1 表示未知/缺失';
COMMENT ON COLUMN jl_data01.ods_lwzxsfsj_fee_records_01_v3.plate_parse_status IS
    '派生：ok/no_color/color_unparsed/unparsed';

-- -----------------------------------------------------------------------------
-- 4. 轨迹表：时间 extime，主键 cid；trailpoints 保持 text[]（ES 不存）
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_shadow_partitioned(
    'zdata_trail_fitting',
    'zdata_trail_fitting_v3',
    'extime',
    'cid',
    90,
    3
);

-- 车牌索引统一在 006_post_copy_indexes.sql 中创建（避免搬运期维护索引）

-- 轨迹点大字段：更激进的 autovacuum 已在通用函数中设置，此处追加 toast 说明
COMMENT ON COLUMN jl_data01.zdata_trail_fitting_v3.trailpoints IS
    'text[] JSON 字符串数组；不进入 ES，仅按 (cid, extime) 回查详情/导出';

-- -----------------------------------------------------------------------------
-- 5. 完成提示
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'V3 影子分区表创建完成。下一步：';
    RAISE NOTICE '  1) 按月执行 002_copy_data.sql（可中断续跑）；';
    RAISE NOTICE '  2) 执行 004_sync_tables.sql（Outbox/DLQ/对账表）；';
    RAISE NOTICE '  3) 全部月份搬完后执行 006_post_copy_indexes.sql；';
    RAISE NOTICE '  4) 停写窗口执行 003_cutover.sql；';
    RAISE NOTICE '  5) 出问题执行 003_cutover_rollback.sql。';
    RAISE NOTICE '============================================================';
END $$;
