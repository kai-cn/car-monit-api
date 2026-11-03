package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/TrailAggregationService.java:35-445
// 类/职责: TrailAggregationService — 轨迹补点（位置富集 + 缺失点补齐）、质量评估、多轨迹合并
// 对应 Go 文件: internal/service/trail.go
// 关键映射:
//   performTrailFitting(TrailInfo)        → PerformTrailFitting
//   enrichLocationInfo / enrichFrom*      → enrichLocationInfo / enrichFromLocationDict / enrichFromGantryIP / enrichFromStationIP
//   fillMissingPoints / tryFillBetween    → fillMissingPoints / tryFillBetween
//   buildNewTrailVersion                  → buildNewTrailVersion
//   assessTrailQuality + TrailQuality     → AssessTrailQuality + TrailQuality
//   mergeTrails(List<TrailInfo>)          → MergeTrails
//   注入 4 个 Service（location/gantryIp/stationIp/section） → 单个 DictRegistry
//
// DIFF: Java 的 enrichLocationInfo 用 `JSON.parseObject(JSON.toJSONString(point), TrailBo.class)`
// 做深拷贝（只为避免改到调用方的对象）。Go 侧用值拷贝 `enriched := *point` ——
// 富集只覆盖标量字段与两个 BO 指针，不修改嵌套对象的内容，浅拷贝语义已足够，
// 且省掉一次 JSON 往返（8 亿级数据量下这条路径是热点）。
//
// DIFF: Java 的 captureTime 是字符串，用 DateUtils.parseDate 转 Date 再比大小；
// Go 侧保留字符串（与出入参 JSON 一致），仅在需要时间差/时间区间时解析——
// 解析失败按零值处理并打日志，不 panic（Java 会 NPE）。

