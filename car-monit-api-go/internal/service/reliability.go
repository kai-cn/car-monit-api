package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataReliabilityService.java:48-723
// 类/职责: DataReliabilityService — 消息「三重确认 + 超时补偿 + 死信」保障
// 对应 Go 文件: internal/service/reliability.go
// 关键映射:
//   ReliableMessageWrapper（静态内部类）      → ReliableMessageWrapper 结构体
//   MessageMeta + ConcurrentHashMap          → messageMeta + sync.Map
//   MessageStatus 枚举                       → MessageStatus（string 常量）
//   ExecutorService（重试 4 / 补偿 2 线程）   → 每次异步动作一个 goroutine（Go 里 goroutine 就是线程池）
//   @Scheduled(fixedRateString = "...000")   → scheduler 注册（见 internal/scheduler）
//   redisTemplate.opsForValue/opsForList     → cache.Client / cache.Client.Raw()
// DIFF: Java 的 Redis 是"裸 RedisTemplate"，取值要强转；Go 侧统一走 cache.Client，
//       只有 List 操作（超时队列）才退化用 Raw()——因为 cache 包只封装了高频的 KV 用法。

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"sync/atomic"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/mq"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

// Redis key 常量，对应 L88-108
const (
	msgStatusPrefix     = "reliability:msg:status:"
	msgContentPrefix    = "reliability:msg:content:"
	timeoutQueue        = "reliability:timeout:queue"
	deviceHeartbeatPref = "reliability:device:heartbeat:"
	latencyStatsPrefix  = "reliability:latency:stats:"
	msgContentTTL       = 24 * time.Hour
	offlineThreshold    = 5 * time.Minute
	deviceHeartbeatTTL  = 5 * time.Minute
)

// MessageStatus 对应 MessageStatus 枚举（L702-722）。
//
// DIFF: Java 用 enum（可用 Enum.valueOf 反查）；Go 用带类型字符串常量，
// 反查由 parseMessageStatus 承担——少一层"枚举类"，多一个显式函数。
type MessageStatus string

const (
	MsgPending   MessageStatus = "PENDING"   // 待发送
	MsgSent      MessageStatus = "SENT"      // 已发送到 Kafka
	MsgConfirmed MessageStatus = "CONFIRMED" // 消费端已确认
	MsgDead      MessageStatus = "DEAD"      // 死信
)

// parseMessageStatus 对应 MessageStatus.valueOf(str)（不抛异常版本）
func parseMessageStatus(s string) (MessageStatus, bool) {
	switch MessageStatus(s) {
	case MsgPending, MsgSent, MsgConfirmed, MsgDead:
		return MessageStatus(s), true
	}
	return "", false
}

// ReliableMessageWrapper 对应 ReliableMessageWrapper（L642-677）
type ReliableMessageWrapper struct {
	MessageID     string `json:"messageId"`
	DataID        string `json:"dataId"`
	Checksum      string `json:"checksum"`
	OperationType string `json:"operationType"`
	Data          any    `json:"data"`
	Timestamp     int64  `json:"timestamp"`
	Version       int    `json:"version"`
}

// messageMeta 对应 MessageMeta（L683-697）
type messageMeta struct {
	MessageID   string
	DataID      string
	Topic       string
	Checksum    string
	Status      MessageStatus
	CreateTime  int64
	KafkaOffset int64
	RetryCount  atomic.Int32
	Error       string
}

// DataReliabilityService 对应 DataReliabilityService.java
type DataReliabilityService struct {
	pub   mq.Publisher
	cache *cache.Client
	repo  *repo.KafkaMessageRecordRepo
	cfg   config.ReliabilityConfig

	pending sync.Map // messageID → *messageMeta（对应 ConcurrentHashMap）
}

// NewDataReliabilityService 构造
func NewDataReliabilityService(pub mq.Publisher, cacheClient *cache.Client,
	recordRepo *repo.KafkaMessageRecordRepo, cfg config.ReliabilityConfig) *DataReliabilityService {
	return &DataReliabilityService{pub: pub, cache: cacheClient, repo: recordRepo, cfg: cfg}
}

