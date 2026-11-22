package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/MultiSourceDataFlowService.java:30-501
// 类/职责: MultiSourceDataFlowService — 6 类数据源 → 统一 TrailBo → 实时轨迹拼接（Redis）+ 乱序待处理队列
// 对应 Go 文件: internal/service/multisource.go
// 关键映射:
//   processData(Object, dataType)                     → ProcessData
//   convertToStandardEvent + convertFromXxx ×6        → convertToStandardEvent + convertFromXxx ×6
//   tryAppendToTrail / createNewTrail / appendToXxx   → tryAppendToTrail / createNewTrail / appendToExistingTrail
//   needSplitTrail（7 天阈值）                          → needSplitTrail
//   addToPendingQueue / processPendingQueue           → addToPendingQueue / ProcessPendingQueue
//   PendingEvent 私有静态类                             → PendingEvent 结构体
//   redisTemplate(JDK 序列化 TrailInfo)                → JSON 序列化 TrailInfo（见 PARITY）
//
// PARITY: Java 把 TrailInfo / PendingEvent 直接塞进 Redis（JDK 序列化），Go 只能存 JSON。
// 因此 `trail:realtime:*` / `trail:pending:*` 两类 key 不能跨版本共用，切换前需清空。
//
// DIFF: Java 的 processData 用 (Exception e) 兜住所有异常并只打日志（调用方永远"成功"）；
// Go 版本把 error 返回给调用方 —— MQ 消费者可以据此决定 ack 还是重投，而不是默默丢数据。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 常量，对应 L40-60
const (
	realtimeTrailKeyPrefix = "trail:realtime:"
	pendingQueueKeyPrefix  = "trail:pending:"

	realtimeTrailTTL    = 7 * 24 * time.Hour // REALTIME_TRAIL_TTL = 604800 秒
	trailSplitThreshold = 7 * 24 * time.Hour // TRAIL_SPLIT_THRESHOLD = 7 天
	pendingMaxRetry     = 3                  // 重试 3 次后放弃
)

// 数据源类型常量，对应 convertToStandardEvent 的 switch 分支（L120-150）
const (
	DataTypeGantryCapture      = "GantryCapture"
	DataTypeBorderWeighing     = "BorderWeighingCapture"
	DataTypeProvCapture        = "ProvCapture"
	DataTypeServiceAreaCapture = "ServiceAreaCapture"
	DataTypeStationCapture     = "StationCapture"
	DataTypeFeeRecord          = "FeeRecord"
	DataTypeFeeStationEnter    = "FeeStationEnter"
	DataTypeFeeStationExit     = "FeeStationExit"
)

// PendingEvent 对应 PendingEvent（L495-500）
type PendingEvent struct {
	Event      model.TrailBo `json:"event"`
	RetryCount int           `json:"retryCount"`
	CreateTime string        `json:"createTime"`
}

// MultiSourceDataFlowService 对应 MultiSourceDataFlowService.java
type MultiSourceDataFlowService struct {
	cache *cache.Client
}

// NewMultiSourceDataFlowService 构造
func NewMultiSourceDataFlowService(cacheClient *cache.Client) *MultiSourceDataFlowService {
	return &MultiSourceDataFlowService{cache: cacheClient}
}

// ProcessData 对应 processData()（L73-104）：多源入口。
func (s *MultiSourceDataFlowService) ProcessData(ctx context.Context, data any, dataType string) error {
	slog.Debug("[数据流转] 收到数据", "dataType", dataType)

	event, err := convertToStandardEvent(data, dataType)
	if err != nil {
		return err
	}
	if event == nil {
		// 未知类型：记日志后跳过（与 Java 的 warn + return 一致）
		return nil
	}

	plateKey := event.Platenumber
	if utils.IsBlank(model.Val(plateKey)) {
		slog.Warn("[数据流转] 车牌号为空，跳过处理", "pointUuid", event.PointUuid)
		return nil
	}

	appended, err := s.tryAppendToTrail(ctx, model.Val(plateKey), event)
	if err != nil {
		return err
	}
	if !appended {
		slog.Info("[数据流转] 无法直接拼接，加入待处理队列",
			"plateKey", plateKey, "pointUuid", event.PointUuid)
		if err := s.addToPendingQueue(ctx, model.Val(plateKey), *event); err != nil {
			return err
		}
	}
	return nil
}

