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

use futures::FutureExt;
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

/// 消费端运行状态：started 表示订阅成功；last_recv_ms 最近一次成功 recv；
/// last_error_ms/last_error 最近一次拉取/订阅错误。readyz 据此区分
/// “topic 安静（STALE）”与“连接异常（DOWN）”。
#[derive(Clone, Default)]
pub struct ConsumerState {
    started: Arc<std::sync::atomic::AtomicBool>,
    last_recv_ms: Arc<std::sync::atomic::AtomicI64>,
    last_error_ms: Arc<std::sync::atomic::AtomicI64>,
    last_error: Arc<std::sync::Mutex<Option<String>>>,
}

impl ConsumerState {
    /// 订阅成功：清空历史错误。否则"订阅失败→恢复→topic 安静"会永久显示 DOWN。
    pub fn mark_started(&self) {
        self.started
            .store(true, std::sync::atomic::Ordering::SeqCst);
        self.last_error_ms
            .store(0, std::sync::atomic::Ordering::SeqCst);
        if let Ok(mut guard) = self.last_error.lock() {
            *guard = None;
        }
    }

    pub fn mark_stopped(&self) {
        self.started
            .store(false, std::sync::atomic::Ordering::SeqCst);
    }

    /// 成功收到消息：刷新 recv 时间，并清空历史错误。
    /// 否则一次历史错误会让 readyz 永久停留在 STALE/DOWN，即使链路早已恢复。
    pub fn mark_recv(&self) {
        self.last_recv_ms.store(
            crate::services::sysutil::now_ms(),
            std::sync::atomic::Ordering::SeqCst,
        );
        self.last_error_ms
            .store(0, std::sync::atomic::Ordering::SeqCst);
        if let Ok(mut guard) = self.last_error.lock() {
            *guard = None;
        }
    }

    pub fn mark_error(&self, err: &str) {
        self.last_error_ms.store(
            crate::services::sysutil::now_ms(),
            std::sync::atomic::Ordering::SeqCst,
        );
        if let Ok(mut guard) = self.last_error.lock() {
            *guard = Some(err.to_string());
        }
    }

    pub fn is_started(&self) -> bool {
        self.started.load(std::sync::atomic::Ordering::SeqCst)
    }

    pub fn last_recv_ms(&self) -> i64 {
        self.last_recv_ms.load(std::sync::atomic::Ordering::SeqCst)
    }

    pub fn last_error(&self) -> Option<(i64, String)> {
        let ms = self
            .last_error_ms
            .load(std::sync::atomic::Ordering::SeqCst);
        if ms == 0 {
            return None;
        }
        let text = self
            .last_error
            .lock()
            .ok()
            .and_then(|g| g.clone())
            .unwrap_or_default();
        Some((ms, text))
    }
}

