package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DelayMonitoringService.java:36-471
// 类/职责: DelayMonitoringService — 四段延迟（设备上报 / 消息传输 / 数据处理 / 端到端）的埋点、告警与统计
// 对应 Go 文件: internal/service/delay_monitor.go
// 关键映射:
//   ConcurrentHashMap<String,Long> ×3          → sync.Map ×3（messageProduceTimes/messageConsumeTimes/deviceCaptureTimes）
//   @Value("${monitoring.*-threshold-ms}")     → config.MonitoringConfig
//   redisTemplate.opsForList().rightPush+expire → Redis RPush + Expire(48h)
//   @PostConstruct 建 2 线程池                  → 无（Go 不需要线程池，见 DIFF）
//   @Scheduled(fixedRate = 600000)             → scheduler 注册 GenerateStatsReport
//   DelayStats / 内部静态类                     → DelayStats 结构体
//
// DIFF: Java 的 statsExecutor（fixed 2 线程）是为了"统计任务不占调用线程"；
// Go 里调用方自己决定 go GenerateStatsReport()，所以服务内不持有线程池——
// 少一个需要 shutdown 的资源，也少一处"任务堆积没人发现"的隐患。
//
// DIFF: Java 的 ConcurrentHashMap 只增不减会内存泄漏（dataId 未回调时永不清理），
// Go 侧保持同构行为以免语义漂移，但在 README「已知风险」里登记了这一点。

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// 延迟监控的 Redis key 前缀，对应 L78-98
const (
	deviceDelayPrefix  = "monitoring:delay:device:"
	messageDelayPrefix = "monitoring:delay:message:"
	processDelayPrefix = "monitoring:delay:process:"
	e2eDelayPrefix     = "monitoring:delay:e2e:"
	alertCountPrefix   = "monitoring:alert:count:"

	delaySampleTTL      = 48 * time.Hour // 对应 expire(key, 2, TimeUnit.DAYS)
	alertThrottleWindow = time.Minute    // 对应 "1 分钟内最多告警 1 次"
	alertThrottleTTL    = time.Minute
)

// DelayStats 对应 DelayStats 内部类（L428-469）
type DelayStats struct {
	DeviceReportAvg    int64 `json:"deviceReportAvg"`
	DeviceReportMax    int64 `json:"deviceReportMax"`
	MessageTransferAvg int64 `json:"messageTransferAvg"`
	MessageTransferMax int64 `json:"messageTransferMax"`
	DataProcessAvg     int64 `json:"dataProcessAvg"`
	DataProcessMax     int64 `json:"dataProcessMax"`
	EndToEndAvg        int64 `json:"endToEndAvg"`
	EndToEndMax        int64 `json:"endToEndMax"`
}

// DelayMonitoringService 对应 DelayMonitoringService.java
type DelayMonitoringService struct {
	cache *cache.Client
	cfg   config.MonitoringConfig

	// 三个"时间戳暂存表"：key 是 dataId / messageId，value 是毫秒时间戳
	messageProduceTimes sync.Map
	messageConsumeTimes sync.Map
	deviceCaptureTimes  sync.Map
}

// NewDelayMonitoringService 构造
func NewDelayMonitoringService(cacheClient *cache.Client, cfg config.MonitoringConfig) *DelayMonitoringService {
	return &DelayMonitoringService{cache: cacheClient, cfg: cfg}
}

// Init 对应 @PostConstruct init()（L121-127）：只打初始化日志。
//
// DIFF: Java 在这里创建线程池；Go 没有线程池可建，保留方法是为了让装配代码与 Java 的
// Bean 生命周期一一对应（main 里能看到"谁在启动时做了什么"）。
func (s *DelayMonitoringService) Init() {
	slog.Info("[延迟监控] 初始化完成",
		"deviceReportThresholdMs", s.cfg.DeviceReportThresholdMs,
		"messageTransferThresholdMs", s.cfg.MessageTransferThresholdMs,
		"dataProcessThresholdMs", s.cfg.DataProcessThresholdMs,
		"endToEndThresholdMs", s.cfg.EndToEndThresholdMs)
}

// ==================== 设备上报延迟 ====================

// RecordDeviceCaptureTime 对应 recordDeviceCaptureTime()（L139-141）
func (s *DelayMonitoringService) RecordDeviceCaptureTime(dataID string, captureTime int64) {
	s.deviceCaptureTimes.Store(dataID, captureTime)
}