// SendReliableMessage 对应 sendReliableMessage()（L152-194）。
//
// 六步与 Java 完全一致：生成 ID → 计算校验值 → 组装包装体 → 本地缓存元数据 →
// Redis 缓存消息体（用于重试）→ 发送 + 注册超时检测。
func (s *DataReliabilityService) SendReliableMessage(ctx context.Context, data any, dataID, topic string) (string, error) {
	messageID := generateMessageID(dataID)
	checksum := s.CalculateChecksum(data)

	wrapper := ReliableMessageWrapper{
		MessageID:     messageID,
		DataID:        dataID,
		Checksum:      checksum,
		OperationType: "INSERT",
		Data:          data,
		Timestamp:     time.Now().UnixMilli(),
		Version:       1,
	}

	meta := &messageMeta{
		MessageID:   messageID,
		DataID:      dataID,
		Topic:       topic,
		Checksum:    checksum,
		Status:      MsgPending,
		CreateTime:  time.Now().UnixMilli(),
		KafkaOffset: -1,
	}
	s.pending.Store(messageID, meta)

	raw, err := json.Marshal(wrapper)
	if err != nil {
		return "", fmt.Errorf("序列化可靠消息失败: %w", err)
	}
	if s.cache != nil {
		_ = s.cache.SetWithTTL(ctx, msgContentPrefix+messageID, string(raw), msgContentTTL)
		_ = s.cache.SetWithTTL(ctx, msgStatusPrefix+messageID, string(MsgPending), msgContentTTL)
	}

	s.sendToKafka(ctx, wrapper, topic, messageID)
	s.scheduleTimeoutCheck(ctx, messageID)

	slog.Info("[可靠性服务] 发送可靠消息", "messageId", messageID, "dataId", dataID, "topic", topic)
	return messageID, nil
}

// sendToKafka 对应 sendToKafka()（L199-213）。
//
// DIFF: Java 的 KafkaTemplate.send 返回 ListenableFuture，回调在 IO 线程执行；
// Go 的 Publisher.Publish 同步等待 ack 并返回 error——所以"成功/失败"直接顺序判断，
// 失败分支另起 goroutine 走退避重试，避免阻塞调用方（对应 Java 回调的异步语义）。
func (s *DataReliabilityService) sendToKafka(ctx context.Context, wrapper ReliableMessageWrapper,
	topic, messageID string) {

	raw, err := json.Marshal(wrapper)
	if err != nil {
		s.handleSendFailure(ctx, messageID, err.Error())
		return
	}
	if s.pub == nil {
		slog.Warn("[可靠性服务] 消息总线未启用，跳过发送", "messageId", messageID)
		return
	}
	err = s.pub.Publish(ctx, mq.Message{Topic: topic, Key: wrapper.DataID, Value: raw})
	if err != nil {
		s.handleSendFailure(ctx, messageID, err.Error())
		return
	}
	s.handleKafkaAck(ctx, messageID, 0)
}

// HandleKafkaAck 对应 handleKafkaAck()（L218-226）
func (s *DataReliabilityService) HandleKafkaAck(ctx context.Context, messageID string, offset int64) {
	s.handleKafkaAck(ctx, messageID, offset)
}

func (s *DataReliabilityService) handleKafkaAck(ctx context.Context, messageID string, offset int64) {
	v, ok := s.pending.Load(messageID)
	if !ok {
		return
	}
	meta := v.(*messageMeta)
	meta.Status = MsgSent
	meta.KafkaOffset = offset
	if s.cache != nil {
		_ = s.cache.Set(ctx, msgStatusPrefix+messageID, string(MsgSent))
	}
	slog.Debug("[可靠性服务] Kafka 确认消息", "messageId", messageID, "offset", offset)
}

// HandleSendFailure 对应 handleSendFailure()（L231-246）：未超限则退避重试，超限则入死信。
func (s *DataReliabilityService) HandleSendFailure(ctx context.Context, messageID, errMsg string) {
	s.handleSendFailure(ctx, messageID, errMsg)
}

func (s *DataReliabilityService) handleSendFailure(ctx context.Context, messageID, errMsg string) {
	v, ok := s.pending.Load(messageID)
	if !ok {
		return
	}
	meta := v.(*messageMeta)
	n := meta.RetryCount.Add(1)
	slog.Warn("[可靠性服务] 消息发送失败", "messageId", messageID, "retryCount", n, "err", errMsg)

	if int(n) < s.cfg.MaxRetryCount {
		go func() {
			defer func() {
				if r := recover(); r != nil {
					slog.Error("[可靠性服务] 重试协程 panic", "messageId", messageID, "panic", r)
				}
			}()
			s.retrySend(context.WithoutCancel(ctx), messageID)
		}()
		return
	}
	s.markAsDeadLetter(ctx, messageID, errMsg)
}

// RetrySend 对应 retrySend()（L251-276）：指数退避 2^retryCount 秒后重发。
func (s *DataReliabilityService) RetrySend(ctx context.Context, messageID string) {
	s.retrySend(ctx, messageID)
}

