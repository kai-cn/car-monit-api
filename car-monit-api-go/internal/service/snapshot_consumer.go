package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java:60-448
//
// 类/职责: SnapshotFlowConsumer —— 抓拍流水的 MQ 消费端：
// 消息体 → {operationType, data} → 幂等判重 → GaussDB 落库 + Elasticsearch 同步
//
// 对应 Go 文件: internal/service/snapshot_consumer.go
//
// 关键映射:
//
//	@PulsarConsumer + consumerExecutor.submit(消费循环)   → Start(ctx) 里一个 goroutine 跑 bus.Consume
//	snapshotFlowConsumer.receive()                       → bus.Consume 内部的 FetchMessage 循环
//	boolean processMessage(dataId, json)                 → error Handle(ctx, msg)
//	success=true  → acknowledge(msg)（提交 offset）      → return nil
//	success=false → negativeAcknowledge(msg)（触发重投）  → return error
//	redisTemplate.setIfAbsent("pulsar:msg:processed:x")  → cache.SetNXWithTTL（同一个 key 前缀）
//	snapshotFlowService.saveOrUpdate / updateById        → repo.Insert / repo.Update
//	esService.saveSnapshotFlow / deleteSnapshotFlow      → es.Bulk / es.DeleteDoc
//
// DIFF: Java 在 for 循环里 try/catch 兜住异常、睡 5 秒后继续；Go 把这层"重试 + 退避 + 死信"
// 下沉到 mq.KafkaBus.Consume（见 internal/mq/kafka.go:handleWithRetry），
// 消费端只负责回答"这条消息算是处理成功还是失败"——异常路径因此没有裸 sleep，关机能立刻响应。
//
// PARITY: Java 的 processMessage 只做「库 + ES」两件事，从未调用
// MultiSourceDataFlowService.processData / DataReliabilityService.confirmConsumption
// （全仓仅 DataFlowTask.java:65 有一行被注释掉的调用）。Go 侧同样不接这两条链路，
// 避免"迁移时顺手加功能"导致与 Java 行为不一致；需要时在 Handle 的成功分支处接入即可。

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/mq"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

// idempotentKeyPrefix 对应 L96 的 IDEMPOTENT_KEY_PREFIX。
// 刻意与 Java 保持同一字符串：切换期两个版本共用 Redis 时，幂等判重能直接互认。
const idempotentKeyPrefix = "pulsar:msg:processed:"

// SnapshotFlowMessage 对应消息信封 {operationType, data}（L265-266）。
//
// DIFF: Java 用 FastJSON 的 JSONObject 边走边取字段；Go 先声明信封结构再 Unmarshal，
// data 保留为 json.RawMessage，这样"信封能解析但 data 解析失败"可以与 Java 一样单独处理。
type SnapshotFlowMessage struct {
	OperationType string          `json:"operationType"`
	Data          json.RawMessage `json:"data"`
}

// SnapshotFlowConsumer 对应 SnapshotFlowPulsarConsumer。
type SnapshotFlowConsumer struct {
	bus       mq.Consumer
	snapshot  *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	es        *es.Client
	esIndex   string
	cache     *cache.Client
	ttl       time.Duration
	consumerT string
	// wg 追踪消费循环，供 Close() 等待退出（ctx 取消后 FetchMessage 最多 1s 感知）。
	wg sync.WaitGroup
}

// NewSnapshotFlowConsumer 构造。
//
// idempotentTTLSeconds 对应 application.yml:100 的 pulsar.idempotent-ttl-seconds。
func NewSnapshotFlowConsumer(bus mq.Consumer, snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	esClient *es.Client, esIndex string, cacheClient *cache.Client,
	idempotentTTLSeconds int) *SnapshotFlowConsumer {

	ttl := time.Duration(idempotentTTLSeconds) * time.Second
	if ttl <= 0 {
		ttl = 24 * time.Hour // 与 application.yml 默认值 86400 一致
	}
	return &SnapshotFlowConsumer{
		bus:       bus,
		snapshot:  snapshotRepo,
		es:        esClient,
		esIndex:   esIndex,
		cache:     cacheClient,
		ttl:       ttl,
		consumerT: "snapshotflow",
	}
}

