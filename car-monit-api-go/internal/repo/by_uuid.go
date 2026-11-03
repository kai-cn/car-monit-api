package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/
//   OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl.java:62-90  select...ByQueryUuids
//   OdsRtSzdnSnapshotFlowAddcodeServiceImpl.java:59-88                  select...ByQueryUuids
//   OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl.java:63-90       select...ByQueryUuids
//   OdsCxztFwqcllsServiceImpl.java:57-86                                select...ByQueryUuids
//   OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl.java:62-94     select...ByQueryUuids
//   OdsLwzxsfsjFeeRecords01ServiceImpl.java:54-85                        select...ByQueryUuids
//   OdsLwzxsfsjFeeStationEnter01ServiceImpl.java:57-86                   select...ByQueryUuids
//   OdsLwzxsfsjFeeStationExit01ServiceImpl.java:57-86                    select...ByQueryUuids
// 类/职责: 按 datauuid / cid 单条回源查询 —— "ByQueryUuids" 系列方法在缓存未命中时走的那一步
// 对应 Go 文件: internal/repo/by_uuid.go
// 关键映射:
//   querybo.setDatauuid(uuid) + selectList(querybo)  → ListByDatauuid(..., limit 1)
//   querybo.setCid(uuid)      + selectList(querybo)  → ListByCid(..., limit 1)
//   querybo.setApplyTime1/2   （时间区间）            → from / to 参数
//
// DIFF: Go 把"缓存未命中 → 回源"的编排留在 service（见 sysutil.go 的 lookupByUUIDs），
// repo 只负责那一条 SQL —— 否则缓存逻辑要在 8 个 Repo 里各抄一遍。
//
// PARITY: Java 侧这些 Mapper 同样没有 XML，selectList 的时间列名只能从实体字段推断：
// addcode/stationcapture 用 snapshottime，fee_records01 用 transtime。

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// applyTimeRange 把 Java 的 applyTime1 / applyTime2 两个 "yyyy-MM-dd HH:mm:ss" 字符串翻译成闭区间条件。
// 任一为 time.Time{} 即不加该侧条件，等价于 MyBatis <if test="applyTime1 != null and applyTime1 != ”">。
func applyTimeRange(tx *gorm.DB, column string, from, to time.Time) *gorm.DB {
	if !from.IsZero() {
		tx = tx.Where(column+" >= ?", from)
	}
	if !to.IsZero() {
		tx = tx.Where(column+" <= ?", to)
	}
	return tx
}

// ListByDatauuid 对应省界称重 selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids 的回源查询。
func (r *OdsSzdnProvinceBorderVehicleWeightNewstructureRepo) ListByDatauuid(ctx context.Context, uuid string) (
	[]model.OdsSzdnProvinceBorderVehicleWeightNewstructure, error) {

	var list []model.OdsSzdnProvinceBorderVehicleWeightNewstructure
	err := r.db.ORM(ctx).Table(OdsSzdnProvinceBorderVehicleWeightNewstructureTable).
		Where("datauuid = ?", uuid).Limit(1).Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsSzdnProvinceBorderVehicleWeightNewstructureRepo.ListByDatauuid: %w", err)
	}
	return list, nil
}

// ListByDatauuid 对应门架抓拍 selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids 的回源查询（带抓拍时间区间）。
func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) ListByDatauuid(ctx context.Context, uuid string, from, to time.Time) (
	[]model.OdsRtSzdnSnapshotFlowAddcode, error) {

	tx := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowAddcodeTable).Where("datauuid = ?", uuid)
	tx = applyTimeRange(tx, "snapshottime", from, to)
	var list []model.OdsRtSzdnSnapshotFlowAddcode
	if err := tx.Limit(1).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowAddcodeRepo.ListByDatauuid: %w", err)
	}
	return list, nil
}

// ListByDatauuid 对应省界抓拍 selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids 的回源查询。
func (r *OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo) ListByDatauuid(ctx context.Context, uuid string) (
	[]model.OdsRtSzdnSnapshotFlowProvcaptureAddcode, error) {

	var list []model.OdsRtSzdnSnapshotFlowProvcaptureAddcode
	err := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowProvcaptureAddcodeTable).
		Where("datauuid = ?", uuid).Limit(1).Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowProvcaptureAddcodeRepo.ListByDatauuid: %w", err)
	}
	return list, nil
}

// ListByDatauuid 对应服务区抓拍 selectOdsCxztFwqcllsByQueryUuids 的回源查询。
func (r *OdsCxztFwqcllsRepo) ListByDatauuid(ctx context.Context, uuid string) ([]model.OdsCxztFwqclls, error) {
	var list []model.OdsCxztFwqclls
	err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).
		Where("datauuid = ?", uuid).Limit(1).Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsCxztFwqcllsRepo.ListByDatauuid: %w", err)
	}
	return list, nil
}

// ListByDatauuid 对应收费站抓拍 selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids 的回源查询。
func (r *OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo) ListByDatauuid(ctx context.Context, uuid string, from, to time.Time) (
	[]model.OdsRtSzdnSnapshotFlowStationcaptureAddcode, error) {

	tx := r.db.ORM(ctx).Table(OdsRtSzdnSnapshotFlowStationcaptureAddcodeTable).Where("datauuid = ?", uuid)
	tx = applyTimeRange(tx, "snapshottime", from, to)
	var list []model.OdsRtSzdnSnapshotFlowStationcaptureAddcode
	if err := tx.Limit(1).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsRtSzdnSnapshotFlowStationcaptureAddcodeRepo.ListByDatauuid: %w", err)
	}
	return list, nil
}

// ListByCid 对应卡口流水 selectOdsLwzxsfsjFeeRecords01ByQueryUuids 的回源查询（带交易时间区间）。
func (r *OdsLwzxsfsjFeeRecords01Repo) ListByCid(ctx context.Context, cid string, from, to time.Time) (
	[]model.OdsLwzxsfsjFeeRecords01, error) {

	tx := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Where("cid = ?", cid)
	tx = applyTimeRange(tx, "transtime", from, to)
	var list []model.OdsLwzxsfsjFeeRecords01
	if err := tx.Limit(1).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.ListByCid: %w", err)
	}
	return list, nil
}

// ListByCid 对应收费站入口流水 selectOdsLwzxsfsjFeeStationEnter01ByQueryUuids 的回源查询。
func (r *OdsLwzxsfsjFeeStationEnter01Repo) ListByCid(ctx context.Context, cid string) (
	[]model.OdsLwzxsfsjFeeStationEnter01, error) {

	var list []model.OdsLwzxsfsjFeeStationEnter01
	err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationEnter01Table).
		Where("cid = ?", cid).Limit(1).Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationEnter01Repo.ListByCid: %w", err)
	}
	return list, nil
}

// ListByCid 对应收费站出口流水 selectOdsLwzxsfsjFeeStationExit01ByQueryUuids 的回源查询。
func (r *OdsLwzxsfsjFeeStationExit01Repo) ListByCid(ctx context.Context, cid string) (
	[]model.OdsLwzxsfsjFeeStationExit01, error) {

	var list []model.OdsLwzxsfsjFeeStationExit01
	err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeStationExit01Table).
		Where("cid = ?", cid).Limit(1).Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeStationExit01Repo.ListByCid: %w", err)
	}
	return list, nil
}
