-- =============================================================================
-- 本地联调最小种子数据（可选）
--
-- 仅用于验证 DB 链路与列表接口能返回数据；生产环境不要执行本文件。
-- 列名与 02-placeholder-tables.sql 保持一致。
-- =============================================================================

INSERT INTO jl_data01.ods_szdn_service (id, service_code, service_name, business_date)
VALUES ('1', 'SVC001', '本地联调示例服务', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

INSERT INTO jl_data01.ods_szdn_gantry (id, gantry_code, gantry_name, road_code, section_code)
VALUES ('gantry-1', 'G001', '示例门架', 'R001', 'S001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO jl_data01.ods_szdn_section (id, road_code, road_name, section_code, section_name)
VALUES ('section-1', 'R001', '示例路段', 'S001', '示例路段一')
ON CONFLICT (id) DO NOTHING;
