# 核心数据表

## 抓拍流水表 snapshot

- 物理表：`jl_data01.ods_rt_szdn_snapshot_flow_addcode`
- 内容：门架抓拍、省界抓拍、收费站抓拍。
- 时间字段：`snapshottime`（抓拍时间）。
- 主键：`big_id`；分区表口径为 `(big_id, snapshottime)`。
- 常用维度：`orgcode`（管理单位）、`sectioncode`（路段）、`roadcode`（道路）、`gantrycode`（门架）、`tollcode`（收费站）。
- 车牌：`platenumber` 原始车牌；`plate_norm` 归一化车牌（去空格、统一大写、去颜色后缀）。
- 适用问题：某车牌在某时间段经过哪些门架/省界；某门架某时段的抓拍量。

## 收费流水表 fee

- 物理表：`jl_data01.ods_lwzxsfsj_fee_records_01`
- 内容：出口收费流水、门架计费流水。
- 时间字段：`transtime`（交易时间）。
- 主键：`big_id`；分区表口径为 `(big_id, transtime)`。
- 金额字段：`fee`（应收）、`discountfee`（优惠）、`realfee`（实收，若存在以现场口径为准）。
- 车牌派生列：`plate_core`（车牌核心号）、`plate_color_code`（颜色码，未知为 -1）、`plate_raw`（原始串）、`plate_parse_status`（解析状态）。
- 适用问题：某车牌某次通行费用；某收费站某时段收入；某路段收费额分布。

## 轨迹拟合表 trail

- 物理表：`jl_data01.zdata_trail_fitting`
- 内容：一次出入口行程的拟合轨迹，`trailpoints` 为轨迹点数组（门架/省界/收费站抓拍 + 经纬度）。
- 时间字段：`extime`（出口时间）；`entime`（入口时间）。
- 主键：`cid`；分区表口径为 `(cid, extime)`。
- 车牌：`envehicleid`（入口车牌）、`exvehicleid`（出口车牌）；`plate_norm` 由入口车牌归一化。
- 注意：`trailpoints` 是大字段，ES 不存，列表查询只返回元数据；轨迹回放需按 `cid` 回 GaussDB 取点。
- 适用问题：车辆行驶路径、是否绕行、入口-出口时间差。

## 时间与分区口径

- 三张表均按月 RANGE 分区，热数据保留 13 个月，历史分区归档。
- 业务时区固定 `Asia/Shanghai`；接口传时间不要带时区后缀。
- 跨月查询会命中多个月分区/索引，时间范围越大越慢；对话场景限制 31 天，轨迹回放限制 24 小时。
