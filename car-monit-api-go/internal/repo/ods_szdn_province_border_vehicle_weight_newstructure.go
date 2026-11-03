package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.java
// 类/职责: OdsSzdnProvinceBorderVehicleWeightNewstructureMapper — 表 ods_szdn_province_border_vehicle_weight_newstructure 的数据访问入口
// 对应 Go 文件: internal/repo/ods_szdn_province_border_vehicle_weight_newstructure.go
// 关键映射:
//   extends BaseMapper<OdsSzdnProvinceBorderVehicleWeightNewstructure>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(Datauuid)   → GetByID
//   selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(OdsSzdnProvinceBorderVehicleWeightNewstructure q) → List/Count（条件见 applyOdsSzdnProvinceBorderVehicleWeightNewstructureFilters）
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

// OdsSzdnProvinceBorderVehicleWeightNewstructureTable 对应 Java @TableName(value = 'ods_szdn_province_border_vehicle_weight_newstructure', schema = None)
const OdsSzdnProvinceBorderVehicleWeightNewstructureTable = "jl_data01.ods_szdn_province_border_vehicle_weight_newstructure"

// OdsSzdnProvinceBorderVehicleWeightNewstructureRepo 对应 Java 的 OdsSzdnProvinceBorderVehicleWeightNewstructureMapper（@Repository 由 main() 里的显式构造代替）
type OdsSzdnProvinceBorderVehicleWeightNewstructureRepo struct{ db *db.Client }

// NewOdsSzdnProvinceBorderVehicleWeightNewstructureRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsSzdnProvinceBorderVehicleWeightNewstructureRepo(c *db.Client) *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo {
	return &OdsSzdnProvinceBorderVehicleWeightNewstructureRepo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) TableName() string {
	return OdsSzdnProvinceBorderVehicleWeightNewstructureTable
}

