#pragma once
// SnapshotFlowSyncService（Java: com.ruoyi.base.service.impl.SnapshotFlowSyncService）
//
// Java 在 @PostConstruct 中创建固定大小 2 的线程池：
//   * full-sync-enabled=true 时提交 fullSync()（按 big_id 游标全量推送）
//   * 始终提交 incrementalSync()（按 snapshottime 时间窗口增量推送）
// C++ 侧在启动时创建两条后台线程复现同样行为，不阻塞启动。
namespace cm::service {

void start_snapshot_flow_sync();
// 优雅停机：停止两条同步线程并 join（对应 Java @PreDestroy 的 shutdownNow 语义）。
void stop_snapshot_flow_sync();

} // namespace cm::service