// Start 对应 @PostConstruct 里的 consumerExecutor.submit(...)（L169-234）。
//
// DIFF: Java 把循环塞进线程池；Go 用 goroutine。ctx 取消即退出循环，
// 因此 main() 里只需要 cancel()，不需要额外的"停止消费"标志位。
func (s *SnapshotFlowConsumer) Start(ctx context.Context) {
	if s == nil || s.bus == nil {
		slog.Warn("[快照消费者] 未配置消息总线，消费端不启动")
		return
	}
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[快照消费者] 消费循环 panic 退出", "panic", r)
			}
		}()
		slog.Info("[快照消费者] 消费循环已启动")
		// DIFF（R2 关联）: Java 的 while(true) 在 catch 后 sleep(5s) 再进入下一轮，永不放弃；
		// 旧 Go 实现只重试一次就退出，导致消费端"静默死亡"且探针仍为 UP。这里改为循环重试。
		for ctx.Err() == nil {
			err := s.bus.Consume(ctx, s.Handle)
			if ctx.Err() != nil {
				break
			}
			if err == nil {
				// Consume 只在 ctx 取消时返回 nil，正常退出。
				break
			}
			slog.Error("[快照消费者] 消费循环异常退出，5 秒后重启", "err", err)
			if !s.retryAfterDelay(ctx) {
				break
			}
		}
		slog.Info("[快照消费者] 消费循环已退出")
	}()
}

// Close 等待消费循环退出（调用方需先取消启动时传入的 ctx）。
//
// 对应 @PreDestroy：Java 侧容器关闭会等待 in-flight 消息处理完；这里靠
// Consume 的『当前消息处理完才退出』语义 + wg 等待达到同样效果。
func (s *SnapshotFlowConsumer) Close() {
	if s == nil {
		return
	}
	s.wg.Wait()
}

// Healthy 返回消费端是否健康（供 /readyz 与指标使用）。
//
// 未配置消息总线（本地降级模式）→ false；实现了 mq.HealthChecker 的总线
// 按真实心跳判定；其他实现退回"已启动即健康"。
func (s *SnapshotFlowConsumer) Healthy() bool {
	if s == nil || s.bus == nil {
		return false
	}
	if hc, ok := s.bus.(interface{ Healthy() bool }); ok {
		return hc.Healthy()
	}
	return true
}

// HealthSnapshot 透传总线的心跳明细；总线不支持时返回零值。
func (s *SnapshotFlowConsumer) HealthSnapshot() (registered, running bool, lastTick time.Time, consecutiveErrors int, lastErr string) {
	if s == nil || s.bus == nil {
		return false, false, time.Time{}, 0, ""
	}
	if hb, ok := s.bus.(interface {
		HealthSnapshot() (bool, bool, time.Time, int, string)
	}); ok {
		return hb.HealthSnapshot()
	}
	return true, true, time.Time{}, 0, ""
}

// retryAfterDelay 对应 catch 块里的 TimeUnit.SECONDS.sleep(5)（L224-229）。
//
// PARITY: Java 在这里固定睡 5 秒再重新进入循环；Go 的 Consume 自己会重建 reader，
// 所以这 5 秒只是"不要立刻重连"的退避，语义与 Java 一致。
// 返回 false 表示 ctx 已取消，调用方应退出重试循环。
func (s *SnapshotFlowConsumer) retryAfterDelay(ctx context.Context) bool {
	select {
	case <-ctx.Done():
		return false
	case <-time.After(5 * time.Second):
		return true
	}
}

