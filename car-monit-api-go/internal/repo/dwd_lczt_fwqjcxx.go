package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/DwdLcztFwqjcxxMapper.java
// 类/职责: DwdLcztFwqjcxxMapper — 服务区基础信息的读入口（见下方 PARITY：表名不是同名表）
// 对应 Go 文件: internal/repo/dwd_lczt_fwqjcxx.go
// 关键映射:
//   extends BaseMapper<DwdLcztFwqjcxx>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectDwdLcztFwqjcxxById(AgentPk)   → GetByID
//   selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx q) → List/Count（条件见 applyDwdLcztFwqjcxxFilters）
// DIFF: Java 用 XML/注解把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。
//
// PARITY: 这个 Mapper 的名字会骗人 —— 它并不查 dwd_lczt_fwqjcxx 表。
// DwdLcztFwqjcxxMapper.xml:42-68 的 <sql id="selectDwdLcztFwqjcxxVo"> 一律从
// `jl_data01.ods_szdn_service` 取数，再把 t.id_card / t.service_code / ... 逐列 AS 成
// agent_pk / yxtzj / fwqbm / ... 。上一版 Go 直接 Table("dwd_lczt_fwqjcxx") 并
// WHERE agent_pk = ?，而库里既没有这张表、也没有 agent_pk 这个列，接口必然 42P01。
// 现在按 XML 原样重建：表 + 别名列全部对齐。

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// DwdLcztFwqjcxxTable 是 XML 里真正读的表（见上方 PARITY）。
const DwdLcztFwqjcxxTable = "jl_data01.ods_szdn_service"

// dwdLcztFwqjcxxSelect 逐字对应 XML 的 selectDwdLcztFwqjcxxVo（25 列，去掉 t. 前缀以便直接配 Table()）。
// XML 没选的列（fxmc/sslxmc/sczhszgs/mj/sftgcshfw/synx/load_time/all_col_pk）在 Java 里也是 null，
// 对应 Go 零值，两边一致。
//
// PARITY: business_date 在库里是 timestamp without time zone，而实体字段 yyrq 是 String。
// Java 侧走 ResultSet#getString，拿到的是服务器原样的墙钟文本 "2012-12-01 00:00:00"（不发生时区换算）；
// Go 侧 pgx 把 timestamp 解成 time.Time 再转字符串会变成 "2012-12-01T00:00:00Z"。
// 所以这里用 to_char 在 SQL 里就定型成同样的文本，不能去掉 HH24:MI:SS。
//
// 注意：这个 raw string 里不能出现 // 注释 —— Go 不会把 raw string 里的 // 当注释，
// 它会原样拼进 SQL 导致 syntax error。所有解释性文字必须放在字符串外面。
const dwdLcztFwqjcxxSelect = `id AS agent_pk,
	id_card AS yxtzj,
	service_code AS fwqbm,
	service_name AS fwqmc,
	direction AS fxdm,
	longitude AS jd,
	latitude AS wd,
	road_code AS sslxbh,
	section_code AS ssldbh,
	section_name AS ssldmc,
	pile_no AS sczhkgs,
	org_code AS ssglzxbm,
	org_name AS ssglzxmc,
	city_code AS xzqhmc,
	district_name AS xzqhdm,
	to_char(business_date, 'YYYY-MM-DD HH24:MI:SS') AS yyrq,
	parking_num AS cws,
	has_cross AS sfszlkk,
	charge_num AS cdzs,
	food_service AS sfcyfw,
	stay_service AS sftgzsfw,
	automobile_service AS sftgqxfw,
	supermarket_service AS sftgcsfw,
	gas_service AS sftgjyfw,
	service_alias_name AS lyxt`

// DwdLcztFwqjcxxRepo 对应 Java 的 DwdLcztFwqjcxxMapper（@Repository 由 main() 里的显式构造代替）
type DwdLcztFwqjcxxRepo struct{ db *db.Client }

// NewDwdLcztFwqjcxxRepo 对应 Spring @Repository 的 Bean 注册
func NewDwdLcztFwqjcxxRepo(c *db.Client) *DwdLcztFwqjcxxRepo { return &DwdLcztFwqjcxxRepo{db: c} }

