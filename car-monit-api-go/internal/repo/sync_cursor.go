package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeRecords01Mapper.java:selectByCursorShard
//           pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataTrailFittingMapper.java:selectByCursorShard
// 类/职责: 收费流水 / 车辆轨迹的 keyset（游标）分页读取 —— GaussDB → ES 同步的读取端
// 对应 Go 文件: internal/repo/sync_cursor.go
// 关键映射:
//   selectByCursorShard(start,end,cursorTime,cursorUuid,limit) → ListByCursorShard
//   @Param 命名参数绑定                                        → ? 位置参数（顺序即 SQL 出现顺序）
//
// 说明：与 snapshot_flow_cursor.go 同属**手写**文件，重新运行 tools/gen_repos.py 不会覆盖。
//
// PARITY（半开区间）: 三个 selectByCursorShard 的 XML 都把区间写成
//
//	t.<time> >= to_timestamp(#{startTime},...)  AND  t.<time> < to_timestamp(#{endTime},...)
//
// 即 **[start, end)**，不是闭区间。上一版 Go 写成了 `<=`，会把每个分片的最后一行
// 与下一个分片的第一行重复读出——对游标同步而言就是同一条流水被写两次 ES。
// 这里统一改成 `<`，与 XML 逐字对齐。
//
// DIFF（时间入参）: XML 把字符串显式交给 to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')；
// Go 直接传字符串，由 GaussDB 做隐式转换。调用方约定的入参格式本就是 'yyyy-MM-dd HH:mm:ss'，
// 两种写法结果一致；不在这里再包一层 to_timestamp，是为了让 SQL 保持可读、便于抓取慢日志时对照。

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// ListByCursorShard 对应 OdsLwzxsfsjFeeRecords01Mapper.selectByCursorShard。
//
// 游标键是 (transtime, big_id)：收费流水的 transtime 精确到秒，同秒多车是常态，
// 只用时间做游标会漏数据，所以必须带第二排序键 big_id（Java 侧 cursorUuid 参数即此意）。
func (r *OdsLwzxsfsjFeeRecords01Repo) ListByCursorShard(ctx context.Context,
	startTime, endTime, cursorTime, cursorUUID string, limit int) ([]model.OdsLwzxsfsjFeeRecords01, error) {

	if limit <= 0 {
		limit = 2000
	}
	sql := "SELECT * FROM " + OdsLwzxsfsjFeeRecords01Table + " WHERE 1 = 1"
	args := make([]any, 0, 6)
	if startTime != "" {
		sql += " AND transtime >= ?"
		args = append(args, startTime)
	}
	if endTime != "" {
		sql += " AND transtime < ?"
		args = append(args, endTime)
	}
	if cursorTime != "" {
		if cursorUUID != "" {
			sql += " AND (transtime, big_id) > (?, ?)"
			args = append(args, cursorTime, cursorUUID)
		} else {
			sql += " AND transtime > ?"
			args = append(args, cursorTime)
		}
	}
	sql += " ORDER BY transtime ASC, big_id ASC LIMIT ?"
	args = append(args, limit)

	var list []model.OdsLwzxsfsjFeeRecords01
	if err := r.db.ORM(ctx).Raw(sql, args...).Scan(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.ListByCursorShard: %w", err)
	}
	return list, nil
}

// ListByCursorShard 对应 ZdataTrailFittingMapper.selectByCursorShard（主键 cid，时间 extime）。
func (r *ZdataTrailFittingRepo) ListByCursorShard(ctx context.Context,
	startTime, endTime, cursorTime, cursorUUID string, limit int) ([]model.ZdataTrailFitting, error) {

	if limit <= 0 {
		limit = 2000
	}
	sql := "SELECT * FROM " + ZdataTrailFittingTable + " WHERE 1 = 1"
	args := make([]any, 0, 6)
	if startTime != "" {
		sql += " AND extime >= ?"
		args = append(args, startTime)
	}
	if endTime != "" {
		sql += " AND extime < ?"
		args = append(args, endTime)
	}
	if cursorTime != "" {
		if cursorUUID != "" {
			sql += " AND (extime, cid) > (?, ?)"
			args = append(args, cursorTime, cursorUUID)
		} else {
			sql += " AND extime > ?"
			args = append(args, cursorTime)
		}
	}
	sql += " ORDER BY extime ASC, cid ASC LIMIT ?"
	args = append(args, limit)

	var list []model.ZdataTrailFitting
	if err := r.db.ORM(ctx).Raw(sql, args...).Scan(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailFittingRepo.ListByCursorShard: %w", err)
	}
	return list, nil
}

// CountBetween 对应 GaussEsConsistencyService.countInGaussDb（MyBatis-Plus selectCount + between）。
//
// DIFF: Java 用 QueryWrapper<Entity>().between(...) 生成 SQL；
// Go 侧手写 COUNT(*) 并把时间列名、区间作为参数——列名来自固定常量，不接受外部输入。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) CountBetween(ctx context.Context, start, end string) (int64, error) {
	return countBetween(ctx, r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable), "snapshottime", start, end)
}

// CountBetween 对应收费流水的对账计数
func (r *OdsLwzxsfsjFeeRecords01Repo) CountBetween(ctx context.Context, start, end string) (int64, error) {
	return countBetween(ctx, r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table), "transtime", start, end)
}

// CountBetween 对应轨迹表的对账计数
func (r *ZdataTrailFittingRepo) CountBetween(ctx context.Context, start, end string) (int64, error) {
	return countBetween(ctx, r.db.ORM(ctx).Table(ZdataTrailFittingTable), "extime", start, end)
}

// countBetween 是三个 CountBetween 的公共实现。
//
// PARITY: Java 的 QueryWrapper.between 是闭区间 [start, end]，这里同样用 BETWEEN（闭区间），
// 保证对账数字与既有报表一致；按月切片时边界那一条会被相邻两个月各算一次，属已知偏差。
func countBetween(ctx context.Context, tx *gorm.DB, column, start, end string) (int64, error) {
	if column == "" {
		return 0, fmt.Errorf("countBetween: 列名不能为空")
	}
	var n int64
	err := tx.WithContext(ctx).Where(column+" BETWEEN ? AND ?", start, end).Count(&n).Error
	if err != nil {
		return 0, fmt.Errorf("countBetween(%s): %w", column, err)
	}
	return n, nil
}
