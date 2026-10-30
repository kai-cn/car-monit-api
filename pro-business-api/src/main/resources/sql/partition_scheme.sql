-- ==============================================
-- PostgreSQL 分区方案设计文档
-- 适用版本：PostgreSQL 11+
-- 适用场景：大表（>100GB）、按时间查询频繁
-- ==============================================

-- ==============================================
-- 1. zdata_trail_fitting 表分区方案
-- 分区键：extime（出站时间）
-- 分区策略：按月份范围分区
-- ==============================================

-- 1.1 创建主表（分区表模板）
CREATE TABLE IF NOT EXISTS jl_data01.zdata_trail_fitting (
    cid BIGSERIAL,
    envehicleid VARCHAR(32),
    enaxlecount INTEGER,
    entime TIMESTAMP,
    entolllaneid VARCHAR(64),
    entollstationid VARCHAR(64),
    entollstationname VARCHAR(128),
    envehicleclass VARCHAR(32),
    envehicletype VARCHAR(32),
    enweight NUMERIC(10,2),
    extime TIMESTAMP,
    extolllaneid VARCHAR(64),
    extollstationid VARCHAR(64),
    extollstationname VARCHAR(128),
    exvehicleclass VARCHAR(32),
    exvehicleid VARCHAR(32),
    exvehicletype VARCHAR(32),
    exweight NUMERIC(10,2),
    trailpoints JSONB,
    trailtype INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (extime);

-- 1.2 创建索引（主表上创建，自动继承到分区）
CREATE INDEX IF NOT EXISTS idx_zdata_trail_fitting_trailtype_extime 
    ON jl_data01.zdata_trail_fitting (trailtype, extime, cid);
CREATE INDEX IF NOT EXISTS idx_zdata_trail_fitting_envehicleid 
    ON jl_data01.zdata_trail_fitting (envehicleid);

-- 1.3 创建分区（示例：2024年各月分区）
-- 注意：生产环境建议使用脚本自动创建
DO $$
DECLARE
    start_month DATE := '2024-01-01';
    end_month DATE;
    part_name TEXT;
BEGIN
    FOR i IN 0..11 LOOP
        end_month := (start_month + INTERVAL '1 month')::DATE;
        part_name := 'zdata_trail_fitting_' || TO_CHAR(start_month, 'yyyymm');
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS jl_data01.%I 
             PARTITION OF jl_data01.zdata_trail_fitting
             FOR VALUES FROM (%L) TO (%L)',
            part_name, start_month, end_month
        );
        
        -- 为每个分区创建独立索引（可选，PostgreSQL会自动创建）
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I_idx_extime ON jl_data01.%I (extime, cid)',
            part_name, part_name
        );
        
        start_month := end_month;
    END LOOP;
END $$;

-- ==============================================
-- 2. ods_rt_szdn_snapshot_flow_addcode 表分区方案
-- 分区键：snapshottime（快照时间）
-- 分区策略：按小时范围分区（数据量大，更新频繁）
-- ==============================================

-- 2.1 创建主表
CREATE TABLE IF NOT EXISTS jl_data01.ods_rt_szdn_snapshot_flow_addcode (
    id BIGSERIAL,
    snapshottime TIMESTAMP,
    laneid VARCHAR(64),
    deviceid VARCHAR(64),
    vehicleplate VARCHAR(32),
    vehiclecolor VARCHAR(16),
    vehicletype VARCHAR(32),
    axlecount INTEGER,
    weight NUMERIC(10,2),
    speed NUMERIC(8,2),
    laneinout VARCHAR(8),
    imagelocation VARCHAR(256),
    addcode VARCHAR(64),
    dataorigin VARCHAR(32),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (snapshottime);

-- 2.2 创建索引
CREATE INDEX IF NOT EXISTS idx_ods_snapshot_snapshottime 
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (snapshottime);
CREATE INDEX IF NOT EXISTS idx_ods_snapshot_vehicleplate 
    ON jl_data01.ods_rt_szdn_snapshot_flow_addcode (vehicleplate);

-- 2.3 创建分区（按小时分区，示例创建2024年1月1日的24个分区）
DO $$
DECLARE
    start_hour TIMESTAMP := '2024-01-01 00:00:00';
    end_hour TIMESTAMP;
    part_name TEXT;
BEGIN
    FOR i IN 0..23 LOOP
        end_hour := start_hour + INTERVAL '1 hour';
        part_name := 'ods_rt_szdn_snapshot_flow_addcode_' || TO_CHAR(start_hour, 'yyyymmdd_hh24');
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS jl_data01.%I 
             PARTITION OF jl_data01.ods_rt_szdn_snapshot_flow_addcode
             FOR VALUES FROM (%L) TO (%L)',
            part_name, start_hour, end_hour
        );
        
        start_hour := end_hour;
    END LOOP;
END $$;

-- ==============================================
-- 3. ods_lwzxsfsj_fee_records_01 表分区方案
-- 分区键：transtime（交易时间）
-- 分区策略：按日期范围分区（每日一个分区）
-- ==============================================

