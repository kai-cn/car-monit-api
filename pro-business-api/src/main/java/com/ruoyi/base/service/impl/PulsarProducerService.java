package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.domain.PulsarMessageRecord;
import com.ruoyi.base.mapper.PulsarMessageRecordMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.pulsar.client.api.MessageId;
import org.apache.pulsar.client.api.Producer;
import org.apache.pulsar.client.api.TypedMessageBuilder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Pulsar 消息发送服务
 *
 * 功能说明：
 * - 将门架抓拍流水数据发送到 Pulsar 消息队列
 * - 完全等价替换原 KafkaProducerService 功能
 *
 * 可靠性保障机制（与 Kafka 版一一对应）：
 * 1. 消息先入库再发送（status=0 待发送）
 * 2. 异步发送并通过回调更新状态
 * 3. 后台定时线程扫描待重试记录并重发
 * 4. 超过最大重试次数（默认 10 次）停止重试，需要人工介入
 *
 * Pulsar 与 Kafka API 区别：
 * - KafkaTemplate.send()  <=>  Producer.newMessage().sendAsync()
 * - ListenableFuture       <=>  CompletableFuture<MessageId>
 * - ProducerRecord(key,value) <=> newMessage().key(dataId).value(json)
 * - MessageId（Pulsar原生）  <=>  offset + partition（Kafka概念）
 */
@Slf4j
//@Service
public class PulsarProducerService {

    @Autowired
    private Producer<String> snapshotFlowProducer;

    @Autowired
    private PulsarMessageRecordMapper pulsarMessageRecordMapper;

    @Value("${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}")
    private String defaultTopic;

    @Value("${spring.pulsar.max-retry-count:10}")
    private int maxRetryCount;

    private ExecutorService retryExecutor;

    /**
     * 服务初始化：启动后台重试线程
     */
    @PostConstruct
    public void init() {
        retryExecutor = Executors.newSingleThreadExecutor();
        startRetryTask();
        log.info("[PulsarProducer] 初始化完成，主题={}, 最大重试={}", defaultTopic, maxRetryCount);
    }

    /**
     * 服务销毁：优雅关闭线程池和 Producer
     */
    @PreDestroy
    public void destroy() {
        log.info("[PulsarProducer] 正在关闭...");
        if (retryExecutor != null) {
            retryExecutor.shutdownNow();
        }
        try {
            if (snapshotFlowProducer != null && snapshotFlowProducer.isConnected()) {
                snapshotFlowProducer.close();
            }
        } catch (Exception e) {
            log.error("[PulsarProducer] 关闭 Producer 异常", e);
        }
    }

    /**
     * 发送单条抓拍流水数据
     *
     * 步骤：
     * 1. 构建标准消息格式 JSON：{ "operationType": "INSERT", "data": {...} }
     * 2. 消息记录入库（status=0 待发送），生成 UUID 主键
     * 3. 调用 sendMessage() 异步发送，通过 CompletableFuture 回调更新数据库状态
     *
     * @param data   业务数据对象（OdsRtSzdnSnapshotFlowAddcode）
     * @param dataId 业务数据ID（用作 Pulsar Message 的 key）
     * @return dataId
     */
    public String sendSnapshotFlowData(Object data, String dataId) {
        try {
            // 1. 构建标准消息 JSON 格式
            JSONObject messageObj = new JSONObject();
            messageObj.put("operationType", "INSERT");
            messageObj.put("data", data);
            String messageJson = messageObj.toJSONString();

            // 2. 先入库：status=0 待发送
            PulsarMessageRecord record = new PulsarMessageRecord();
            record.setId(UUID.randomUUID().toString().replace("-", ""));
            record.setDataId(dataId);
            record.setTopic(defaultTopic);
            record.setMessageJson(messageJson);
            record.setStatus(0);
            record.setRetryCount(0);
            record.setCreateTime(new Date());
            pulsarMessageRecordMapper.insert(record);

            // 3. 异步发送
            sendMessage(record);

            log.info("[PulsarProducer] 消息已提交发送: dataId={}, recordId={}", dataId, record.getId());
            return dataId;

        } catch (Exception e) {
            log.error("[PulsarProducer] 发送异常: dataId={}", dataId, e);
            return dataId;
        }
    }

    /**
     * 实际发送消息到 Pulsar
     *
     * sendAsync() 返回 CompletableFuture<MessageId>，注册 thenAccept / exceptionally 回调：
     * - 成功回调：UPDATE status=1，记录 messageId 和 sendTime
     * - 失败回调：UPDATE status=2，retry_count+1，记录 errorMsg
     */
    private void sendMessage(PulsarMessageRecord record) {
        // 构建消息：key=dataId（路由一致性） value=JSON
        TypedMessageBuilder<String> messageBuilder = snapshotFlowProducer.newMessage()
                .key(record.getDataId())
                .value(record.getMessageJson());

        // 异步发送
        CompletableFuture<MessageId> future = messageBuilder.sendAsync();

        // 成功回调
        future.thenAccept(messageId -> {
            pulsarMessageRecordMapper.updateStatusById(
                    record.getId(), 1, new Date(), messageId.toString());
            log.info("[PulsarProducer] 发送成功: dataId={}, messageId={}",
                    record.getDataId(), messageId);
        });

        // 失败回调
        future.exceptionally(ex -> {
            String errorMsg = ex.getMessage();
            if (errorMsg != null && errorMsg.length() > 500) {
                errorMsg = errorMsg.substring(0, 500);
            }
            pulsarMessageRecordMapper.incrementRetryCount(record.getId(), errorMsg);
            log.error("[PulsarProducer] 发送失败: dataId={}, error={}", record.getDataId(), errorMsg);
            return null;
        });
    }

    /**
     * 后台重试任务：每 30 秒扫描待重试记录
     *
     * 思路：
     * 1. 查询 status IN (0, 2) AND retry_count < maxRetryCount 的记录（最多 100 条）
     * 2. 逐条调用 sendMessage() 重新发送
     * 3. 休眠 30 秒后进入下一轮
     */
    private void startRetryTask() {
        retryExecutor.submit(() -> {
            while (!Thread.currentThread().isInterrupted()) {
                try {
                    List<PulsarMessageRecord> failedRecords =
                            pulsarMessageRecordMapper.selectFailedRecords(maxRetryCount, 100);

                    if (failedRecords != null && !failedRecords.isEmpty()) {
                        log.info("[PulsarProducer] 开始重试 {} 条消息", failedRecords.size());
                        for (PulsarMessageRecord record : failedRecords) {
                            sendMessage(record);
                        }
                    }

                    TimeUnit.SECONDS.sleep(30);

                } catch (InterruptedException ie) {
                    log.info("[PulsarProducer] 重试任务收到中断信号，退出");
                    Thread.currentThread().interrupt();
                    break;
                } catch (Exception e) {
                    log.error("[PulsarProducer] 重试任务异常，等待 60s 后继续", e);
                    try {
                        TimeUnit.SECONDS.sleep(60);
                    } catch (InterruptedException ie2) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        });
    }

    /**
     * 健康检查：Producer 是否正常连接
     */
    public boolean isProducerHealthy() {
        return snapshotFlowProducer != null && snapshotFlowProducer.isConnected();
    }
}
