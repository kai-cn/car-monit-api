package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataLossDetectionService.java:37-417
// 类/职责: DataLossDetectionService — 上报消息 ID 与库内主键的差集统计，识别「丢了哪些」「重复了哪些」
// 对应 Go 文件: internal/service/loss_detection.go
// 关键映射:
//   DetectionResult（静态内部类）           → DetectionResult 结构体 + Passed()
//   @Value("${detection.*}")                → config.DetectionConfig
//   redisTemplate.opsForSet().add/members   → Redis SAdd / SMembers
//   redisTemplate.opsForValue().increment   → cache.Incr
//   @Scheduled(fixedRateString = "${detection.interval-minutes:30}000") → scheduler 注册 ScheduledDetection
//   detectionExecutor(4 线程)               → 无（见 DIFF）
//
// DIFF: Java 的定时任务是 ThreadPoolExecutor.submit 后立即返回，异常被吞在任务里；
// Go 版本由 scheduler 在 goroutine 里调用，panic 由 scheduler 统一 recover ——
// 检测任务挂掉不会静默，会留下 ERROR 日志与堆栈。
//
// PARITY: Java 侧上报 ID 存 Redis Set（按小时分桶，48h TTL），不做去重上限；
// 高峰期单小时集合可能有百万级成员，SMembers 一次性拉回是主要内存风险，README 已登记。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 数据丢失检测的 Redis key 前缀，对应 L73-83
const (
	reportedMsgPrefix  = "detection:reported:"
	detectionReportPfx = "detection:report:"
	deviceCountPrefix  = "detection:device:count:"

	reportedSetTTL     = 48 * time.Hour     // expire(hourKey, 48, HOURS)
	deviceCountTTL     = 48 * time.Hour     // expire(deviceKey, 2, DAYS)
	detectionReportTTL = 7 * 24 * time.Hour // set(reportKey, report, 7, DAYS)
)

// DetectionResult 对应 DetectionResult（L362-415）
type DetectionResult struct {
	StartTime           time.Time `json:"startTime"`
	EndTime             time.Time `json:"endTime"`
	ReportedCount       int       `json:"reportedCount"`
	StoredCount         int       `json:"storedCount"`
	LostCount           int       `json:"lostCount"`
	LossRate            float64   `json:"lossRate"`
	LostMessageIDs      []string  `json:"lostMessageIds"`
	DuplicateCount      int       `json:"duplicateCount"`
	DuplicateMessageIDs []string  `json:"duplicateMessageIds"`
}

// Passed 对应 isPassed()（L412-414）：零丢失且零重复才算通过
func (r *DetectionResult) Passed() bool {
	return r.LossRate == 0 && r.DuplicateCount == 0
}

// DataLossDetectionService 对应 DataLossDetectionService.java
type DataLossDetectionService struct {
	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	cache        *cache.Client
	reliability  *DataReliabilityService
	cfg          config.DetectionConfig
}

// NewDataLossDetectionService 构造
func NewDataLossDetectionService(snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	cacheClient *cache.Client, reliability *DataReliabilityService,
	cfg config.DetectionConfig) *DataLossDetectionService {

	return &DataLossDetectionService{
		snapshotRepo: snapshotRepo, cache: cacheClient, reliability: reliability, cfg: cfg,
	}
}

// Init 对应 @PostConstruct init()（L89-94）
func (s *DataLossDetectionService) Init() {
	slog.Info("[数据丢失检测] 初始化完成",
		"windowSizeMinutes", s.cfg.WindowSizeMinutes,
		"intervalMinutes", s.cfg.IntervalMinutes,
		"lossThresholdPercent", s.cfg.LossThresholdPct)
}

// RecordReportedMessage 对应 recordReportedMessage()（L106-116）：
// 上报即记账——按小时进 Set（去重），按设备+日期计数。
func (s *DataLossDetectionService) RecordReportedMessage(ctx context.Context,
	messageID, deviceID string, timestamp int64) {

	if s.cache == nil {
		return
	}
	rdb := s.cache.Raw()
	at := time.UnixMilli(timestamp)

	hourKey := reportedMsgPrefix + utils.FormatHour(at)
	if err := rdb.SAdd(ctx, hourKey, messageID).Err(); err != nil {
		slog.Warn("[数据丢失检测] 记录上报消息失败", "messageId", messageID, "err", err)
	}
	_ = rdb.Expire(ctx, hourKey, reportedSetTTL).Err()

	deviceKey := deviceCountPrefix + deviceID + ":" + utils.FormatDate(at)
	if _, err := s.cache.Incr(ctx, deviceKey, 1); err != nil {
		slog.Warn("[数据丢失检测] 设备计数失败", "deviceId", deviceID, "err", err)
	}
	_ = rdb.Expire(ctx, deviceKey, deviceCountTTL).Err()
}