func (s *DataReliabilityService) retrySend(ctx context.Context, messageID string) {
	if s.cache == nil {
		return
	}
	content, ok, err := s.cache.Get(ctx, msgContentPrefix+messageID)
	if err != nil || !ok {
		slog.Error("[可靠性服务] 重试失败：消息内容已过期", "messageId", messageID)
		return
	}
	var wrapper ReliableMessageWrapper
	if err := json.Unmarshal([]byte(content), &wrapper); err != nil {
		slog.Error("[可靠性服务] 重试失败：消息体解析异常", "messageId", messageID, "err", err)
		return
	}
	v, ok := s.pending.Load(messageID)
	if !ok {
		return
	}
	meta := v.(*messageMeta)
	delay := time.Duration(1<<uint(meta.RetryCount.Load())) * time.Second
	select {
	case <-ctx.Done():
		return
	case <-time.After(delay):
	}

	s.sendToKafka(ctx, wrapper, meta.Topic, messageID)
	slog.Info("[可靠性服务] 重试消息", "messageId", messageID,
		"retryCount", meta.RetryCount.Load(), "delayMs", delay.Milliseconds())
}

// markAsDeadLetter 对应 markAsDeadLetter()（L281-304）：写 status=3 的死信记录并告警。
func (s *DataReliabilityService) markAsDeadLetter(ctx context.Context, messageID, errMsg string) {
	v, ok := s.pending.LoadAndDelete(messageID)
	if !ok {
		return
	}
	meta := v.(*messageMeta)
	meta.Status = MsgDead
	meta.Error = errMsg
	if s.cache != nil {
		_ = s.cache.Set(ctx, msgStatusPrefix+messageID, string(MsgDead))
	}

	content := ""
	if s.cache != nil {
		if c, ok, err := s.cache.Get(ctx, msgContentPrefix+messageID); err == nil && ok {
			content = c
		}
	}
	now := time.Now()
	rec := &model.KafkaMessageRecord{
		Id:          uuid.NewString(),
		DataId:      meta.DataID,
		Topic:       meta.Topic,
		MessageJson: content,
		RetryCount:  intPtr(int(meta.RetryCount.Load())),
		CreateTime:  model.NewTimestamp(now),
		ErrorMsg:    model.Str(errMsg),
	}
	if s.repo != nil {
		if err := s.repo.InsertDeadLetter(ctx, rec); err != nil {
			slog.Error("[可靠性服务] 死信入库失败", "messageId", messageID, "err", err)
		}
	}
	slog.Error("[可靠性服务] 消息进入死信队列", "messageId", messageID, "dataId", meta.DataID, "err", errMsg)
	s.sendAlert("DEAD_LETTER", "消息进入死信队列: "+messageID+", 错误: "+errMsg)
}

// ConfirmConsumption 对应 confirmConsumption()（L317-340）：三重确认的最后一步。
func (s *DataReliabilityService) ConfirmConsumption(ctx context.Context, messageID, consumerType string) {
	v, ok := s.pending.LoadAndDelete(messageID)
	if !ok {
		return
	}
	meta := v.(*messageMeta)
	latency := time.Now().UnixMilli() - meta.CreateTime
	meta.Status = MsgConfirmed
	if s.cache != nil {
		_ = s.cache.Set(ctx, msgStatusPrefix+messageID, string(MsgConfirmed))
	}
	s.recordLatency(ctx, consumerType, latency)
	s.scheduleCacheCleanup(ctx, messageID)

	slog.Info("[可靠性服务] 消费端确认", "messageId", messageID,
		"consumer", consumerType, "latencyMs", latency)

	if latency > int64(s.cfg.AlertThresholdMs) {
		s.sendAlert("HIGH_LATENCY", fmt.Sprintf("消息处理延迟过高: %s, 延迟: %dms", messageID, latency))
	}
}

// scheduleTimeoutCheck 对应 scheduleTimeoutCheck()（L347-364）。
//
// DIFF: Java 用 retryExecutor.submit + Thread.sleep 实现"延时任务"；
// Go 用 time.After + goroutine。注意：不要用 time.Ticker 累积——每个消息一个定时器，
// 消息量大时会创建大量 goroutine，生产环境可换成"单 ticker 扫 ZSET"，这里保持与 Java 同构。
func (s *DataReliabilityService) scheduleTimeoutCheck(ctx context.Context, messageID string) {
	timeout := time.Duration(s.cfg.MessageTimeoutMs) * time.Millisecond
	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[可靠性服务] 超时检测协程 panic", "messageId", messageID, "panic", r)
			}
		}()
		select {
		case <-ctx.Done():
			return
		case <-time.After(timeout):
		}
		var status MessageStatus
		if s.cache != nil {
			if v, ok, err := s.cache.Get(ctx, msgStatusPrefix+messageID); err == nil && ok {
				status, _ = parseMessageStatus(v)
			}
		}
		if status != MsgConfirmed {
			s.handleMessageTimeout(ctx, messageID, status)
		}
	}()
}

