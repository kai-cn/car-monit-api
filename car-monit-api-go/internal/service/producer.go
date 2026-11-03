package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/KafkaProducerService.java:41-285
// 类/职责: KafkaProducerService — 消息生产入口：可靠发送 + 失败消息后台重试 + 延迟/丢失埋点
// 对应 Go 文件: internal/service/producer.go
// 关键映射:
//   KafkaTemplate<String,Object>.send            → mq.Publisher.Publish（同步 ack，见 DIFF）
//   ListenableFutureCallback onSuccess/onFailure → Publish 的返回 error 分支
//   kafkaMessageRecordMapper.updateStatusById    → repo.UpdateStatusByID
//   kafkaMessageRecordMapper.incrementRetryCount → repo.IncrementRetryCount
//   @PostConstruct init() + startRetryTask       → Start(ctx) 启一个重试 goroutine
//   retryExecutor(newSingleThreadExecutor)       → 单个 goroutine + stopCh
//   @Value("${kafka.topic.snapshot-flow:...}")   → config.KafkaConfig.Topic.SnapshotFlow
//   @Value("${kafka.max-retry-count:10}")        → config.KafkaConfig.MaxRetryCount
//
// DIFF: Java 的发送是"异步 + 回调"，回调在 Kafka IO 线程上跑，业务线程立刻返回；
// Go 的 Publish 同步等 ack，因此 sendMessage 会阻塞到 broker 确认（kafka-go Writer 内部仍批量）。
// 语义差别只在延迟：Java 的调用方感知不到发送耗时，Go 的调用方能感知。
// 需要"不阻塞"时由调用方 go SendSnapshotFlowData(...) 即可——比回调更直观。
//
// DIFF: Java 的 retryExecutor.submit(while(true)+sleep) 无法停止（没有 shutdown 钩子）；
// Go 提供 Close() 通过 stopCh + WaitGroup 优雅退出，容器滚动发布时不会留下跑着旧代码的协程。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/mq"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

const (
	retryBatchSize    = 100              // selectFailedRecords(maxRetryCount, 100)
	retryInterval     = 30 * time.Second // 两轮重试之间
	retryErrorBackoff = 60 * time.Second // 一轮异常后
)

// KafkaProducerService 对应 KafkaProducerService.java
type KafkaProducerService struct {
	pub         mq.Publisher
	recordRepo  *repo.KafkaMessageRecordRepo
	reliability *DataReliabilityService
	loss        *DataLossDetectionService
	delay       *DelayMonitoringService

	topic    string
	maxRetry int

	stopCh   chan struct{}
	stopOnce sync.Once
	wg       sync.WaitGroup
}

// NewKafkaProducerService 构造
func NewKafkaProducerService(pub mq.Publisher, recordRepo *repo.KafkaMessageRecordRepo,
	reliability *DataReliabilityService, loss *DataLossDetectionService,
	delay *DelayMonitoringService, cfg config.KafkaConfig) *KafkaProducerService {

	topic := cfg.Topic.SnapshotFlow
	if topic == "" {
		topic = "ods-rt-szdn-snapshot-flow"
	}
	maxRetry := cfg.MaxRetryCount
	if maxRetry <= 0 {
		maxRetry = 10
	}
	return &KafkaProducerService{
		pub: pub, recordRepo: recordRepo, reliability: reliability, loss: loss, delay: delay,
		topic: topic, maxRetry: maxRetry, stopCh: make(chan struct{}),
	}
}

// Start 对应 @PostConstruct init()（L80-87）：拉起后台重试任务。
func (s *KafkaProducerService) Start(ctx context.Context) {
	s.wg.Add(1)
	go s.startRetryTask(ctx)
	slog.Info("[Kafka生产者服务] 初始化完成，集成可靠性保障机制", "topic", s.topic, "maxRetry", s.maxRetry)
}

// Close 停掉后台重试任务并等待其退出（对应 Java 缺失的 @PreDestroy）。
func (s *KafkaProducerService) Close() {
	s.stopOnce.Do(func() { close(s.stopCh) })
	s.wg.Wait()
}