// RecordServiceReceiveTime 对应 recordServiceReceiveTime()（L151-173）。
// 返回 -1 表示"没有采集时间可对账"（Java 用 Long == null 分支表达同样语义）。
func (s *DelayMonitoringService) RecordServiceReceiveTime(ctx context.Context, dataID, deviceID string) int64 {
	v, ok := s.deviceCaptureTimes.LoadAndDelete(dataID)
	if !ok {
		return -1
	}
	captureTime, _ := v.(int64)
	delay := time.Now().UnixMilli() - captureTime

	s.pushSample(ctx, deviceDelayPrefix+deviceID+":"+utils.FormatCompactDate(time.Now()), delay)
	if delay > int64(s.cfg.DeviceReportThresholdMs) {
		s.triggerAlert(ctx, "DEVICE_REPORT_DELAY", deviceID, delay, int64(s.cfg.DeviceReportThresholdMs))
	}
	slog.Debug("[延迟监控] 设备上报延迟", "deviceId", deviceID, "dataId", dataID, "delayMs", delay)
	return delay
}

// ==================== 消息传输延迟 ====================

// RecordMessageProduceTime 对应 recordMessageProduceTime()（L182-184）
func (s *DelayMonitoringService) RecordMessageProduceTime(messageID string) {
	s.messageProduceTimes.Store(messageID, time.Now().UnixMilli())
}

// RecordMessageConsumeTime 对应 recordMessageConsumeTime()（L193-215）
func (s *DelayMonitoringService) RecordMessageConsumeTime(ctx context.Context, messageID string) int64 {
	v, ok := s.messageProduceTimes.LoadAndDelete(messageID)
	if !ok {
		return -1
	}
	produceTime, _ := v.(int64)
	delay := time.Now().UnixMilli() - produceTime

	s.pushSample(ctx, messageDelayPrefix+utils.FormatCompactDate(time.Now()), delay)
	if delay > int64(s.cfg.MessageTransferThresholdMs) {
		s.triggerAlert(ctx, "MESSAGE_TRANSFER_DELAY", messageID, delay, int64(s.cfg.MessageTransferThresholdMs))
	}
	slog.Debug("[延迟监控] 消息传输延迟", "messageId", messageID, "delayMs", delay)
	return delay
}

// ==================== 数据处理延迟 ====================

// RecordProcessStartTime 对应 recordProcessStartTime()（L224-226）
func (s *DelayMonitoringService) RecordProcessStartTime(messageID string) {
	s.messageConsumeTimes.Store(messageID, time.Now().UnixMilli())
}

// RecordProcessEndTime 对应 recordProcessEndTime()（L235-257）
func (s *DelayMonitoringService) RecordProcessEndTime(ctx context.Context, messageID string) int64 {
	v, ok := s.messageConsumeTimes.LoadAndDelete(messageID)
	if !ok {
		return -1
	}
	consumeTime, _ := v.(int64)
	delay := time.Now().UnixMilli() - consumeTime

	s.pushSample(ctx, processDelayPrefix+utils.FormatCompactDate(time.Now()), delay)
	if delay > int64(s.cfg.DataProcessThresholdMs) {
		s.triggerAlert(ctx, "DATA_PROCESS_DELAY", messageID, delay, int64(s.cfg.DataProcessThresholdMs))
	}
	slog.Debug("[延迟监控] 数据处理延迟", "messageId", messageID, "delayMs", delay)
	return delay
}

// ==================== 端到端延迟 ====================

// CalculateEndToEndDelay 对应 calculateEndToEndDelay()（L271-286）：
// 设备采集 → 最终落库的完整耗时，无暂存表参与，直接由调用方给两个时间点。
func (s *DelayMonitoringService) CalculateEndToEndDelay(ctx context.Context,
	dataID string, captureTime, storageTime int64, deviceID string) int64 {

	delay := storageTime - captureTime
	s.pushSample(ctx, e2eDelayPrefix+deviceID+":"+utils.FormatCompactDate(time.Now()), delay)
	if delay > int64(s.cfg.EndToEndThresholdMs) {
		s.triggerAlert(ctx, "END_TO_END_DELAY", deviceID, delay, int64(s.cfg.EndToEndThresholdMs))
	}
	slog.Debug("[延迟监控] 端到端延迟", "deviceId", deviceID, "dataId", dataID, "delayMs", delay)
	return delay
}

// ==================== 告警 ====================

// triggerAlert 对应 triggerAlert()（L300-322）：同一 (类型,目标) 每分钟最多告警一次。
//
// DIFF: Java 用 Redis 存"上次告警时间戳"做节流（跨实例共享）；Go 保持同样做法，
// 但用 SetNX 抢占窗口而不是"读-判断-写"三步——并发下不会出现两个实例同时通过闸门。
func (s *DelayMonitoringService) triggerAlert(ctx context.Context,
	alertType, targetID string, actualDelay, threshold int64) {

	if s.cache == nil {
		return
	}
	alertKey := alertCountPrefix + alertType + ":" + targetID
	ok, err := s.cache.SetNXWithTTL(ctx, alertKey, time.Now().UnixMilli(), alertThrottleTTL)
	if err != nil || !ok {
		// 已在节流窗口内，跳过
		return
	}
	slog.Error(fmt.Sprintf("[延迟监控告警] [%s] 延迟超过阈值！目标: %s, 实际延迟: %dms, 阈值: %dms",
		alertType, targetID, actualDelay, threshold))
	// PARITY: Java 侧此处是 "// TODO: 集成告警系统"，Go 同样只落日志，
	// 接入告警通道时改这里即可（单点收口）。
}