// convertToStandardEvent 对应 convertToStandardEvent()（L116-151）。
//
// DIFF: Java 在 switch 里直接强转 `(OdsRtSzdnSnapshotFlowAddcode) data`，类型不符时抛
// ClassCastException 被外层 catch 吞掉；Go 用类型断言 + ok 返回值，类型不符返回明确 error。
func convertToStandardEvent(data any, dataType string) (*model.TrailBo, error) {
	trailBo := &model.TrailBo{StateType: model.Str(dataType)}

	switch dataType {
	case DataTypeGantryCapture:
		src, ok := data.(*model.OdsRtSzdnSnapshotFlowAddcode)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsRtSzdnSnapshotFlowAddcode", dataType)
		}
		return convertFromGantryCapture(src, trailBo), nil

	case DataTypeBorderWeighing:
		src, ok := data.(*model.OdsSzdnProvinceBorderVehicleWeightNewstructure)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsSzdnProvinceBorderVehicleWeightNewstructure", dataType)
		}
		return convertFromBorderWeighing(src, trailBo), nil

	case DataTypeStationCapture:
		src, ok := data.(*model.OdsRtSzdnSnapshotFlowStationcaptureAddcode)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsRtSzdnSnapshotFlowStationcaptureAddcode", dataType)
		}
		return convertFromStationCapture(src, trailBo), nil

	case DataTypeFeeRecord:
		src, ok := data.(*model.OdsLwzxsfsjFeeRecords01)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsLwzxsfsjFeeRecords01", dataType)
		}
		return convertFromFeeRecord(src, trailBo), nil

	case DataTypeFeeStationEnter:
		src, ok := data.(*model.OdsLwzxsfsjFeeStationEnter01)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsLwzxsfsjFeeStationEnter01", dataType)
		}
		return convertFromFeeStationEnter(src, trailBo), nil

	case DataTypeFeeStationExit:
		src, ok := data.(*model.OdsLwzxsfsjFeeStationExit01)
		if !ok {
			return nil, fmt.Errorf("数据类型不匹配: %s ≠ *OdsLwzxsfsjFeeStationExit01", dataType)
		}
		return convertFromFeeStationExit(src, trailBo), nil

	default:
		slog.Warn("[数据转换] 未知的数据类型", "dataType", dataType)
		return nil, nil
	}
}

