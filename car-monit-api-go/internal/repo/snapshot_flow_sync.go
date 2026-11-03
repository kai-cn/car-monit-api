package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowSyncService.java:63-175
//           pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataLossDetectionService.java:234-239
// 类/职责: 快照流水的三种"同步/检测"查询——按 big_id 全量续传、按 snapshottime 增量窗口、按时间窗取主键集合
// 对应 Go 文件: internal/repo/snapshot_flow_sync.go
// 关键映射:
//   LambdaQueryWrapper.gt(bigId, lastSyncId).orderByAsc(bigId).last("LIMIT n") → ListByBigIDAfter
//   LambdaQueryWrapper.gt(snapshottime, last).le(snapshottime, now).orderByAsc(snapshottime) → ListIncrementalBySnapshotTime
//   wrapper.between(snapshottime, start, end).select(bigId)                    → ListBigIDsBetween
//
// 说明：Java 侧这三处都写在 Service 里用 QueryWrapper 拼，没有 Mapper 方法；
// Go 侧统一下沉到 repo —— 理由是"凑 SQL 的地方越少越好"，Service 只表达业务意图。
//
// PARITY: Java 的 LIMIT 用 wrapper.last("LIMIT " + batchSize) 拼接字符串，
// batchSize 来自 @Value("${sync.batch-size:1000}")；Go 侧用占位符绑定，杜绝拼接注入面。

import (
	"context"
	"fmt"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// ListByBigIDAfter 对应 SnapshotFlowSyncService.fullSync() 的查询：
// big_id > lastSyncID，按 big_id 升序，取 limit 条（主键 keyset 翻页，O(1) 定位）。
//
// DIFF: lastSyncID 为空表示首次全量同步（Java 里是 `if (lastSyncId != null)` 分支），
// Go 用空串表达"没有游标"，SQL 里对应没有该条件——而不是拼一个 big_id > ”。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListByBigIDAfter(ctx context.Context,
	lastSyncID string, limit int) ([]model.OdsRtSzdnSnapshotFlowAddcode, error) {

	if limit <= 0 {
		limit = 1000
	}
	tx := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable)
	if lastSyncID != "" {
		tx = tx.Where("big_id > ?", lastSyncID)
	}
	var list []model.OdsRtSzdnSnapshotFlowAddcode
	if err := tx.Order("big_id ASC").Limit(limit).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListByBigIDAfter: %w", err)
	}
	return list, nil
}

// ListIncrementalBySnapshotTime 对应 SnapshotFlowSyncService.incrementalSync() 的查询：
// snapshottime > from 且 <= to，按 snapshottime 升序，取 limit 条。
//
// PARITY: 区间左开右闭（gt/le）与 Java 完全一致——右闭是为了"当前这一秒"的数据不被漏掉，
// 代价是边界秒可能重复投递一次；下游靠 messageId 幂等兜住（见 DataReliabilityService）。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListIncrementalBySnapshotTime(ctx context.Context,
	from, to time.Time, limit int) ([]model.OdsRtSzdnSnapshotFlowAddcode, error) {

	if limit <= 0 {
		limit = 1000
	}
	var list []model.OdsRtSzdnSnapshotFlowAddcode
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).
		Where("snapshottime > ? AND snapshottime <= ?", from, to).
		Order("snapshottime ASC").
		Limit(limit).
		Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListIncrementalBySnapshotTime: %w", err)
	}
	return list, nil
}

// ListBigIDsBetween 对应 DataLossDetectionService.queryDatabaseRecords()：
// `wrapper.between(snapshottime, start, end).select(bigId)`。
//
// DIFF: Java 查出整行实体只为拿 bigId（select 只投影一列，但对象仍是完整实体）；
// Go 直接 Scan 成 []string，省掉一个 8 亿行表的对象分配——比对逻辑要的只是主键集合。
// PARITY: between 是闭区间 [start, end]，与 Java 一致。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListBigIDsBetween(ctx context.Context,
	start, end time.Time) ([]string, error) {

	var ids []string
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).
		Where("snapshottime BETWEEN ? AND ?", start, end).
		Pluck("big_id", &ids).Error
	if err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListBigIDsBetween: %w", err)
	}
	return ids, nil
}
