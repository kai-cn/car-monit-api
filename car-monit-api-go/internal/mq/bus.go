// Package mq 提供消息总线抽象与 Kafka 实现。
//
// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/config/KafkaProducerConfig.java
//	pro-business-api/src/main/java/com/ruoyi/base/config/PulsarConsumerConfig.java
//	pro-business-api/.../service/impl/KafkaProducerService.java:103-254
//	pro-business-api/.../service/impl/SnapshotFlowPulsarConsumer.java:169-447
//	pro-business-api/src/main/java/com/ruoyi/mq/consumer/RocketMqConsumer.java
//
// 对应 Go 文件: internal/mq/bus.go + internal/mq/kafka.go
//
// 关键映射:
//
//	@KafkaListener（容器托管 + 线程池）→ Consume(ctx, handler)：显式的 for 循环 + 失败重试 + 优雅退出
//	KafkaTemplate.send(...) + 回调        → Publisher.Publish(ctx, msg) 返回 error（同步等待 ack）
//	Pulsar 的 MessageId ack/nack         → Consume 里 Handler 返回 error 即 nack（不提交 offset）
//	@RabbitListener 死信队列             → 本项目用 Kafka 的 dlq topic 模拟（见 Config.DeadLetterTopic）
//
// 架构决策（Pulsar / RocketMQ / RabbitMQ）:
//
//	这三者在 Java 侧各有一套客户端与消费模型，Go 侧的替代品成熟度是：
//	  Pulsar  → apache/pulsar-client-go 可用，但依赖 CGO + C++ 客户端，破坏交叉编译；
//	  RocketMQ→ github.com/apache/rocketmq-client-go 维护活跃度低；
//	  RabbitMQ→ rabbitmq/amqp091-go 成熟。
//	因此本项目把"发/收"收敛为 MessageBus 接口：默认 Kafka 实现同语义，
//	需要接真 Pulsar 时新增一个源文件实现 Publisher/Consumer 即可，业务代码零改动。
package mq

import (
	"context"
	"time"
)

// Message 是统一的消息载体。
//
// DIFF: Java 侧每个 MQ 客户端都有自己的 Message 类型（ConsumerRecord/Message/KafkaMessage）；
// Go 侧统一成一个结构，避免业务层为切换 MQ 改签名。
type Message struct {
	// Topic 主题（Kafka topic / Pulsar topic / RabbitMQ routing key）
	Topic string
	// Key 分区键（车牌号/设备号，保证同一车辆的顺序性）
	Key string
	// Value 消息体（JSON 字节）
	Value []byte
	// Headers 头信息（traceId、来源等）
	Headers map[string]string
	// Attempt 已投递次数（由 Consume 维护，用于判重/告警）
	Attempt int
}

// Handler 是消息处理函数。
// 返回 nil 表示处理成功（提交 offset）；返回 error 表示失败（不提交，按 Configure.MaxRetry 重试）。
//
// DIFF: Java 的 @KafkaListener 方法抛异常后由 DefaultErrorHandler 决定重试；
// Go 里"重试与否"完全由这个返回值 + Consume 的循环代码决定，逻辑外显但可控。
type Handler func(ctx context.Context, msg Message) error

// Publisher 生产端接口（对应 KafkaTemplate / PulsarTemplate / RabbitTemplate）
type Publisher interface {
	Publish(ctx context.Context, msg Message) error
	PublishBatch(ctx context.Context, msgs []Message) error
	Close() error
}

// Consumer 消费端接口（对应 @KafkaListener 容器）
type Consumer interface {
	Consume(ctx context.Context, handler Handler) error
	Close() error
}

// Bus 同时具备生产与消费能力。
type Bus interface {
	Publisher
	Consumer
}

// Configure 是 Kafka 实现的参数（对应 KafkaProducerConfig / PulsarConsumerConfig 里的属性）
type Configure struct {
	Brokers         []string
	GroupID         string
	Topic           string
	DeadLetterTopic string
	// MaxRetry 单条消息的最大重试次数，超过后投递到死信 topic（对应 Pulsar 的 max-retry-times / DLQ）
	MaxRetry int
	// RetryBackoff 重试退避基数（指数退避：base * 2^attempt）
	RetryBackoff time.Duration
	// BatchSize Producer 批量条数（对应 batch-max-messages）
	BatchSize int
	// BatchTimeout Producer 批量等待时间（对应 batch-max-publish-delay-ms）
	BatchTimeout time.Duration
	// CommitInterval 手动提交 offset 的间隔
	CommitInterval time.Duration
}