// handleMessageTimeout 对应 handleMessageTimeout()（L369-377）：入超时队列 + 告警。
func (s *DataReliabilityService) handleMessageTimeout(ctx context.Context, messageID string, status MessageStatus) {
	slog.Warn("[可靠性服务] 消息超时", "messageId", messageID, "status", string(status))
	if s.cache != nil {
		// List 操作走 Raw()：cache 包只封装了高频 KV，队列类操作直接透传
		_ = s.cache.Raw().RPush(ctx, timeoutQueue, messageID).Err()
	}
	s.sendAlert("MESSAGE_TIMEOUT", fmt.Sprintf("消息超时未确认: %s, 状态: %s", messageID, status))
}

// CompensationTask 对应 @Scheduled(fixedRate) compensationTask()（L385-430）。
// 由 scheduler 周期调用：取超时队列前 50 条按状态补偿。
func (s *DataReliabilityService) CompensationTask(ctx context.Context) {
	if s.cache == nil {
		return
	}
	rdb := s.cache.Raw()
	ids, err := rdb.LRange(ctx, timeoutQueue, 0, 50).Result()
	if err != nil {
		if err != redis.Nil {
			slog.Error("[可靠性服务] 补偿任务读取超时队列失败", "err", err)
		}
		return
	}
	if len(ids) == 0 {
		return
	}
	slog.Info("[可靠性服务] 补偿任务处理", "count", len(ids))

	for _, messageID := range ids {
		// 从队列移除（对应 redisTemplate.opsForList().remove(KEY, 1, id)）
		_ = rdb.LRem(ctx, timeoutQueue, 1, messageID).Err()

		var status MessageStatus
		if v, ok, err := s.cache.Get(ctx, msgStatusPrefix+messageID); err == nil && ok {
			status, _ = parseMessageStatus(v)
		}
		switch status {
		case MsgPending:
			s.retrySend(ctx, messageID)
		case MsgSent:
			s.resendMessage(ctx, messageID)
		case MsgConfirmed, MsgDead:
			// 已确认 / 死信：无需处理
		default:
			slog.Warn("[可靠性服务] 未知状态", "messageId", messageID, "status", string(status))
		}
	}
}

// resendMessage 对应 resendMessage()（L435-460）
func (s *DataReliabilityService) resendMessage(ctx context.Context, messageID string) {
	if s.cache == nil {
		return
	}
	content, ok, err := s.cache.Get(ctx, msgContentPrefix+messageID)
	if err != nil || !ok {
		slog.Error("[可靠性服务] 重发失败：消息内容已过期", "messageId", messageID)
		return
	}
	var wrapper ReliableMessageWrapper
	if err := json.Unmarshal([]byte(content), &wrapper); err != nil {
		slog.Error("[可靠性服务] 重发失败：消息体解析异常", "messageId", messageID, "err", err)
		return
	}
	topic := ""
	if v, ok := s.pending.Load(messageID); ok {
		topic = v.(*messageMeta).Topic
	}
	s.pending.Store(messageID, &messageMeta{
		MessageID:  messageID,
		DataID:     wrapper.DataID,
		Topic:      topic,
		Checksum:   wrapper.Checksum,
		CreateTime: time.Now().UnixMilli(),
		Status:     MsgPending,
	})
	s.sendToKafka(ctx, wrapper, topic, messageID)
	slog.Info("[可靠性服务] 重发消息", "messageId", messageID)
}

// UpdateDeviceHeartbeat 对应 updateDeviceHeartbeat()（L472-474）
func (s *DataReliabilityService) UpdateDeviceHeartbeat(ctx context.Context, deviceID string) {
	if s.cache == nil {
		return
	}
	_ = s.cache.SetWithTTL(ctx, deviceHeartbeatPref+deviceID, time.Now().UnixMilli(), deviceHeartbeatTTL)
}

