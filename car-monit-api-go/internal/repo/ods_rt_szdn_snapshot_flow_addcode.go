package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsRtSzdnSnapshotFlowAddcodeMapper.java
// 类/职责: OdsRtSzdnSnapshotFlowAddcodeMapper — 表 ods_rt_szdn_snapshot_flow_addcode 的数据访问入口
// 对应 Go 文件: internal/repo/ods_rt_szdn_snapshot_flow_addcode.go
// 关键映射:
//   extends BaseMapper<OdsRtSzdnSnapshotFlowAddcode>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsRtSzdnSnapshotFlowAddcodeById(BigId)   → GetByID
//   selectOdsRtSzdnSnapshotFlowAddcodeList(q) → List/Count（条件见 applyOdsRtSzdnSnapshotFlowAddcodeFilters）
// DIFF: Java 用 XML 把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。
//
// 修正说明（本文件之前的一次迁移判断是错的）：
// XML 确实在 —— 只是不在 resources/mapper/xml/，而在
// pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/OdsRtSzdnSnapshotFlowAddcodeMapper.xml。
// 早期因为找不到文件而改成「按字段语义重建」，因此三处全部跑偏：
//   1) 投影：XML 的 <sql id="selectOdsRtSzdnSnapshotFlowAddcodeVo"> 只返 17 列，Go 之前返全部列；
//   2) 排序：XML list 有 order by t.snapshottime desc，Go 之前没有；
//   3) 谓词：gantrycode/tollcode/deviceid/datauuid 在 XML 里是精确 =，Go 之前当成了 ILIKE。
// 下面逐项按 XML 原文重建。

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// OdsRtSzdnSnapshotFlowAddcodeTable 对应 Java @TableName(value = 'ods_rt_szdn_snapshot_flow_addcode', schema = 'jl_data01')
const OdsRtSzdnSnapshotFlowAddcodeTable = "jl_data01.ods_rt_szdn_snapshot_flow_addcode"

// snapshotFlowAddcodeVo 逐字对应 XML 的 <sql id="selectOdsRtSzdnSnapshotFlowAddcodeVo">（17 列，去掉 t. 前缀）。
//
// PARITY: 这份列表是投影，不是装饰 —— XML 没选的列（big_id / datasource / cameratype / deviceid /
// gantrycode / roadcode / sectioncode / tollcode / tollname / orgcode / orgname / hexcode / pileno /
// lon / lat / deviceip / siteid / laneid / receivedtime(unix) / plateconfidence / carbrand /
// cardirection / loadtime / gradelevel / reserve3）在 Java 响应里就是 JSON null。
// Go 如果直接 SELECT * 把这些列填上，/base/snapshotflow/{bigId} 就和 Java 对不上。
const snapshotFlowAddcodeVo = `datauuid,
	gantryname,
	roadname,
	sectionname,
	direction,
	snapshottimeunix,
	snapshottime,
	platenumber,
	platecolor,
	platecolorcode,
	platetype,
	platetypecode,
	carcolor,
	carcolorcode,
	cartype,
	cartypecode,
	snappicturepath`

// flagJiAnDong 对应 Controller 在查询范围不是 queryall 时强加的值：
// `odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong")`（OdsRtSzdnSnapshotFlowAddcodeController.java:54）。
const flagJiAnDong = "JiAnDong"

// OdsRtSzdnSnapshotFlowAddcodeRepo 对应 Java 的 OdsRtSzdnSnapshotFlowAddcodeMapper（@Repository 由 main() 里的显式构造代替）
type OdsRtSzdnSnapshotFlowAddcodeRepo struct{ db *db.Client }

// NewOdsRtSzdnSnapshotFlowAddcodeRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsRtSzdnSnapshotFlowAddcodeRepo(c *db.Client) *OdsRtSzdnSnapshotFlowAddcodeRepo {
	return &OdsRtSzdnSnapshotFlowAddcodeRepo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) TableName() string {
	return OdsRtSzdnSnapshotFlowAddcodeTable
}

// GetByID 对应 OdsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeById(BigId)
// XML L147-152：`select <include Vo> from jl_data01.ods_rt_szdn_snapshot_flow_addcode t where t.big_id = #{bigId}`
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) GetByID(ctx context.Context, id string) (*model.OdsRtSzdnSnapshotFlowAddcode, error) {
	var m model.OdsRtSzdnSnapshotFlowAddcode
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).
		Select(snapshotFlowAddcodeVo).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(q)
