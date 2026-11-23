package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataTrailTracksMapper.java
// 类/职责: ZdataTrailTracksMapper — 表 zdata_trail_tracks 的数据访问入口
// 对应 Go 文件: internal/repo/zdata_trail_tracks.go
// 关键映射:
//   extends BaseMapper<ZdataTrailTracks>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectZdataTrailTracksById(Uuid)   → GetByID
//   selectZdataTrailTracksList(ZdataTrailTracks q) → List/Count（条件见 applyZdataTrailTracksFilters）
// DIFF: Java 用 XML/注解把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。
// PARITY: 本 Mapper 的 XML 存在（base/mapper/xml/ZdataTrailTracksMapper.xml），
//         getHistoryTrail 已按 XML 逐条对齐；其余 BaseMapper 的 selectList 仍按字段语义重建
//         （code → 精确，时间 → 区间）。

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// ZdataTrailTracksTable 对应 Java @TableName(value = 'zdata_trail_tracks', schema = None)
const ZdataTrailTracksTable = "jl_data01.zdata_trail_tracks"

// ZdataTrailTracksHistoryTable 对应 ZdataTrailTracksMapper.xml:138 的 `from jl_data01.zdata_trail_fitting t`。
//
// PARITY: getHistoryTrail 是手写 SQL，它查的是 jl_data01.zdata_trail_fitting，
// 而 BaseMapper 的 CRUD 走的是 @TableName 上的 zdata_trail_tracks —— 两者不是同一张表。
// 这里保留 XML 里的 schema 前缀：JDBC URL 没有配 currentSchema，去掉前缀会落到 public。
const ZdataTrailTracksHistoryTable = "jl_data01.zdata_trail_fitting"

// historyTrailColumns 对应 XML:117-137 的 select 列表。
//
// historyTrailColumns 对应 ZdataTrailTracksMapper.xml:117-136 的 20 列投影。
//
// 背景（两轮修正）：这里原来只选 5 列，理由写在旧注释里 ——
// 那 15 列在 Java 实体上是 @TableField(exist=false)、Go 模型对应 gorm:"-"，
// 而下游 BuildTrailInfos / ChangeData 也只用这 5 个。
// 但**响应体**要用：Java 会把它们随 tracks 一起返回，实测
// carTrackQueryByTime 的 94/94 个车牌共 2162 个字段值在 Go 侧是 null
// （enaxlecount / entollstationname / exweight / startLonDec …）。
//
// 不能直接去掉模型上的 gorm:"-"：这 15 列只存在于 zdata_trail_fitting（20 列），
// zdata_trail_tracks 只有 10 列，去掉会让 /base/trailtracks/list 那条 SQL 直接报列不存在。
// 所以改成：历史查询用 historyTrailRow 这个专用投影结构体接收，再逐字段拷进模型。
const historyTrailColumns = "cid AS uuid, envehicleid AS plate_key, " +
	"enaxlecount, entolllaneid, entollstationid, entollstationname, " +
	"envehicleclass, envehicleid, envehicletype, enweight, " +
	"entime AS enter_time, extime AS exit_time, " +
	"extolllaneid, extollstationid, extollstationname, " +
	"exvehicleclass, exvehicleid, exvehicletype, exweight, " +
	"trailpoints AS trail_points"

// historyTrailRow 是 zdata_trail_fitting 的 20 列投影接收器。
// 与 model.ZdataTrailTracks 的差别只在 gorm tag：这里的 15 列要真的从库里回填。
type historyTrailRow struct {
	Uuid              *string         `gorm:"column:uuid"`
	PlateKey          *string         `gorm:"column:plate_key"`
	EnterTime         *model.DateTime `gorm:"column:enter_time"`
	ExitTime          *model.DateTime `gorm:"column:exit_time"`
	TrailPoints       *string         `gorm:"column:trail_points"`
	Enaxlecount       *int            `gorm:"column:enaxlecount"`
	Entolllaneid      *string         `gorm:"column:entolllaneid"`
	Entollstationid   *string         `gorm:"column:entollstationid"`
	Entollstationname *string         `gorm:"column:entollstationname"`
	Envehicleclass    *string         `gorm:"column:envehicleclass"`
	Envehicleid       *string         `gorm:"column:envehicleid"`
	Envehicletype     *string         `gorm:"column:envehicletype"`
	Enweight          *float64        `gorm:"column:enweight"`
	Extolllaneid      *string         `gorm:"column:extolllaneid"`
	Extollstationid   *string         `gorm:"column:extollstationid"`
	Extollstationname *string         `gorm:"column:extollstationname"`
	Exvehicleclass    *string         `gorm:"column:exvehicleclass"`
	Exvehicleid       *string         `gorm:"column:exvehicleid"`
	Exvehicletype     *string         `gorm:"column:exvehicletype"`
	Exweight          *float64        `gorm:"column:exweight"`
}