// convertFromGantryCapture 对应 convertFromGantryCapture()（L156-171）
func convertFromGantryCapture(data *model.OdsRtSzdnSnapshotFlowAddcode, trailBo *model.TrailBo) *model.TrailBo {
	trailBo.PointUuid = data.BigId
	trailBo.Platenumber = data.Platenumber
	trailBo.CaptureTime = model.Str(formatTimePtr(data.Snapshottime))
	trailBo.LocationCode = data.Deviceip
	trailBo.RoadCode = data.Roadcode
	trailBo.SectionCode = data.Sectioncode
	trailBo.Lon = data.Lon
	trailBo.Lat = data.Lat
	trailBo.GantryCaptureBO = data
	trailBo.IpType = model.Str("gantryip")
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// convertFromBorderWeighing 对应 convertFromBorderWeighing()（L176-185）
func convertFromBorderWeighing(data *model.OdsSzdnProvinceBorderVehicleWeightNewstructure,
	trailBo *model.TrailBo) *model.TrailBo {

	trailBo.PointUuid = data.Datauuid
	trailBo.Platenumber = data.PlateNo
	trailBo.CaptureTime = model.Str(formatDayPtr(data.CheckTime))
	trailBo.LocationCode = data.Location
	trailBo.BorderWeighingCaptureBO = data
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// convertFromStationCapture 对应 convertFromStationCapture()（L190-200）
func convertFromStationCapture(data *model.OdsRtSzdnSnapshotFlowStationcaptureAddcode,
	trailBo *model.TrailBo) *model.TrailBo {

	trailBo.PointUuid = model.Str(int64PtrToString(data.BigId))
	trailBo.Platenumber = data.Platenumber
	trailBo.CaptureTime = model.Str(formatDayPtr(data.Snapshottime))
	trailBo.LocationCode = data.Deviceip
	trailBo.StationCapture = data
	trailBo.IpType = model.Str("stationip")
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// convertFromFeeRecord 对应 convertFromFeeRecord()（L205-212）
func convertFromFeeRecord(data *model.OdsLwzxsfsjFeeRecords01, trailBo *model.TrailBo) *model.TrailBo {
	trailBo.PointUuid = model.Str(data.BigId)
	trailBo.Platenumber = data.Vehicleplate
	trailBo.CaptureTime = model.Str(formatDayPtr(data.Transtime))
	trailBo.FeeRecord = data
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// convertFromFeeStationEnter 对应 convertFromFeeStationEnter()（L217-226）：directionIn = true
func convertFromFeeStationEnter(data *model.OdsLwzxsfsjFeeStationEnter01, trailBo *model.TrailBo) *model.TrailBo {
	trailBo.PointUuid = model.Str(int64PtrToString(data.BigId))
	trailBo.Platenumber = data.Vehicleid
	trailBo.CaptureTime = model.Str(formatDayPtr(data.Entime))
	trailBo.LocationCode = data.Entolllaneid
	in := true
	trailBo.DirectionIn = &in
	trailBo.FeeStationEnter = data
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// convertFromFeeStationExit 对应 convertFromFeeStationExit()（L231-240）：directionIn = false
func convertFromFeeStationExit(data *model.OdsLwzxsfsjFeeStationExit01, trailBo *model.TrailBo) *model.TrailBo {
	trailBo.PointUuid = model.Str(data.BigId)
	trailBo.Platenumber = data.Exvehicleid
	trailBo.CaptureTime = model.Str(formatDayPtr(data.Extime))
	trailBo.LocationCode = data.Extolllaneid
	out := false
	trailBo.DirectionIn = &out
	trailBo.FeeStationExit = data
	trailBo.PointJosn = model.Str(mustJSON(data))
	return trailBo
}

// tryAppendToTrail 对应 tryAppendToTrail()（L257-294）
func (s *MultiSourceDataFlowService) tryAppendToTrail(ctx context.Context, plateKey string,
	newEvent *model.TrailBo) (bool, error) {

	if s.cache == nil {
		slog.Warn("[轨迹拼接] 缓存未启用，无法拼接", "plateKey", plateKey)
		return false, nil
	}
	trailKey := realtimeTrailKeyPrefix + plateKey

	current, err := s.loadTrail(ctx, trailKey)
	if err != nil {
		return false, err
	}

	// 无现有轨迹 → 新建
	if current == nil || current.Tracks == nil {
		slog.Info("[轨迹拼接] 无现有轨迹，创建新轨迹", "plateKey", plateKey)
		return true, s.createNewTrail(ctx, plateKey, *newEvent)
	}

	// 时间差超过 7 天 → 开启新轨迹链
	if needSplitTrail(current, newEvent) {
		slog.Info("[轨迹拼接] 时间差超过7天，开启新轨迹链", "plateKey", plateKey)
		return true, s.createNewTrail(ctx, plateKey, *newEvent)
	}

	appendToExistingTrail(current, *newEvent)
	if err := s.saveTrail(ctx, trailKey, current); err != nil {
		return false, err
	}
	slog.Debug("[轨迹拼接] 成功拼接到现有轨迹", "plateKey", plateKey, "pointUuid", newEvent.PointUuid)
	return true, nil
}

// needSplitTrail 对应 needSplitTrail()（L306-321）：与进入/离开时间任一相差超过 7 天即切割。
func needSplitTrail(current *model.TrailInfo, newEvent *model.TrailBo) bool {
	tracks := current.Tracks
	if tracks.EnterTime == nil || tracks.ExitTime == nil {
		return false
	}
	eventTime, err := utils.ParseDate(model.Val(newEvent.CaptureTime))
	if err != nil {
		slog.Warn("[轨迹拼接] 新事件时间无法解析，按不切割处理", "captureTime", newEvent.CaptureTime)
		return false
	}
	diffEnter := absDuration(eventTime.Sub(tracks.EnterTime.Time()))
	diffExit := absDuration(eventTime.Sub(tracks.ExitTime.Time()))
	return diffEnter > trailSplitThreshold || diffExit > trailSplitThreshold
}

// createNewTrail 对应 createNewTrail()（L329-360）
func (s *MultiSourceDataFlowService) createNewTrail(ctx context.Context, plateKey string,
	newEvent model.TrailBo) error {

	tracks := &model.ZdataTrailTracks{
		PlateKey: model.Str(plateKey),
		// Java: UUID.randomUUID().toString().replace("-", "")
		Uuid: model.Str(utils.GetUUID()),
	}
	zero := 0
	tracks.Type = &zero
	one := int64(1)
	tracks.PointCount = &one

	eventTime, err := utils.ParseDate(model.Val(newEvent.CaptureTime))
	if err != nil {
		// PARITY: Java 此时会 NPE 并进 catch（拼接失败）；Go 用零值继续，保证这条事件至少进轨迹
		slog.Warn("[轨迹拼接] 事件时间无法解析，使用零值", "captureTime", newEvent.CaptureTime)
	}
	day := model.NewDateTime(eventTime)
	tracks.EnterTime = day
	tracks.ExitTime = day

	trailList := []model.TrailBo{newEvent}
	tracks.TrailPoints = model.Str(mustJSON(trailList))

	newTrail := &model.TrailInfo{
		TrailUuid: tracks.Uuid,
		Tracks:    tracks,
		TrailList: trailList,
	}
	if err := s.saveTrail(ctx, realtimeTrailKeyPrefix+plateKey, newTrail); err != nil {
		return err
	}
	slog.Info("[轨迹拼接] 创建新轨迹成功", "plateKey", plateKey, "trailUuid", model.Val(tracks.Uuid))
	return nil
}

// appendToExistingTrail 对应 appendToExistingTrail()（L373-410）：
// 追加 → 按时间排序 → 更新点数/起止 → 点数 >= 3 标记完整。
func appendToExistingTrail(current *model.TrailInfo, newEvent model.TrailBo) {
	tracks := current.Tracks
	trailList := current.TrailList
	if trailList == nil {
		trailList = []model.TrailBo{}
	}
	trailList = append(trailList, newEvent)

	sort.SliceStable(trailList, func(i, j int) bool {
		return model.Val(trailList[i].CaptureTime) < model.Val(trailList[j].CaptureTime)
	})

	count := int64(len(trailList))
	tracks.PointCount = &count

	firstTime, firstErr := utils.ParseDate(model.Val(trailList[0].CaptureTime))
	lastTime, lastErr := utils.ParseDate(model.Val(trailList[len(trailList)-1].CaptureTime))

	if firstErr == nil && (tracks.EnterTime == nil || firstTime.Before(tracks.EnterTime.Time())) {
		tracks.EnterTime = model.NewDateTime(firstTime)
	}
	if lastErr == nil && (tracks.ExitTime == nil || lastTime.After(tracks.ExitTime.Time())) {
		tracks.ExitTime = model.NewDateTime(lastTime)
	}
	if len(trailList) >= 3 {
		full := 1
		tracks.Type = &full
	}
	tracks.TrailPoints = model.Str(mustJSON(trailList))
	current.TrailList = trailList
}

// addToPendingQueue 对应 addToPendingQueue()（L418-432）
func (s *MultiSourceDataFlowService) addToPendingQueue(ctx context.Context, plateKey string,
	event model.TrailBo) error {

	if s.cache == nil {
		return nil
	}
	pending := PendingEvent{Event: event, RetryCount: 0, CreateTime: utils.FormatDateTime(time.Now())}
	raw, err := json.Marshal(pending)
	if err != nil {
		return fmt.Errorf("待处理事件序列化失败: %w", err)
	}
	if err := s.cache.Raw().RPush(ctx, pendingQueueKeyPrefix+plateKey, string(raw)).Err(); err != nil {
		return fmt.Errorf("待处理事件入队失败: %w", err)
	}
	slog.Debug("[待处理队列] 加入队列", "plateKey", plateKey, "pointUuid", event.PointUuid)
	return nil
}

// ProcessPendingQueue 对应 processPendingQueue()（L440-490）：定时任务调用，重试乱序数据。
//
// PARITY: Java 先 range 全量取回再 delete 整个 key（不是原子操作，两步之间写入的事件会丢）；
// Go 保持同样顺序以对齐行为，README「已知风险」登记了这一点（可用 LMOVE 或 Lua 改造成原子）。
func (s *MultiSourceDataFlowService) ProcessPendingQueue(ctx context.Context) {
	if s.cache == nil {
		return
	}
	slog.Info("[待处理队列] 开始处理")
	rdb := s.cache.Raw()

	// DIFF（报告 02 P1-2）: Java 用 KEYS 枚举，Go 改为 SCAN 游标遍历 —— 大库上 KEYS 是
	// O(N) 且阻塞 Redis 单线程。ScanKeys 内部去重（SCAN 可能重复返回同一个键）。
	keys, err := s.cache.ScanKeys(ctx, pendingQueueKeyPrefix+"*", 500)
	if err != nil {
		slog.Error("[待处理队列] 读取队列 key 失败", "err", err)
		return
	}
	if len(keys) == 0 {
		slog.Info("[待处理队列] 无待处理数据")
		return
	}

	totalProcessed := 0
	for _, queueKey := range keys {
		plateKey := trimPrefix(queueKey, pendingQueueKeyPrefix)

		items, err := rdb.LRange(ctx, queueKey, 0, -1).Result()
		if err != nil {
			slog.Error("[待处理队列] 读取队列失败", "key", queueKey, "err", err)
			continue
		}
		if len(items) == 0 {
			continue
		}
		// 清空队列（与 Java 的 delete 一致）
		_ = rdb.Del(ctx, queueKey).Err()

		for _, raw := range items {
			var pending PendingEvent
			if err := json.Unmarshal([]byte(raw), &pending); err != nil {
				slog.Error("[待处理队列] 解析待处理事件失败", "key", queueKey, "err", err)
				continue
			}
			event := pending.Event
			ok, err := s.tryAppendToTrail(ctx, plateKey, &event)
			if err != nil {
				slog.Error("[待处理队列] 重试拼接异常", "plateKey", plateKey, "err", err)
			}
			if ok {
				totalProcessed++
				continue
			}
			pending.RetryCount++
			if pending.RetryCount < pendingMaxRetry {
				if raw, err := json.Marshal(pending); err == nil {
					_ = rdb.RPush(ctx, queueKey, string(raw)).Err()
				}
			} else {
				slog.Warn("[待处理队列] 超过最大重试次数，放弃",
					"plateKey", plateKey, "pointUuid", event.PointUuid)
			}
		}
	}
	slog.Info("[待处理队列] 处理完成", "successCount", totalProcessed)
}

// ---- 缓存读写 ----

// loadTrail 从 Redis 读实时轨迹（Java: redisTemplate.opsForValue().get）
func (s *MultiSourceDataFlowService) loadTrail(ctx context.Context, key string) (*model.TrailInfo, error) {
	raw, ok, err := s.cache.Get(ctx, key)
	if err != nil || !ok || raw == "" {
		return nil, err
	}
	var trail model.TrailInfo
	if err := json.Unmarshal([]byte(raw), &trail); err != nil {
		slog.Warn("[轨迹拼接] 轨迹反序列化失败，按无轨迹处理", "key", key, "err", err)
		return nil, nil
	}
	return &trail, nil
}

// saveTrail 写实时轨迹并刷新 7 天 TTL
func (s *MultiSourceDataFlowService) saveTrail(ctx context.Context, key string, trail *model.TrailInfo) error {
	raw, err := json.Marshal(trail)
	if err != nil {
		return fmt.Errorf("实时轨迹序列化失败: %w", err)
	}
	if err := s.cache.SetWithTTL(ctx, key, string(raw), realtimeTrailTTL); err != nil {
		return fmt.Errorf("实时轨迹写缓存失败: %w", err)
	}
	return nil
}

// ---- 小工具 ----

// formatTimePtr 对应 DateUtils.parseDateToStr(YYYY_MM_DD_HH_MM_SS, Date)，
// 把「Java 里带 @JsonFormat 的 Date 字段」格式化成 yyyy-MM-dd HH:mm:ss。
//
// DIFF: Java 侧靠 Jackson 注解决定格式，字段声明的都是 Date，所以同一个工具方法能处理所有时间字段；
// Go 侧把三种格式拆成了 model.Day / model.DateTime / model.Timestamp 三个类型，
// 这里用一个小约束把它们统一起来，避免每个调用点都写一次类型转换。
func formatTimePtr[T interface{ Time() time.Time }](p *T) string {
	if p == nil {
		return ""
	}
	return utils.FormatDateTime((*p).Time())
}

// formatDayPtr 保留为别名，语义与 formatTimePtr 完全一致（早期只有 model.Day 一种时间类型）。
func formatDayPtr[T interface{ Time() time.Time }](d *T) string { return formatTimePtr(d) }

// int64PtrToString 对应 String.valueOf(Long)
func int64PtrToString(v *int64) string {
	if v == nil {
		return ""
	}
	return strconv.FormatInt(*v, 10)
}

// trimPrefix 对应 queueKey.replace(PENDING_QUEUE_KEY_PREFIX, "")
func trimPrefix(s, prefix string) string {
	if len(s) >= len(prefix) && s[:len(prefix)] == prefix {
		return s[len(prefix):]
	}
	return s
}

// absDuration 取绝对值
func absDuration(d time.Duration) time.Duration {
	if d < 0 {
		return -d
	}
	return d
}

// mustJSON 序列化失败时返回空串并记日志（对应 Java 的 JSON.toJSONString，异常不外抛）
func mustJSON(v any) string {
	raw, err := json.Marshal(v)
	if err != nil {
		slog.Warn("[数据转换] 序列化失败", "err", err)
		return ""
	}
	return string(raw)
}
