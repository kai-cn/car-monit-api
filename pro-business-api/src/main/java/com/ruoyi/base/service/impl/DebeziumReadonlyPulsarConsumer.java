package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.base.service.IEsService;
import lombok.extern.slf4j.Slf4j;
import org.apache.pulsar.client.api.Consumer;
import org.apache.pulsar.client.api.Message;
import org.apache.pulsar.client.api.MessageId;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Debezium CDC 只读 Pulsar 消费者
 *
 * 功能说明（与原 DebeziumReadonlyKafkaConsumer 等价）：
 * - 消费 Pulsar 中的 CDC 变更消息（由 Debezium 从源数据库捕获）
 * - 保证消息幂等：基于 Redis SETNX + LSN（Log Sequence Number）
 * - 保证数据不丢失：先持久化到 MySQL，再写入 Elasticsearch
 *
 * 设计背景：
 * - 原方案使用 Debezium 监听源 GaussDB 的数据变更（逻辑复制槽）
 * - 生产者将 Debezium 产出的变更事件转换为统一消息格式并发送到 Pulsar
 * - 消费者端（本类）从 Pulsar 消费这些变更事件
 * - 源数据库只有查询权限，因此 CDC 是"只读"模式（Debezium snapshot.locking.mode=none）
 *
 * 消息格式（与生产者约定）：
 *   {
 *     "operationType": "INSERT",                // INSERT / UPDATE / DELETE
 *     "data": { ... },                          // OdsRtSzdnSnapshotFlowAddcode 对象
 *     "source": {                               // Debezium source 元数据（可选）
 *       "lsn": "123456",                        // 日志序列号（用于幂等性判断）
 *       "ts_ms": 1719897600000                  // 事件时间戳
 *     }
 *   }
 *
 * Pulsar 消费者特性（与 Kafka 的区别）：
 * -----------------------------------------------------------------------------
 * 原 Kafka 机制             Pulsar 对应机制
 * -----------------------------------------------------------------------------
 * @KafkaListener 注解       手动 while(true) 循环 receive()
 * consumer.commitAsync()    consumer.acknowledgeAsync(message)
 * consumer.seekToBeginning() consumer.seek(messageId) / seekByTime()
 * auto.offset.reset=earliest subscriptionInitialPosition=Earliest
 * consumer group 负载均衡   SubscriptionType.Key_Shared（按 key 路由保证有序）
 * -----------------------------------------------------------------------------
 *
 * 可靠性保证（4 层机制）：
 * 1. LSN 幂等检查：同一 LSN 的消息只处理一次（Redis SETNX）
 * 2. 数据持久化：先写 MySQL，成功后写 Elasticsearch
 * 3. 手动确认：业务处理成功后才 acknowledge，否则 negativeAcknowledge 重投
 * 4. 死信队列：超过 max-retry-times 次重投失败的消息路由到 DLQ
 */
@Slf4j
//@Service
public class DebeziumReadonlyPulsarConsumer {

    /**
     * 注入 Pulsar CDC 消费者（由 PulsarConsumerConfig 的 debeziumReadonlyConsumer 创建）
     * Key_Shared 订阅模式：相同 key 的消息始终路由到同一个 consumer 实例
     * 保证同一 dataId 的变更事件按顺序处理（与 Kafka partition 顺序语义一致）
     */
    @Autowired
    private Consumer<String> debeziumReadonlyConsumer;

    /**
     * 业务服务：MySQL 分表写入
     * 与主消费者共享同一服务实例
     */
    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowService;

    /**
     * 业务服务：Elasticsearch 写入
     * 与主消费者共享同一 ES 服务
     */
    @Autowired
    private IEsService esService;

    /**
     * Redis 模板：幂等性检查用
     */
    @Autowired
    private StringRedisTemplate redisTemplate;

    /**
     * 幂等性过期时间（秒）
     * 默认 7 天：CDC 消息的有效期通常更长，因为可能需要回放
     */
    @Value("${spring.pulsar.idempotent-ttl-seconds:604800}")
    private long idempotentTtlSeconds;

