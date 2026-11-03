package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.java
// 类/职责: OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper — 表 ods_rt_szdn_snapshot_flow_stationcapture_addcode 的数据访问入口
// 对应 Go 文件: internal/repo/ods_rt_szdn_snapshot_flow_stationcapture_addcode.go
// 关键映射:
//   extends BaseMapper<OdsRtSzdnSnapshotFlowStationcaptureAddcode>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(BigId)   → GetByID
//   selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(OdsRtSzdnSnapshotFlowStationcaptureAddcode q) → List/Count（条件见 applyOdsRtSzdnSnapshotFlowStationcaptureAddcodeFilters）
// DIFF: Java 用 XML/注解把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。
// PARITY: selectList 的实际 SQL 以 XML 为准，本文件的过滤条件由 _probe_go/genfilters.py
//         从 XML 的 <if> 列表逐条生成（标记见函数内 BEGIN/END generated-from-XML）。
//         注意：XML 不在 resources/mapper/xml/，而在
//         pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/ —— 早先一次迁移因为
//         只翻了 resources 目录就断定「XML 缺失」，改成按字段名猜，猜错了运算符和列集合。

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable 对应 Java @TableName(value = 'ods_rt_szdn_snapshot_flow_stationcapture_addcode', schema = None)
const OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable = "jl_data01.ods_rt_szdn_snapshot_flow_stationcapture_addcode"

// OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo 对应 Java 的 OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper（@Repository 由 main() 里的显式构造代替）
type OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo struct{ db *db.Client }

// NewOdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo(c *db.Client) *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo {
	return &OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) TableName() string {
	return OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable
}