// CheckOfflineDevices 对应 @Scheduled(fixedRate = 300000) checkOfflineDevices()（L482-512）。
//
// DIFF（报告 02 P1-2）: Java 用 redisTemplate.keys(pattern)（KEYS 会阻塞 Redis）；
// Go 改为 SCAN 游标遍历（cache.ScanKeys），键空间按设备数增长，大库下不再阻塞主线程。
func (s *DataReliabilityService) CheckOfflineDevices(ctx context.Context) {
	if s.cache == nil {
		return
	}
	rdb := s.cache.Raw()
	keys, err := s.cache.ScanKeys(ctx, deviceHeartbeatPref+"*", 500)
	if err != nil || len(keys) == 0 {
		return
	}
	now := time.Now().UnixMilli()
	for _, key := range keys {
		v, err := rdb.Get(ctx, key).Int64()
		if err != nil {
			continue
		}
		deviceID := key[len(deviceHeartbeatPref):]
		if now-v > offlineThreshold.Milliseconds() {
			slog.Warn("[可靠性服务] 设备离线", "deviceId", deviceID, "sinceSec", (now-v)/1000)
			s.sendAlert("DEVICE_OFFLINE", "设备离线: "+deviceID)
		}
	}
}

// CalculateChecksum 对应 calculateChecksum()（L525-539）：JSON 的 MD5，用于传输完整性校验。
func (s *DataReliabilityService) CalculateChecksum(data any) string {
	raw, err := json.Marshal(data)
	if err != nil {
		slog.Error("[可靠性服务] 序列化失败，退化为随机值", "err", err)
		return uuid.NewString()
	}
	sum := md5.Sum(raw)
	return hex.EncodeToString(sum[:])
}

// VerifyChecksum 对应 verifyChecksum()（L548-555）
func (s *DataReliabilityService) VerifyChecksum(data any, expected string) bool {
	actual := s.CalculateChecksum(data)
	if actual != expected {
		slog.Warn("[可靠性服务] 数据完整性校验失败", "expected", expected, "actual", actual)
		return false
	}
	return true
}

// IsMessageProcessed 对应 isMessageProcessed()（L568-571）：基于消息 ID 的幂等判重。
func (s *DataReliabilityService) IsMessageProcessed(ctx context.Context, messageID string) bool {
	if s.cache == nil {
		return false
	}
	ok, err := s.cache.Exists(ctx, msgStatusPrefix+messageID)
	return err == nil && ok
}

// MarkMessageProcessed 对应 markMessageProcessed()（L578-580）
func (s *DataReliabilityService) MarkMessageProcessed(ctx context.Context, messageID string) {
	if s.cache == nil {
		return
	}
	_ = s.cache.SetWithTTL(ctx, msgStatusPrefix+messageID, string(MsgConfirmed), msgContentTTL)
}

// generateMessageID 对应 generateMessageId()（L589-594）：时间戳-纳秒-随机-数据ID哈希
func generateMessageID(dataID string) string {
	return fmt.Sprintf("%d-%d-%s-%d", time.Now().UnixMilli(), time.Now().UnixNano()%1000000,
		uuid.NewString()[:8], hashCode(dataID))
}

// hashCode 等价于 Java 的 String.hashCode()（s[0]*31^(n-1) + ...），
// 保证同一个 dataId 在 Java/Go 两侧得到同一个哈希（便于日志串联）。
func hashCode(s string) int32 {
	var h int32
	for _, c := range s {
		h = 31*h + int32(c)
	}
	return h
}

// scheduleCacheCleanup 对应 scheduleCacheCleanup()（L599-611）：延迟 1 小时清理，避免误删。
func (s *DataReliabilityService) scheduleCacheCleanup(ctx context.Context, messageID string) {
	if s.cache == nil {
		return
	}
	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[可靠性服务] 缓存清理协程 panic", "panic", r)
			}
		}()
		select {
		case <-ctx.Done():
			return
		case <-time.After(time.Hour):
		}
		_ = s.cache.Delete(context.WithoutCancel(ctx), msgContentPrefix+messageID, msgStatusPrefix+messageID)
	}()
}

// recordLatency 对应 recordLatency()（L616-622）：Redis List 存最近 1000 条延迟样本。
func (s *DataReliabilityService) recordLatency(ctx context.Context, consumerType string, latency int64) {
	if s.cache == nil {
		return
	}
	key := latencyStatsPrefix + consumerType + ":" + time.Now().Format("2006-01-02")
	rdb := s.cache.Raw()
	_ = rdb.RPush(ctx, key, latency).Err()
	_ = rdb.LTrim(ctx, key, -1000, -1).Err()
}

// sendAlert 对应 sendAlert()（L629-632）
//
// PARITY: Java 侧这里也是 log.error + TODO（未接告警系统），Go 侧保持一致，
// 预留 AlertHook 供后续接钉钉/企业微信，但不改变当前行为。
func (s *DataReliabilityService) sendAlert(alertType, message string) {
	slog.Error("[告警] "+alertType, "message", message)
}

func intPtr(v int) *int { return &v }