// toModel 把投影结果落回模型对象。模型上那 15 个字段虽然是 gorm:"-"（不参与 SQL），
// 但仍然参与 JSON 输出，所以必须显式拷。
func (h historyTrailRow) toModel() model.ZdataTrailTracks {
	m := model.ZdataTrailTracks{
		Uuid: h.Uuid, PlateKey: h.PlateKey,
		EnterTime: h.EnterTime, ExitTime: h.ExitTime, TrailPoints: h.TrailPoints,
	}
	m.Enaxlecount = h.Enaxlecount
	m.Entolllaneid = h.Entolllaneid
	m.Entollstationid = h.Entollstationid
	m.Entollstationname = h.Entollstationname
	m.Envehicleclass = h.Envehicleclass
	m.Envehicleid = h.Envehicleid
	m.Envehicletype = h.Envehicletype
	m.Enweight = h.Enweight
	m.Extolllaneid = h.Extolllaneid
	m.Extollstationid = h.Extollstationid
	m.Extollstationname = h.Extollstationname
	m.Exvehicleclass = h.Exvehicleclass
	m.Exvehicleid = h.Exvehicleid
	m.Exvehicletype = h.Exvehicletype
	m.Exweight = h.Exweight
	return m
}

// ZdataTrailTracksRepo 对应 Java 的 ZdataTrailTracksMapper（@Repository 由 main() 里的显式构造代替）
type ZdataTrailTracksRepo struct{ db *db.Client }

// NewZdataTrailTracksRepo 对应 Spring @Repository 的 Bean 注册
func NewZdataTrailTracksRepo(c *db.Client) *ZdataTrailTracksRepo { return &ZdataTrailTracksRepo{db: c} }

// TableName 供测试与日志使用
func (r *ZdataTrailTracksRepo) TableName() string { return ZdataTrailTracksTable }

