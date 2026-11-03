package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowAddcodeMapper.java:44-72
// 类/职责: 门架抓拍流水的游标分页 / 最大快照时间查询（Mapper 上的 @Param + @Select 方法）
// 对应 Go 文件: internal/repo/snapshot_flow_cursor.go
// 关键映射:
//   selectByCursorShard(start,end,cursorTime,cursorUuid,limit) → ListByCursorShard
//   @Select("SELECT COALESCE(MAX(snapshottime), NOW()) ...")   → MaxSnapshotTime
//
// 说明：本文件是**手写**而非生成。原因是这两个方法在 Java 侧带显式 SQL 语义（游标/聚合），
// 生成器无法推断；放在独立文件里，重新运行 tools/gen_repos.py 也不会被覆盖。
//
// PARITY（半开区间）: XML:205-206 是 `snapshottime >= start AND snapshottime < end`，
// 即 **[start, end)**。Go 侧上一版写成 `<=`，相邻分片会在边界那一条上重叠，
// 导致同一 datauuid 被重复读入；现改为 `<` 与 XML 对齐（另两份游标 SQL 同此处理，见 sync_cursor.go）。

import (
	"context"
	"fmt"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// ListByCursorShard 对应 selectByCursorShard：按 (snapshottime, datauuid) 复合游标向后翻页。
//
// PARITY: 投影必须按 XML L196-202 那 37 列写，不能用 SELECT *。
// XML 没选的 datasource / siteid / laneid / plateconfidence / carcolorcode / reserve3
// 在 Java 同步任务里就是 null，写进 ES 文档里也不会出现这个字段；Go 用 * 会多灌 6 个字段，
// 两边同步出来的 ES 文档结构就不一样。
//
// DIFF: Java 用 @Param 命名参数绑定；Go 用 ? 占位符 + 位置参数，顺序即 SQL 中出现的顺序。
// 复合游标（时间可能重复）必须带上第二排序键，否则同秒数据会被跳过——这正是 Java 侧传入 cursorUuid 的原因。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListByCursorShard(ctx context.Context,
	startTime, endTime, cursorTime, cursorUUID string, limit int) ([]model.OdsRtSzdnSnapshotFlowAddcode, error) {

	if limit <= 0 {
		limit = 500
	}
	// 注意要给表加上别名 t：上面的投影列全部带 t. 前缀（照拄 XML），PG 里没定义 t 这个别名会直接报错。
	sql := "SELECT " + snapshotFlowCursorCols + " FROM " + OdsRtSzdnSnapshotFlowAddcodeTable +
		" t WHERE 1 = 1"
	args := make([]any, 0, 6)
	if startTime != "" {
		sql += " AND t.snapshottime >= ?"
		args = append(args, startTime)
	}
	if endTime != "" {
		sql += " AND t.snapshottime < ?"
		args = append(args, endTime)
	}
	if cursorTime != "" {
		if cursorUUID != "" {
			sql += " AND (t.snapshottime, t.datauuid) > (?, ?)"
			args = append(args, cursorTime, cursorUUID)
		} else {
			sql += " AND t.snapshottime > ?"
			args = append(args, cursorTime)
		}
	}
	sql += " ORDER BY t.snapshottime ASC, t.datauuid ASC LIMIT ?"
	args = append(args, limit)

	var list []model.OdsRtSzdnSnapshotFlowAddcode
	if err := r.db.ORM(ctx).Raw(sql, args...).Scan(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListByCursorShard: %w", err)
	}
	return list, nil
}

// snapshotFlowCursorCols 对应 XML selectByCursorShard 里手写的 37 列（L196-202，去掉 t. 前缀）。
const snapshotFlowCursorCols = `t.big_id, t.datauuid, t.gantrycode, t.gantryname, t.roadcode, t.roadname,
	t.sectioncode, t.sectionname, t.tollcode, t.tollname, t.orgcode, t.orgname,
	t.platenumber, t.platecolor, t.platecolorcode, t.platetypecode, t.platetype,
	t.carbrand, t.carcolor, t.cartypecode, t.cartype, t.cardirection,
	t.snapshottime, t.snapshottimeunix, t.hexcode, t.pileno, t.lon, t.lat,
	t.direction, t.deviceid, t.deviceip, t.gradelevel, t.loadtime, t.cameratype,
	t.snappicturepath, t.receivedtimeunix, t.receivedtime`

// MaxSnapshotTime 对应 getMaxSnapshotTime()（Java 用 @Select 注解写在 Mapper 接口上）。
//
// DIFF: Java 返回 java.util.Date，SQL 里用 COALESCE(..., NOW()) 保证非空；
// Go 侧对应 COALESCE(..., now())，返回 time.Time（非指针，语义等价于"必有一个值"）。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) MaxSnapshotTime(ctx context.Context) (time.Time, error) {
	var t time.Time
	sql := "SELECT COALESCE(MAX(snapshottime), now()) FROM " + OdsRtSzdnSnapshotFlowAddcodeTable
	if err := r.db.ORM(ctx).Raw(sql).Scan(&t).Error; err != nil {
		return time.Time{}, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.MaxSnapshotTime: %w", err)
	}
	return t, nil
}
