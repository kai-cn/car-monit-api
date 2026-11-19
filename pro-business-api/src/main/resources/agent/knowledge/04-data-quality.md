# 数据质量与延迟

## 数据链路

设备（华为/海康/新陆威）→ 华为 IoTDA → Kafka → Flink 聚合 → GaussDB（SoR）→ Outbox/CDC → Elasticsearch（查询副本）。

## 延迟口径

- 端到端正常延迟：秒级到分钟级；网络抖动或设备离线时会拉长。
- 明细查询查不到最近几分钟的数据，通常是 ES 刷新延迟（refresh_interval=5s）或同步链路积压，不代表数据丢失。
- 大屏指标按 DWS 预聚合，通常滞后 1 个调度周期（默认 5 分钟）。

## 丢失与重复

- 丢失率 =（上报数 - 入库数）/ 上报数；重复量按消息 ID 去重统计。
- 常见原因：设备离线、IoTDA 限流、Kafka 分区倾斜、Flink 反压、入库主键冲突。
- 诊断工具 `get_data_quality` 返回 reportedCount/storedCount/lostCount/lossRate/duplicateCount/passed。
- 丢失率非 0 时先看是否为单设备/单分区；补偿由运维在确认后触发，对话中不要承诺自动补数。

## 一致性

- GaussDB 是明细事实源；ES 是查询副本，可能出现短暂不一致。
- 对账任务按小时/天核对行数与金额；差异超过阈值会告警。
- 同一 `big_id`/`cid` 幂等写入，重复消费不会产生重复明细。