    /**
     * Redis 幂等性 Key 前缀（CDC 专用）
     * 与主消费者使用不同前缀，避免混淆
     */
    private static final String CDC_IDEMPOTENT_KEY_PREFIX = "pulsar:cdc:processed:";

    /**
     * 消费线程池（单线程即可，因为 Key_Shared 模式下同一 key 的消息有序）
     */
    private ExecutorService consumerExecutor;

    /**
     * 初始化（与 SnapshotFlowPulsarConsumer 相同的生命周期模式）
     */
    @PostConstruct
    public void init() {
        consumerExecutor = Executors.newSingleThreadExecutor();
        startConsume();
        log.info("[Pulsar-CDC消费者] 初始化完成，开始消费 CDC 主题");
    }

    /**
     * 销毁
     */
    @PreDestroy
    public void destroy() {
        log.info("[Pulsar-CDC消费者] 正在关闭...");
        if (consumerExecutor != null) {
            consumerExecutor.shutdownNow();
        }
        try {
            if (debeziumReadonlyConsumer != null) {
                debeziumReadonlyConsumer.close();
                log.info("[Pulsar-CDC消费者] Consumer 已关闭");
            }
        } catch (Exception e) {
            log.error("[Pulsar-CDC消费者] 关闭异常", e);
        }
    }

