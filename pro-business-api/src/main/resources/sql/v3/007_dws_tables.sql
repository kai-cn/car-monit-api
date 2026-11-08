-- =============================================================================
-- V3：大屏预聚合表（dws_*）DWS 层 DDL
--
-- 设计依据：architecture-traffic-query-design.md §5.4 / §8.4
-- 数据来源：ETL 从 car_except_record / car_confim_free / car_aduit_free /
--           car_warning_info 按日聚合；API 只读，不直连 backend 业务表。
--
-- 存储选型（见 docs/decisions-v3.md D16）：
--   dws_* 为按日聚合的小表（每年约 3.6 万行/表），不按月分区；
--   原因：openGauss 3.0 的分区 DDL 能力受限（不支持 PARTITION OF/ADD PARTITION(...)/
--   DETACH），而 DWS 数据量小、分区收益有限，非分区表 + 主键/查询索引更稳妥。
--
-- 幂等：CREATE TABLE IF NOT EXISTS；索引存在性由 v3_create_index_if_absent 判断。
-- =============================================================================

\set ON_ERROR_STOP on
SET search_path TO jl_data01, public;

-- -----------------------------------------------------------------------------
-- 0. 幂等索引助手（openGauss 3.0 不支持 CREATE INDEX IF NOT EXISTS）
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION jl_data01.v3_create_index_if_absent(
    p_table   text,
    p_index   text,
    p_columns text,
    p_where   text DEFAULT NULL
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
    IF v_exists = 0 THEN
        EXECUTE 'CREATE INDEX ' || quote_ident(p_index)
                || ' ON jl_data01.' || quote_ident(p_table)
                || ' (' || p_columns || ')'
                || CASE WHEN p_where IS NULL THEN '' ELSE ' WHERE ' || p_where END;
        RAISE NOTICE '[V3] 索引已创建: %.%', p_table, p_index;
    END IF;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. 逃费/追缴按日、机构、逃费类型（同时服务 carStatistics 与 carAudit）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.dws_escape_daily (
    stat_date    date          NOT NULL,
    org_id       varchar(32)   NOT NULL,
    escaped_type varchar(32)   NOT NULL,
    cnt          bigint        NOT NULL DEFAULT 0,
    amount       numeric(18,2) NOT NULL DEFAULT 0,
    car_cnt      bigint        NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, org_id, escaped_type)
);

COMMENT ON TABLE jl_data01.dws_escape_daily IS
    '大屏逃费日汇总：按 stat_date + org_id + escaped_type；car_cnt 为去重近似值';

-- -----------------------------------------------------------------------------
-- 2. 堵漏增收按日、机构、suo/zhan
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.dws_income_daily (
    stat_date   date          NOT NULL,
    org_id      varchar(32)   NOT NULL,
    org_name    varchar(100),
    query_type  varchar(8)    NOT NULL,
    amount      numeric(18,2) NOT NULL DEFAULT 0,
    car_cnt     bigint        NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, org_id, query_type)
);

COMMENT ON TABLE jl_data01.dws_income_daily IS
    '大屏堵漏增收日汇总：query_type=suo/zhan；同时作为 carAudit 的已完成口径';

-- -----------------------------------------------------------------------------
-- 3. 路段预警 Top-N 按日、路线、路段
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jl_data01.dws_warning_section_daily (
    stat_date    date        NOT NULL,
    road_code    varchar(32) NOT NULL,
    section_code varchar(32) NOT NULL,
    warning_cnt  bigint      NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, road_code, section_code)
);

COMMENT ON TABLE jl_data01.dws_warning_section_daily IS
    '大屏路段预警日汇总：用于 warning-top；Top-N 由查询层排序计算';

-- -----------------------------------------------------------------------------
-- 4. 查询索引（主键已覆盖；补给按机构/类型的时间倒序）
-- -----------------------------------------------------------------------------
SELECT jl_data01.v3_create_index_if_absent(
    'dws_escape_daily', 'idx_dws_escape_org_type_date', 'org_id, escaped_type, stat_date DESC', NULL);

SELECT jl_data01.v3_create_index_if_absent(
    'dws_income_daily', 'idx_dws_income_org_type_date', 'org_id, query_type, stat_date DESC', NULL);

SELECT jl_data01.v3_create_index_if_absent(
    'dws_warning_section_daily', 'idx_dws_warning_section_date', 'section_code, stat_date DESC', NULL);

DO $$
BEGIN
    RAISE NOTICE 'dws_* 表已就绪。请由 ETL 回填后再设置 traffic.bigscreen.stats-enabled=true。';
END $$;