// Handle 对应 processMessage(dataId, messageJson)（L253-331）。
//
// 返回值语义（与 mq.Handler 的约定一一对应）：
//
//	nil   → ack（Java 的 return true，含"确认丢弃"的格式错误/重复消息）
//	error → nack（Java 的 return false，触发 Broker 重投）
func (s *SnapshotFlowConsumer) Handle(ctx context.Context, msg mq.Message) error {
	startTime := time.Now()
	dataID := msg.Key

	// 1. 解析消息信封
	var envelope SnapshotFlowMessage
	if err := json.Unmarshal(msg.Value, &envelope); err != nil {
		slog.Error("[快照消费者] 消息格式错误，确认丢弃", "dataId", dataID, "err", err)
		return nil // 格式错误的消息：直接确认丢弃，不重试
	}
	if envelope.OperationType == "" || len(envelope.Data) == 0 || string(envelope.Data) == "null" {
		slog.Error("[快照消费者] 消息缺少必要字段，确认丢弃",
			"dataId", dataID, "operationType", envelope.OperationType)
		return nil
	}

	// 2. 幂等判重：SETNX pulsar:msg:processed:{dataId}
	if first, err := s.markProcessing(ctx, dataID); err != nil {
		// DIFF: Java 在 Redis 异常时抛 NPE 落到外层 catch → nack。
		// Go 显式返回 error，让 Consume 走重试——语义相同，但日志能说清是 Redis 的问题。
		return fmt.Errorf("幂等标记写入失败: %w", err)
	} else if !first {
		slog.Info("[快照消费者] 消息已处理（幂等去重）", "dataId", dataID)
		return nil
	}

	// 3. 解析 data 为业务实体
	var flow model.OdsRtSzdnSnapshotFlowAddcode
	if err := json.Unmarshal(envelope.Data, &flow); err != nil {
		slog.Error("[快照消费者] data 字段解析失败，确认丢弃", "dataId", dataID, "err", err)
		return nil // 解析失败：确认丢弃，避免重试死循环
	}
	if model.Blank(flow.BigId) {
		// PARITY: Java 只判 flowData == null（FastJSON 反序列化成功即非空），
		// 主键为空时它会在 DB 层报错并 nack。Go 提前拦下并明确记为"格式问题"，
		// 否则会造成无意义的无限重投。
		slog.Error("[快照消费者] data 缺少 bigId，确认丢弃", "dataId", dataID)
		return nil
	}

	// 4. 按 operationType 分发
	switch strings.ToUpper(envelope.OperationType) {
	case "INSERT":
		return s.handleInsert(ctx, &flow, dataID, startTime)
	case "UPDATE":
		return s.handleUpdate(ctx, &flow, dataID, startTime)
	case "DELETE":
		return s.handleDelete(ctx, dataID, startTime)
	default:
		slog.Warn("[快照消费者] 未知操作类型，确认丢弃",
			"dataId", dataID, "operationType", envelope.OperationType)
		return nil // 未知类型：确认丢弃，不重试
	}
}

// markProcessing 对应 setIfAbsent(idempotentKey, timestamp, ttl)（L279-287）。
// 返回 true 表示"首次处理"。
func (s *SnapshotFlowConsumer) markProcessing(ctx context.Context, dataID string) (bool, error) {
	if s.cache == nil {
		// 缓存不可用时无法判重：与 Java 的 NPE→nack 不同，这里选择"继续处理"，
		// 因为下游写库/写 ES 都是幂等 upsert，重复消息不会产生错误数据。
		slog.Warn("[快照消费者] 缓存未启用，跳过幂等判重", "dataId", dataID)
		return true, nil
	}
	return s.cache.SetNXWithTTL(ctx, idempotentKeyPrefix+dataID,
		time.Now().UnixMilli(), s.ttl)
}

// handleInsert 对应 handleInsert()（L348-375）：DB upsert + ES index。
func (s *SnapshotFlowConsumer) handleInsert(ctx context.Context, flow *model.OdsRtSzdnSnapshotFlowAddcode,
	dataID string, startTime time.Time) error {

	if err := s.saveOrUpdate(ctx, flow); err != nil {
		slog.Error("[快照消费者] 写入 GaussDB 失败", "dataId", dataID, "err", err)
		return err // 触发重投
	}
	if err := s.saveToES(ctx, flow); err != nil {
		slog.Error("[快照消费者] 写入 Elasticsearch 失败", "dataId", dataID, "err", err)
		return err // ES 失败同样重投，保证最终一致性
	}
	slog.Info("[快照消费者] INSERT 操作成功", "dataId", dataID,
		"costMs", time.Since(startTime).Milliseconds())
	return nil
}