    /**
     * 启动消费循环（CDC 专用）
     *
     * 设计思路：
     * 1. 使用 while(true) 循环不断 receive() 消息（与 Kafka 消费者等价）
     * 2. receive() 阻塞等待，收到消息后解析并处理
     * 3. CDC 场景额外需要检查 LSN / 事务 ID 的幂等性
     * 4. 处理成功：acknowledge 确认（异步 ack，提高吞吐）
     * 5. 处理失败：negativeAcknowledge 触发重投
     *
     * Pulsar Message 元数据：
     * - message.getKey(): dataId（消息 key，由 producer 设置）
     * - message.getValue(): JSON 字符串
     * - message.getMessageId(): MessageId（由 broker 分配的唯一标识）
     * - message.getEventTime(): 事件时间戳（可选，由 producer 设置）
     * - message.getProperties(): 附加属性（类似 Kafka header）
     */
    private void startConsume() {
        consumerExecutor.submit(() -> {
            log.info("[Pulsar-CDC消费者] CDC 消费循环已启动");

            while (!Thread.currentThread().isInterrupted()) {
                Message<String> msg = null;
                try {
                    // 阻塞接收消息（Pulsar 核心 API）
                    // 也可使用 receive(10, TimeUnit.SECONDS) 限时，防止无限阻塞
                    msg = debeziumReadonlyConsumer.receive();

                    if (msg == null) {
                        continue;
                    }

                    MessageId messageId = msg.getMessageId();
                    String dataId = msg.getKey();
                    String messageJson = msg.getValue();

                    log.debug("[Pulsar-CDC消费者] 收到消息: dataId={}, messageId={}", dataId, messageId);

                    // 处理消息（业务逻辑）
                    boolean success = processMessage(dataId, messageJson, messageId);

                    if (success) {
                        // 异步确认：不阻塞当前消费循环，提高吞吐
                        // 与 Kafka consumer.commitAsync() 等价
                        debeziumReadonlyConsumer.acknowledgeAsync(msg);

                        log.info("[Pulsar-CDC消费者] 消息处理成功（异步确认）: dataId={}", dataId);
                    } else {
                        // 业务处理失败：触发重投
                        // 负确认后，Broker 会立即重新投递该消息
                        debeziumReadonlyConsumer.negativeAcknowledge(msg);

                        log.warn("[Pulsar-CDC消费者] 消息处理失败，触发重投: dataId={}", dataId);
                    }

                } catch (Exception e) {
                    log.error("[Pulsar-CDC消费者] 消费异常", e);

                    if (msg != null) {
                        try {
                            debeziumReadonlyConsumer.negativeAcknowledge(msg);
                        } catch (Exception ackEx) {
                            log.error("[Pulsar-CDC消费者] 负确认异常", ackEx);
                        }
                    }

                    try {
                        TimeUnit.SECONDS.sleep(5);
                    } catch (InterruptedException ie2) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }

            log.info("[Pulsar-CDC消费者] 消费循环已退出");
        });
    }

    /**
     * 处理单条 CDC 消息（核心业务逻辑）
     *
     * 设计思路（与原 Kafka DebeziumReadonlyKafkaConsumer 等价）：
     * 1. 解析 JSON：{ operationType, data, source.lsn }
     * 2. LSN 幂等检查：基于 LSN + dataId 的组合 key
     * 3. 解析 data 为 OdsRtSzdnSnapshotFlowAddcode 对象
     * 4. 根据 operationType 分发到 INSERT / UPDATE / DELETE 处理
     *
     * 与主消费者的区别：
     * - 多了 source.lsn 字段的幂等检查（CDC 场景特有）
     * - 使用 Key_Shared 订阅模式保证同一 dataId 的消息按序处理
     * - 幂等性 Key 前缀不同，避免与主消费者冲突
     *
     * @param dataId     消息 key
     * @param messageJson 消息体
     * @param messageId   Pulsar messageId（用于日志）
     * @return true=成功；false=失败
     */
    private boolean processMessage(String dataId, String messageJson, MessageId messageId) {
        try {
            // 1. 解析消息 JSON
            JSONObject messageObj = JSONObject.parseObject(messageJson);
            if (messageObj == null) {
                log.error("[Pulsar-CDC消费者] 消息格式错误: messageJson={}", messageJson);
                return true;
            }

            String operationType = messageObj.getString("operationType");
            Object dataObj = messageObj.get("data");
            JSONObject sourceObj = messageObj.getJSONObject("source");

            if (operationType == null || dataObj == null) {
                log.error("[Pulsar-CDC消费者] 消息缺少必要字段: operationType={}, data={}",
                        operationType, dataObj);
                return true;
            }

            // 2. LSN 幂等检查（CDC 特有，基于 Redis SETNX）
            //    从 source 字段提取 lsn / xid / txId 等可用于去重的标识
            //    如果无 lsn，则退化为按 dataId 去重（与主消费者相同）
            String lsn = extractLsn(sourceObj, dataId);
            String idempotentKey = CDC_IDEMPOTENT_KEY_PREFIX + lsn;

            Boolean isNew = redisTemplate.opsForValue()
                    .setIfAbsent(idempotentKey, String.valueOf(System.currentTimeMillis()),
                            idempotentTtlSeconds, TimeUnit.SECONDS);

            if (isNew == null || !isNew) {
                log.info("[Pulsar-CDC消费者] LSN 消息已处理（幂等去重）: lsn={}, dataId={}",
                        lsn, dataId);
                return true;  // 已处理：直接确认，不重试
            }

            // 3. 解析 data 为业务对象
            OdsRtSzdnSnapshotFlowAddcode flowData = null;
            try {
                if (dataObj instanceof JSONObject) {
                    flowData = ((JSONObject) dataObj).toJavaObject(OdsRtSzdnSnapshotFlowAddcode.class);
                } else {
                    flowData = JSONObject.parseObject(dataObj.toString(),
                            OdsRtSzdnSnapshotFlowAddcode.class);
                }
            } catch (Exception parseEx) {
                log.error("[Pulsar-CDC消费者] data 解析失败: dataId={}", dataId, parseEx);
                return true;  // 解析失败：确认丢弃
            }

            if (flowData == null) {
                log.error("[Pulsar-CDC消费者] flowData 解析为 null: dataId={}", dataId);
                return true;
            }

            // 4. 分发操作类型
            switch (operationType.toUpperCase()) {
                case "INSERT":
                case "CREATE":  // Debezium 对 MySQL 的 CREATE 操作标识
                    return handleInsert(flowData, dataId);

                case "UPDATE":
                    return handleUpdate(flowData, dataId);

                case "DELETE":
                    return handleDelete(dataId);

                default:
                    log.warn("[Pulsar-CDC消费者] 未知操作类型: operationType={}, dataId={}",
                            operationType, dataId);
                    return true;
            }

        } catch (Exception e) {
            log.error("[Pulsar-CDC消费者] processMessage 异常: dataId={}", dataId, e);
            return false;
        }
    }

    /**
     * 从 source 对象中提取 LSN（Log Sequence Number）
     *
     * 思路：
     * 1. LSN 是数据库事务日志的序列号，每个变更事件都有唯一的 LSN
     * 2. Debezium 对不同数据库使用不同的字段名：
     *    - PostgreSQL/GaussDB: lsn
     *    - MySQL: file + pos 组合
     *    - SQL Server: change_lsn
     * 3. 如果没有 source 字段，则退化到 dataId 作为去重 key
     *
     * @param sourceObj source 元数据对象（可能为 null）
     * @param dataId    业务数据ID（兜底方案）
     * @return LSN 或 dataId
     */
    private String extractLsn(JSONObject sourceObj, String dataId) {
        if (sourceObj == null) {
            return dataId;  // 无 source：使用 dataId
        }

        // 常见字段名优先级（适配不同数据库的 Debezium 输出）
        String[] lsnFields = {"lsn", "xid", "txId", "txId", "pos", "change_lsn", "scn"};
        for (String field : lsnFields) {
            Object value = sourceObj.get(field);
            if (value != null && !value.toString().isEmpty()) {
                return value.toString();
            }
        }

        // 退化为 dataId
        return dataId;
    }

    /**
     * 处理 INSERT / CREATE：写入 MySQL + 写入 Elasticsearch
     *
     * 逻辑与 SnapshotFlowPulsarConsumer.handleInsert 相同
     * 使用相同的 IOdsRtSzdnSnapshotFlowAddcodeService 和 IEsService
     *
     * @param flowData 业务数据
     * @param dataId   数据ID
     * @return true=成功；false=失败
     */
    private boolean handleInsert(OdsRtSzdnSnapshotFlowAddcode flowData, String dataId) {
        try {
            // 写入 MySQL 分表（MyBatis-Plus 自动分表策略）
            boolean dbSuccess = snapshotFlowService.saveOrUpdate(flowData);
            if (!dbSuccess) {
                log.error("[Pulsar-CDC消费者] 写入 MySQL 失败: dataId={}", dataId);
                return false;
            }

            // 写入 Elasticsearch
            boolean esSuccess = esService.saveSnapshotFlow(flowData);
            if (!esSuccess) {
                log.error("[Pulsar-CDC消费者] 写入 Elasticsearch 失败: dataId={}", dataId);
                return false;
            }

            log.info("[Pulsar-CDC消费者] INSERT 操作成功: dataId={}", dataId);
            return true;

        } catch (Exception e) {
            log.error("[Pulsar-CDC消费者] handleInsert 异常: dataId={}", dataId, e);
            return false;
        }
    }

    /**
     * 处理 UPDATE
     */
    private boolean handleUpdate(OdsRtSzdnSnapshotFlowAddcode flowData, String dataId) {
        try {
            boolean dbSuccess = snapshotFlowService.updateById(flowData);
            if (!dbSuccess) {
                log.warn("[Pulsar-CDC消费者] UPDATE MySQL 失败（记录可能不存在）: dataId={}", dataId);
                dbSuccess = snapshotFlowService.saveOrUpdate(flowData);
                if (!dbSuccess) return false;
            }

            boolean esSuccess = esService.saveSnapshotFlow(flowData);
            if (!esSuccess) {
                log.error("[Pulsar-CDC消费者] UPDATE Elasticsearch 失败: dataId={}", dataId);
                return false;
            }

            log.info("[Pulsar-CDC消费者] UPDATE 操作成功: dataId={}", dataId);
            return true;

        } catch (Exception e) {
            log.error("[Pulsar-CDC消费者] handleUpdate 异常: dataId={}", dataId, e);
            return false;
        }
    }

    /**
     * 处理 DELETE
     */
    private boolean handleDelete(String dataId) {
        try {
            snapshotFlowService.removeById(dataId);
            esService.deleteSnapshotFlow(dataId);
            log.info("[Pulsar-CDC消费者] DELETE 操作完成: dataId={}", dataId);
            return true;

        } catch (Exception e) {
            log.error("[Pulsar-CDC消费者] handleDelete 异常: dataId={}", dataId, e);
            return false;
        }
    }
}
