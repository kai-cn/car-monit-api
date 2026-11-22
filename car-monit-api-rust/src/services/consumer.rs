// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java:60-448
// 职责: 抓拍流水消费端：{operationType,data} → 幂等判重 → GaussDB 落库 + ES 同步。
// 对应关系:
//   @PulsarConsumer consumerExecutor.submit(循环) ↔ tokio::spawn + Bus::consume
//   boolean processMessage(dataId,json)          ↔ handle()（Ok=ack，Err=nack）
//   setIfAbsent("pulsar:msg:processed:x",ttl)    ↔ cache.set_nx
//   saveOrUpdate / updateById / deleteById       ↔ SnapshotFlowRepo::{insert,update,delete_by_id}
//   esService.saveSnapshotFlow/delete            ↔ es.bulk_upsert / delete_by_id
//
// PARITY: Java 的 processMessage 只做「库 + ES」，从未调用 MultiSourceDataFlowService /
// DataReliabilityService.confirmConsumption（全仓仅 DataFlowTask 有一行被注释的调用）。
// Rust 侧同样不接这两条链路，避免迁移时顺手加功能。

use futures::FutureExt;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::{error, info, warn};

use crate::cache::Cache;
use crate::config::{PulsarConfig, PROCESSING_TTL_SECONDS};
use crate::error::AppResult;
use crate::es::EsClient;
use crate::models::OdsRtSzdnSnapshotFlowAddcode;
use crate::mq::{Bus, Message};
use crate::repo::SnapshotFlowRepo;
use crate::services::IDEMPOTENT_KEY_PREFIX;

/// 消费循环异常/panic 后的重连退避（5s 起步，最长 60s）。
const RECONNECT_MIN: std::time::Duration = std::time::Duration::from_secs(5);
const RECONNECT_MAX: std::time::Duration = std::time::Duration::from_secs(60);
/// 一次消费运行超过该时长后失败，退避重置回 RECONNECT_MIN。
const RECONNECT_RESET: std::time::Duration = std::time::Duration::from_secs(120);

/// 等待"另一处理者"完成时的轮询步长。
const PROCESSING_WAIT_STEP: std::time::Duration = std::time::Duration::from_millis(200);

