package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeStationExit01Mapper.java
// 类/职责: OdsLwzxsfsjFeeStationExit01Mapper — 表 ods_lwzxsfsj_fee_station_exit_01 的数据访问入口
// 对应 Go 文件: internal/repo/ods_lwzxsfsj_fee_station_exit01.go
// 关键映射:
//   extends BaseMapper<OdsLwzxsfsjFeeStationExit01>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsLwzxsfsjFeeStationExit01ById(BigId)   → GetByID
//   selectOdsLwzxsfsjFeeStationExit01List(OdsLwzxsfsjFeeStationExit01 q) → List/Count（条件见 applyOdsLwzxsfsjFeeStationExit01Filters）
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

// OdsLwzxsfsjFeeStationExit01Table 对应 Java @TableName(value = 'ods_lwzxsfsj_fee_station_exit_01', schema = None)
const OdsLwzxsfsjFeeStationExit01Table = "jl_data01.ods_lwzxsfsj_fee_station_exit_01"

// OdsLwzxsfsjFeeStationExit01Repo 对应 Java 的 OdsLwzxsfsjFeeStationExit01Mapper（@Repository 由 main() 里的显式构造代替）
type OdsLwzxsfsjFeeStationExit01Repo struct{ db *db.Client }

// NewOdsLwzxsfsjFeeStationExit01Repo 对应 Spring @Repository 的 Bean 注册
func NewOdsLwzxsfsjFeeStationExit01Repo(c *db.Client) *OdsLwzxsfsjFeeStationExit01Repo {
	return &OdsLwzxsfsjFeeStationExit01Repo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsLwzxsfsjFeeStationExit01Repo) TableName() string { return OdsLwzxsfsjFeeStationExit01Table }