// SendSnapshotFlowData 对应 sendSnapshotFlowData()（L103-115）。
//
// 三步：记生产时间（延迟监控）→ 可靠发送（持久化/校验/超时）→ 记上报消息 ID（丢失检测）。
func (s *KafkaProducerService) SendSnapshotFlowData(ctx context.Context, data any, dataID string) (string, error) {
	// 1. 消息生产时间
	if s.delay != nil {
		s.delay.RecordMessageProduceTime(dataID)
	}

	// 2. 可靠发送（内部已含 Redis 缓存 + Kafka 发送 + 超时检测）
	if s.reliability == nil {
		return "", fmt.Errorf("可靠性服务未初始化")
	}
	messageID, err := s.reliability.SendReliableMessage(ctx, data, dataID, s.topic)
	if err != nil {
		return "", err
	}

	// 3. 上报消息 ID（用于丢失检测）
	if s.loss != nil {
		s.loss.RecordReportedMessage(ctx, messageID, ExtractDeviceID(data), time.Now().UnixMilli())
	}

	slog.Info("[Kafka生产者] 发送消息", "dataId", dataID, "messageId", messageID)
	return messageID, nil
}

// SendBatchSnapshotFlowData 对应 sendBatchSnapshotFlowData()（L254-267）。
//
// PARITY: 逐条发送、单条失败只记日志继续（与 Java 一致）——批量接口不保证原子性，
// 也不返回失败明细；需要明细时用 SendSnapshotFlowData 逐条调用。
func (s *KafkaProducerService) SendBatchSnapshotFlowData(ctx context.Context, dataList []any) {
	slog.Info("[Kafka生产者] 批量发送消息", "count", len(dataList))
	for _, data := range dataList {
		dataID := ExtractDataID(data)
		if dataID == "" {
			continue
		}
		if _, err := s.SendSnapshotFlowData(ctx, data, dataID); err != nil {
			slog.Error("[Kafka生产者] 批量发送异常", "dataId", dataID, "err", err)
		}
	}
}

// sendMessage 对应私有 sendMessage(record)（L130-175）：重试链路专用——把库里存的消息体再发一次。
//
// DIFF: Java 用 ListenableFuture 回调更新状态；Go 同步拿到结果后顺序更新，
// 失败分支另起 goroutine 通知可靠性服务，避免"重试任务被一次失败拖住整批"。
//
// PARITY: Java 的 handleKafkaAck / handleSendFailure 传的是 record.getDataId()，
// 而可靠性服务的 pending 表 key 是 messageId —— 这两个方法在重试链路上其实查不到元数据，
// 属于既有实现缺陷。Go 侧**保持传 dataId** 以对齐行为，缺陷登记在 README「已知问题」。
func (s *KafkaProducerService) sendMessage(ctx context.Context, record *repoMsgRecord) {
	if s.pub == nil {
		slog.Warn("[Kafka生产者] 消息总线未启用，跳过重试发送", "id", record.ID)
		return
	}
	topic := record.Topic
	if topic == "" {
		topic = s.topic
	}

	err := s.pub.Publish(ctx, mq.Message{
		Topic: topic,
		Key:   record.DataID,
		Value: []byte(record.MessageJSON),
	})
	if err == nil {
		slog.Info("[Kafka生产者] 消息发送成功", "dataId", record.DataID)
		if s.recordRepo != nil {
			if e := s.recordRepo.UpdateStatusByID(ctx, record.ID, repo.MsgStatusSuccess, time.Now()); e != nil {
				slog.Error("[Kafka生产者] 更新发送状态失败", "id", record.ID, "err", e)
			}
		}
		if s.reliability != nil {
			s.reliability.HandleKafkaAck(ctx, record.DataID, 0)
		}
		return
	}

	slog.Error("[Kafka生产者] 消息发送失败", "dataId", record.DataID, "err", err)
	if s.recordRepo != nil {
		if e := s.recordRepo.IncrementRetryCount(ctx, record.ID, err.Error()); e != nil {
			slog.Error("[Kafka生产者] 累加重试次数失败", "id", record.ID, "err", e)
		}
	}
	if s.reliability != nil {
		go s.reliability.HandleSendFailure(context.WithoutCancel(ctx), record.DataID, err.Error())
	}
}