// TableName 供测试与日志使用
func (r *DwdLcztFwqjcxxRepo) TableName() string { return DwdLcztFwqjcxxTable }

// GetByID 对应 DwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxById(AgentPk)
// XML 的条件是 `where t.id = #{agentPk}`（不是 agent_pk 列）。
func (r *DwdLcztFwqjcxxRepo) GetByID(ctx context.Context, id string) (*model.DwdLcztFwqjcxx, error) {
	var m model.DwdLcztFwqjcxx
	err := r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Select(dwdLcztFwqjcxxSelect).
		Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("DwdLcztFwqjcxxRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 DwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *DwdLcztFwqjcxxRepo) List(ctx context.Context, q *model.DwdLcztFwqjcxx, limit int) ([]model.DwdLcztFwqjcxx, error) {
	tx := applyDwdLcztFwqjcxxFilters(r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Select(dwdLcztFwqjcxxSelect), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.DwdLcztFwqjcxx
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("DwdLcztFwqjcxxRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectDwdLcztFwqjcxxList 配合 PageInfo#getTotal
func (r *DwdLcztFwqjcxxRepo) Count(ctx context.Context, q *model.DwdLcztFwqjcxx) (int64, error) {
	tx := applyDwdLcztFwqjcxxFilters(r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("DwdLcztFwqjcxxRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *DwdLcztFwqjcxxRepo) ListAll(ctx context.Context) ([]model.DwdLcztFwqjcxx, error) {
	var list []model.DwdLcztFwqjcxx
	if err := r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Select(dwdLcztFwqjcxxSelect).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("DwdLcztFwqjcxxRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *DwdLcztFwqjcxxRepo) Insert(ctx context.Context, m *model.DwdLcztFwqjcxx) error {
	if err := r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Create(m).Error; err != nil {
		return fmt.Errorf("DwdLcztFwqjcxxRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *DwdLcztFwqjcxxRepo) BatchInsert(ctx context.Context, list []*model.DwdLcztFwqjcxx, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *DwdLcztFwqjcxxRepo) Update(ctx context.Context, m *model.DwdLcztFwqjcxx) error {
	if err := r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Save(m).Error; err != nil {
		return fmt.Errorf("DwdLcztFwqjcxxRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
// 注意主键列在真实表上叫 id（agent_pk 只是 SELECT 期间的别名，不能写进 WHERE）。
func (r *DwdLcztFwqjcxxRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(DwdLcztFwqjcxxTable).Where("id = ?", id).Delete(&model.DwdLcztFwqjcxx{}).Error; err != nil {
		return fmt.Errorf("DwdLcztFwqjcxxRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyDwdLcztFwqjcxxFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
//
// PARITY: XML 的 <if> 写的是 t.agent_pk / t.yxtzj / t.wd / t.jd / t.xzqhmc …，这些名字在
// ods_szdn_service 里都不存在（它们只是 SELECT 的别名）—— 只要前端带上其中任何一个参数，
// Java 侧就会拼出非法 SQL 而报错。Go 侧不复制这个 bug：把参数映射到真实列上。
func applyDwdLcztFwqjcxxFilters(tx *gorm.DB, q *model.DwdLcztFwqjcxx) *gorm.DB {
	if q == nil {
		return tx
	}
	if model.NonEmpty(q.AgentPk) {
		tx = tx.Where("id = ?", q.AgentPk)
	}
	if model.NonEmpty(q.Fwqbm) {
		tx = tx.Where("service_code = ?", q.Fwqbm)
	}
	if model.NonEmpty(q.Fwqmc) {
		tx = tx.Where("service_name = ?", q.Fwqmc)
	}
	if model.NonEmpty(q.Sslxbh) {
		tx = tx.Where("road_code = ?", q.Sslxbh)
	}
	if model.NonEmpty(q.Ssldbh) {
		tx = tx.Where("section_code = ?", q.Ssldbh)
	}
	if model.NonEmpty(q.Ssldmc) {
		tx = tx.Where("section_name = ?", q.Ssldmc)
	}
	return tx
}