// GetByID 对应 OdsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01ById(BigId)
func (r *OdsLwzxsfsjFeeStationExit01Repo) GetByID(ctx context.Context, id string) (*model.OdsLwzxsfsjFeeStationExit01, error) {
	var m model.OdsLwzxsfsjFeeStationExit01
	err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsLwzxsfsjFeeStationExit01Mapper.selectOdsLwzxsfsjFeeStationExit01List(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsLwzxsfsjFeeStationExit01Repo) List(ctx context.Context, q *model.OdsLwzxsfsjFeeStationExit01, limit int) ([]model.OdsLwzxsfsjFeeStationExit01, error) {
	tx := applyOdsLwzxsfsjFeeStationExit01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsLwzxsfsjFeeStationExit01
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsLwzxsfsjFeeStationExit01List 配合 PageInfo#getTotal
func (r *OdsLwzxsfsjFeeStationExit01Repo) Count(ctx context.Context, q *model.OdsLwzxsfsjFeeStationExit01) (int64, error) {
	tx := applyOdsLwzxsfsjFeeStationExit01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsLwzxsfsjFeeStationExit01Repo) ListAll(ctx context.Context) ([]model.OdsLwzxsfsjFeeStationExit01, error) {
	var list []model.OdsLwzxsfsjFeeStationExit01
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsLwzxsfsjFeeStationExit01Repo) Insert(ctx context.Context, m *model.OdsLwzxsfsjFeeStationExit01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).Create(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsLwzxsfsjFeeStationExit01Repo) BatchInsert(ctx context.Context, list []*model.OdsLwzxsfsjFeeStationExit01, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsLwzxsfsjFeeStationExit01Repo) Update(ctx context.Context, m *model.OdsLwzxsfsjFeeStationExit01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).Save(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsLwzxsfsjFeeStationExit01Repo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).Where("big_id = ?", id).Delete(&model.OdsLwzxsfsjFeeStationExit01{}).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsLwzxsfsjFeeStationExit01Filters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsLwzxsfsjFeeStationExit01Filters(tx *gorm.DB, q *model.OdsLwzxsfsjFeeStationExit01) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null and bigId != ''">
	if q.BigId != "" {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="actualfeeclass != null and actualfeeclass != ''">
	if model.NonEmpty(q.Actualfeeclass) {
		tx = tx.Where("actualfeeclass = ?", q.Actualfeeclass)
	}
	// XML <if test="axlecount != null">
	if q.Axlecount != nil {
		tx = tx.Where("axlecount = ?", q.Axlecount)
	}
	// XML <if test="discountfee != null">
	if q.Discountfee != nil {
		tx = tx.Where("discountfee = ?", q.Discountfee)
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
	// XML <if test="entollstationname != null and entollstationname != ''">
	if model.NonEmpty(q.Entollstationname) {
		tx = tx.Where("entollstationname like ?", "%"+model.Val(q.Entollstationname)+"%")
	}
	// XML <if test="envehicleclass != null">
	if q.Envehicleclass != nil {
		tx = tx.Where("envehicleclass = ?", q.Envehicleclass)
	}
	// XML <if test="envehicleid != null and envehicleid != ''">
	if model.NonEmpty(q.Envehicleid) {
		tx = tx.Where("envehicleid = ?", q.Envehicleid)
	}
	// XML <if test="envehicletype != null">
	if q.Envehicletype != nil {
		tx = tx.Where("envehicletype = ?", q.Envehicletype)
	}
	// XML <if test="enweight != null">
	if q.Enweight != nil {
		tx = tx.Where("enweight = ?", q.Enweight)
	}
	// XML <if test="entryoperatorid != null and entryoperatorid != ''">
	if model.NonEmpty(q.Entryoperatorid) {
		tx = tx.Where("entryoperatorid = ?", q.Entryoperatorid)
	}
	// XML <if test="extime != null">
	if q.Extime != nil {
		tx = tx.Where("extime = ?", q.Extime)
	}
	// XML <if test="extolllaneid != null and extolllaneid != ''">
	if model.NonEmpty(q.Extolllaneid) {
		tx = tx.Where("extolllaneid = ?", q.Extolllaneid)
	}
	// XML <if test="extollstationid != null and extollstationid != ''">
	if model.NonEmpty(q.Extollstationid) {
		tx = tx.Where("extollstationid = ?", q.Extollstationid)
	}
	// XML <if test="extollstationname != null and extollstationname != ''">
	if model.NonEmpty(q.Extollstationname) {
		tx = tx.Where("extollstationname like ?", "%"+model.Val(q.Extollstationname)+"%")
	}
	// XML <if test="exvehicleclass != null">
	if q.Exvehicleclass != nil {
		tx = tx.Where("exvehicleclass = ?", q.Exvehicleclass)
	}
	// XML <if test="exvehicleid != null and exvehicleid != ''">
	if model.NonEmpty(q.Exvehicleid) {
		tx = tx.Where("exvehicleid = ?", q.Exvehicleid)
	}
	// XML <if test="exvehicletype != null">
	if q.Exvehicletype != nil {
		tx = tx.Where("exvehicletype = ?", q.Exvehicletype)
	}
	// XML <if test="fee != null">
	if q.Fee != nil {
		tx = tx.Where("fee = ?", q.Fee)
	}
	// XML <if test="exweight != null">
	if q.Exweight != nil {
		tx = tx.Where("exweight = ?", q.Exweight)
	}
	// XML <if test="feeboardplay != null and feeboardplay != ''">
	if model.NonEmpty(q.Feeboardplay) {
		tx = tx.Where("feeboardplay = ?", q.Feeboardplay)
	}
	// XML <if test="feemileage != null">
	if q.Feemileage != nil {
		tx = tx.Where("feemileage = ?", q.Feemileage)
	}
	// XML <if test="identification != null and identification != ''">
	if model.NonEmpty(q.Identification) {
		tx = tx.Where("identification = ?", q.Identification)
	}
	// XML <if test="feerate != null">
	if q.Feerate != nil {
		tx = tx.Where("feerate = ?", q.Feerate)
	}
	// XML <if test="identifyvehicleid != null and identifyvehicleid != ''">
	if model.NonEmpty(q.Identifyvehicleid) {
		tx = tx.Where("identifyvehicleid like ?", "%"+model.Val(q.Identifyvehicleid)+"%")
	}
	// XML <if test="lanetype != null and lanetype != ''">
	if model.NonEmpty(q.Lanetype) {
		tx = tx.Where("lanetype = ?", q.Lanetype)
	}
	// XML <if test="mediano != null and mediano != ''">
	if model.NonEmpty(q.Mediano) {
		tx = tx.Where("mediano = ?", q.Mediano)
	}
	// XML <if test="mediatype != null and mediatype != ''">
	if model.NonEmpty(q.Mediatype) {
		tx = tx.Where("mediatype = ?", q.Mediatype)
	}
	// XML <if test="nocardcount != null">
	if q.Nocardcount != nil {
		tx = tx.Where("nocardcount = ?", q.Nocardcount)
	}
	// XML <if test="obuid != null and obuid != ''">
	if model.NonEmpty(q.Obuid) {
		tx = tx.Where("obuid = ?", q.Obuid)
	}
	// XML <if test="obusign != null and obusign != ''">
	if model.NonEmpty(q.Obusign) {
		tx = tx.Where("obusign = ?", q.Obusign)
	}
	// XML <if test="obutotalamount != null">
	if q.Obutotalamount != nil {
		tx = tx.Where("obutotalamount = ?", q.Obutotalamount)
	}
	// XML <if test="obutotaldiscountamount != null">
	if q.Obutotaldiscountamount != nil {
		tx = tx.Where("obutotaldiscountamount = ?", q.Obutotaldiscountamount)
	}
	// XML <if test="params != null and params != ''">
	if model.NonEmpty(q.Params) {
		tx = tx.Where("params = ?", q.Params)
	}
	// XML <if test="operid != null and operid != ''">
	if model.NonEmpty(q.Operid) {
		tx = tx.Where("operid = ?", q.Operid)
	}
	// XML <if test="passid != null and passid != ''">
	if model.NonEmpty(q.Passid) {
		tx = tx.Where("passid = ?", q.Passid)
	}
	// XML <if test="paycardid != null and paycardid != ''">
	if model.NonEmpty(q.Paycardid) {
		tx = tx.Where("paycardid = ?", q.Paycardid)
	}
	// XML <if test="payfee != null">
	if q.Payfee != nil {
		tx = tx.Where("payfee = ?", q.Payfee)
	}
	// XML <if test="paytype != null and paytype != ''">
	if model.NonEmpty(q.Paytype) {
		tx = tx.Where("paytype = ?", q.Paytype)
	}
	// XML <if test="provfee != null">
	if q.Provfee != nil {
		tx = tx.Where("provfee = ?", q.Provfee)
	}
	// XML <if test="provtranscount != null">
	if q.Provtranscount != nil {
		tx = tx.Where("provtranscount = ?", q.Provtranscount)
	}
	// XML <if test="provincecount != null">
	if q.Provincecount != nil {
		tx = tx.Where("provincecount = ?", q.Provincecount)
	}
	// XML <if test="shift != null and shift != ''">
	if model.NonEmpty(q.Shift) {
		tx = tx.Where("shift = ?", q.Shift)
	}
	// XML <if test="receivetime != null">
	if q.Receivetime != nil {
		tx = tx.Where("receivetime = ?", q.Receivetime)
	}
	// XML <if test="shortfee != null">
	if q.Shortfee != nil {
		tx = tx.Where("shortfee = ?", q.Shortfee)
	}
	// XML <if test="shortfeemileage != null">
	if q.Shortfeemileage != nil {
		tx = tx.Where("shortfeemileage = ?", q.Shortfeemileage)
	}
	// XML <if test="signstatus != null and signstatus != ''">
	if model.NonEmpty(q.Signstatus) {
		tx = tx.Where("signstatus = ?", q.Signstatus)
	}
	// XML <if test="spcrateversion != null and spcrateversion != ''">
	if model.NonEmpty(q.Spcrateversion) {
		tx = tx.Where("spcrateversion = ?", q.Spcrateversion)
	}
	// XML <if test="tac != null and tac != ''">
	if model.NonEmpty(q.Tac) {
		tx = tx.Where("tac = ?", q.Tac)
	}
	// XML <if test="specialtype != null and specialtype != ''">
	if model.NonEmpty(q.Specialtype) {
		tx = tx.Where("specialtype = ?", q.Specialtype)
	}
	// XML <if test="splitprovince != null and splitprovince != ''">
	if model.NonEmpty(q.Splitprovince) {
		tx = tx.Where("splitprovince = ?", q.Splitprovince)
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
	// XML <if test="transpaytype != null and transpaytype != ''">
	if model.NonEmpty(q.Transpaytype) {
		tx = tx.Where("transpaytype = ?", q.Transpaytype)
	}
	// XML <if test="transtype != null and transtype != ''">
	if model.NonEmpty(q.Transtype) {
		tx = tx.Where("transtype = ?", q.Transtype)
	}
	// XML <if test="loadTime != null">
	if q.LoadTime != nil {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="vehiclesign != null and vehiclesign != ''">
	if model.NonEmpty(q.Vehiclesign) {
		tx = tx.Where("vehiclesign = ?", q.Vehiclesign)
	}
	// XML <if test="gradeLevel != null and gradeLevel != ''">
	if model.NonEmpty(q.GradeLevel) {
		tx = tx.Where("grade_level = ?", q.GradeLevel)
	}
	// XML <if test="vehiclesignid != null and vehiclesignid != ''">
	if model.NonEmpty(q.Vehiclesignid) {
		tx = tx.Where("vehiclesignid = ?", q.Vehiclesignid)
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
