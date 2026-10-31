// 来源: pro-business-api/src/main/java/com/ruoyi/base/config/KafkaProducerConfig.java
//       pro-business-api/src/main/java/com/ruoyi/base/config/PulsarConsumerConfig.java
//       pro-business-api/src/main/java/com/ruoyi/base/service/impl/KafkaProducerService.java
//       pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java
// 职责: 消息总线：生产（同步等 ack）、消费（手动提交、指数退避、死信）。
// 对应关系:
//   KafkaTemplate.send             ↔ KafkaBus::publish
//   @KafkaListener 容器             ↔ KafkaBus::consume（自建循环）
//   DefaultErrorHandler 重试        ↔ handle_with_retry（指数退避 + DLQ）
//   Pulsar 的 MessageId ack/nack    ↔ commit_message（成功提交 offset，失败重投）
//
// DIFF: Java 的消费线程由容器托管；Rust 侧循环、退避、提交、优雅退出全部显式。
// 这 80 行就是 Spring Kafka "魔法"的全部代价，也是排查消费问题的唯一入口。

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use rdkafka::config::ClientConfig;
use rdkafka::consumer::{CommitMode, Consumer, StreamConsumer};
use rdkafka::message::{Header, Headers, OwnedHeaders};
use rdkafka::producer::{FutureProducer, FutureRecord};
use rdkafka::Message as KafkaMessage;
use tokio::sync::Mutex;
use tracing::{error, info, warn};

use crate::config::{KafkaConfig, PulsarConfig};
use crate::error::{AppError, AppResult};

#[derive(Debug, Clone, Default)]
pub struct Message {
    pub topic: String,
    pub key: String,
    pub value: Vec<u8>,
    pub headers: HashMap<String, String>,
    /// 第几次投递（消费者重试时递增，对应 pulsar 的 redeliveryCount）
    pub attempt: i32,
}

pub type Handler =
    Arc<dyn Fn(Message) -> futures::future::BoxFuture<'static, AppResult<()>> + Send + Sync>;

#[derive(Clone)]
pub enum Bus {
    Kafka(KafkaBus),
    Noop,
}

impl Bus {
    /// bootstrap-servers 为空时降级为 Noop（与 Java 侧 Kafka 不可用时的行为一致：应用不退出）。
    pub fn new(kafka: &KafkaConfig, pulsar: &PulsarConfig) -> AppResult<Self> {
        if kafka.bootstrap_servers.trim().is_empty() {
            warn!("未配置 kafka.bootstrap-servers，消息总线降级为本地模式");
            return Ok(Bus::Noop);
        }
        Ok(Bus::Kafka(KafkaBus::new(kafka, pulsar)?))
    }

    pub async fn publish(&self, msg: Message) -> AppResult<()> {
        match self {
            Bus::Kafka(k) => k.publish(msg).await,
            Bus::Noop => {
                warn!(key = %msg.key, "消息总线为 Noop，消息未发送（仅记录）");
                Ok(())
            }
        }
    }

    pub async fn publish_batch(&self, msgs: Vec<Message>) -> AppResult<()> {
        match self {
            Bus::Kafka(k) => {
                for m in msgs {
                    k.publish(m).await?;
                }
                Ok(())
            }
            Bus::Noop => Ok(()),
        }
    }

    pub fn is_active(&self) -> bool {
        matches!(self, Bus::Kafka(_))
    }

    /// 启动消费循环（阻塞直到 ctx 取消）。业务 handler 返回 Err 表示 nack（重投）。
    pub async fn consume(
        &self,
        ctx: tokio::sync::watch::Receiver<bool>,
        handler: Handler,
    ) -> AppResult<()> {
        match self {
            Bus::Kafka(k) => k.consume(ctx, handler).await,
            Bus::Noop => {
                info!("消息总线为 Noop，消费端不启动");
                Ok(())
            }
        }
    }
}

struct OwnedKafkaMessage {
    topic: String,
    partition: i32,
    offset: i64,
    key: String,
    value: Vec<u8>,
    headers: HashMap<String, String>,
}

#[derive(Clone)]
pub struct KafkaBus {
    producer: Arc<FutureProducer>,
    consumer: Arc<tokio::sync::Mutex<StreamConsumer>>,
    topic: String,
    group_id: String,
    pubsar: PulsarConfig,
    max_retry: i32,
    retry_backoff: Duration,
    dead_letter_topic: String,
    commit_lock: Arc<Mutex<()>>,
}

impl KafkaBus {
    pub fn new(kafka: &KafkaConfig, pulsar: &PulsarConfig) -> AppResult<Self> {
        let producer: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", &kafka.bootstrap_servers)
            .set("message.timeout.ms", "30000")
            .set("acks", "1")
            .set("linger.ms", "10")
            .set("batch.num.messages", "1000")
            .create()
            .map_err(|e| AppError::biz(format!("创建 Kafka producer 失败: {}", e)))?;

        let group_id = if kafka.group_id.is_empty() {
            pulsar.subscription_name.clone()
        } else {
            kafka.group_id.clone()
        };
        let consumer: StreamConsumer = ClientConfig::new()
            .set("bootstrap.servers", &kafka.bootstrap_servers)
            .set("group.id", &group_id)
            .set("enable.auto.commit", "false")
            .set("auto.offset.reset", "earliest")
            .set("enable.partition.eof", "false")
            .set("session.timeout.ms", "10000")
            .create()
            .map_err(|e| AppError::biz(format!("创建 Kafka consumer 失败: {}", e)))?;

        let topic = if kafka.topic.snapshot_flow.is_empty() {
            pulsar.topic.clone()
        } else {
            kafka.topic.snapshot_flow.clone()
        };

        Ok(Self {
            producer: Arc::new(producer),
            consumer: Arc::new(tokio::sync::Mutex::new(consumer)),
            topic,
            group_id,
            pubsar: pulsar.clone(),
            max_retry: pulsar.max_retry_times.max(0),
            retry_backoff: Duration::from_millis(200),
            dead_letter_topic: String::new(),
            commit_lock: Arc::new(Mutex::new(())),
        })
    }

