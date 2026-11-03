package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeStationEnter01Mapper.java
// 类/职责: OdsLwzxsfsjFeeStationEnter01Mapper — 表 ods_lwzxsfsj_fee_station_enter_01 的数据访问入口
// 对应 Go 文件: internal/repo/ods_lwzxsfsj_fee_station_enter01.go
// 关键映射:
//   extends BaseMapper<OdsLwzxsfsjFeeStationEnter01>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsLwzxsfsjFeeStationEnter01ById(BigId)   → GetByID
//   selectOdsLwzxsfsjFeeStationEnter01List(OdsLwzxsfsjFeeStationEnter01 q) → List/Count（条件见 applyOdsLwzxsfsjFeeStationEnter01Filters）
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

// OdsLwzxsfsjFeeStationEnter01Table 对应 Java @TableName(value = 'ods_lwzxsfsj_fee_station_enter_01', schema = None)
const OdsLwzxsfsjFeeStationEnter01Table = "jl_data01.ods_lwzxsfsj_fee_station_enter_01"

// OdsLwzxsfsjFeeStationEnter01Repo 对应 Java 的 OdsLwzxsfsjFeeStationEnter01Mapper（@Repository 由 main() 里的显式构造代替）
type OdsLwzxsfsjFeeStationEnter01Repo struct{ db *db.Client }

// NewOdsLwzxsfsjFeeStationEnter01Repo 对应 Spring @Repository 的 Bean 注册
func NewOdsLwzxsfsjFeeStationEnter01Repo(c *db.Client) *OdsLwzxsfsjFeeStationEnter01Repo {
	return &OdsLwzxsfsjFeeStationEnter01Repo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsLwzxsfsjFeeStationEnter01Repo) TableName() string {
	return OdsLwzxsfsjFeeStationEnter01Table
}

