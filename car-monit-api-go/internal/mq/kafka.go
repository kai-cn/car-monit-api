package mq

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/config/KafkaProducerConfig.java:1-131
//           + com.ruoyi.base.config.PulsarConsumerConfig.java:1-218（消费语义对齐）
// 类/职责: KafkaBus — Kafka 生产/消费的 Go 实现
// 对应 Go 文件: internal/mq/kafka.go
// 关键映射:
//   KafkaProducerConfig 里的 KafkaTemplate              → kafka.Writer（同步 WriteMessages 等 ack）
//   @KafkaListener 容器                                → kafka.Reader + Consume 里的 for 循环
//   Pulsar 的 DLQ / max-retry-times                    → dlq topic + 指数退避（见 Consume）
// DIFF: Java 的消费线程由容器托管、失败重试由 DefaultErrorHandler 隐式完成；
//       Go 的循环、退避、提交 offset、优雅退出全部要自己写——这 60 行就是"魔法"的全部代价。

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/segmentio/kafka-go"
)

// KafkaBus 同时实现 Publisher 与 Consumer。
type KafkaBus struct {
	cfg    Configure
	writer *kafka.Writer
	reader *kafka.Reader
	// health 记录消费循环心跳；/readyz 通过 Healthy() 读取，避免"启动过就当健康"
	health *Heartbeat
}

// NewKafka 构造 Kafka 总线。
//
// DIFF: Java 侧 Producer 与 Consumer 是两个独立的 @Bean（KafkaTemplate / ConcurrentKafkaListenerContainerFactory）；
// Go 侧合成一个 struct，是因为它们共享同一份 brokers/topic 配置，拆开只会多一次参数传递。
func NewKafka(cfg Configure) *KafkaBus {
	if cfg.BatchSize <= 0 {
		cfg.BatchSize = 500
	}
	if cfg.BatchTimeout <= 0 {
		cfg.BatchTimeout = 10 * time.Millisecond
	}
	if cfg.MaxRetry <= 0 {
		cfg.MaxRetry = 3
	}
	if cfg.RetryBackoff <= 0 {
		cfg.RetryBackoff = 200 * time.Millisecond
	}
	if cfg.CommitInterval <= 0 {
		cfg.CommitInterval = time.Second
	}

	w := &kafka.Writer{
		Addr:         kafka.TCP(cfg.Brokers...),
		Topic:        cfg.Topic,
		Balancer:     &kafka.Hash{}, // 按 Key 分区，保证同一车牌的顺序性
		RequiredAcks: kafka.RequireOne,
		BatchSize:    cfg.BatchSize,
		BatchTimeout: cfg.BatchTimeout,
		Async:        false, // 同步写：拿到 error 才能做业务重试
		Logger:       kafka.LoggerFunc(func(msg string, args ...interface{}) { slog.Debug(msg, "component", "kafka") }),
		ErrorLogger:  kafka.LoggerFunc(func(msg string, args ...interface{}) { slog.Error(msg, "component", "kafka") }),
	}

	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        cfg.Brokers,
		GroupID:        cfg.GroupID,
		Topic:          cfg.Topic,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: 0, // 手动提交：处理成功后才提交 offset
		StartOffset:    kafka.FirstOffset,
	})

	return &KafkaBus{cfg: cfg, writer: w, reader: r, health: NewHeartbeat()}
}

// Publish 对应 KafkaProducerService.sendSnapshotFlowData 的发送段（application.yml:145-148 topic）
func (b *KafkaBus) Publish(ctx context.Context, msg Message) error {
	if b == nil || b.writer == nil {
		return errors.New("mq: KafkaBus 未初始化")
	}
	topic := msg.Topic
	if topic == "" {
		topic = b.cfg.Topic
	}
	m := kafka.Message{
		Topic: topic,
		Key:   []byte(msg.Key),
		Value: msg.Value,
	}
	for k, v := range msg.Headers {
		m.Headers = append(m.Headers, kafka.Header{Key: k, Value: []byte(v)})
	}
	return b.writer.WriteMessages(ctx, m)
}

// PublishBatch 对应 sendBatchSnapshotFlowData（application.yml:79 batch-max-messages）
func (b *KafkaBus) PublishBatch(ctx context.Context, msgs []Message) error {
	if len(msgs) == 0 {
		return nil
	}
	km := make([]kafka.Message, 0, len(msgs))
	for _, msg := range msgs {
		topic := msg.Topic
		if topic == "" {
			topic = b.cfg.Topic
		}
		km = append(km, kafka.Message{Topic: topic, Key: []byte(msg.Key), Value: msg.Value})
	}
	return b.writer.WriteMessages(ctx, km...)
}