// handleUpdate 对应 handleUpdate()（L388-417）：
// 先 updateById，记录不存在则退化为 saveOrUpdate，最后同步 ES。
func (s *SnapshotFlowConsumer) handleUpdate(ctx context.Context, flow *model.OdsRtSzdnSnapshotFlowAddcode,
	dataID string, startTime time.Time) error {

	if err := s.snapshot.Update(ctx, flow); err != nil {
		slog.Warn("[快照消费者] UPDATE 失败（记录可能不存在），转 INSERT", "dataId", dataID, "err", err)
		if err := s.saveOrUpdate(ctx, flow); err != nil {
			return err
		}
	}
	if err := s.saveToES(ctx, flow); err != nil {
		slog.Error("[快照消费者] 更新 Elasticsearch 失败", "dataId", dataID, "err", err)
		return err
	}
	slog.Info("[快照消费者] UPDATE 操作成功", "dataId", dataID,
		"costMs", time.Since(startTime).Milliseconds())
	return nil
}

// handleDelete 对应 handleDelete()（L425-446）：两边失败都只告警，整体视为成功（幂等）。
func (s *SnapshotFlowConsumer) handleDelete(ctx context.Context, dataID string, startTime time.Time) error {
	if err := s.snapshot.DeleteByID(ctx, dataID); err != nil {
		slog.Warn("[快照消费者] DELETE GaussDB 失败（记录可能不存在）", "dataId", dataID, "err", err)
	}
	if s.es != nil {
		if err := s.es.DeleteDoc(ctx, s.esIndex, dataID); err != nil {
			slog.Warn("[快照消费者] DELETE Elasticsearch 失败（文档可能不存在）", "dataId", dataID, "err", err)
		}
	}
	slog.Info("[快照消费者] DELETE 操作完成", "dataId", dataID,
		"costMs", time.Since(startTime).Milliseconds())
	return nil
}

// saveOrUpdate 对应 snapshotFlowService.saveOrUpdate(entity)。
//
// DIFF: MyBatis-Plus 的 saveOrUpdate 是"先查主键再 insert/update"两次 SQL；
// Go 侧等价实现相同（GetByID → Insert/Update），因为 GaussDB 的 upsert 语法
// （ON CONFLICT）在分表场景下不保证可用，保持与 Java 一致的两次访问更容易对照。
func (s *SnapshotFlowConsumer) saveOrUpdate(ctx context.Context, flow *model.OdsRtSzdnSnapshotFlowAddcode) error {
	existing, err := s.snapshot.GetByID(ctx, model.Val(flow.BigId))
	if err != nil {
		return fmt.Errorf("查询主键失败: %w", err)
	}
	if existing == nil {
		return s.snapshot.Insert(ctx, flow)
	}
	return s.snapshot.Update(ctx, flow)
}

// saveToES 对应 esService.saveSnapshotFlow(entity)：以 bigId 作为文档 ID，天然幂等 upsert。
//
// DIFF: Java 用 IndexRequest(id)。ES 的 index-with-id 本身就是 upsert，所以 Go 用 Bulk 的
// index 动作 + _id 达到同一效果（见 internal/es/client.go:Bulk）。
func (s *SnapshotFlowConsumer) saveToES(ctx context.Context, flow *model.OdsRtSzdnSnapshotFlowAddcode) error {
	if s.es == nil || s.esIndex == "" {
		slog.Warn("[快照消费者] Elasticsearch 未配置，跳过写入", "dataId", model.Val(flow.BigId))
		return nil
	}
	raw, err := json.Marshal(flow)
	if err != nil {
		return fmt.Errorf("实体序列化失败: %w", err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		return fmt.Errorf("实体转 ES 文档失败: %w", err)
	}
	// 去掉 gorm:"-" 带来的空占位字段，避免污染索引 mapping
	for _, transient := range []string{"id", "snapshottimeStr", "applyTime1", "applyTime2",
		"queryUuids", "flag", "sectionCodeStr", "type", "code", "codeList", "sectionList",
		"startNum", "endNum"} {
		delete(doc, transient)
	}
	doc["_id"] = flow.BigId
	return s.es.Bulk(ctx, s.esIndex, []map[string]any{doc})
}

// ConsumerType 返回消费者标识（用于延迟监控/可靠性服务的分组统计）。
func (s *SnapshotFlowConsumer) ConsumerType() string { return s.consumerT }

// ErrConsumerNotStarted 供健康检查使用：消费端未启动时由 /health 暴露。
var ErrConsumerNotStarted = errors.New("snapshotflow 消费端未启动")