// GetByID 对应 OdsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01ById(BigId)
func (r *OdsLwzxsfsjFeeStationEnter01Repo) GetByID(ctx context.Context, id string) (*model.OdsLwzxsfsjFeeStationEnter01, error) {
	var m model.OdsLwzxsfsjFeeStationEnter01
	err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsLwzxsfsjFeeStationEnter01Mapper.selectOdsLwzxsfsjFeeStationEnter01List(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsLwzxsfsjFeeStationEnter01Repo) List(ctx context.Context, q *model.OdsLwzxsfsjFeeStationEnter01, limit int) ([]model.OdsLwzxsfsjFeeStationEnter01, error) {
	tx := applyOdsLwzxsfsjFeeStationEnter01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsLwzxsfsjFeeStationEnter01
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsLwzxsfsjFeeStationEnter01List 配合 PageInfo#getTotal
func (r *OdsLwzxsfsjFeeStationEnter01Repo) Count(ctx context.Context, q *model.OdsLwzxsfsjFeeStationEnter01) (int64, error) {
	tx := applyOdsLwzxsfsjFeeStationEnter01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsLwzxsfsjFeeStationEnter01Repo) ListAll(ctx context.Context) ([]model.OdsLwzxsfsjFeeStationEnter01, error) {
	var list []model.OdsLwzxsfsjFeeStationEnter01
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsLwzxsfsjFeeStationEnter01Repo) Insert(ctx context.Context, m *model.OdsLwzxsfsjFeeStationEnter01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).Create(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsLwzxsfsjFeeStationEnter01Repo) BatchInsert(ctx context.Context, list []*model.OdsLwzxsfsjFeeStationEnter01, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsLwzxsfsjFeeStationEnter01Repo) Update(ctx context.Context, m *model.OdsLwzxsfsjFeeStationEnter01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).Save(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsLwzxsfsjFeeStationEnter01Repo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).Where("big_id = ?", id).Delete(&model.OdsLwzxsfsjFeeStationEnter01{}).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsLwzxsfsjFeeStationEnter01Filters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsLwzxsfsjFeeStationEnter01Filters(tx *gorm.DB, q *model.OdsLwzxsfsjFeeStationEnter01) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null">
	if q.BigId != nil {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="cardid != null and cardid != ''">
	if model.NonEmpty(q.Cardid) {
		tx = tx.Where("cardid = ?", q.Cardid)
	}
	// XML <if test="electricalpercentage != null">
	if q.Electricalpercentage != nil {
		tx = tx.Where("electricalpercentage = ?", q.Electricalpercentage)
	}
	// XML <if test="enaxlecount != null">
	if q.Enaxlecount != nil {
		tx = tx.Where("enaxlecount = ?", q.Enaxlecount)
	}
	// XML <if test="entime != null">
	if q.Entime != nil {
		tx = tx.Where("entime = ?", q.Entime)
	}
	// XML <if test="entolllanehex != null and entolllanehex != ''">
	if model.NonEmpty(q.Entolllanehex) {
		tx = tx.Where("entolllanehex = ?", q.Entolllanehex)
	}
	// XML <if test="entolllaneid != null and entolllaneid != ''">
	if model.NonEmpty(q.Entolllaneid) {
		tx = tx.Where("entolllaneid = ?", q.Entolllaneid)
	}
	// XML <if test="entollstationid != null and entollstationid != ''">
	if model.NonEmpty(q.Entollstationid) {
		tx = tx.Where("entollstationid = ?", q.Entollstationid)
	}
	// XML <if test="enweight != null">
	if q.Enweight != nil {
		tx = tx.Where("enweight = ?", q.Enweight)
	}
	// XML <if test="identifyvehicleid != null and identifyvehicleid != ''">
	if model.NonEmpty(q.Identifyvehicleid) {
		tx = tx.Where("identifyvehicleid = ?", q.Identifyvehicleid)
	}
	// XML <if test="lanetype != null and lanetype != ''">
	if model.NonEmpty(q.Lanetype) {
		tx = tx.Where("lanetype = ?", q.Lanetype)
	}
	// XML <if test="mediatype != null and mediatype != ''">
	if model.NonEmpty(q.Mediatype) {
		tx = tx.Where("mediatype = ?", q.Mediatype)
	}
	// XML <if test="operid != null and operid != ''">
	if model.NonEmpty(q.Operid) {
		tx = tx.Where("operid = ?", q.Operid)
	}
	// XML <if test="operationmedia != null and operationmedia != ''">
	if model.NonEmpty(q.Operationmedia) {
		tx = tx.Where("operationmedia = ?", q.Operationmedia)
	}
	// XML <if test="params != null and params != ''">
	if model.NonEmpty(q.Params) {
		tx = tx.Where("params = ?", q.Params)
	}
	// XML <if test="passid != null and passid != ''">
	if model.NonEmpty(q.Passid) {
		tx = tx.Where("passid = ?", q.Passid)
	}
	// XML <if test="receivetime != null">
	if q.Receivetime != nil {
		tx = tx.Where("receivetime = ?", q.Receivetime)
	}
	// XML <if test="shift != null and shift != ''">
	if model.NonEmpty(q.Shift) {
		tx = tx.Where("shift = ?", q.Shift)
	}
	// XML <if test="signstatus != null and signstatus != ''">
	if model.NonEmpty(q.Signstatus) {
		tx = tx.Where("signstatus = ?", q.Signstatus)
	}
	// XML <if test="specialtype != null and specialtype != ''">
	if model.NonEmpty(q.Specialtype) {
		tx = tx.Where("specialtype = ?", q.Specialtype)
	}
	// XML <if test="tac != null and tac != ''">
	if model.NonEmpty(q.Tac) {
		tx = tx.Where("tac = ?", q.Tac)
	}
	// XML <if test="terminalno != null and terminalno != ''">
	if model.NonEmpty(q.Terminalno) {
		tx = tx.Where("terminalno = ?", q.Terminalno)
	}
	// XML <if test="terminaltransno != null and terminaltransno != ''">
	if model.NonEmpty(q.Terminaltransno) {
		tx = tx.Where("terminaltransno = ?", q.Terminaltransno)
	}
	// XML <if test="transfee != null">
	if q.Transfee != nil {
		tx = tx.Where("transfee = ?", q.Transfee)
	}
	// XML <if test="transtype != null and transtype != ''">
	if model.NonEmpty(q.Transtype) {
		tx = tx.Where("transtype = ?", q.Transtype)
	}
	// XML <if test="vcount != null">
	if q.Vcount != nil {
		tx = tx.Where("vcount = ?", q.Vcount)
	}
	// XML <if test="vehicleclass != null and vehicleclass != ''">
	if model.NonEmpty(q.Vehicleclass) {
		tx = tx.Where("vehicleclass = ?", q.Vehicleclass)
	}
	// XML <if test="vehicleid != null and vehicleid != ''">
	if model.NonEmpty(q.Vehicleid) {
		tx = tx.Where("vehicleid = ?", q.Vehicleid)
	}
	// XML <if test="vehiclesign != null and vehiclesign != ''">
	if model.NonEmpty(q.Vehiclesign) {
		tx = tx.Where("vehiclesign = ?", q.Vehiclesign)
	}
	// XML <if test="vehiclesignid != null and vehiclesignid != ''">
	if model.NonEmpty(q.Vehiclesignid) {
		tx = tx.Where("vehiclesignid = ?", q.Vehiclesignid)
	}
	// XML <if test="vehicletype != null and vehicletype != ''">
	if model.NonEmpty(q.Vehicletype) {
		tx = tx.Where("vehicletype = ?", q.Vehicletype)
	}
	// XML <if test="loadTime != null">
	if q.LoadTime != nil {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="gradeLevel != null and gradeLevel != ''">
	if model.NonEmpty(q.GradeLevel) {
		tx = tx.Where("grade_level = ?", q.GradeLevel)
	}
	// XML <if test="cidList != null and cidList.size() > 0">
	if len(q.CidList) > 0 {
		tx = tx.Where("cid IN ?", q.CidList)
	}
	// XML <if test="cid != null and cid != ''">
	if model.NonEmpty(q.Cid) {
		tx = tx.Where("cid = ?", q.Cid)
	}
	// ---- END generated-from-XML ----
	return tx
}