// ==================== 统计报告 ====================

// GenerateStatsReport 对应 @Scheduled(fixedRate = 600000) generateStatsReport()（L329-344）。
// 由 scheduler 每 10 分钟调用。
func (s *DelayMonitoringService) GenerateStatsReport(ctx context.Context) {
	stats := s.CalculateStats(ctx)
	slog.Info("[延迟监控统计]",
		"deviceReportAvg", stats.DeviceReportAvg, "deviceReportMax", stats.DeviceReportMax,
		"messageTransferAvg", stats.MessageTransferAvg, "messageTransferMax", stats.MessageTransferMax,
		"dataProcessAvg", stats.DataProcessAvg, "dataProcessMax", stats.DataProcessMax,
		"endToEndAvg", stats.EndToEndAvg, "endToEndMax", stats.EndToEndMax)
}

// CalculateStats 对应 calculateStats()（L349-373）
func (s *DelayMonitoringService) CalculateStats(ctx context.Context) DelayStats {
	var stats DelayStats

	deviceDelays := s.getDelays(ctx, deviceDelayPrefix)
	stats.DeviceReportAvg = calculateAvg(deviceDelays)
	stats.DeviceReportMax = calculateMax(deviceDelays)

	messageDelays := s.getDelays(ctx, messageDelayPrefix)
	stats.MessageTransferAvg = calculateAvg(messageDelays)
	stats.MessageTransferMax = calculateMax(messageDelays)

	processDelays := s.getDelays(ctx, processDelayPrefix)
	stats.DataProcessAvg = calculateAvg(processDelays)
	stats.DataProcessMax = calculateMax(processDelays)

	e2eDelays := s.getDelays(ctx, e2eDelayPrefix)
	stats.EndToEndAvg = calculateAvg(e2eDelays)
	stats.EndToEndMax = calculateMax(e2eDelays)

	return stats
}

// getDelays 对应 getDelays()（L378-393）：把当天所有维度 key 的样本摊平成一个切片。
//
// PARITY: Java 用 keys(prefix + "*:" + today)（KEYS 命令，生产会阻塞 Redis）。
// Go 保持同为 Keys 以对齐行为；README「已知风险」已登记：>1 万 key 时应改 SCAN 游标遍历。
func (s *DelayMonitoringService) getDelays(ctx context.Context, prefix string) []int64 {
	if s.cache == nil {
		return nil
	}
	rdb := s.cache.Raw()
	pattern := prefix + "*:" + utils.FormatCompactDate(time.Now())
	keys, err := rdb.Keys(ctx, pattern).Result()
	if err != nil || len(keys) == 0 {
		return nil
	}
	delays := make([]int64, 0, len(keys)*16)
	for _, key := range keys {
		values, err := rdb.LRange(ctx, key, 0, -1).Result()
		if err != nil {
			continue
		}
		for _, v := range values {
			var d int64
			if _, err := fmt.Sscanf(v, "%d", &d); err == nil {
				delays = append(delays, d)
			}
		}
	}
	return delays
}

// calculateAvg 对应 calculateAvg()（L398-403）：空集合返回 0（不是 NaN）
func calculateAvg(values []int64) int64 {
	if len(values) == 0 {
		return 0
	}
	var sum int64
	for _, v := range values {
		sum += v
	}
	return sum / int64(len(values))
}

// calculateMax 对应 calculateMax()（L408-413）
func calculateMax(values []int64) int64 {
	if len(values) == 0 {
		return 0
	}
	max := values[0]
	for _, v := range values[1:] {
		if v > max {
			max = v
		}
	}
	return max
}

// pushSample 封装 "RPush + Expire 2 天"（Java 侧每处都是这两行相邻出现）。
func (s *DelayMonitoringService) pushSample(ctx context.Context, key string, delay int64) {
	if s.cache == nil {
		return
	}
	rdb := s.cache.Raw()
	pipe := rdb.Pipeline()
	pipe.RPush(ctx, key, delay)
	pipe.Expire(ctx, key, delaySampleTTL)
	if _, err := pipe.Exec(ctx); err != nil {
		slog.Warn("[延迟监控] 写入延迟样本失败", "key", key, "err", err)
	}
}