// Consume 启动消费循环。
//
// 语义对照 SnapshotFlowPulsarConsumer.startConsume（L169-253）：
//  1. 读取消息 → 2. 处理 → 3. 成功则提交 offset；失败则按指数退避重试，
//  4. 超过 MaxRetry 投递到死信 topic 并提交（避免毒消息阻塞分区）。
//
// 优雅退出：ctx 被取消后，当前消息处理完即退出循环（不丢正在处理的消息）。
//
// DIFF: Java 容器关闭时会等待 in-flight 消息；Go 里等价语义只能靠"ctx 取消 → 循环条件退出"实现，
//
//	因此这里**不能**用 goroutine 包住 handler，否则退出时无法感知处理是否完成。
func (b *KafkaBus) Consume(ctx context.Context, handler Handler) error {
	if b == nil || b.reader == nil {
		return errors.New("mq: KafkaBus 未初始化")
	}
	lg := slog.Default().With("component", "kafka-consumer", "topic", b.cfg.Topic, "group", b.cfg.GroupID)
	lg.Info("消费者已启动")
	// 心跳：进入循环即登记 running，退出/panic 时置 false（defer 覆盖所有返回路径）。
	b.health.markRunning()
	defer b.health.stop()

	for {
		if ctx.Err() != nil {
			lg.Info("消费者收到退出信号，准备停止")
			return nil
		}
		// DIFF: Java 的 poll 超时由容器配置；这里用一个较短的 FetchMessage 超时，
		// 以便 ctx 取消能在 1 秒内被感知（否则关机会一直卡在 ReadMessage 上）。
		fetchCtx, cancel := context.WithTimeout(ctx, time.Second)
		raw, err := b.reader.FetchMessage(fetchCtx)
		cancel()
		if err != nil {
			if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
				// 空闲 topic 的正常超时：循环仍在前进，刷新心跳。
				b.health.tick()
				continue
			}
			// 非预期失败：不刷新心跳，连续 3 次会让 Healthy() 转 false。
			b.health.fail(err)
			lg.Error("拉取消息失败", "err", err)
			time.Sleep(time.Second)
			continue
		}
		b.health.tick()

		msg := Message{
			Topic: raw.Topic,
			Key:   string(raw.Key),
			Value: raw.Value,
		}
		for _, h := range raw.Headers {
			if msg.Headers == nil {
				msg.Headers = map[string]string{}
			}
			msg.Headers[h.Key] = string(h.Value)
		}

		if err := b.handleWithRetry(ctx, lg, handler, msg); err != nil {
			// 已在 handleWithRetry 内部记日志；此处仍要继续消费后续消息
			lg.Error("消息最终处理失败，已投递死信或丢弃", "key", msg.Key, "err", err)
		}

		if err := b.reader.CommitMessages(ctx, raw); err != nil && ctx.Err() == nil {
			lg.Error("提交 offset 失败", "err", err)
		}
		// 一轮完整处理（含慢 handler）结束后刷新心跳，避免"处理慢但确实在前进"被误判。
		b.health.tick()
	}
}

// Healthy 返回消费循环的心跳状态（供 /readyz 与指标使用）。
//
// 语义：未启动、已退出、连续拉取失败或心跳超过 HeartbeatStaleAfter 未刷新，均返回 false。
func (b *KafkaBus) Healthy() bool {
	if b == nil {
		return false
	}
	return b.health.Healthy()
}

// HealthSnapshot 暴露心跳明细（registered/running/lastTick/连续失败数/最近错误）。
func (b *KafkaBus) HealthSnapshot() (registered, running bool, lastTick time.Time, consecutiveErrors int, lastErr string) {
	if b == nil {
		return false, false, time.Time{}, 0, ""
	}
	return b.health.Snapshot()
}

func (b *KafkaBus) handleWithRetry(ctx context.Context, lg *slog.Logger, handler Handler, msg Message) error {
	var lastErr error
	for attempt := 0; attempt <= b.cfg.MaxRetry; attempt++ {
		msg.Attempt = attempt
		lastErr = safeCall(ctx, handler, msg)
		if lastErr == nil {
			return nil
		}
		lg.Warn("消息处理失败，准备重试", "attempt", attempt, "key", msg.Key, "err", lastErr)
		if attempt == b.cfg.MaxRetry {
			break
		}
		backoff := b.cfg.RetryBackoff * time.Duration(1<<attempt)
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(backoff):
		}
	}
	if b.cfg.DeadLetterTopic != "" {
		dlq := Message{
			Topic:   b.cfg.DeadLetterTopic,
			Key:     msg.Key,
			Value:   msg.Value,
			Headers: msg.Headers,
		}
		if err := b.Publish(ctx, dlq); err != nil {
			lg.Error("投递死信失败", "err", err)
			return fmt.Errorf("%v; 且死信投递失败: %w", lastErr, err)
		}
		lg.Warn("消息已投递死信队列", "topic", b.cfg.DeadLetterTopic, "key", msg.Key)
	}
	return lastErr
}

// safeCall 保证 handler 的 panic 不会带走整个消费循环。
//
// DIFF: Java 容器会捕获 listener 抛出的 RuntimeException 并交给 ErrorHandler；
// Go 的 panic 若不 recover 会直接终止进程，因此这里必须包一层。
func safeCall(ctx context.Context, handler Handler, msg Message) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("handler panic: %v", r)
		}
	}()
	return handler(ctx, msg)
}

// Close 对应 @PreDestroy：先停 producer 再停 consumer。
func (b *KafkaBus) Close() error {
	var errs []error
	if b.reader != nil {
		if err := b.reader.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	if b.writer != nil {
		if err := b.writer.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}
