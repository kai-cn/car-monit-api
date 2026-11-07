#pragma once
// 运维类定时任务（Java 中带 @Scheduled 的可靠性与监控服务）。
//
// 对应 Java 类：
//   DataLossDetectionService#scheduledDetection          （每 detection.interval-minutes 分钟）
//   DataReliabilityService#compensationTask              （每 reliability.compensation-interval-seconds 秒）
//   DataReliabilityService#checkOfflineDevices           （每 5 分钟）
//   DelayMonitoringService#generateStatsReport           （每 10 分钟）
//   GaussEsConsistencyService#scheduledReconcile         （cron，默认关闭）
//
// Java 中这些方法把实际工作提交到线程池执行（CompletableFuture/ExecutorService）；
// C++ 侧由 scheduler 在独立线程中调用，语义等价（不阻塞调度线程）。
#include <string>

namespace cm::service::ops {

void data_loss_detection_tick();
void reliability_compensation_tick();
void device_offline_check_tick();
void delay_stats_report_tick();
void gauss_es_consistency_tick();

// DataLossDetectionService#recordReportedMessage：消费端每收到一条上报就登记，
// 供周期性检测比对“上报数 vs 入库数”。
void record_reported_message(const std::string& message_id, const std::string& device_id,
                             long long timestamp_ms);

// DataReliabilityService#updateDeviceHeartbeat
void update_device_heartbeat(const std::string& device_id);

} // namespace cm::service::ops