import (
	"context"
	"encoding/json"
	"log/slog"
	"sort"
	"strconv"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 轨迹补点的判定阈值，对应 L275
const fillTimeGapThreshold = 30 * time.Minute

// TrailQuality 对应静态内部类 TrailQuality（L386-393）
type TrailQuality struct {
	Score                float64 `json:"score"`
	Level                string  `json:"level"`
	PointCount           int     `json:"pointCount"`
	DurationHours        float64 `json:"durationHours"`
	LocationCompleteRate float64 `json:"locationCompleteRate"`
}

// TrailAggregationService 对应 TrailAggregationService.java
type TrailAggregationService struct {
	dict *DictRegistry
}

// NewTrailAggregationService 构造
func NewTrailAggregationService(dict *DictRegistry) *TrailAggregationService {
	return &TrailAggregationService{dict: dict}
}

// PerformTrailFitting 对应 performTrailFitting()（L64-92）：
// 富集 → 补点 → 按时间重排 → 生成新版本（UUID 不变，便于版本追溯）。
func (s *TrailAggregationService) PerformTrailFitting(ctx context.Context,
	original *model.TrailInfo) (*model.TrailInfo, error) {

	if original == nil {
		slog.Warn("[轨迹补点] 原始轨迹为空，跳过")
		return original, nil
	}
	slog.Info("[轨迹补点] 开始补点", "trailUuid", original.TrailUuid)

	if original.TrailList == nil {
		slog.Warn("[轨迹补点] 原始轨迹点为空，跳过", "trailUuid", original.TrailUuid)
		return original, nil
	}
	originalCount := len(original.TrailList)

	// 步骤1：补充位置信息
	enriched, err := s.enrichLocationInfo(ctx, original.TrailList)
	if err != nil {
		return nil, err
	}

	// 步骤2：检测并补全缺失点
	fitted := s.fillMissingPoints(enriched)

	// 步骤3：按采集时间重排（Java 用 Comparator.comparing(String)，即字典序）
	sort.SliceStable(fitted, func(i, j int) bool {
		return model.Val(fitted[i].CaptureTime) < model.Val(fitted[j].CaptureTime)
	})

	// 步骤4：构建新版本
	newTrail := s.buildNewTrailVersion(original, fitted)

	slog.Info("[轨迹补点] 补点完成", "trailUuid", original.TrailUuid,
		"original", originalCount, "fitted", len(fitted), "added", len(fitted)-originalCount)
	return newTrail, nil
}

// enrichLocationInfo 对应 enrichLocationInfo()（L100-134）：
// 四张字典一次加载，逐点按 locationCode 富集。
func (s *TrailAggregationService) enrichLocationInfo(ctx context.Context,
	points []model.TrailBo) ([]model.TrailBo, error) {

	if s.dict == nil {
		slog.Warn("[轨迹补点] 字典未装配，跳过位置富集")
		return points, nil
	}

	locationDict, err := s.dict.LocationDictMap(ctx)
	if err != nil {
		return nil, err
	}
	gantryIPMap, err := s.dict.GantryIPMap(ctx)
	if err != nil {
		return nil, err
	}
	stationIPMap, err := s.dict.StationIPMap(ctx)
	if err != nil {
		return nil, err
	}
	sectionMap, err := s.dict.SectionMap(ctx)
	if err != nil {
		return nil, err
	}

	result := make([]model.TrailBo, len(points))
	for i := range points {
		enriched := points[i] // 浅拷贝，见文件头 DIFF
		locationCode := model.Val(enriched.LocationCode)
		if utils.IsNotBlank(locationCode) {
			if location, ok := locationDict[locationCode]; ok && location != nil {
				enrichFromLocationDict(&enriched, location)
			}
			if gantryIP, ok := gantryIPMap[locationCode]; ok && gantryIP != nil {
				enrichFromGantryIP(&enriched, gantryIP, sectionMap)
			}
			if stationIP, ok := stationIPMap[locationCode]; ok && stationIP != nil {
				enrichFromStationIP(&enriched, stationIP)
			}
		}
		result[i] = enriched
	}
	return result, nil
}

// enrichFromLocationDict 对应 enrichFromLocationDict()（L139-156）：
// 只填空字段，不覆盖已有值；standardCode 无条件覆盖。
func enrichFromLocationDict(point *model.TrailBo, location *model.ZdataLocationDict) {
	if point.Lon == nil {
		point.Lon = location.Longitude
	}
	if point.Lat == nil {
		point.Lat = location.Latitude
	}
	if utils.IsBlank(model.Val(point.RoadCode)) {
		point.RoadCode = location.Roadcode
	}
	if utils.IsBlank(model.Val(point.SectionCode)) {
		point.SectionCode = location.Sectioncode
	}
	if utils.IsBlank(model.Val(point.DevName)) {
		point.DevName = location.Name
	}
	point.StandardCode = location.StandardCode
}

// enrichFromGantryIP 对应 enrichFromGantryIp()（L161-189）：
// 门架 IP 命中后，连带门架主表的经纬度/路线/桩号一起补上，并标记 locationFlag=1。
//
// 参数 sectionMap 在 Java 里传了但未使用（保留签名以便将来按路段派生信息）。
func enrichFromGantryIP(point *model.TrailBo, gantryIP *model.OdsSzdnGantryIp,
	sectionMap map[string]*model.OdsSzdnSection) {

	point.GantryIpBO = gantryIP
	point.DevCode = model.Str(gantryIP.GantryCode)
	point.DevName = model.Str(gantryIP.GantryName)

	if gantry := gantryIP.OdsSzdnGantry; gantry != nil {
		if point.Lon == nil {
			point.Lon = parseFloatPtr(model.Val(gantry.Lon))
		}
		if point.Lat == nil {
			point.Lat = parseFloatPtr(model.Val(gantry.Lat))
		}
		if utils.IsBlank(model.Val(point.RoadCode)) {
			point.RoadCode = gantry.RoadCode
		}
		if utils.IsBlank(model.Val(point.SectionCode)) {
			point.SectionCode = gantry.SectionCode
		}
		if utils.IsBlank(model.Val(point.Pileno)) {
			point.Pileno = gantry.PileNo
		}
		point.Direction = gantry.Direction
		point.IsVirtual = gantry.IsVirtual
	}
	point.LocationFlag = model.Str("1")
}

// enrichFromStationIP 对应 enrichFromStationIp()（L194-216）
func enrichFromStationIP(point *model.TrailBo, stationIP *model.OdsSzdnTollStationIp) {
	point.StationIpBO = stationIP
	point.DevCode = model.Str(stationIP.TollCode)
	point.DevName = model.Str(stationIP.TollName)

	if toll := stationIP.OdsSzdnToll; toll != nil {
		if point.Lon == nil && utils.IsNotBlank(model.Val(toll.Longitude)) {
			point.Lon = parseFloatPtr(model.Val(toll.Longitude))
		}
		if point.Lat == nil && utils.IsNotBlank(model.Val(toll.Latitude)) {
			point.Lat = parseFloatPtr(model.Val(toll.Latitude))
		}
		if utils.IsBlank(model.Val(point.RoadCode)) {
			point.RoadCode = toll.RoadCode
		}
		if utils.IsBlank(model.Val(point.SectionCode)) {
			point.SectionCode = toll.SectionCode
		}
	}
	point.LocationFlag = model.Str("1")
}

// fillMissingPoints 对应 fillMissingPoints()（L228-252）
//
// PARITY: Java 的 tryFillBetween 目前只打日志不产出补点（TODO 待接路段门架序列），
// 所以这里同样是"原样返回 + 记录可疑间隔"。保持空实现是刻意的：
// 一旦凭空造点，轨迹就成了假数据，比缺点更危险。
func (s *TrailAggregationService) fillMissingPoints(points []model.TrailBo) []model.TrailBo {
	if len(points) < 2 {
		return points
	}
	result := make([]model.TrailBo, 0, len(points))
	result = append(result, points[0])
	for i := 1; i < len(points); i++ {
		prev, curr := points[i-1], points[i]
		result = append(result, curr)
		if fill := s.tryFillBetween(prev, curr); len(fill) > 0 {
			// 插在当前点之前（Java: result.addAll(result.size() - 1, fillPoints)）
			tail := result[len(result)-1]
			result = append(result[:len(result)-1], append(fill, tail)...)
		}
	}
	return result
}

// tryFillBetween 对应 tryFillBetween()（L257-282）
func (s *TrailAggregationService) tryFillBetween(prev, curr model.TrailBo) []model.TrailBo {
	// 必须同路段才有"中间漏点"的可能
	if utils.IsBlank(model.Val(prev.SectionCode)) || utils.IsBlank(model.Val(curr.SectionCode)) {
		return nil
	}
	if model.Val(prev.SectionCode) != model.Val(curr.SectionCode) {
		return nil
	}

	prevTime, prevErr := utils.ParseDate(model.Val(prev.CaptureTime))
	currTime, currErr := utils.ParseDate(model.Val(curr.CaptureTime))
	if prevErr != nil || currErr != nil {
		return nil
	}
	timeDiff := currTime.Sub(prevTime)
	if timeDiff < 0 {
		timeDiff = -timeDiff
	}
	if timeDiff > fillTimeGapThreshold {
		slog.Debug("[轨迹补点] 发现可能缺失点", "prev", prev.PointUuid, "curr", curr.PointUuid,
			"timeDiffMinutes", timeDiff/time.Minute)
		// TODO（与 Java 一致）：接入路段门架序列后生成虚拟补点
	}
	return nil
}

// buildNewTrailVersion 对应 buildNewTrailVersion()（L290-321）：
// UUID 不变、点数与起止时间随补点结果更新、点数 >= 5 标记为完整轨迹。
func (s *TrailAggregationService) buildNewTrailVersion(original *model.TrailInfo,
	newPoints []model.TrailBo) *model.TrailInfo {

	newTrail := &model.TrailInfo{TrailUuid: original.TrailUuid}

	var newTracks model.ZdataTrailTracks
	if original.Tracks != nil {
		newTracks = *original.Tracks // 值拷贝，避免改到入参
	}
	pointCount := int64(len(newPoints))
	newTracks.PointCount = &pointCount

	if len(newPoints) > 0 {
		newTracks.EnterTime = parseDateTimePtr(model.Val(newPoints[0].CaptureTime))
		newTracks.ExitTime = parseDateTimePtr(model.Val(newPoints[len(newPoints)-1].CaptureTime))
	}
	if len(newPoints) >= 5 {
		full := 1
		newTracks.Type = &full
	}
	// PARITY：Java 用 JSON.toJSONString 序列化点时带上了全部 getter 字段；
	// Go 用结构体 tag 序列化，字段集合由 TrailBo 的 json tag 决定（与 Java 字段名一致）。
	if raw, err := json.Marshal(newPoints); err == nil {
		newTracks.TrailPoints = model.Str(string(raw))
	} else {
		slog.Error("[轨迹补点] 轨迹点序列化失败", "trailUuid", original.TrailUuid, "err", err)
	}

	newTrail.Tracks = &newTracks
	newTrail.TrailList = newPoints
	return newTrail
}

// AssessTrailQuality 对应 assessTrailQuality()（L331-381）：
// 总分 100 = 点数(30) + 时间跨度(30) + 经纬度完整度(40)。
func (s *TrailAggregationService) AssessTrailQuality(trail *model.TrailInfo) TrailQuality {
	quality := TrailQuality{}
	if trail == nil || len(trail.TrailList) == 0 {
		quality.Level = "EMPTY"
		return quality
	}

	points := trail.TrailList
	pointCount := len(points)

	// 点数量评分：10 个点封顶
	pointScore := minFloat(1.0, float64(pointCount)/10.0) * 30

	// 时间跨度评分：2 小时封顶
	firstTime, _ := utils.ParseDate(model.Val(points[0].CaptureTime))
	lastTime, _ := utils.ParseDate(model.Val(points[pointCount-1].CaptureTime))
	durationHours := lastTime.Sub(firstTime).Hours()
	durationScore := minFloat(1.0, durationHours/2.0) * 30

	// 位置完整度评分
	locationComplete := 0
	for i := range points {
		if points[i].Lon != nil && points[i].Lat != nil {
			locationComplete++
		}
	}
	locationScore := float64(locationComplete) / float64(pointCount) * 40

	total := pointScore + durationScore + locationScore
	quality.Score = total
	switch {
	case total >= 90:
		quality.Level = "EXCELLENT"
	case total >= 70:
		quality.Level = "GOOD"
	case total >= 50:
		quality.Level = "FAIR"
	default:
		quality.Level = "POOR"
	}
	quality.PointCount = pointCount
	quality.DurationHours = durationHours
	quality.LocationCompleteRate = float64(locationComplete) / float64(pointCount)

	slog.Debug("[轨迹质量] 评估完成", "score", total, "level", quality.Level, "points", pointCount)
	return quality
}

// MergeTrails 对应 mergeTrails()（L403-444）：把同一辆车的多段轨迹拼成一条。
func (s *TrailAggregationService) MergeTrails(trails []*model.TrailInfo) *model.TrailInfo {
	if len(trails) == 0 {
		return nil
	}
	if len(trails) == 1 {
		return trails[0]
	}
	slog.Info("[轨迹合并] 开始合并", "count", len(trails))

	allPoints := make([]model.TrailBo, 0, 64)
	for _, t := range trails {
		if t == nil || t.TrailList == nil {
			continue
		}
		allPoints = append(allPoints, t.TrailList...)
	}
	if len(allPoints) == 0 {
		slog.Warn("[轨迹合并] 所有轨迹点均为空，返回空结果")
		return nil
	}
	sort.SliceStable(allPoints, func(i, j int) bool {
		return model.Val(allPoints[i].CaptureTime) < model.Val(allPoints[j].CaptureTime)
	})

	mergedTracks := model.ZdataTrailTracks{}
	trailing := int64(len(allPoints))
	mergedTracks.PointCount = &trailing
	mergedTracks.EnterTime = parseDateTimePtr(model.Val(allPoints[0].CaptureTime))
	mergedTracks.ExitTime = parseDateTimePtr(model.Val(allPoints[len(allPoints)-1].CaptureTime))
	trailType := 0
	if len(allPoints) >= 5 {
		trailType = 1
	}
	mergedTracks.Type = &trailType
	if raw, err := json.Marshal(allPoints); err == nil {
		mergedTracks.TrailPoints = model.Str(string(raw))
	}

	// 沿用第一条轨迹的 UUID / 车牌标识
	if head := trails[0]; head != nil && head.Tracks != nil {
		mergedTracks.Uuid = head.Tracks.Uuid
		mergedTracks.PlateKey = head.Tracks.PlateKey
	}

	merged := &model.TrailInfo{
		TrailUuid: mergedTracks.Uuid,
		Tracks:    &mergedTracks,
		TrailList: allPoints,
	}
	slog.Info("[轨迹合并] 合并完成", "originalCount", len(trails), "mergedPoints", len(allPoints))
	return merged
}

// ---- 内部小工具 ----

// parseFloatPtr 等价于 Java 的 new BigDecimal(String)；空串/非法值返回 nil。
func parseFloatPtr(s string) *float64 {
	if utils.IsBlank(s) {
		return nil
	}
	v, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return nil
	}
	return &v
}

// parseDateTimePtr 对应 DateUtils.parseDate(String)：解析失败或空串时返回 nil。
//
// DIFF: Java 的 DateUtils.parseDate 返回 null（异常被吞掉），这里用 (*model.DateTime)(nil) 复现同样的「空值」。
func parseDateTimePtr(s string) *model.DateTime {
	if utils.IsBlank(s) {
		return nil
	}
	t, err := utils.ParseDate(s)
	if err != nil || t.IsZero() {
		return nil
	}
	return model.NewDateTime(t)
}

// minFloat 等价于 Java 的 Math.min
func minFloat(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}
