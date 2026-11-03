package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.java
// 类/职责: OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper — 表 ods_rt_szdn_snapshot_flow_provcapture_addcode 的数据访问入口
// 对应 Go 文件: internal/repo/ods_rt_szdn_snapshot_flow_provcapture_addcode.go
// 关键映射:
//   extends BaseMapper<OdsRtSzdnSnapshotFlowProvcaptureAddcode>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(BigId)   → GetByID
//   selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(OdsRtSzdnSnapshotFlowProvcaptureAddcode q) → List/Count（条件见 applyOdsRtSzdnSnapshotFlowProvcaptureAddcodeFilters）
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

// OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable 对应 Java @TableName(value = 'ods_rt_szdn_snapshot_flow_provcapture_addcode', schema = None)
const OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable = "jl_data01.ods_rt_szdn_snapshot_flow_provcapture_addcode"

// OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo 对应 Java 的 OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper（@Repository 由 main() 里的显式构造代替）
type OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo struct{ db *db.Client }

// NewOdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo(c *db.Client) *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo {
	return &OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) TableName() string {
	return OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable
}

// GetByID 对应 OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(BigId)
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) GetByID(ctx context.Context, id string) (*model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, error) {
	var m model.OdsRtSzdnSnapshotFlowProvcaptureAddcode
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) List(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, limit int) ([]model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, error) {
	tx := applyOdsRtSzdnSnapshotFlowProvcaptureAddcodeFilters(r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsRtSzdnSnapshotFlowProvcaptureAddcode
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList 配合 PageInfo#getTotal
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) Count(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode) (int64, error) {
	tx := applyOdsRtSzdnSnapshotFlowProvcaptureAddcodeFilters(r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) ListAll(ctx context.Context) ([]model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, error) {
	var list []model.OdsRtSzdnSnapshotFlowProvcaptureAddcode
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) Insert(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) BatchInsert(ctx context.Context, list []*model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) Update(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).Where("big_id = ?", id).Delete(&model.OdsRtSzdnSnapshotFlowProvcaptureAddcode{}).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsRtSzdnSnapshotFlowProvcaptureAddcodeFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsRtSzdnSnapshotFlowProvcaptureAddcodeFilters(tx *gorm.DB, q *model.OdsRtSzdnSnapshotFlowProvcaptureAddcode) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null">
	if q.BigId != nil {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="deviceip != null and deviceip != ''">
	if model.NonEmpty(q.Deviceip) {
		tx = tx.Where("deviceip = ?", q.Deviceip)
	}
	// XML <if test="tailcapturetimeunix != null">
	if q.Tailcapturetimeunix != nil {
		tx = tx.Where("tailcapturetimeunix = ?", q.Tailcapturetimeunix)
	}
	// XML <if test="tailcapturetime != null">
	if q.Tailcapturetime != nil {
		tx = tx.Where("tailcapturetime = ?", q.Tailcapturetime)
	}
	// XML <if test="extendattribute != null and extendattribute != ''">
	if model.NonEmpty(q.Extendattribute) {
		tx = tx.Where("extendattribute = ?", q.Extendattribute)
	}
	// XML <if test="smallsideimagewidth != null">
	if q.Smallsideimagewidth != nil {
		tx = tx.Where("smallsideimagewidth = ?", q.Smallsideimagewidth)
	}
	// XML <if test="axletype != null and axletype != ''">
	if model.NonEmpty(q.Axletype) {
		tx = tx.Where("axletype = ?", q.Axletype)
	}
	// XML <if test="smallsideimageheight != null">
	if q.Smallsideimageheight != nil {
		tx = tx.Where("smallsideimageheight = ?", q.Smallsideimageheight)
	}
	// XML <if test="platecolorcode != null">
	if q.Platecolorcode != nil {
		tx = tx.Where("platecolorcode = ?", q.Platecolorcode)
	}
	// XML <if test="platecolor != null and platecolor != ''">
	if model.NonEmpty(q.Platecolor) {
		tx = tx.Where("platecolor = ?", q.Platecolor)
	}
	// XML <if test="cover != null and cover != ''">
	if model.NonEmpty(q.Cover) {
		tx = tx.Where("cover = ?", q.Cover)
	}
	// XML <if test="averageauthoritative != null">
	if q.Averageauthoritative != nil {
		tx = tx.Where("averageauthoritative = ?", q.Averageauthoritative)
	}
	// XML <if test="headlanecode != null">
	if q.Headlanecode != nil {
		tx = tx.Where("headlanecode = ?", q.Headlanecode)
	}
	// XML <if test="specialvehicle != null">
	if q.Specialvehicle != nil {
		tx = tx.Where("specialvehicle = ?", q.Specialvehicle)
	}
	// XML <if test="carlength != null">
	if q.Carlength != nil {
		tx = tx.Where("carlength = ?", q.Carlength)
	}
	// XML <if test="resulttype != null and resulttype != ''">
	if model.NonEmpty(q.Resulttype) {
		tx = tx.Where("resulttype = ?", q.Resulttype)
	}
	// XML <if test="carhight != null">
	if q.Carhight != nil {
		tx = tx.Where("carhight = ?", q.Carhight)
	}
	// XML <if test="carmodelscode != null">
	if q.Carmodelscode != nil {
		tx = tx.Where("carmodelscode = ?", q.Carmodelscode)
	}
	// XML <if test="carmodels != null and carmodels != ''">
	if model.NonEmpty(q.Carmodels) {
		tx = tx.Where("carmodels = ?", q.Carmodels)
	}
	// XML <if test="laneposition != null and laneposition != ''">
	if model.NonEmpty(q.Laneposition) {
		tx = tx.Where("laneposition = ?", q.Laneposition)
	}
	// XML <if test="firstauthoritative != null">
	if q.Firstauthoritative != nil {
		tx = tx.Where("firstauthoritative = ?", q.Firstauthoritative)
	}
	// XML <if test="tailplateimageheight != null">
	if q.Tailplateimageheight != nil {
		tx = tx.Where("tailplateimageheight = ?", q.Tailplateimageheight)
	}
	// XML <if test="axlecount != null">
	if q.Axlecount != nil {
		tx = tx.Where("axlecount = ?", q.Axlecount)
	}
	// XML <if test="plateimagewidth != null">
	if q.Plateimagewidth != nil {
		tx = tx.Where("plateimagewidth = ?", q.Plateimagewidth)
	}
	// XML <if test="specialclass != null and specialclass != ''">
	if model.NonEmpty(q.Specialclass) {
		tx = tx.Where("specialclass = ?", q.Specialclass)
	}
	// XML <if test="tailplatenumber != null and tailplatenumber != ''">
	if model.NonEmpty(q.Tailplatenumber) {
		tx = tx.Where("tailplatenumber = ?", q.Tailplatenumber)
	}
	// XML <if test="tailimage != null and tailimage != ''">
	if model.NonEmpty(q.Tailimage) {
		tx = tx.Where("tailimage = ?", q.Tailimage)
	}
	// XML <if test="sidecapturetimeunix != null">
	if q.Sidecapturetimeunix != nil {
		tx = tx.Where("sidecapturetimeunix = ?", q.Sidecapturetimeunix)
	}
	// XML <if test="sidecapturetime != null">
	if q.Sidecapturetime != nil {
		tx = tx.Where("sidecapturetime = ?", q.Sidecapturetime)
	}
	// XML <if test="sidelanecode != null">
	if q.Sidelanecode != nil {
		tx = tx.Where("sidelanecode = ?", q.Sidelanecode)
	}
	// XML <if test="wheelbase != null">
	if q.Wheelbase != nil {
		tx = tx.Where("wheelbase = ?", q.Wheelbase)
	}
	// XML <if test="attached != null and attached != ''">
	if model.NonEmpty(q.Attached) {
		tx = tx.Where("attached = ?", q.Attached)
	}
	// XML <if test="wheelcount != null">
	if q.Wheelcount != nil {
		tx = tx.Where("wheelcount = ?", q.Wheelcount)
	}
	// XML <if test="guid != null and guid != ''">
	if model.NonEmpty(q.Guid) {
		tx = tx.Where("guid = ?", q.Guid)
	}
	// XML <if test="sideimagewidth != null">
	if q.Sideimagewidth != nil {
		tx = tx.Where("sideimagewidth = ?", q.Sideimagewidth)
	}
	// XML <if test="plateimageheight != null">
	if q.Plateimageheight != nil {
		tx = tx.Where("plateimageheight = ?", q.Plateimageheight)
	}
	// XML <if test="datasource != null and datasource != ''">
	if model.NonEmpty(q.Datasource) {
		tx = tx.Where("datasource = ?", q.Datasource)
	}
	// XML <if test="carclass != null and carclass != ''">
	if model.NonEmpty(q.Carclass) {
		tx = tx.Where("carclass = ?", q.Carclass)
	}
	// XML <if test="gantryid != null and gantryid != ''">
	if model.NonEmpty(q.Gantryid) {
		tx = tx.Where("gantryid = ?", q.Gantryid)
	}
	// XML <if test="smallsideimage != null and smallsideimage != ''">
	if model.NonEmpty(q.Smallsideimage) {
		tx = tx.Where("smallsideimage = ?", q.Smallsideimage)
	}
	// XML <if test="headimageheight != null">
	if q.Headimageheight != nil {
		tx = tx.Where("headimageheight = ?", q.Headimageheight)
	}
	// XML <if test="sidescenetypecode != null">
	if q.Sidescenetypecode != nil {
		tx = tx.Where("sidescenetypecode = ?", q.Sidescenetypecode)
	}
	// XML <if test="sidescenetype != null and sidescenetype != ''">
	if model.NonEmpty(q.Sidescenetype) {
		tx = tx.Where("sidescenetype = ?", q.Sidescenetype)
	}
	// XML <if test="tailimagewidth != null">
	if q.Tailimagewidth != nil {
		tx = tx.Where("tailimagewidth = ?", q.Tailimagewidth)
	}
	// XML <if test="envstate != null and envstate != ''">
	if model.NonEmpty(q.Envstate) {
		tx = tx.Where("envstate = ?", q.Envstate)
	}
	// XML <if test="headscenetypecode != null">
	if q.Headscenetypecode != nil {
		tx = tx.Where("headscenetypecode = ?", q.Headscenetypecode)
	}
	// XML <if test="headscenetype != null and headscenetype != ''">
	if model.NonEmpty(q.Headscenetype) {
		tx = tx.Where("headscenetype = ?", q.Headscenetype)
	}
	// XML <if test="sidedrivingdirectioncode != null">
	if q.Sidedrivingdirectioncode != nil {
		tx = tx.Where("sidedrivingdirectioncode = ?", q.Sidedrivingdirectioncode)
	}
	// XML <if test="sidedrivingdirection != null and sidedrivingdirection != ''">
	if model.NonEmpty(q.Sidedrivingdirection) {
		tx = tx.Where("sidedrivingdirection = ?", q.Sidedrivingdirection)
	}
	// XML <if test="sideimageheight != null">
	if q.Sideimageheight != nil {
		tx = tx.Where("sideimageheight = ?", q.Sideimageheight)
	}
	// XML <if test="speed != null and speed != ''">
	if model.NonEmpty(q.Speed) {
		tx = tx.Where("speed = ?", q.Speed)
	}
	// XML <if test="tailplateimage != null and tailplateimage != ''">
	if model.NonEmpty(q.Tailplateimage) {
		tx = tx.Where("tailplateimage = ?", q.Tailplateimage)
	}
	// XML <if test="headdrivingdirectioncode != null">
	if q.Headdrivingdirectioncode != nil {
		tx = tx.Where("headdrivingdirectioncode = ?", q.Headdrivingdirectioncode)
	}
	// XML <if test="headdrivingdirection != null and headdrivingdirection != ''">
	if model.NonEmpty(q.Headdrivingdirection) {
		tx = tx.Where("headdrivingdirection = ?", q.Headdrivingdirection)
	}
	// XML <if test="cartype != null and cartype != ''">
	if model.NonEmpty(q.Cartype) {
		tx = tx.Where("cartype = ?", q.Cartype)
	}
	// XML <if test="plateimage != null and plateimage != ''">
	if model.NonEmpty(q.Plateimage) {
		tx = tx.Where("plateimage = ?", q.Plateimage)
	}
	// XML <if test="changelane != null and changelane != ''">
	if model.NonEmpty(q.Changelane) {
		tx = tx.Where("changelane = ?", q.Changelane)
	}
	// XML <if test="sideimage != null and sideimage != ''">
	if model.NonEmpty(q.Sideimage) {
		tx = tx.Where("sideimage = ?", q.Sideimage)
	}
	// XML <if test="tailplateposition != null and tailplateposition != ''">
	if model.NonEmpty(q.Tailplateposition) {
		tx = tx.Where("tailplateposition = ?", q.Tailplateposition)
	}
	// XML <if test="headimagewidth != null">
	if q.Headimagewidth != nil {
		tx = tx.Where("headimagewidth = ?", q.Headimagewidth)
	}
	// XML <if test="headimage != null and headimage != ''">
	if model.NonEmpty(q.Headimage) {
		tx = tx.Where("headimage = ?", q.Headimage)
	}
	// XML <if test="carweight != null">
	if q.Carweight != nil {
		tx = tx.Where("carweight = ?", q.Carweight)
	}
	// XML <if test="tailimageheight != null">
	if q.Tailimageheight != nil {
		tx = tx.Where("tailimageheight = ?", q.Tailimageheight)
	}
	// XML <if test="devicecode != null and devicecode != ''">
	if model.NonEmpty(q.Devicecode) {
		tx = tx.Where("devicecode = ?", q.Devicecode)
	}
	// XML <if test="platenumber != null and platenumber != ''">
	if model.NonEmpty(q.Platenumber) {
		tx = tx.Where("platenumber = ?", q.Platenumber)
	}
	// XML <if test="tailplatecolorcode != null">
	if q.Tailplatecolorcode != nil {
		tx = tx.Where("tailplatecolorcode = ?", q.Tailplatecolorcode)
	}
	// XML <if test="tailplatecolor != null and tailplatecolor != ''">
	if model.NonEmpty(q.Tailplatecolor) {
		tx = tx.Where("tailplatecolor = ?", q.Tailplatecolor)
	}
	// XML <if test="uploadtimeunix != null">
	if q.Uploadtimeunix != nil {
		tx = tx.Where("uploadtimeunix = ?", q.Uploadtimeunix)
	}
	// XML <if test="uploadtime != null">
	if q.Uploadtime != nil {
		tx = tx.Where("uploadtime = ?", q.Uploadtime)
	}
	// XML <if test="impostoraxlecount != null">
	if q.Impostoraxlecount != nil {
		tx = tx.Where("impostoraxlecount = ?", q.Impostoraxlecount)
	}
	// XML <if test="taillanecode != null">
	if q.Taillanecode != nil {
		tx = tx.Where("taillanecode = ?", q.Taillanecode)
	}
	// XML <if test="siteid != null">
	if q.Siteid != nil {
		tx = tx.Where("siteid = ?", q.Siteid)
	}
	// XML <if test="headcapturetimeunix != null">
	if q.Headcapturetimeunix != nil {
		tx = tx.Where("headcapturetimeunix = ?", q.Headcapturetimeunix)
	}
	// XML <if test="headcapturetime != null">
	if q.Headcapturetime != nil {
		tx = tx.Where("headcapturetime = ?", q.Headcapturetime)
	}
	// XML <if test="plateposition != null and plateposition != ''">
	if model.NonEmpty(q.Plateposition) {
		tx = tx.Where("plateposition = ?", q.Plateposition)
	}
	// XML <if test="tailplateimagewidth != null">
	if q.Tailplateimagewidth != nil {
		tx = tx.Where("tailplateimagewidth = ?", q.Tailplateimagewidth)
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
