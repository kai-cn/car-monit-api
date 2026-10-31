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

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::{error, info, warn};

use crate::cache::Cache;
use crate::config::PulsarConfig;
use crate::error::AppResult;
use crate::es::EsClient;
use crate::models::OdsRtSzdnSnapshotFlowAddcode;
use crate::mq::{Bus, Message};
use crate::repo::SnapshotFlowRepo;
use crate::services::IDEMPOTENT_KEY_PREFIX;

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

    pub fn start(self, bus: Bus, stop: tokio::sync::watch::Receiver<bool>) {
        if !bus.is_active() {
            warn!("[快照消费者] 未配置消息总线，消费端不启动");
            return;
        }
        tokio::spawn(async move {
            info!("[快照消费者] 消费循环已启动");
            let this = self.clone();
            let handler: crate::mq::Handler = std::sync::Arc::new(move |msg: Message| {
                let this = this.clone();
                Box::pin(async move { this.handle(msg).await })
            });
            if let Err(e) = bus.consume(stop.clone(), handler).await {
                if !*stop.borrow() {
                    error!(err = %e, "[快照消费者] 消费循环异常退出");
                    tokio::time::sleep(std::time::Duration::from_secs(5)).await;
                }
            }
            info!("[快照消费者] 消费循环已退出");
        });
    }

    /// 返回 Ok 表示 ack（含"确认丢弃"的格式错误/重复消息）；Err 表示 nack 触发重投。
    pub async fn handle(&self, msg: Message) -> AppResult<()> {
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

        // 幂等判重
        if let Some(c) = &self.cache {
            let first = c
                .set_nx(
                    &format!("{}{}", IDEMPOTENT_KEY_PREFIX, data_id),
                    crate::services::sysutil::now_ms().to_string(),
                    std::time::Duration::from_secs(self.ttl_seconds),
                )
                .await
                .map_err(|e| crate::error::AppError::biz(format!("幂等标记写入失败: {}", e)))?;
            if !first {
                info!(data_id = %data_id, "[快照消费者] 消息已处理（幂等去重）");
                return Ok(());
            }
        } else {
            warn!(data_id = %data_id, "[快照消费者] 缓存未启用，跳过幂等判重");
        }

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
                if let Err(e) = self.repo.delete_by_id(&data_id).await {
                    warn!(data_id = %data_id, err = %e, "[快照消费者] DELETE GaussDB 失败（记录可能不存在）");
                }
                if let Some(es) = &self.es {
                    if let Err(e) = es.delete_by_id(&self.es_index, &data_id).await {
                        warn!(data_id = %data_id, err = %e, "[快照消费者] DELETE Elasticsearch 失败");
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
            obj.insert(
                "_id".into(),
                Value::String(flow.big_id.as_str().to_string()),
            );
        }
        es.bulk_upsert(&self.es_index, "_id", &[doc]).await?;
        Ok(())
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