// ScheduledDetection 对应 @Scheduled(fixedRateString = "${detection.interval-minutes:30}000")
//
// 一次检测 = 取窗口 [now - windowSize, now] → 差集 → 报告 → 超阈值告警。
// 由 scheduler 每 intervalMinutes 调用一次。
func (s *DataLossDetectionService) ScheduledDetection(ctx context.Context) {
	endTime := time.Now()
	startTime := utils.AddMinutes(endTime, -s.cfg.WindowSizeMinutes)
	slog.Info("[数据丢失检测] 开始检测", "startTime", startTime, "endTime", endTime)

	result, err := s.DetectDataLoss(ctx, startTime, endTime)
	if err != nil {
		slog.Error("[数据丢失检测] 定时检测异常", "err", err)
		return
	}
	s.generateReport(ctx, result)
	if result.LossRate > s.cfg.LossThresholdPct {
		s.sendAlert(result)
	}
}

// DetectDataLoss 对应 detectDataLoss()（L166-209）：
// 上报集合 - 库内主键集合 = 丢失集合；库内主键重复出现的即重复记录。
//
// DIFF: Java 方法返回对象、异常向上抛（@Scheduled 里 catch 打日志）；
// Go 返回 (result, error)，由调用方决定"继续还是放弃"——定时任务与 HTTP 触发共用同一个实现。
func (s *DataLossDetectionService) DetectDataLoss(ctx context.Context,
	startTime, endTime time.Time) (*DetectionResult, error) {

	result := &DetectionResult{StartTime: startTime, EndTime: endTime}

	// 1. 窗口内上报的消息 ID
	reported := s.getReportedMessageIDs(ctx, startTime, endTime)
	result.ReportedCount = len(reported)
	slog.Debug("[数据丢失检测] 窗口内上报消息数", "count", reported)

	// 2. 库内同窗口的主键（只取 big_id，不拉整行）
	storedIDs, err := s.snapshotRepo.ListBigIDsBetween(ctx, startTime, endTime)
	if err != nil {
		return nil, fmt.Errorf("查询数据库记录失败: %w", err)
	}
	result.StoredCount = len(storedIDs)
	slog.Debug("[数据丢失检测] 数据库存储记录数", "count", len(storedIDs))

	// 3. 建库内主键集合，同时统计重复
	stored := make(map[string]struct{}, len(storedIDs))
	seen := make(map[string]struct{}, len(storedIDs))
	duplicates := make([]string, 0)
	for _, id := range storedIDs {
		stored[id] = struct{}{}
		if _, dup := seen[id]; dup {
			duplicates = append(duplicates, id)
			continue
		}
		seen[id] = struct{}{}
	}

	// 4. 差集：上报了但库里没有
	lost := make([]string, 0)
	for id := range reported {
		if _, ok := stored[id]; !ok {
			lost = append(lost, id)
		}
	}
	result.LostCount = len(lost)
	result.LostMessageIDs = lost

	// 5. 丢失率（上报为 0 时记 0，避免除零）
	if result.ReportedCount > 0 {
		result.LossRate = float64(result.LostCount) / float64(result.ReportedCount) * 100
	}
	result.DuplicateCount = len(duplicates)
	result.DuplicateMessageIDs = duplicates

	slog.Info("[数据丢失检测] 检测完成",
		"reported", result.ReportedCount, "stored", result.StoredCount,
		"lost", result.LostCount, "duplicate", result.DuplicateCount,
		"lossRate", fmt.Sprintf("%.2f", result.LossRate))
	return result, nil
}

// getReportedMessageIDs 对应 getReportedMessageIds()（L214-229）：逐小时 SUnION 成一个集合。
//
// DIFF: Java 用 addHours 跳过整点，最后一小时可能取不到；
// Go 用同样的整点步进（对齐行为），但用 startTime 的整点向下取整作起点 ——
// 见 PARITY 说明：若窗口起点是 10:37，Java 的 formatHour 会把它映射到 10:00 key，
// Go 同样 FormatHour(10:37) = "…10:00:00"，因此 key 一致，无需额外取整。
func (s *DataLossDetectionService) getReportedMessageIDs(ctx context.Context,
	startTime, endTime time.Time) map[string]struct{} {

	ids := make(map[string]struct{})
	if s.cache == nil {
		return ids
	}
	rdb := s.cache.Raw()
	for current := startTime; current.Before(endTime); current = utils.AddHours(current, 1) {
		hourKey := reportedMsgPrefix + utils.FormatHour(current)
		members, err := rdb.SMembers(ctx, hourKey).Result()
		if err != nil {
			slog.Warn("[数据丢失检测] 读取上报集合失败", "key", hourKey, "err", err)
			continue
		}
		for _, id := range members {
			ids[id] = struct{}{}
		}
	}
	return ids
}