    pub async fn publish(&self, msg: Message) -> AppResult<()> {
        let topic = if msg.topic.is_empty() {
            self.topic.clone()
        } else {
            msg.topic.clone()
        };
        let mut headers = OwnedHeaders::new();
        for (k, v) in &msg.headers {
            headers = headers.insert(Header {
                key: k,
                value: Some(v.as_bytes()),
            });
        }
        let record = FutureRecord::to(&topic)
            .key(&msg.key)
            .payload(&msg.value)
            .headers(headers);
        self.producer
            .send(record, Duration::from_secs(30))
            .await
            .map_err(|(e, _)| AppError::biz(format!("Kafka 发送失败: {}", e)))?;
        Ok(())
    }

    /// 消费循环：成功 ack（提交 offset），失败指数退避重试，超过次数投死信并提交。
    pub async fn consume(
        &self,
        mut stop: tokio::sync::watch::Receiver<bool>,
        handler: Handler,
    ) -> AppResult<()> {
        self.consumer
            .lock()
            .await
            .subscribe(&[&self.topic])
            .map_err(|e| AppError::biz(format!("订阅 {} 失败: {}", self.topic, e)))?;
        info!(topic = %self.topic, group = %self.group_id, "消费者已启动");

        loop {
            if *stop.borrow() {
                info!("消费者收到退出信号，准备停止");
                return Ok(());
            }
            let raw = tokio::select! {
                _ = stop.changed() => {
                    if *stop.borrow() { return Ok(()); }
                    continue;
                }
                r = async {
                    let consumer = self.consumer.lock().await;
                    match tokio::time::timeout(Duration::from_secs(1), consumer.recv()).await {
                        Ok(Ok(m)) => Ok(Ok(OwnedKafkaMessage {
                            topic: m.topic().to_string(),
                            partition: m.partition(),
                            offset: m.offset(),
                            key: m.key().map(|k| String::from_utf8_lossy(k).to_string()).unwrap_or_default(),
                            value: m.payload().unwrap_or_default().to_vec(),
                            headers: m
                                .headers()
                                .map(|hs| {
                                    let mut out = HashMap::new();
                                    for i in 0..hs.count() {
                                        let h = hs.get(i);
                                        if let Some(v) = h.value {
                                            out.insert(h.key.to_string(), String::from_utf8_lossy(v).to_string());
                                        }
                                    }
                                    out
                                })
                                .unwrap_or_default(),
                        })),
                        Ok(Err(e)) => Ok(Err(e)),
                        Err(_) => Err(()),
                    }
                } => match r {
                    Ok(Ok(m)) => m,
                    Ok(Err(e)) => {
                        error!(err = %e, "拉取消息失败");
                        tokio::time::sleep(Duration::from_secs(1)).await;
                        continue;
                    }
                    Err(_) => continue,
                },
            };

            let msg = Message {
                topic: raw.topic.clone(),
                key: raw.key.clone(),
                value: raw.value.clone(),
                headers: raw.headers.clone(),
                attempt: 0,
            };

            let _guard = self.commit_lock.lock().await;
            if let Err(e) = self.handle_with_retry(&msg, handler.clone()).await {
                error!(key = %msg.key, err = %e, "消息最终处理失败，已投递死信或丢弃");
            }
            // 等价于 commit_message(raw)：提交 offset+1
            let mut tpl = rdkafka::TopicPartitionList::new();
            let _ = tpl.add_partition_offset(
                &raw.topic,
                raw.partition,
                rdkafka::Offset::Offset(raw.offset + 1),
            );
            if let Err(e) = self.consumer.lock().await.commit(&tpl, CommitMode::Sync) {
                if !*stop.borrow() {
                    error!(err = %e, "提交 offset 失败");
                }
            }
        }
    }

    async fn handle_with_retry(&self, msg: &Message, handler: Handler) -> AppResult<()> {
        let mut last_err = None;
        for attempt in 0..=self.max_retry {
            let mut m = msg.clone();
            m.attempt = attempt;
            match handler(m).await {
                Ok(()) => return Ok(()),
                Err(e) => {
                    warn!(attempt, key = %msg.key, err = %e, "消息处理失败，准备重试");
                    last_err = Some(e);
                }
            }
            if attempt < self.max_retry {
                let backoff = self.retry_backoff * (1u32 << attempt.min(10));
                tokio::time::sleep(backoff).await;
            }
        }
        // 死信：Kafka 侧用 {topic}.DLQ 约定（Pulsar 的 DLQ 由 Broker 自动完成）
        let dlq_topic = if self.dead_letter_topic.is_empty() {
            format!("{}.DLQ", self.topic)
        } else {
            self.dead_letter_topic.clone()
        };
        let dlq = Message {
            topic: dlq_topic.clone(),
            key: msg.key.clone(),
            value: msg.value.clone(),
            headers: msg.headers.clone(),
            attempt: self.max_retry,
        };
        if let Err(e) = self.publish(dlq).await {
            error!(err = %e, "投递死信失败");
        } else {
            warn!(topic = %dlq_topic, key = %msg.key, "消息已投递死信队列");
        }
        let _ = self.pubsar.max_retry_count;
        Err(last_err.unwrap_or_else(|| AppError::biz("消息处理失败")))
    }
}