// XML L72-145：投影用 Vo，末尾固定 `order by t.snapshottime desc`。
//
// PARITY: 这个 order by 必须带上。PageHelper 只负责拼 LIMIT/OFFSET，行序完全依赖它；
// 不写排序时，同一页拿到的行集会随数据库返回顺序飘，和 Java 对不上。
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) List(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowAddcode, limit int) ([]model.OdsRtSzdnSnapshotFlowAddcode, error) {
	tx := applyOdsRtSzdnSnapshotFlowAddcodeFilters(
		r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Select(snapshotFlowAddcodeVo), q)
	// 调用方排序必须加在自身 Order 之前：gorm 的 Order 是追加，先加的优先级高。
	// 否则 ?orderByColumn=captureTime 会被 "snapshottime desc" 压住，等于没生效。
	tx = ApplyOrder(ctx, tx)
	tx = tx.Order("snapshottime desc")
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsRtSzdnSnapshotFlowAddcode
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsRtSzdnSnapshotFlowAddcodeList 配合 PageInfo#getTotal
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) Count(ctx context.Context, q *model.OdsRtSzdnSnapshotFlowAddcode) (int64, error) {
	tx := applyOdsRtSzdnSnapshotFlowAddcodeFilters(r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListAll(ctx context.Context) ([]model.OdsRtSzdnSnapshotFlowAddcode, error) {
	var list []model.OdsRtSzdnSnapshotFlowAddcode
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) Insert(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) BatchInsert(ctx context.Context, list []*model.OdsRtSzdnSnapshotFlowAddcode, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) Update(ctx context.Context, m *model.OdsRtSzdnSnapshotFlowAddcode) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Where("big_id = ?", id).Delete(&model.OdsRtSzdnSnapshotFlowAddcode{}).Error; err != nil {
		return fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsRtSzdnSnapshotFlowAddcodeFilters 把 XML L76-143 的 <where>/<if> 逐条重建。
//
// 对齐要点（都是「按字段语义猜」猜不出来的部分）：
//   - 只有 name / platenumber / platecolor 用 LIKE '%v%'；code / id / uuid / 数值类一律精确 =。
//   - flag == 'JiAnDong' 在 XML 里是 `t.orgcode = '030000011'`（固定机构编码），不是按机构名模糊匹配。
//   - 字符串字段的判定是 `x != null and x != ”`，数值/时间字段只判 `x != null`，
//     所以 Go 这边字符串用 model.NonEmpty，指针数值用 != nil。
//   - codeList / sectionList 是 Controller 先把逗号串拆开再传进来，XML 用 or 拼接，
//     等价于 IN。
func applyOdsRtSzdnSnapshotFlowAddcodeFilters(tx *gorm.DB, q *model.OdsRtSzdnSnapshotFlowAddcode) *gorm.DB {
	if q == nil {
		return tx
	}
	// 时间区间：XML 用 to_timestamp(#{applyTime},'yyyy-mm-dd HH24:MI:SS')，Go 直接传文本由 PG 隐式转换。
	if model.NonEmpty(q.ApplyTime1) {
		tx = tx.Where("snapshottime >= ?", model.Val(q.ApplyTime1))
	}
	if model.NonEmpty(q.ApplyTime2) {
		tx = tx.Where("snapshottime <= ?", model.Val(q.ApplyTime2))
	}
	if model.NonEmpty(q.BigId) {
		tx = tx.Where("big_id = ?", model.Val(q.BigId))
	}
	if model.NonEmpty(q.Datasource) {
		tx = tx.Where("datasource = ?", q.Datasource)
	}
	if model.NonEmpty(q.Cameratype) {
		tx = tx.Where("cameratype = ?", q.Cameratype)
	}
	if model.NonEmpty(q.Deviceid) {
		tx = tx.Where("deviceid = ?", q.Deviceid)
	}
	if model.NonEmpty(q.Gantrycode) {
		tx = tx.Where("gantrycode = ?", q.Gantrycode)
	}
	if model.NonEmpty(q.Gantryname) {
		tx = tx.Where("gantryname like ?", "%"+model.Val(q.Gantryname)+"%")
	}
	if model.NonEmpty(q.Roadcode) {
		tx = tx.Where("roadcode = ?", q.Roadcode)
	}
	if model.NonEmpty(q.Roadname) {
		tx = tx.Where("roadname like ?", "%"+model.Val(q.Roadname)+"%")
	}
	if model.NonEmpty(q.Sectioncode) {
		tx = tx.Where("sectioncode = ?", q.Sectioncode)
	}
	if model.NonEmpty(q.Sectionname) {
		tx = tx.Where("sectionname like ?", "%"+model.Val(q.Sectionname)+"%")
	}
	if model.NonEmpty(q.Tollcode) {
		tx = tx.Where("tollcode = ?", q.Tollcode)
	}
	if model.NonEmpty(q.Tollname) {
		tx = tx.Where("tollname like ?", "%"+model.Val(q.Tollname)+"%")
	}
	if model.NonEmpty(q.Orgcode) {
		tx = tx.Where("orgcode = ?", q.Orgcode)
	}
	// 权限范围：XML 是硬编码的机构号，不是机构名模糊匹配。
	if model.Val(q.Flag) == flagJiAnDong {
		tx = tx.Where("orgcode = ?", "030000011")
	}
	if model.NonEmpty(q.Orgname) {
		tx = tx.Where("orgname like ?", "%"+model.Val(q.Orgname)+"%")
	}
	if q.Direction != nil {
		tx = tx.Where("direction = ?", q.Direction)
	}
	if model.NonEmpty(q.Hexcode) {
		tx = tx.Where("hexcode = ?", q.Hexcode)
	}
	if model.NonEmpty(q.Pileno) {
		tx = tx.Where("pileno = ?", q.Pileno)
	}
	if q.Lon != nil {
		tx = tx.Where("lon = ?", q.Lon)
	}
	if q.Lat != nil {
		tx = tx.Where("lat = ?", q.Lat)
	}
	if model.NonEmpty(q.Deviceip) {
		tx = tx.Where("deviceip = ?", q.Deviceip)
	}
	if q.Siteid != nil {
		tx = tx.Where("siteid = ?", q.Siteid)
	}
	if q.Laneid != nil {
		tx = tx.Where("laneid = ?", q.Laneid)
	}
	if q.Snapshottimeunix != nil {
		tx = tx.Where("snapshottimeunix = ?", q.Snapshottimeunix)
	}
	if q.Snapshottime != nil {
		tx = tx.Where("snapshottime = ?", q.Snapshottime)
	}
	if q.Receivedtimeunix != nil {
		tx = tx.Where("receivedtimeunix = ?", q.Receivedtimeunix)
	}
	if q.Receivedtime != nil {
		tx = tx.Where("receivedtime = ?", q.Receivedtime)
	}
	if model.NonEmpty(q.Platenumber) {
		tx = tx.Where("platenumber like ?", "%"+model.Val(q.Platenumber)+"%")
	}
	if model.NonEmpty(q.Platecolor) {
		tx = tx.Where("platecolor like ?", "%"+model.Val(q.Platecolor)+"%")
	}
	if q.Platecolorcode != nil {
		tx = tx.Where("platecolorcode = ?", q.Platecolorcode)
	}
	if model.NonEmpty(q.Platetype) {
		tx = tx.Where("platetype = ?", q.Platetype)
	}
	if q.Platetypecode != nil {
		tx = tx.Where("platetypecode = ?", q.Platetypecode)
	}
	if q.Plateconfidence != nil {
		tx = tx.Where("plateconfidence = ?", q.Plateconfidence)
	}
	if model.NonEmpty(q.Carbrand) {
		tx = tx.Where("carbrand = ?", q.Carbrand)
	}
	if model.NonEmpty(q.Carcolor) {
		tx = tx.Where("carcolor = ?", q.Carcolor)
	}
	if q.Carcolorcode != nil {
		tx = tx.Where("carcolorcode = ?", q.Carcolorcode)
	}
	if model.NonEmpty(q.Cartype) {
		tx = tx.Where("cartype = ?", q.Cartype)
	}
	if q.Cartypecode != nil {
		tx = tx.Where("cartypecode = ?", q.Cartypecode)
	}
	if model.NonEmpty(q.Cardirection) {
		tx = tx.Where("cardirection = ?", q.Cardirection)
	}
	if model.NonEmpty(q.Snappicturepath) {
		tx = tx.Where("snappicturepath = ?", q.Snappicturepath)
	}
	if q.Loadtime != nil {
		tx = tx.Where("loadtime = ?", q.Loadtime)
	}
	if q.Gradelevel != nil {
		tx = tx.Where("gradelevel = ?", q.Gradelevel)
	}
	if model.NonEmpty(q.Datauuid) {
		tx = tx.Where("datauuid = ?", q.Datauuid)
	}
	if model.NonEmpty(q.Reserve3) {
		tx = tx.Where("reserve3 = ?", q.Reserve3)
	}
	// Controller 先把逗号串拆成切片，XML 再用 foreach 拼 or，语义等价于 IN。
	if len(q.CodeList) > 0 {
		tx = tx.Where("gantrycode IN ?", q.CodeList)
	}
	if len(q.SectionList) > 0 {
		tx = tx.Where("sectioncode IN ?", q.SectionList)
	}
	return tx
}