/// 消费重连监督器：`run` 每被调用一次代表一次 bus.consume 尝试。
///
/// 抽成泛型函数（而不是写死在 start 的闭包里）是为了让单测注入不依赖 Kafka 的假 consume，
/// 真正覆盖 panic/Err → mark_error/mark_stopped → 退避 → 重连 → mark_started 的接线；
/// 只测 `mark_panic_exit()` 本身无法发现"循环里忘了调用它"。
async fn supervise_consume<F, Fut>(
    mut stop: tokio::sync::watch::Receiver<bool>,
    state: &crate::mq::ConsumerState,
    min_backoff: std::time::Duration,
    max_backoff: std::time::Duration,
    reset_after: std::time::Duration,
    mut run: F,
) where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = AppResult<()>>,
{
    let mut backoff = min_backoff;
    loop {
        if *stop.borrow() {
            break;
        }
        let attempt_started = std::time::Instant::now();
        let outcome = std::panic::AssertUnwindSafe(run()).catch_unwind().await;
        match outcome {
            Ok(Ok(())) => break, // 收到停机信号，正常退出
            Ok(Err(e)) => {
                // 必须记录原因：否则 /readyz 只看到 DOWN，运维无法区分订阅失败还是拉取失败。
                state.mark_error(&format!("消费循环异常退出: {}", e));
                state.mark_stopped();
                if *stop.borrow() {
                    break;
                }
                error!(
                    err = %e,
                    backoff_seconds = backoff.as_secs(),
                    "[快照消费者] 消费循环异常退出，稍后重连"
                );
            }
            Err(_) => {
                mark_panic_exit(state);
                if *stop.borrow() {
                    break;
                }
                error!(
                    backoff_seconds = backoff.as_secs(),
                    "[快照消费者] 消费循环 panic，稍后重连"
                );
            }
        }
        if attempt_started.elapsed() >= reset_after {
            backoff = min_backoff;
        }
        // changed() 在 Sender 提前 drop 时返回 Err；此时 borrow() 仍是 false，
        // 继续循环会形成忙循环，因此 Err 也按停机处理。
        let stop_now = tokio::select! {
            r = stop.changed() => r.is_err() || *stop.borrow(),
            _ = tokio::time::sleep(backoff) => false,
        };
        if stop_now {
            break;
        }
        backoff = std::cmp::min(backoff.saturating_mul(2), max_backoff);
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SnapshotFlowMessage {
    operation_type: String,
    data: Value,
}

#[derive(Clone)]
pub struct SnapshotFlowConsumer {
    pub repo: SnapshotFlowRepo,
    pub es: Option<EsClient>,
    pub es_index: String,
    pub cache: Option<Cache>,
    pub ttl_seconds: u64,
    pub consumer_type: String,
}

impl SnapshotFlowConsumer {
    pub fn new(
        repo: SnapshotFlowRepo,
        es: Option<EsClient>,
        es_index: String,
        cache: Option<Cache>,
        cfg: &PulsarConfig,
    ) -> Self {
        Self {
            repo,
            es,
            es_index,
            cache,
            ttl_seconds: if cfg.idempotent_ttl_seconds == 0 {
                86_400
            } else {
                cfg.idempotent_ttl_seconds
            },
            consumer_type: "snapshotflow".into(),
        }
    }

    pub fn start(
        self,
        bus: Bus,
        stop: tokio::sync::watch::Receiver<bool>,
        state: crate::mq::ConsumerState,
    ) -> Option<tokio::task::JoinHandle<()>> {
        if !bus.is_active() {
            warn!("[快照消费者] 未配置消息总线，消费端不启动");
            return None;
        }
        Some(tokio::spawn(async move {
            let this = self.clone();
            let attempt_stop = stop.clone();
            // handler 需要独立的停机信号副本：幂等"处理中"的等待循环要能被停机打断，
            // 否则 main 只能在 3s 预算到点后强杀任务。
            let handler_stop = attempt_stop.clone();
            let handler: crate::mq::Handler = std::sync::Arc::new(move |msg: Message| {
                let this = this.clone();
                let mut stop = handler_stop.clone();
                Box::pin(async move { this.handle(msg, Some(&mut stop)).await })
            });
            // 消费循环异常退出（含 panic）时整体重连，而不是永久放弃：
            // 任务停摆若只体现在 /readyz JSON 里，探针仍 200、K8s 既不摘流也不重启。
            // 选"重连"而不是"readyz 503"，是因为 Kafka 故障不应连带把 HTTP 服务摘出流量
            // （消费是旁路写链路，API 查询仍可用），且 panic 属进程内可自愈故障。
            // 退避 5s → 60s；若一次消费运行超过 120s 才失败，退避重置回 5s。
            supervise_consume(
                stop,
                &state,
                RECONNECT_MIN,
                RECONNECT_MAX,
                RECONNECT_RESET,
                || {
                    let bus = bus.clone();
                    let stop = attempt_stop.clone();
                    let handler = handler.clone();
                    let state = state.clone();
                    async move { bus.consume(stop, handler, Some(state)).await }
                },
            )
            .await;
            state.mark_stopped();
            info!("[快照消费者] 消费循环已退出");
        }))
    }

    /// 返回 Ok 表示 ack（含"确认丢弃"的格式错误/重复消息）；Err 表示 nack 触发重投。
    /// `stop` 用于在幂等"处理中"等待时响应停机信号：尽快返回 Err，由 mq 层跳过 offset 提交。
    pub async fn handle(
        &self,
        msg: Message,
        mut stop: Option<&mut tokio::sync::watch::Receiver<bool>>,
    ) -> AppResult<()> {
        let started = std::time::Instant::now();
        let data_id = msg.key.clone();

        let envelope: SnapshotFlowMessage = match serde_json::from_slice(&msg.value) {
            Ok(v) => v,
            Err(e) => {
                error!(data_id = %data_id, err = %e, "[快照消费者] 消息格式错误，确认丢弃");
                return Ok(());
            }
        };
        if envelope.operation_type.is_empty() || envelope.data.is_null() {
            error!(data_id = %data_id, "[快照消费者] 消息缺少必要字段，确认丢弃");
            return Ok(());
        }

        // ---- 两段式幂等 ----
        // done_key：沿用旧前缀，跨版本/跨语言兼容，TTL = 完整幂等窗口（默认 24h）。
        // processing_key：只表示"正在处理"，短 TTL。停机 abort/panic 时即使 Drop 里的
        //   异步删除没跑完，最多 PROCESSING_TTL_SECONDS 后自动失效，重投即可重新处理，
        //   不会被旧的"已处理"标记永久挡住。
        // 看到 processing 但 done 不存在：说明另一实例正在处理或崩溃残留。
        //   不立即 ack（避免丢消息），也不立即 Err（避免在 mq 1.4s 重试预算内耗尽后进 DLQ）；
        //   在本次 handler 内等待 done 出现或 processing 过期（见下方等待循环）。
        let done_key = format!("{}{}", IDEMPOTENT_KEY_PREFIX, data_id);
        let processing_key = format!("{}processing:{}", IDEMPOTENT_KEY_PREFIX, data_id);
        let mut idem_guard = IdempotencyGuard::new(processing_key.clone(), None);
        if let Some(c) = &self.cache {
            let done = c
                .exists(&done_key)
                .await
                .map_err(|e| crate::error::AppError::biz(format!("幂等完成标记读取失败: {}", e)))?;
            if done {
                info!(data_id = %data_id, "[快照消费者] 消息已处理（幂等去重）");
                return Ok(());
            }
            let ttl = std::time::Duration::from_secs(PROCESSING_TTL_SECONDS);
            let first = c
                .set_nx(
                    &processing_key,
                    crate::services::sysutil::now_ms().to_string(),
                    ttl,
                )
                .await
                .map_err(|e| crate::error::AppError::biz(format!("幂等处理标记写入失败: {}", e)))?;
            if !first {
                // 不能直接返回 Err：mq 重试总窗口（默认 4 次 ×200ms 指数退避 ≈1.4s）
                // 小于 processing TTL（10s），直接 Err 会在 1.4s 内耗尽重试并投 DLQ，
                // 而实际上再等几秒原处理者就会完成或 TTL 到期。
                // 跨副本 rebalance / 10s 内重启 / Drop 异步删除失败都会走到这里。
                // 处理方式：在本次 handler 内等待——
                //   done 出现 → 别的副本已成功 → ack；
                //   processing 消失 → 原处理者失败或 TTL 到期 → 重新抢占继续处理。
                warn!(
                    data_id = %data_id,
                    max_block_seconds = PROCESSING_TTL_SECONDS + 1,
                    "[快照消费者] 消息处理中，等待原处理者完成或 TTL 到期（单线程顺序消费，等待期间阻塞所有分区）"
                );
                let deadline = std::time::Instant::now()
                    + std::time::Duration::from_secs(PROCESSING_TTL_SECONDS + 1);
                loop {
                    // 等待必须响应停机信号：否则 main 只能在 3s 预算到点后强杀任务。
                    let stopped = match stop.as_deref_mut() {
                        Some(s) => tokio::select! {
                            _ = tokio::time::sleep(PROCESSING_WAIT_STEP) => false,
                            r = s.changed() => r.is_err() || *s.borrow(),
                        },
                        None => {
                            tokio::time::sleep(PROCESSING_WAIT_STEP).await;
                            false
                        }
                    };
                    if stopped {
                        warn!(data_id = %data_id, "[快照消费者] 停机中，取消处理中等待，offset 不提交");
                        return Err(crate::error::AppError::biz("停机中，取消处理中等待"));
                    }
                    if c.exists(&done_key).await.map_err(|e| {
                        crate::error::AppError::biz(format!("幂等完成标记读取失败: {}", e))
                    })? {
                        info!(data_id = %data_id, "[快照消费者] 消息已由其它副本处理完成（幂等去重）");
                        return Ok(());
                    }
                    let still_processing = c.exists(&processing_key).await.map_err(|e| {
                        crate::error::AppError::biz(format!("幂等处理标记读取失败: {}", e))
                    })?;
                    if !still_processing {
                        let reacquired = c
                            .set_nx(
                                &processing_key,
                                crate::services::sysutil::now_ms().to_string(),
                                ttl,
                            )
                            .await
                            .map_err(|e| {
                                crate::error::AppError::biz(format!("幂等处理标记写入失败: {}", e))
                            })?;
                        if reacquired {
                            // done→processing 双检竞态：原处理者可能在两次检查之间写完 done
                            // 并删掉 processing；抢占成功后再查一次 done，命中则撤销本次抢占并 ack。
                            if c.exists(&done_key).await.map_err(|e| {
                                crate::error::AppError::biz(format!("幂等完成标记读取失败: {}", e))
                            })? {
                                info!(data_id = %data_id, "[快照消费者] 抢占后确认已完成（幂等去重）");
                                if let Err(e) =
                                    c.del(std::slice::from_ref(&processing_key)).await
                                {
                                    warn!(data_id = %data_id, err = %e, "[快照消费者] 撤销处理中标记失败（短 TTL 会自动失效）");
                                }
                                return Ok(());
                            }
                            break;
                        }
                    }
                    if std::time::Instant::now() >= deadline {
                        warn!(data_id = %data_id, "[快照消费者] 等待处理中标记超时，触发重投");
                        return Err(crate::error::AppError::biz("消息长时间处理中，稍后重试"));
                    }
                }
            }
            idem_guard = IdempotencyGuard::new(
                processing_key.clone(),
                Some(Box::new({
                    let cache = c.clone();
                    let data_id = data_id.clone();
                    move |key: String| {
                        tokio::spawn(async move {
                            if let Err(e) = cache.del(std::slice::from_ref(&key)).await {
                                warn!(data_id = %data_id, err = %e, "[快照消费者] panic 后清理幂等标记失败，重投可能被误判为重复");
                            }
                        });
                    }
                })),
            );
        } else {
            warn!(data_id = %data_id, "[快照消费者] 缓存未启用，跳过幂等判重");
        }

        let result = self.process(&data_id, envelope, started).await;
        if result.is_ok() {
            if let Some(c) = &self.cache {
                if let Err(e) = c
                    .set_ttl(
                        &done_key,
                        "1",
                        std::time::Duration::from_secs(self.ttl_seconds),
                    )
                    .await
                {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] 写入幂等完成标记失败，本次按失败重试");
                    let _ = c.del(std::slice::from_ref(&processing_key)).await;
                    idem_guard.keep();
                    return Err(crate::error::AppError::biz(format!(
                        "幂等完成标记写入失败: {}",
                        e
                    )));
                }
                if let Err(e) = c.del(std::slice::from_ref(&processing_key)).await {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] 清理处理中标记失败（短 TTL 会自动失效）");
                }
            }
            idem_guard.keep();
        } else {
            if let Some(c) = &self.cache {
                if let Err(e) = c.del(std::slice::from_ref(&processing_key)).await {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] 清理处理中标记失败，重投将等待短 TTL 过期");
                }
            }
            idem_guard.keep();
        }
        result
    }

    async fn process(
        &self,
        data_id: &str,
        envelope: SnapshotFlowMessage,
        started: std::time::Instant,
    ) -> AppResult<()> {
        let flow: OdsRtSzdnSnapshotFlowAddcode = match serde_json::from_value(envelope.data) {
            Ok(v) => v,
            Err(e) => {
                error!(data_id = %data_id, err = %e, "[快照消费者] data 字段解析失败，确认丢弃");
                return Ok(());
            }
        };
        if flow.big_id.is_empty() {
            error!(data_id = %data_id, "[快照消费者] data 缺少 bigId，确认丢弃");
            return Ok(());
        }

        match envelope.operation_type.to_uppercase().as_str() {
            "INSERT" => {
                self.save_or_update(&flow).await?;
                self.save_to_es(&flow).await?;
                info!(data_id = %data_id, cost_ms = started.elapsed().as_millis() as u64, "[快照消费者] INSERT 成功");
            }
            "UPDATE" => {
                if let Err(e) = self.repo.update(&flow).await {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] UPDATE 失败（记录可能不存在），转 INSERT");
                    self.save_or_update(&flow).await?;
                }
                self.save_to_es(&flow).await?;
                info!(data_id = %data_id, cost_ms = started.elapsed().as_millis() as u64, "[快照消费者] UPDATE 成功");
            }
            "DELETE" => {
                if let Err(e) = self.repo.delete_by_id(data_id).await {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] DELETE GaussDB 失败（记录可能不存在）");
                }
                if let Some(es) = &self.es {
                    // PARITY: ES 文档 _id 与同步链路保持一致（快照表用 datauuid）。
                    // 之前先 delete_by_id 再 get_by_id 反查，删除后必然查不到，导致
                    // _id=datauuid 的文档永远删不掉。这里直接用消息里已解析的 datauuid，
                    // 同时按 bigId 删一次以兼容历史文档。
                    let mut es_ids = vec![data_id.to_string()];
                    let uuid = flow.datauuid.as_str().to_string();
                    if !uuid.is_empty() && !es_ids.contains(&uuid) {
                        es_ids.push(uuid);
                    }
                    for id in es_ids {
                        if let Err(e) = es.delete_by_id(&self.es_index, &id).await {
                            warn!(data_id = %data_id, es_id = %id, err = %e, "[快照消费者] DELETE Elasticsearch 失败");
                        }
                    }
                }
                info!(data_id = %data_id, "[快照消费者] DELETE 完成");
            }
            other => {
                warn!(data_id = %data_id, operation = other, "[快照消费者] 未知操作类型，确认丢弃")
            }
        }
        Ok(())
    }

    async fn save_or_update(&self, flow: &OdsRtSzdnSnapshotFlowAddcode) -> AppResult<()> {
        match self.repo.get_by_id(&flow.big_id).await? {
            None => self.repo.insert(flow).await,
            Some(_) => self.repo.update(flow).await,
        }
    }

    async fn save_to_es(&self, flow: &OdsRtSzdnSnapshotFlowAddcode) -> AppResult<()> {
        let Some(es) = &self.es else {
            warn!(data_id = %flow.big_id, "[快照消费者] Elasticsearch 未配置，跳过写入");
            return Ok(());
        };
        if self.es_index.is_empty() {
            return Ok(());
        }
        let mut doc = serde_json::to_value(flow)?;
        if let Some(obj) = doc.as_object_mut() {
            for k in [
                "id",
                "snapshottimeStr",
                "applyTime1",
                "applyTime2",
                "queryUuids",
                "flag",
                "sectionCodeStr",
                "type",
                "code",
                "codeList",
                "sectionList",
                "startNum",
                "endNum",
            ] {
                obj.remove(k);
            }
            // PARITY: 同步链路（LargeScaleDataSyncService）快照表以 datauuid 作为 ES 文档 _id；
            // 消费端此前用 bigId，导致同一行在索引里出现两份文档。统一为 datauuid（为空时回退 bigId）。
            let uuid = flow.datauuid.as_str().to_string();
            let es_id = if uuid.is_empty() {
                flow.big_id.as_str().to_string()
            } else {
                uuid
            };
            obj.insert("_id".into(), Value::String(es_id));
        }
        // PARITY: 与 Java saveSnapshotFlow 的返回值语义一致 —— 写入失败要让 mq 重投，
        // 不能把 HTTP 200 + errors=true 当成成功。
        let outcome = es
            .bulk_upsert(&self.es_index, "_id", &[doc])
            .await
            .map_err(|e| crate::error::AppError::biz(format!("ES 写入失败: {}", e)))?;
        if !outcome.is_all_ok() {
            return Err(crate::error::AppError::biz(format!(
                "ES bulk 写入失败 {} 条: {}",
                outcome.failed,
                outcome.first_error.unwrap_or_default()
            )));
        }
        Ok(())
    }
}