// startRetryTask 对应 startRetryTask()（L188-220）：无限循环扫失败消息。
//
// DIFF: Java 用 Thread.sleep + InterruptedException 退出；Go 用 select{stopCh, timer}——
// 退出时立即返回，不用等满 30 秒。
func (s *KafkaProducerService) startRetryTask(ctx context.Context) {
	defer s.wg.Done()
	for {
		select {
		case <-s.stopCh:
			slog.Info("[Kafka生产者] 重试任务退出")
			return
		case <-ctx.Done():
			return
		default:
		}

		if err := s.runRetryOnce(ctx); err != nil {
			slog.Error("[Kafka生产者] 重试任务异常", "err", err)
			if !s.sleep(retryErrorBackoff) {
				return
			}
			continue
		}
		if !s.sleep(retryInterval) {
			return
		}
	}
}

// runRetryOnce 抽出一轮重试逻辑，便于单测与"异常后多睡一会儿"的分支处理。
func (s *KafkaProducerService) runRetryOnce(ctx context.Context) error {
	if s.recordRepo == nil {
		return nil
	}
	records, err := s.recordRepo.SelectFailedRecords(ctx, s.maxRetry, retryBatchSize)
	if err != nil {
		return err
	}
	if len(records) == 0 {
		return nil
	}
	slog.Info("[Kafka生产者] 开始重试消息", "count", len(records))
	for i := range records {
		r := records[i]
		s.sendMessage(ctx, &repoMsgRecord{
			ID:          r.Id,
			DataID:      r.DataId,
			Topic:       r.Topic,
			MessageJSON: r.MessageJson,
		})
	}
	return nil
}

// sleep 等待 d，期间可被 stopCh 打断；返回 false 表示应退出循环。
func (s *KafkaProducerService) sleep(d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-s.stopCh:
		return false
	case <-timer.C:
		return true
	}
}

// repoMsgRecord 是 sendMessage 的最小入参视图。
//
// DIFF: Java 直接传 KafkaMessageRecord 实体；Go 用局部结构体只挑三个字段，
// 让"重试发送只需要 id/dataId/topic/messageJson"这件事在签名上可见。
type repoMsgRecord struct {
	ID          string
	DataID      string
	Topic       string
	MessageJSON string
}

// deviceIDFields / dataIDFields 对应 Java 里的两个 possibleFields 数组（L235、L275）。
var (
	deviceIDFields = []string{"deviceId", "deviceid", "device_ip", "deviceIp", "gantrycode", "gantryId"}
	dataIDFields   = []string{"bigId", "id", "uuid", "dataId"}
)

// ExtractDeviceID 对应私有 extractDeviceId()（L231-244）：按候选字段顺序取第一个非空值。
//
// DIFF: Java 只认 fastjson 的 JSONObject（传 POJO 会返回 "unknown"）；
// Go 统一先把对象规约成 map —— 结构体走 json tag，map 直接读，
// 结果与"调用方显式 toJSON 再取"一致，但省掉调用方这一步。
func ExtractDeviceID(data any) string {
	if v := firstNonEmptyField(data, deviceIDFields); v != "" {
		return v
	}
	return "unknown"
}

// ExtractDataID 对应私有 extractDataId()（L272-284）：取不到返回空串（Java 返回 null）。
func ExtractDataID(data any) string {
	return firstNonEmptyField(data, dataIDFields)
}

// firstNonEmptyField 在 data 上按顺序查找候选字段。
func firstNonEmptyField(data any, fields []string) string {
	m := toStringMap(data)
	if m == nil {
		return ""
	}
	for _, f := range fields {
		if v, ok := m[f]; ok && v != nil {
			return fmt.Sprint(v)
		}
	}
	return ""
}

// toStringMap 把任意对象规约成 map[string]any；失败返回 nil。
func toStringMap(data any) map[string]any {
	if data == nil {
		return nil
	}
	if m, ok := data.(map[string]any); ok {
		return m
	}
	raw, err := json.Marshal(data)
	if err != nil {
		return nil
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil
	}
	return m
}