// generateReport 对应 generateReport()（L263-281）：报告落 Redis，7 天可查。
func (s *DataLossDetectionService) generateReport(ctx context.Context, result *DetectionResult) {
	reportID := uuid.NewString()[:8]
	report := map[string]any{
		"reportId":       reportID,
		"startTime":      utils.FormatDateTime(result.StartTime),
		"endTime":        utils.FormatDateTime(result.EndTime),
		"reportedCount":  result.ReportedCount,
		"storedCount":    result.StoredCount,
		"lostCount":      result.LostCount,
		"duplicateCount": result.DuplicateCount,
		"lossRate":       result.LossRate,
		"generatedTime":  utils.FormatDateTime(time.Now()),
	}
	raw, err := json.Marshal(report)
	if err == nil && s.cache != nil {
		if err := s.cache.SetWithTTL(ctx, detectionReportPfx+reportID, string(raw), detectionReportTTL); err != nil {
			slog.Warn("[数据丢失检测] 报告写入失败", "reportId", reportID, "err", err)
		}
	}
	slog.Info("[数据丢失检测] 生成报告", "reportId", reportID)
}

// sendAlert 对应 sendAlert()（L286-295）
func (s *DataLossDetectionService) sendAlert(result *DetectionResult) {
	slog.Error(fmt.Sprintf(
		"[数据丢失检测告警] 数据丢失率超过阈值！时间窗口: %s ~ %s, 上报: %d, 存储: %d, 丢失: %d, 丢失率: %.2f%%",
		utils.FormatDateTime(result.StartTime), utils.FormatDateTime(result.EndTime),
		result.ReportedCount, result.StoredCount, result.LostCount, result.LossRate))
	// PARITY: Java 此处为 "// TODO: 集成告警系统"，Go 保持一致（告警通道单点接入）。
}

// TriggerCompensation 对应 triggerCompensation()（L304-328）：
// 对每条丢失消息，若 Redis 里还有消息体就走可靠性服务的重发链路。
//
// DIFF: Java 先 get 一次消息体只为判空，再调 retrySend（内部又 get 一次）；
// Go 把"判空"与"重发"都交给 RetrySend，但保留一次预检以输出"内容已过期"这条可观测日志。
func (s *DataLossDetectionService) TriggerCompensation(ctx context.Context, result *DetectionResult) {
	if result == nil || result.LostCount == 0 {
		return
	}
	slog.Info("[数据丢失检测] 触发补偿拉取", "lostCount", result.LostCount)

	for _, messageID := range result.LostMessageIDs {
		if s.cache != nil {
			_, ok, err := s.cache.Get(ctx, msgContentPrefix+messageID)
			if err != nil {
				slog.Error("[数据丢失检测] 补偿拉取异常", "messageId", messageID, "err", err)
				continue
			}
			if !ok {
				slog.Warn("[数据丢失检测] 丢失消息内容已过期", "messageId", messageID)
				continue
			}
		}
		if s.reliability != nil {
			s.reliability.RetrySend(ctx, messageID)
		}
	}
}

// GetDeviceReportStats 对应 getDeviceReportStats()（L337-357）：
// deviceID 为空时按日期枚举所有设备（Redis KEYS）。
//
// PARITY: KEYS 同样是阻塞命令，Java 侧就是这么写的；Go 侧保持一致，
// 统计口径（deviceId + 当天计数）与 Java 完全对齐，便于两边对数。
func (s *DataLossDetectionService) GetDeviceReportStats(ctx context.Context,
	deviceID string, date time.Time) (map[string]int64, error) {

	stats := make(map[string]int64)
	if s.cache == nil {
		return stats, nil
	}
	rdb := s.cache.Raw()
	day := utils.FormatDate(date)

	if deviceID != "" {
		n, err := rdb.Get(ctx, deviceCountPrefix+deviceID+":"+day).Int64()
		if err != nil && err.Error() != "redis: nil" {
			return nil, fmt.Errorf("读取设备上报计数失败: %w", err)
		}
		stats[deviceID] = n
		return stats, nil
	}

	keys, err := rdb.Keys(ctx, deviceCountPrefix+"*:"+day).Result()
	if err != nil {
		return nil, fmt.Errorf("枚举设备上报计数失败: %w", err)
	}
	for _, key := range keys {
		// key 形如 detection:device:count:<deviceId>:<yyyy-MM-dd>
		rest := strings.TrimPrefix(key, deviceCountPrefix)
		idx := strings.LastIndex(rest, ":")
		if idx < 0 {
			continue
		}
		devID := rest[:idx]
		n, err := rdb.Get(ctx, key).Int64()
		if err != nil {
			continue
		}
		stats[devID] = n
	}
	return stats, nil
}