-- 3.1 创建主表
CREATE TABLE IF NOT EXISTS jl_data01.ods_lwzxsfsj_fee_records_01 (
    id BIGSERIAL,
    transtime TIMESTAMP,
    tollstationid VARCHAR(64),
    laneid VARCHAR(64),
    vehicleplate VARCHAR(32),
    vehicletype VARCHAR(32),
    axlecount INTEGER,
    feeamount NUMERIC(12,2),
    discountamount NUMERIC(12,2),
    actualamount NUMERIC(12,2),
    paytype VARCHAR(32),
    transactionid VARCHAR(64),
    status INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (transtime);

-- 3.2 创建索引
CREATE INDEX IF NOT EXISTS idx_ods_fee_transtime 
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (transtime);
CREATE INDEX IF NOT EXISTS idx_ods_fee_vehicleplate 
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (vehicleplate);
CREATE INDEX IF NOT EXISTS idx_ods_fee_transactionid 
    ON jl_data01.ods_lwzxsfsj_fee_records_01 (transactionid);

-- 3.3 创建分区（按日期分区，示例创建2024年1月前10天）
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE;
    part_name TEXT;
BEGIN
    FOR i IN 0..9 LOOP
        end_date := start_date + INTERVAL '1 day';
        part_name := 'ods_lwzxsfsj_fee_records_01_' || TO_CHAR(start_date, 'yyyymmdd');
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS jl_data01.%I 
             PARTITION OF jl_data01.ods_lwzxsfsj_fee_records_01
             FOR VALUES FROM (%L) TO (%L)',
            part_name, start_date, end_date
        );
        
        start_date := end_date;
    END LOOP;
END $$;

-- ==============================================
-- 4. 分区管理维护脚本
-- ==============================================

-- 4.1 自动创建下一个月的分区（每月执行一次）
CREATE OR REPLACE FUNCTION create_next_month_partitions() 
RETURNS VOID AS $$
DECLARE
    current_month DATE := date_trunc('month', CURRENT_DATE)::DATE;
    next_month DATE := current_month + INTERVAL '1 month';
    part_name TEXT;
BEGIN
    -- zdata_trail_fitting
    part_name := 'zdata_trail_fitting_' || TO_CHAR(next_month, 'yyyymm');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS jl_data01.%I 
         PARTITION OF jl_data01.zdata_trail_fitting
         FOR VALUES FROM (%L) TO (%L)',
        part_name, next_month, next_month + INTERVAL '1 month'
    );
    
    -- ods_lwzxsfsj_fee_records_01（创建下个月所有日期分区）
    FOR i IN 0..31 LOOP
        DECLARE
            part_date DATE := next_month + i * INTERVAL '1 day';
            part_end_date DATE := part_date + INTERVAL '1 day';
        BEGIN
            EXIT WHEN part_date >= (next_month + INTERVAL '1 month')::DATE;
            part_name := 'ods_lwzxsfsj_fee_records_01_' || TO_CHAR(part_date, 'yyyymmdd');
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS jl_data01.%I 
                 PARTITION OF jl_data01.ods_lwzxsfsj_fee_records_01
                 FOR VALUES FROM (%L) TO (%L)',
                part_name, part_date, part_end_date
            );
        END;
    END LOOP;
    
    RAISE NOTICE 'Created partitions for month: %', TO_CHAR(next_month, 'YYYY-MM');
END $$ LANGUAGE plpgsql;

-- 4.2 删除过期分区（保留最近N个月）
CREATE OR REPLACE FUNCTION drop_old_partitions(months_to_keep INTEGER) 
RETURNS INTEGER AS $$
DECLARE
    cutoff_date DATE := CURRENT_DATE - INTERVAL '' || months_to_keep || ' months';
    part_name TEXT;
    drop_count INTEGER := 0;
BEGIN
    -- 删除 zdata_trail_fitting 过期分区
    FOR part_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'jl_data01' 
          AND tablename LIKE 'zdata_trail_fitting_%'
    LOOP
        DECLARE
            part_month DATE;
        BEGIN
            part_month := TO_DATE(SUBSTRING(part_name FROM 'zdata_trail_fitting_(.*)'), 'yyyymm');
            IF part_month < cutoff_date THEN
                EXECUTE format('DROP TABLE IF EXISTS jl_data01.%I', part_name);
                drop_count := drop_count + 1;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            CONTINUE;
        END;
    END LOOP;
    
    RETURN drop_count;
END $$ LANGUAGE plpgsql;

-- ==============================================
-- 5. 查询示例（验证分区裁剪）
-- ==============================================

-- 5.1 查询单个月份数据（只扫描对应分区）
EXPLAIN ANALYZE
SELECT * FROM jl_data01.zdata_trail_fitting
WHERE extime >= '2024-01-01' AND extime < '2024-02-01';

-- 5.2 查询跨月份数据（扫描多个分区）
EXPLAIN ANALYZE
SELECT * FROM jl_data01.zdata_trail_fitting
WHERE extime >= '2024-01-15' AND extime < '2024-03-15';

-- ==============================================
-- 6. 分区表统计信息维护
-- ==============================================

-- 分析所有分区
ANALYZE jl_data01.zdata_trail_fitting;

-- 分析指定分区
ANALYZE jl_data01.zdata_trail_fitting_202401;

-- ==============================================
-- 7. 分区表迁移数据（从非分区表迁移）
-- ==============================================
/*
-- 创建临时表（原表数据）
CREATE TABLE jl_data01.zdata_trail_fitting_old AS SELECT * FROM jl_data01.zdata_trail_fitting;

-- 创建分区表（清空数据）
TRUNCATE TABLE jl_data01.zdata_trail_fitting;

-- 插入数据（PostgreSQL自动路由到对应分区）
INSERT INTO jl_data01.zdata_trail_fitting SELECT * FROM jl_data01.zdata_trail_fitting_old;
*/