// GetByID 对应 ZdataTrailTracksMapper.selectZdataTrailTracksById(Uuid)
func (r *ZdataTrailTracksRepo) GetByID(ctx context.Context, id string) (*model.ZdataTrailTracks, error) {
	var m model.ZdataTrailTracks
	err := r.db.ORM(ctx).Table(ZdataTrailTracksTable).Where("uuid = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("ZdataTrailTracksRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 ZdataTrailTracksMapper.selectZdataTrailTracksList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *ZdataTrailTracksRepo) List(ctx context.Context, q *model.ZdataTrailTracks, limit int) ([]model.ZdataTrailTracks, error) {
	tx := applyZdataTrailTracksFilters(r.db.ORM(ctx).Table(ZdataTrailTracksTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.ZdataTrailTracks
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailTracksRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectZdataTrailTracksList 配合 PageInfo#getTotal
func (r *ZdataTrailTracksRepo) Count(ctx context.Context, q *model.ZdataTrailTracks) (int64, error) {
	tx := applyZdataTrailTracksFilters(r.db.ORM(ctx).Table(ZdataTrailTracksTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("ZdataTrailTracksRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *ZdataTrailTracksRepo) ListAll(ctx context.Context) ([]model.ZdataTrailTracks, error) {
	var list []model.ZdataTrailTracks
	if err := r.db.ORM(ctx).Table(ZdataTrailTracksTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailTracksRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *ZdataTrailTracksRepo) Insert(ctx context.Context, m *model.ZdataTrailTracks) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailTracksTable).Create(m).Error; err != nil {
		return fmt.Errorf("ZdataTrailTracksRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *ZdataTrailTracksRepo) BatchInsert(ctx context.Context, list []*model.ZdataTrailTracks, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(ZdataTrailTracksTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *ZdataTrailTracksRepo) Update(ctx context.Context, m *model.ZdataTrailTracks) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailTracksTable).Save(m).Error; err != nil {
		return fmt.Errorf("ZdataTrailTracksRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *ZdataTrailTracksRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailTracksTable).Where("uuid = ?", id).Delete(&model.ZdataTrailTracks{}).Error; err != nil {
		return fmt.Errorf("ZdataTrailTracksRepo.DeleteByID: %w", err)
	}
	return nil
}

// GetHistoryTrail 对应 ZdataTrailTracksMapper.getHistoryTrail(CarParaVO)，SQL 见 XML:116-158。
//
// 关键映射:
//
//	carNo != ''                    → envehicleid = ?
//	carNoList.size() > 0          → envehicleid IN (...)
//	applyTime1 / applyTime2       → extime >= / <= to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')
//	flag = "bannian"              → extime >= now() - interval '180 days'
//	flag = "yiyue"                → extime >= now() - interval '3 days'
//	order by t.cid, t.extime      → XML:116-158 里**没有** order by（那是 getLatestTrail 的 L111），
//	                                两侧都不加排序，理由见下方 DIFF（排序）
//	pageSize                      → limit（Go 侧安全阀，Java 这条 SQL 没有 PageHelper）
//
// PARITY: `now() - interval '180 days'` / `now() - interval '3 days'` 原样保留，不在 Go 里换算成时间戳。
// XML 的注释写「默认查询半年」/「三天之前」，但 `timestamp - 整数` 在 GaussDB 里到底按天还是按秒
// 由数据库决定 —— 唯一能保证与 Java 结果一致的做法就是把这句表达式原样发下去。
// 同理，XML 的 `<if test="startNum != null"> LIMIT #{startNum} </if>`（LIMIT 绑到了 startNum）
// 是个潜在笔误，本方法的所有调用方都不传 startNum，故不复刻。
//
// DIFF: Java 的 PageHelper 通过 ThreadLocal 注入 limit/offset，Go 必须显式传 limit（0 = 不限）。
//
// DIFF（排序）：XML 没有 order by，Java 的行序由数据库物理扫描决定。
// Go 曾补过 Order("cid, extime") 想换来可复现的分页，但实测证明它会**换行而不是换序**：
// 一个车牌在 zdata_trail_fitting 里有多条轨迹记录时，加排序后 Go 选中的记录与 Java 不同，
// 整个 trailList/轨迹点都对不上（实测 carTrackQueryByTime 有 5/94 个车牌受影响）。
// 因此现在保持与 Java 一致的不加排序；代价也一致 —— 无 ORDER BY 的分页不保证翻页稳定。
func (r *ZdataTrailTracksRepo) GetHistoryTrail(ctx context.Context, vo *model.CarParaVO, limit int) ([]model.ZdataTrailTracks, error) {
	tx := applyHistoryTrailFilters(r.db.ORM(ctx).Table(ZdataTrailTracksHistoryTable), vo).
		Select(historyTrailColumns)

	// 排序：XML 的 getHistoryTrail 没有 order by，Java 靠数据库物理扫描顺序选行。
	// Go 之前补了 Order("cid, extime")，看似更稳，实际会**换行**：同一车牌在
	// zdata_trail_fitting 里有多条记录时，Java 给 cid=39259e80…（10-01 那条）、
	// Go 给 cid=0a1736ee…（10-02 那条，因为 '0'<'3' 排在前面），
	// 连带 trailList 的整串轨迹点都不同 —— 实测 /base/sysutil/carTrackQueryByTime
	// 有 5 个车牌因此内容不一致。为保持与基准一致，这里不再补排序。
	// 代价与 Java 相同：没有 ORDER BY 的分页本身不保证翻页稳定。
	if limit <= 0 && vo != nil && vo.PageSize != nil && *vo.PageSize > 0 {
		limit = *vo.PageSize
	}
	if limit > 0 {
		tx = tx.Limit(limit)
	}

	var raw []historyTrailRow
	if err := tx.Find(&raw).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailTracksRepo.GetHistoryTrail: %w", err)
	}
	list := make([]model.ZdataTrailTracks, 0, len(raw))
	for _, row := range raw {
		list = append(list, row.toModel())
	}
	return list, nil
}

// CountHistoryTrail 是与 GetHistoryTrail 同谓词的行数，对应 PageHelper 给
// `new PageInfo(list).getTotal()` 自动生成的 count 查询。
//
// PARITY: Java 的两个轨迹接口都先 startPage()，PageHelper 会用同一套 WHERE 跑一次
// `select count(*)`，所以响应里的 total 是**全量命中数**，不是本页行数。
// Go 此前用 len(rows) 当 total，实测 /base/sysutil/carTrackQueryByTime?pageNum=1&pageSize=5
// 两端 total = 112 vs 5；越界页（pageNum=999）也没有 total 可回夹，Java 给末页 2 行、Go 给 0 行。
//
// 计数必须与取数共用 applyHistoryTrailFilters：两处谓词各自演化就是 P-FILT-1 的成因
// （`?type=0` 在 Go 被静默丢掉，返回未过滤全量集）。
func (r *ZdataTrailTracksRepo) CountHistoryTrail(ctx context.Context, vo *model.CarParaVO) (int64, error) {
	var n int64
	tx := applyHistoryTrailFilters(r.db.ORM(ctx).Table(ZdataTrailTracksHistoryTable), vo)
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("ZdataTrailTracksRepo.CountHistoryTrail: %w", err)
	}
	return n, nil
}

// applyHistoryTrailFilters 重建 XML:139-156 的 <where> 块。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyHistoryTrailFilters(tx *gorm.DB, vo *model.CarParaVO) *gorm.DB {
	if vo == nil {
		return tx
	}
	// 车牌：Java 的 XML:140 与 XML:151 是**两个独立的 <if>**，两者都传时是 AND 关系。
	// Go 之前写成 if/else if，等于「有 carNoList 就忽略 carNo」，调用方同时传两者时结果会变大。
	if utils.IsNotBlank(vo.CarNo) {
		tx = tx.Where("envehicleid = ?", vo.CarNo)
	}
	if len(vo.CarNoList) > 0 {
		tx = tx.Where("envehicleid IN ?", vo.CarNoList)
	}
	// 时间区间：Java 直接把这些字符串塞进 to_timestamp，Go 侧不解析，避免时区/精度漂移
	if utils.IsNotBlank(vo.ApplyTime1) {
		tx = tx.Where("extime >= to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')", vo.ApplyTime1)
	}
	if utils.IsNotBlank(vo.ApplyTime2) {
		tx = tx.Where("extime <= to_timestamp(?, 'yyyy-mm-dd HH24:MI:SS')", vo.ApplyTime2)
	}
	// 相对时间窗：XML:144-150
	//
	// PARITY: Java 这两个分支都是**双边**条件（`extime >= now() - interval '180 days' and extime <= now()`）。
	// Go 之前只有下界，于是 extime 落在未来的行会被多带出来。
	// `now() - interval '180 days'` 的字面写法保留（不按天/秒自行换算），理由见 GetHistoryTrail 的 PARITY 注释。
	switch vo.Flag {
	case "bannian":
		tx = tx.Where("extime >= now() - interval '180 days'").Where("extime <= now()")
	case "yiyue":
		tx = tx.Where("extime >= now() - interval '3 days'").Where("extime <= now()")
	default:
		if vo.Flag != "" {
			slog.Warn("[轨迹查询] flag 不在 XML 的两个分支内，未参与 SQL", "flag", vo.Flag)
		}
	}
	return tx
}

// applyZdataTrailTracksFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
//
// PARITY: 这里必须覆盖 XML:37-43 的全部 7 项。此前只做了 uuid 与两个进出位置编码
// （后两项并不属于 list 查询），导致 ?type=0 / ?pointCount=45 / ?plateKey=赣CEA826
// 这些条件在 Go 上被静默丢掉，返回的是未过滤的全量集（实测 total 1379 vs Java 879）。
// 数字类型用 != nil 判定而不是 != 0 —— Java 的 <if test="type != null"> 允许 0 作为有效条件。
//
// enterTime / exitTime（XML:41-42）依赖 handler 的日期绑定；解析失败时字段留 nil，
// 这里就不过滤 —— 与 Java「绑不上就当没传」的行为一致（实测 ?enterTime=not-a-date 两端都返回全量）。
func applyZdataTrailTracksFilters(tx *gorm.DB, q *model.ZdataTrailTracks) *gorm.DB {
	if q == nil {
		return tx
	}
	if model.NonEmpty(q.Uuid) {
		tx = tx.Where("uuid = ?", q.Uuid)
	}
	if q.Type != nil {
		tx = tx.Where("type = ?", *q.Type)
	}
	if q.PointCount != nil {
		tx = tx.Where("point_count = ?", *q.PointCount)
	}
	if model.NonEmpty(q.PlateKey) {
		tx = tx.Where("plate_key = ?", *q.PlateKey)
	}
	if model.NonEmpty(q.TrailPoints) {
		tx = tx.Where("trail_points = ?", *q.TrailPoints)
	}
	// 日期条件：绑定器现在支持 DateTime，解析失败会留 nil（等于不过滤），与 Java 一致
	if q.EnterTime != nil {
		tx = tx.Where("enter_time = ?", time.Time(*q.EnterTime))
	}
	if q.ExitTime != nil {
		tx = tx.Where("exit_time = ?", time.Time(*q.ExitTime))
	}
	if model.NonEmpty(q.EnterLocationcode) {
		tx = tx.Where("enter_locationcode = ?", q.EnterLocationcode)
	}
	if model.NonEmpty(q.ExitLocationcode) {
		tx = tx.Where("exit_locationcode = ?", q.ExitLocationcode)
	}
	return tx
}