// GetByID 对应 OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(BigId)
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) GetByID(ctx context.Context, id string) (*model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, error) {
	var m model.OdsRtSzdnSnapshotFlowStationcaptureAddcode
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) List(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, limit int) ([]model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, error) {
	tx := applyOdsRtSzdnSnapshotFlowStationcaptureAddcodeFilters(r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsRtSzdnSnapshotFlowStationcaptureAddcode
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList 配合 PageInfo#getTotal
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) Count(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode) (int64, error) {
	tx := applyOdsRtSzdnSnapshotFlowStationcaptureAddcodeFilters(r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) ListAll(ctx context.Context) ([]model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, error) {
	var list []model.OdsRtSzdnSnapshotFlowStationcaptureAddcode
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) Insert(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) BatchInsert(ctx context.Context, list []*model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) Update(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Where("big_id = ?", id).Delete(&model.OdsRtSzdnSnapshotFlowStationcaptureAddcode{}).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsRtSzdnSnapshotFlowStationcaptureAddcodeFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsRtSzdnSnapshotFlowStationcaptureAddcodeFilters(tx *gorm.DB, q *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null">
	if q.BigId != nil {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="datasource != null and datasource != ''">
	if model.NonEmpty(q.Datasource) {
		tx = tx.Where("datasource = ?", q.Datasource)
	}
	// XML <if test="cameratype != null and cameratype != ''">
	if model.NonEmpty(q.Cameratype) {
		tx = tx.Where("cameratype = ?", q.Cameratype)
	}
	// XML <if test="deviceid != null and deviceid != ''">
	if model.NonEmpty(q.Deviceid) {
		tx = tx.Where("deviceid = ?", q.Deviceid)
	}
	// XML <if test="deviceip != null and deviceip != ''">
	if model.NonEmpty(q.Deviceip) {
		tx = tx.Where("deviceip = ?", q.Deviceip)
	}
	// XML <if test="tollcode != null and tollcode != ''">
	if model.NonEmpty(q.Tollcode) {
		tx = tx.Where("tollcode = ?", q.Tollcode)
	}
	// XML <if test="tollname != null and tollname != ''">
	if model.NonEmpty(q.Tollname) {
		tx = tx.Where("tollname like ?", "%"+model.Val(q.Tollname)+"%")
	}
	// XML <if test="orgcode != null">
	if q.Orgcode != nil {
		tx = tx.Where("orgcode = ?", q.Orgcode)
	}
	// XML <if test="siteid != null">
	if q.Siteid != nil {
		tx = tx.Where("siteid = ?", q.Siteid)
	}
	// XML <if test="laneid != null">
	if q.Laneid != nil {
		tx = tx.Where("laneid = ?", q.Laneid)
	}
	// XML <if test="snapshottimeunix != null">
	if q.Snapshottimeunix != nil {
		tx = tx.Where("snapshottimeunix = ?", q.Snapshottimeunix)
	}
	// XML <if test="snapshottime != null">
	if q.Snapshottime != nil {
		tx = tx.Where("snapshottime = ?", q.Snapshottime)
	}
	// XML <if test="receivedtimeunix != null">
	if q.Receivedtimeunix != nil {
		tx = tx.Where("receivedtimeunix = ?", q.Receivedtimeunix)
	}
	// XML <if test="receivedtime != null">
	if q.Receivedtime != nil {
		tx = tx.Where("receivedtime = ?", q.Receivedtime)
	}
	// XML <if test="platenumber != null and platenumber != ''">
	if model.NonEmpty(q.Platenumber) {
		tx = tx.Where("platenumber = ?", q.Platenumber)
	}
	// XML <if test="platecolorcode != null">
	if q.Platecolorcode != nil {
		tx = tx.Where("platecolorcode = ?", q.Platecolorcode)
	}
	// XML <if test="platecolor != null and platecolor != ''">
	if model.NonEmpty(q.Platecolor) {
		tx = tx.Where("platecolor = ?", q.Platecolor)
	}
	// XML <if test="platetypecode != null">
	if q.Platetypecode != nil {
		tx = tx.Where("platetypecode = ?", q.Platetypecode)
	}
	// XML <if test="platetype != null and platetype != ''">
	if model.NonEmpty(q.Platetype) {
		tx = tx.Where("platetype = ?", q.Platetype)
	}
	// XML <if test="plateconfidence != null">
	if q.Plateconfidence != nil {
		tx = tx.Where("plateconfidence = ?", q.Plateconfidence)
	}
	// XML <if test="carbrand != null and carbrand != ''">
	if model.NonEmpty(q.Carbrand) {
		tx = tx.Where("carbrand = ?", q.Carbrand)
	}
	// XML <if test="carcolorcode != null">
	if q.Carcolorcode != nil {
		tx = tx.Where("carcolorcode = ?", q.Carcolorcode)
	}
	// XML <if test="carcolor != null and carcolor != ''">
	if model.NonEmpty(q.Carcolor) {
		tx = tx.Where("carcolor = ?", q.Carcolor)
	}
	// XML <if test="cartypecode != null">
	if q.Cartypecode != nil {
		tx = tx.Where("cartypecode = ?", q.Cartypecode)
	}
	// XML <if test="cartype != null and cartype != ''">
	if model.NonEmpty(q.Cartype) {
		tx = tx.Where("cartype = ?", q.Cartype)
	}
	// XML <if test="cardirectioncode != null">
	if q.Cardirectioncode != nil {
		tx = tx.Where("cardirectioncode = ?", q.Cardirectioncode)
	}
	// XML <if test="cardirection != null and cardirection != ''">
	if model.NonEmpty(q.Cardirection) {
		tx = tx.Where("cardirection = ?", q.Cardirection)
	}
	// XML <if test="snappicturepath != null and snappicturepath != ''">
	if model.NonEmpty(q.Snappicturepath) {
		tx = tx.Where("snappicturepath = ?", q.Snappicturepath)
	}
	// XML <if test="loadtime != null">
	if q.Loadtime != nil {
		tx = tx.Where("loadtime = ?", q.Loadtime)
	}
	// XML <if test="gradelevel != null">
	if q.Gradelevel != nil {
		tx = tx.Where("gradelevel = ?", q.Gradelevel)
	}
	// XML <if test="datauuid != null and datauuid != ''">
	if model.NonEmpty(q.Datauuid) {
		tx = tx.Where("datauuid = ?", q.Datauuid)
	}
	// XML <if test="maindirection != null and maindirection != ''">
	if model.NonEmpty(q.Maindirection) {
		tx = tx.Where("maindirection = ?", q.Maindirection)
	}
	// XML <if test="maindirectionname != null and maindirectionname != ''">
	if model.NonEmpty(q.Maindirectionname) {
		tx = tx.Where("maindirectionname like ?", "%"+model.Val(q.Maindirectionname)+"%")
	}
	// XML <if test="reserve3 != null and reserve3 != ''">
	if model.NonEmpty(q.Reserve3) {
		tx = tx.Where("reserve3 = ?", q.Reserve3)
	}
	// XML <if test="applyTime1 != null and applyTime1 != ''">
	if model.NonEmpty(q.ApplyTime1) {
		tx = tx.Where("snapshottime >= ?", q.ApplyTime1)
	}
	// XML <if test="applyTime2 != null and applyTime2 != ''">
	if model.NonEmpty(q.ApplyTime2) {
		tx = tx.Where("snapshottime <= ?", q.ApplyTime2)
	}
	// ---- END generated-from-XML ----
	return tx
}
