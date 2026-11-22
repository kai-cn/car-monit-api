-- ============================================================
-- 渐进式查询架构 - 索引与分区SQL脚本
-- Progressive Query Architecture - Index & Partition SQL Scripts
-- ============================================================
-- 适用数据库：GaussDB / openGauss 3.0 / PostgreSQL
-- 适用表：
--   1. jl_data01.ods_rt_szdn_snapshot_flow_addcode（门架抓拍流水）
--   2. jl_data01.ods_lwzxsfsj_fee_records_01（收费流水）
--   3. jl_data01.zdata_trail_fitting（车辆轨迹拟合）
-- ============================================================

-- ============================================================
-- 阶段一：千万级（单表 < 5000万行）
-- Phase 1: Ten Million Level
-- 策略：B-tree 索引 + pg_trgm GIN 索引 + 覆盖索引
-- ============================================================

-- 1. 启用 pg_trgm 扩展（支持 LIKE '%xxx%' 索引加速）
-- Enable pg_trgm extension for trigram-based fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. 门架抓拍流水 - B-tree 索引
-- Snapshot flow - B-tree indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_time
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (snapshottime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_plate_time
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (platenumber, snapshottime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_gantry_time
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (gantrycode, snapshottime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_section_time
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (sectioncode, snapshottime DESC);

-- 3. 门架抓拍流水 - GIN trigram 索引（加速 LIKE '%xxx%'）
-- GIN trigram indexes for fuzzy LIKE queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_plate_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (platenumber gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_gantryname_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (gantryname gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_roadname_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (roadname gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_sectionname_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (sectionname gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_orgname_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (orgname gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_tollname_trgm
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode USING gin (tollname gin_trgm_ops);

-- 4. 门架抓拍流水 - 游标分页复合索引
-- Cursor pagination composite index (snapshottime ASC, datauuid ASC)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshot_flow_cursor
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (snapshottime ASC, datauuid ASC);

-- 5. 收费流水 - B-tree 索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fee_records_time
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (transtime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fee_records_plate_time
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (vehicleplate, transtime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fee_records_gantry_time
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (gantryid, transtime DESC);

-- 6. 收费流水 - GIN trigram 索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fee_records_plate_trgm
    ON jl_data01.ods_lwzxsfsj_fee_records_01 USING gin (vehicleplate gin_trgm_ops);

-- 7. 车辆轨迹 - B-tree 索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trail_fitting_extime
    ON jl_data01.zdata_trail_fitting (extime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trail_fitting_entime
    ON jl_data01.zdata_trail_fitting (entime DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trail_fitting_envehicleid_extime
    ON jl_data01.zdata_trail_fitting (envehicleid, extime DESC);

-- 8. 车辆轨迹 - GIN trigram 索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trail_fitting_stationname_trgm
    ON jl_data01.zdata_trail_fitting USING gin (entollstationname gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trail_fitting_exstationname_trgm
    ON jl_data01.zdata_trail_fitting USING gin (extollstationname gin_trgm_ops);

-- ============================================================
-- 阶段二：亿级（5000万 ~ 5亿行）
-- Phase 2: Hundred Million Level
-- 策略：按月范围分区 + 分区裁剪 + 物化视图
-- ============================================================

-- 注意：分区表迁移需要先备份原表、创建分区表、迁移数据、重建索引
-- 注意：openGauss 3.0 使用 ALTER TABLE ... ADD PARTITION 语法

-- 9. 物化视图 - 按路段统计每日门架抓拍量（统计查询加速）
-- Materialized view for daily snapshot count by section
CREATE MATERIALIZED VIEW IF NOT EXISTS jl_data01.mv_snapshot_daily_section AS
SELECT
    date_trunc('day', snapshottime) AS snapshot_date,
    sectioncode,
    sectionname,
    count(*) AS record_count,
    count(DISTINCT platenumber) AS vehicle_count
FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode
GROUP BY date_trunc('day', snapshottime), sectioncode, sectionname
WITH DATA;

-- 10. 物化视图 - 按月统计收费流水
CREATE MATERIALIZED VIEW IF NOT EXISTS jl_data01.mv_fee_monthly AS
SELECT
    date_trunc('month', transtime) AS trans_month,
    gantryid,
    count(*) AS record_count,
    sum(fee) AS total_fee,
    count(DISTINCT vehicleplate) AS vehicle_count
FROM jl_data01.ods_lwzxsfsj_fee_records_01
GROUP BY date_trunc('month', transtime), gantryid
WITH DATA;

-- 11. 物化视图唯一索引（用于增量刷新）
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_snapshot_daily_section
    ON jl_data01.mv_snapshot_daily_section (snapshot_date, sectioncode);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_fee_monthly
    ON jl_data01.mv_fee_monthly (trans_month, gantryid);

-- 12. 定时刷新物化视图（使用 REFRESH MATERIALIZED VIEW CONCURRENTLY）
-- 在定时任务中执行：
-- REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_snapshot_daily_section;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_fee_monthly;

-- ============================================================
-- 阶段三：十亿级（> 5亿行）
-- Phase 3: Billion Level
-- 策略：冷热分离 + Elasticsearch 全文检索
-- ============================================================

-- 13. 创建冷数据归档表（热数据保留近6个月，冷数据归档）
-- Cold data archive tables (keep hot data for recent 6 months)
CREATE TABLE IF NOT EXISTS jl_data01.ods_rt_szdn_snapshot_flow_archive (
    LIKE jl_data01.ods_rt_szdn_snapshot_flow_addcode INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS jl_data01.ods_lwzxsfsj_fee_records_archive (
    LIKE jl_data01.ods_lwzxsfsj_fee_records_01 INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS jl_data01.zdata_trail_fitting_archive (
    LIKE jl_data01.zdata_trail_fitting INCLUDING ALL
);

-- 14. 归档冷数据（在定时任务中执行，保留近6个月热数据）
-- Archive cold data (execute in scheduled task, keep recent 6 months hot)
-- INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_archive
-- SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode
-- WHERE snapshottime < NOW() - INTERVAL '6 months';
-- DELETE FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode
-- WHERE snapshottime < NOW() - INTERVAL '6 months';

-- 15. Elasticsearch 索引模板通过 Java 代码（EsIndexManageService）自动创建
-- ES index templates are created via Java code (EsIndexManageService)

-- ============================================================
-- 查询优化：ANALYZE 统计信息更新
-- Update table statistics for query planner
-- ============================================================
ANALYZE jl_data01.ods_rt_szdn_snapshot_flow_addcode;
ANALYZE jl_data01.ods_lwzxsfsj_fee_records_01;
ANALYZE jl_data01.zdata_trail_fitting;