// Bus 在进程内只有一份，KafkaBus 体积大是为了持有 producer/consumer/重试配置；
// 装箱只会增加一次解引用，不影响热路径，保持扁平结构便于 clone 与模式匹配。
#[allow(clippy::large_enum_variant)]
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
    /// `on_state` 在 subscribe 成功后标记 started，并在每次 recv 成功时刷新时间。
    pub async fn consume(
        &self,
        ctx: tokio::sync::watch::Receiver<bool>,
        handler: Handler,
        on_state: Option<ConsumerState>,
    ) -> AppResult<()> {
        match self {
            Bus::Kafka(k) => k.consume(ctx, handler, on_state).await,
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
            // 显式配置：handler 在消费线程内同步执行（含幂等等待与重试）。
            // librdkafka 默认 300000ms（300s），Config::validate 校验最坏预算 < 该值。
            .set("max.poll.interval.ms", kafka.max_poll_interval_ms.to_string())
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
            retry_backoff: Duration::from_millis(crate::config::RETRY_BACKOFF_MS),
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
            .send(
                record,
                Duration::from_secs(crate::config::DLQ_SEND_TIMEOUT_SECONDS),
            )
            .await
            .map_err(|(e, _)| AppError::biz(format!("Kafka 发送失败: {}", e)))?;
        Ok(())
    }

    /// 消费循环：成功 ack（提交 offset），失败指数退避重试，超过次数投死信并提交。
    /// subscribe 失败不会退出：每 5s 重试直到成功或收到退出信号；成功后 mark_started。
    pub async fn consume(
        &self,
        mut stop: tokio::sync::watch::Receiver<bool>,
        handler: Handler,
        on_state: Option<ConsumerState>,
    ) -> AppResult<()> {
        loop {
            if *stop.borrow() {
                return Ok(());
            }
            let subscribed = self.consumer.lock().await.subscribe(&[&self.topic]);
            match subscribed {
                Ok(()) => break,
                Err(e) => {
                    if let Some(state) = &on_state {
                        state.mark_error(&format!("订阅失败: {}", e));
                    }
                    warn!(topic = %self.topic, err = %e, "订阅失败，5 秒后重试");
                    tokio::select! {
                        r = stop.changed() => {
                            // Sender 提前 drop 时 changed() 返回 Err，但 borrow() 仍是旧值 false；
                            // 不把 Err 当停机就会立刻重试订阅，形成忙循环。
                            if r.is_err() || *stop.borrow() { return Ok(()); }
                        }
                        _ = tokio::time::sleep(Duration::from_secs(5)) => {}
                    }
                }
            }
        }
        if let Some(state) = &on_state {
            state.mark_started();
        }
        info!(topic = %self.topic, group = %self.group_id, "消费者已启动");

        loop {
            if *stop.borrow() {
                info!("消费者收到退出信号，准备停止");
                return Ok(());
            }
            let raw = tokio::select! {
                r = stop.changed() => {
                    // Err 表示 Sender 已 drop，等价于停机信号。
                    if r.is_err() || *stop.borrow() { return Ok(()); }
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
                    Ok(Ok(m)) => {
                        if let Some(state) = &on_state {
                            state.mark_recv();
                        }
                        m
                    }
                    Ok(Err(e)) => {
                        if let Some(state) = &on_state {
                            state.mark_error(&format!("拉取消息失败: {}", e));
                        }
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
            // 停机中不提交 offset：handler 的等待循环响应 stop 后会返回 Err，
            // 若此时继续提交，未处理完的消息会被当成已消费而丢失。留给重启后重投。
            if *stop.borrow() {
                info!("[mq] 停机中，跳过本次 offset 提交，未处理消息将在重启后重投");
                return Ok(());
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
        let (result, dlq) =
            run_with_retries(self.max_retry, self.retry_backoff, msg, &handler).await;
        if let Some(mut dlq_msg) = dlq {
            // 死信：Kafka 侧用 {topic}.DLQ 约定（Pulsar 的 DLQ 由 Broker 自动完成）
            let dlq_topic = if self.dead_letter_topic.is_empty() {
                format!("{}.DLQ", self.topic)
            } else {
                self.dead_letter_topic.clone()
            };
            dlq_msg.topic = dlq_topic.clone();
            if let Err(e) = self.publish(dlq_msg).await {
                error!(err = %e, "投递死信失败");
            } else {
                warn!(topic = %dlq_topic, key = %msg.key, "消息已投递死信队列");
            }
        }
        let _ = self.pubsar.max_retry_count;
        result
    }
}

/// 重试循环（与 KafkaBus 解耦，便于单测驱动：断言 panic 计入 attempt、耗尽后恰好产出一条 DLQ）。
/// 返回 (最终结果, 待发布死信消息)。死信只在重试耗尽后产生，成功时为 None。
async fn run_with_retries(
    max_retry: i32,
    retry_backoff: Duration,
    msg: &Message,
    handler: &Handler,
) -> (AppResult<()>, Option<Message>) {
    let mut last_err = None;
    for attempt in 0..=max_retry {
        let mut m = msg.clone();
        m.attempt = attempt;
        let (panicked, outcome) = call_handler(handler, m).await;
        match outcome {
            Ok(()) => return (Ok(()), None),
            Err(e) => {
                if panicked {
                    warn!(
                        attempt,
                        key = %msg.key,
                        err = %e,
                        "消息处理 panic，按失败计入重试/死信"
                    );
                } else {
                    warn!(attempt, key = %msg.key, err = %e, "消息处理失败，准备重试");
                }
                last_err = Some(e);
            }
        }
        if attempt < max_retry {
            let backoff = retry_backoff * (1u32 << attempt.min(10));
            tokio::time::sleep(backoff).await;
        }
    }
    let dlq = Message {
        topic: String::new(),
        key: msg.key.clone(),
        value: msg.value.clone(),
        headers: msg.headers.clone(),
        attempt: max_retry,
    };
    (
        Err(last_err.unwrap_or_else(|| AppError::biz("消息处理失败"))),
        Some(dlq),
    )
}

/// 执行一次 handler，并把 panic 转成普通 Err；第二个返回值表示是否发生了 panic。
/// 同时包住 `handler(msg)` 的同步求值阶段和返回 future 的 polling 阶段：
/// 前者若 panic 会直接落到外层重连，绕开单条消息的 attempt/DLQ 计数。
async fn call_handler(handler: &Handler, msg: Message) -> (bool, AppResult<()>) {
    let invoked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| handler(msg)));
    let future = match invoked {
        Ok(f) => f,
        Err(payload) => {
            return (
                true,
                Err(AppError::biz(format!(
                    "消息处理 panic: {}",
                    panic_message(payload)
                ))),
            );
        }
    };
    match std::panic::AssertUnwindSafe(future).catch_unwind().await {
        Ok(result) => (false, result),
        Err(payload) => (
            true,
            Err(AppError::biz(format!(
                "消息处理 panic: {}",
                panic_message(payload)
            ))),
        ),
    }
}

/// 提取 panic payload 的文本，供 handler 层把 panic 转成 Err 时记录原因。
fn panic_message(payload: Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else if let Some(s) = payload.downcast_ref::<&str>() {
        s.to_string()
    } else {
        "unknown panic".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::{call_handler, run_with_retries, Handler, Message};
    use crate::error::AppError;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::time::Duration;

    /// handler panic 必须转成 Err（从而计入 attempt、耗尽后走 DLQ），而不是向上传播触发重连。
    #[tokio::test]
    async fn handler_panic_becomes_err() {
        let handler: Handler = Arc::new(|_m| Box::pin(async { panic!("boom") }));
        let (panicked, outcome) = call_handler(&handler, Message::default()).await;
        assert!(panicked, "必须标记为 panic");
        let err = outcome.expect_err("panic 必须转成 Err");
        assert!(err.message().contains("boom"), "错误应包含 panic 原文");
    }

    #[tokio::test]
    async fn handler_error_is_not_marked_as_panic() {
        let handler: Handler =
            Arc::new(|_m| Box::pin(async { Err(AppError::biz("业务失败")) }));
        let (panicked, outcome) = call_handler(&handler, Message::default()).await;
        assert!(!panicked);
        assert!(outcome.is_err());
    }

    #[tokio::test]
    async fn handler_ok_passes_through() {
        let handler: Handler = Arc::new(|_m| Box::pin(async { Ok(()) }));
        let (panicked, outcome) = call_handler(&handler, Message::default()).await;
        assert!(!panicked);
        assert!(outcome.is_ok());
    }

    /// 驱动真实重试循环：panic 每次计入 attempt，耗尽后恰好产出一条 DLQ。
    /// 若把循环内调用改回裸 `handler(m).await`，panic 会直接冒泡，本用例失败。
    #[tokio::test]
    async fn retry_loop_counts_panic_and_returns_one_dlq() {
        let calls = Arc::new(AtomicUsize::new(0));
        let calls_for_handler = calls.clone();
        let handler: Handler = Arc::new(move |_m| {
            let calls = calls_for_handler.clone();
            Box::pin(async move {
                calls.fetch_add(1, Ordering::SeqCst);
                panic!("poison message");
            })
        });
        let msg = Message {
            key: "k".into(),
            value: b"v".to_vec(),
            ..Default::default()
        };
        let (result, dlq) = run_with_retries(2, Duration::from_millis(1), &msg, &handler).await;
        assert_eq!(calls.load(Ordering::SeqCst), 3, "必须尝试 max_retry+1 次");
        assert!(result.is_err(), "重试耗尽后必须返回 Err");
        let dlq = dlq.expect("失败必须产出一条死信");
        assert_eq!(dlq.key, "k");
        assert_eq!(dlq.attempt, 2);
    }

    #[tokio::test]
    async fn retry_loop_success_produces_no_dlq() {
        let handler: Handler = Arc::new(|_m| Box::pin(async { Ok(()) }));
        let msg = Message::default();
        let (result, dlq) = run_with_retries(2, Duration::from_millis(1), &msg, &handler).await;
        assert!(result.is_ok());
        assert!(dlq.is_none(), "成功时不得产生死信");
    }
}