/// panic 路径的状态接线：任务已停 + 记录错误，/readyz 至少能显示 DOWN。
/// 抽成函数是为了让单测直接覆盖"panic → mark_stopped"这条接线。
pub(crate) fn mark_panic_exit(state: &crate::mq::ConsumerState) {
    state.mark_error("消费循环 panic，准备重连");
    state.mark_stopped();
}

/// "处理中"标记的兜底清理：成功/失败路径都在 handle 里显式 await 删除；
/// panic 路径由 Drop 执行 `on_drop`（内部 `tokio::spawn` 异步删除，Drop 里不能 await），
/// 最坏由短 TTL 兜底。动作以闭包注入，便于单测直接验证 Drop 语义而不依赖 Redis。
struct IdempotencyGuard {
    key: String,
    on_drop: Option<Box<dyn FnOnce(String) + Send>>,
}

impl IdempotencyGuard {
    fn new(key: String, on_drop: Option<Box<dyn FnOnce(String) + Send>>) -> Self {
        Self { key, on_drop }
    }

    fn keep(&mut self) {
        self.on_drop = None;
    }
}

impl Drop for IdempotencyGuard {
    fn drop(&mut self) {
        if let Some(action) = self.on_drop.take() {
            action(self.key.clone());
        }
    }
}

