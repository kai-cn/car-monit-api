# 大屏指标口径

## 逃费统计 escape

- 数据来源：DWS 预聚合表（按管理单位、逃费类型汇总）。
- 字段：`escapedType`（逃费类型编码）、`escapedTypeName`（类型名称）、`number`（逃费车次）、`escapedAmount`（逃费金额，元）。
- 口径：按稽核确认的逃费行为统计，不含疑似未确认记录。
- 常用问法：“本月逃费金额”“各类型逃费车次”。

## 稽核统计 audit

- 字段：`totalCount`（稽核总单数）、`finishedCount`（已完成）、`totalAmount`（涉及金额）、`finishedAmount`（已追缴金额）。
- 口径：按稽核工单创建时间统计；完成率 = finishedCount / totalCount。

## 收入分布 income

- 字段：`orgName`（管理单位/收费站名称）、`amount`（收入金额）、`carNum`（车次）。
- 口径：按出口收费流水的实收金额汇总；`queryDateType` 支持 day / month。
- 注意：收入为 0 的单位可能未参与汇总，不代表无车流。

## 告警 TopN warning_top

- 字段：`roadCode`（道路编码）、`sectionName`（路段名称）、`carNum`（告警车次）、`rank`（排名）、`rate`（占比）。
- 口径：按告警类型统计指定时间窗内车次最多的路段，默认 Top10。
- 常用问法：“昨天告警最多的 5 个路段”。

## 指标使用约束

- 大屏指标是预聚合结果，不能下钻到单车明细；需要明细时改用 `query_traffic_records`。
- 指标时间参数使用 `yyyy-MM-dd`；跨月/跨年按自然日汇总。
- 金额单位统一为元；前端展示“万元”时由回答中明确换算。