// GetByID 对应 OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(Datauuid)
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) GetByID(ctx context.Context, id string) (*model.OdsSzdnProvinceBorderVehicleWeightNewstructure, error) {
	var m model.OdsSzdnProvinceBorderVehicleWeightNewstructure
	err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).Where("datauuid = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) List(ctx context.Context, q *model.OdsSzdnProvinceBorderVehicleWeightNewstructure, limit int) ([]model.OdsSzdnProvinceBorderVehicleWeightNewstructure, error) {
	tx := applyOdsSzdnProvinceBorderVehicleWeightNewstructureFilters(r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsSzdnProvinceBorderVehicleWeightNewstructure
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsSzdnProvinceBorderVehicleWeightNewstructureList 配合 PageInfo#getTotal
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) Count(ctx context.Context, q *model.OdsSzdnProvinceBorderVehicleWeightNewstructure) (int64, error) {
	tx := applyOdsSzdnProvinceBorderVehicleWeightNewstructureFilters(r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) ListAll(ctx context.Context) ([]model.OdsSzdnProvinceBorderVehicleWeightNewstructure, error) {
	var list []model.OdsSzdnProvinceBorderVehicleWeightNewstructure
	if err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) Insert(ctx context.Context, m *model.OdsSzdnProvinceBorderVehicleWeightNewstructure) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) BatchInsert(ctx context.Context, list []*model.OdsSzdnProvinceBorderVehicleWeightNewstructure, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) Update(ctx context.Context, m *model.OdsSzdnProvinceBorderVehicleWeightNewstructure) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).Where("datauuid = ?", id).Delete(&model.OdsSzdnProvinceBorderVehicleWeightNewstructure{}).Error; err != nil {
		return fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsSzdnProvinceBorderVehicleWeightNewstructureFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
//
// PARITY: 列名带双引号是必需的。本表的 column 是驼峰（siteId / plateColorCode ...），
// openGauss 会把未加引号的标识符一律折叠成小写，写成 site_id 或 siteId 不加引号都会报列不存在。
// Java 侧 XML:82-113 同样是 t."siteId" / t.datauuid 这种写法。
func applyOdsSzdnProvinceBorderVehicleWeightNewstructureFilters(tx *gorm.DB, q *model.OdsSzdnProvinceBorderVehicleWeightNewstructure) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="dataSource != null and dataSource != ''">
	if model.NonEmpty(q.DataSource) {
		tx = tx.Where("dataSource = ?", q.DataSource)
	}
	// XML <if test="dataType != null and dataType != ''">
	if model.NonEmpty(q.DataType) {
		tx = tx.Where("dataType = ?", q.DataType)
	}
	// XML <if test="plateNo != null and plateNo != ''">
	if model.NonEmpty(q.PlateNo) {
		tx = tx.Where("plateNo = ?", q.PlateNo)
	}
	// XML <if test="siteId != null and siteId != ''">
	if model.NonEmpty(q.SiteId) {
		tx = tx.Where("siteId = ?", q.SiteId)
	}
	// XML <if test="location != null and location != ''">
	if model.NonEmpty(q.Location) {
		tx = tx.Where("location = ?", q.Location)
	}
	// XML <if test="driveNo != null">
	if q.DriveNo != nil {
		tx = tx.Where("driveNo = ?", q.DriveNo)
	}
	// XML <if test="plateColor != null and plateColor != ''">
	if model.NonEmpty(q.PlateColor) {
		tx = tx.Where("plateColor = ?", q.PlateColor)
	}
	// XML <if test="plateColorCode != null and plateColorCode != ''">
	if model.NonEmpty(q.PlateColorCode) {
		tx = tx.Where("plateColorCode = ?", q.PlateColorCode)
	}
	// XML <if test="plateType != null and plateType != ''">
	if model.NonEmpty(q.PlateType) {
		tx = tx.Where("plateType = ?", q.PlateType)
	}
	// XML <if test="plateTypeCode != null and plateTypeCode != ''">
	if model.NonEmpty(q.PlateTypeCode) {
		tx = tx.Where("plateTypeCode = ?", q.PlateTypeCode)
	}
	// XML <if test="vehicleColor != null and vehicleColor != ''">
	if model.NonEmpty(q.VehicleColor) {
		tx = tx.Where("vehicleColor = ?", q.VehicleColor)
	}
	// XML <if test="vehicleColorCode != null and vehicleColorCode != ''">
	if model.NonEmpty(q.VehicleColorCode) {
		tx = tx.Where("vehicleColorCode = ?", q.VehicleColorCode)
	}
	// XML <if test="vehicleType != null and vehicleType != ''">
	if model.NonEmpty(q.VehicleType) {
		tx = tx.Where("vehicleType = ?", q.VehicleType)
	}
	// XML <if test="vehicleTypeCode != null and vehicleTypeCode != ''">
	if model.NonEmpty(q.VehicleTypeCode) {
		tx = tx.Where("vehicleTypeCode = ?", q.VehicleTypeCode)
	}
	// XML <if test="vehicleSpeed != null">
	if q.VehicleSpeed != nil {
		tx = tx.Where("vehicleSpeed = ?", q.VehicleSpeed)
	}
	// XML <if test="isOverweight != null">
	if q.IsOverweight != nil {
		tx = tx.Where("isOverweight = ?", q.IsOverweight)
	}
	// XML <if test="axleNum != null">
	if q.AxleNum != nil {
		tx = tx.Where("axleNum = ?", q.AxleNum)
	}
	// XML <if test="overWeight != null">
	if q.OverWeight != nil {
		tx = tx.Where("overWeight = ?", q.OverWeight)
	}
	// XML <if test="vehicleWeight != null">
	if q.VehicleWeight != nil {
		tx = tx.Where("vehicleWeight = ?", q.VehicleWeight)
	}
	// XML <if test="limitWeight != null">
	if q.LimitWeight != nil {
		tx = tx.Where("limitWeight = ?", q.LimitWeight)
	}
	// XML <if test="checkTimeUnix != null">
	if q.CheckTimeUnix != nil {
		tx = tx.Where("checkTimeUnix = ?", q.CheckTimeUnix)
	}
	// XML <if test="checkTime != null">
	if q.CheckTime != nil {
		tx = tx.Where("checkTime = ?", q.CheckTime)
	}
	// XML <if test="axleModel != null">
	if q.AxleModel != nil {
		tx = tx.Where("axleModel = ?", q.AxleModel)
	}
	// XML <if test="loadRate != null">
	if q.LoadRate != nil {
		tx = tx.Where("loadRate = ?", q.LoadRate)
	}
	// XML <if test="axleArray != null and axleArray != ''">
	if model.NonEmpty(q.AxleArray) {
		tx = tx.Where("axleArray = ?", q.AxleArray)
	}
	// XML <if test="weighingImagesArry != null and weighingImagesArry != ''">
	if model.NonEmpty(q.WeighingImagesArry) {
		tx = tx.Where("weighingImagesArry = ?", q.WeighingImagesArry)
	}
	// XML <if test="loadTime != null">
	if q.LoadTime != nil {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="gradeLevel != null">
	if q.GradeLevel != nil {
		tx = tx.Where("grade_level = ?", q.GradeLevel)
	}
	// XML <if test="datauuid != null and datauuid != ''">
	if model.NonEmpty(q.Datauuid) {
		tx = tx.Where("datauuid = ?", q.Datauuid)
	}
	// XML <if test="reserve1 != null and reserve1 != ''">
	if model.NonEmpty(q.Reserve1) {
		tx = tx.Where("reserve1 = ?", q.Reserve1)
	}
	// XML <if test="reserve2 != null and reserve2 != ''">
	if model.NonEmpty(q.Reserve2) {
		tx = tx.Where("reserve2 = ?", q.Reserve2)
	}
	// XML <if test="reserve3 != null and reserve3 != ''">
	if model.NonEmpty(q.Reserve3) {
		tx = tx.Where("reserve3 = ?", q.Reserve3)
	}
	// ---- END generated-from-XML ----
	return tx
}