/// 提供给 /readyz 的消费端状态。
pub fn consumer_started_flag() -> std::sync::Arc<std::sync::atomic::AtomicBool> {
    std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false))
}

#[derive(Debug, Clone, Serialize)]
pub struct DeliveryReport {
    pub operation_type: String,
    pub data_id: String,
}

#[cfg(test)]
mod tests {
    use super::{supervise_consume, IdempotencyGuard};
    use crate::error::AppError;
    use crate::mq::ConsumerState;
    use crate::router::consumer_status;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::time::Duration;

    fn status(state: &ConsumerState) -> &'static str {
        consumer_status(
            true,
            state.is_started(),
            state.last_recv_ms(),
            state.last_error().map(|(t, _)| t),
            crate::services::sysutil::now_ms(),
        )
    }

    /// 用假 consume 驱动真实监督器：第一次 panic，第二次在"重连入口"断言状态，
    /// 再模拟订阅成功。若循环里删掉 `mark_panic_exit` 那行，第二次断言会失败。
    #[tokio::test]
    async fn panic_in_consume_marks_down_then_reconnects() {
        let state = ConsumerState::default();
        // Sender 必须活到监督器结束，否则 changed() 返回 Err 会被当作停机。
        let (_tx, stop) = tokio::sync::watch::channel(false);
        let calls = Arc::new(AtomicUsize::new(0));
        let state_for_run = state.clone();
        let calls_for_run = calls.clone();
        supervise_consume(
            stop,
            &state,
            Duration::from_millis(10),
            Duration::from_millis(20),
            Duration::from_secs(60),
            move || {
                let state = state_for_run.clone();
                let calls = calls_for_run.clone();
                async move {
                    if calls.fetch_add(1, Ordering::SeqCst) == 0 {
                        state.mark_started();
                        state.mark_recv();
                        panic!("模拟消费循环 panic");
                    }
                    // 第二次进入说明 panic 后确实退避并重连了：
                    assert!(!state.is_started(), "panic 后重连前必须 stopped");
                    assert!(state.last_error().is_some(), "panic 后必须记录错误原因");
                    assert_eq!(status(&state), "DOWN");
                    // 模拟 bus.consume 订阅成功后 mark_started。
                    state.mark_started();
                    Ok(())
                }
            },
        )
        .await;
        assert_eq!(calls.load(Ordering::SeqCst), 2, "panic 后必须重连一次");
        assert!(state.is_started(), "重连成功后必须重新 mark_started");
        assert!(state.last_error().is_none(), "mark_started 应清空历史错误");
    }

    /// Err 分支：必须 mark_error（带原因）+ mark_stopped，再退避重连。
    #[tokio::test]
    async fn error_in_consume_records_reason_then_reconnects() {
        let state = ConsumerState::default();
        let (_tx, stop) = tokio::sync::watch::channel(false);
        let calls = Arc::new(AtomicUsize::new(0));
        let state_for_run = state.clone();
        let calls_for_run = calls.clone();
        supervise_consume(
            stop,
            &state,
            Duration::from_millis(10),
            Duration::from_millis(20),
            Duration::from_secs(60),
            move || {
                let state = state_for_run.clone();
                let calls = calls_for_run.clone();
                async move {
                    if calls.fetch_add(1, Ordering::SeqCst) == 0 {
                        state.mark_started();
                        return Err(AppError::biz("模拟订阅失败"));
                    }
                    assert!(!state.is_started(), "Err 后重连前必须 stopped");
                    let (_, msg) = state.last_error().expect("Err 后必须 mark_error");
                    assert!(
                        msg.contains("模拟订阅失败"),
                        "last_error 应携带原因: {}",
                        msg
                    );
                    assert_eq!(status(&state), "DOWN");
                    state.mark_started();
                    Ok(())
                }
            },
        )
        .await;
        assert_eq!(calls.load(Ordering::SeqCst), 2, "Err 后必须重连一次");
        assert!(state.is_started());
    }

    /// watch::Sender 提前 drop 时 changed() 返回 Err：必须按停机退出，不能忙循环重试。
    #[tokio::test]
    async fn dropped_stop_sender_is_treated_as_shutdown() {
        let state = ConsumerState::default();
        let (tx, stop) = tokio::sync::watch::channel(false);
        let calls = Arc::new(AtomicUsize::new(0));
        let calls_for_run = calls.clone();
        let task = tokio::spawn(async move {
            supervise_consume(
                stop,
                &state,
                Duration::from_millis(50),
                Duration::from_millis(100),
                Duration::from_secs(60),
                move || {
                    let calls = calls_for_run.clone();
                    async move {
                        calls.fetch_add(1, Ordering::SeqCst);
                        Err(AppError::biz("模拟失败"))
                    }
                },
            )
            .await;
        });
        // 第一次尝试立即失败并进入 50ms 退避；此时 drop Sender，changed() 会返回 Err。
        tokio::time::sleep(Duration::from_millis(20)).await;
        drop(tx);
        tokio::time::timeout(Duration::from_millis(300), task)
            .await
            .expect("Sender drop 后监督器必须按停机退出")
            .unwrap();
        assert_eq!(
            calls.load(Ordering::SeqCst),
            1,
            "changed() 返回 Err 后不得再发起第 2 次尝试（忙循环）"
        );
    }

    #[test]
    fn dropped_guard_runs_cleanup_with_processing_key() {
        let (tx, rx) = std::sync::mpsc::channel();
        let guard = IdempotencyGuard::new(
            "processing-key".to_string(),
            Some(Box::new(move |key| {
                let _ = tx.send(key);
            })),
        );
        drop(guard);
        assert_eq!(rx.try_recv().unwrap(), "processing-key");
    }

    #[test]
    fn kept_guard_does_not_run_cleanup() {
        let (tx, rx) = std::sync::mpsc::channel();
        let mut guard = IdempotencyGuard::new(
            "processing-key".to_string(),
            Some(Box::new(move |key| {
                let _ = tx.send(key);
            })),
        );
        guard.keep();
        drop(guard);
        assert!(rx.try_recv().is_err(), "keep() 后 Drop 不得执行清理");
    }
}
