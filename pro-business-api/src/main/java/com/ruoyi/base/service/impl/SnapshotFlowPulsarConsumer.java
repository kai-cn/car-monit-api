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
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.Date;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 门架抓拍流水 Pulsar 消费者服务
 *
 * 功能说明（与原 SnapshotFlowKafkaConsumerV2 等价替换）：
 * - 消费 ods-rt-szdn-snapshot-flow 主题的 JSON 消息
 * - 将数据写入 MySQL 分表（ods_rt_szdn_snapshot_flow_addcode）
 * - 将数据同步写入 Elasticsearch（多字段模糊查询）
 * - 提供幂等性保证（基于 dataId + Redis SETNX）
 *
 * 消息格式（与生产者约定，必须一致）：
 *   {
 *     "operationType": "INSERT",        // 操作类型：INSERT / UPDATE / DELETE
 *     "data": { ... }                   // OdsRtSzdnSnapshotFlowAddcode 对象 JSON
 *   }
 *
 * Pulsar 消费者模型说明（与 Kafka 的关键区别）：
 * -----------------------------------------------------------------------------
 * Kafka 机制                Pulsar 机制
 * -----------------------------------------------------------------------------
 * ConsumerRecords<>         Message<String> 流
 * record.offset()           message.getMessageId()
 * consumer.commitSync()     consumer.acknowledge(message)
 * consumer.seek(offset)     consumer.seek(messageId) / consumer.seekByTime()
 * @KafkaListener            while(true) { consumer.receive() } 或 MessageListener
 * -----------------------------------------------------------------------------
 *
 * 可靠性保证：
 * 1. 手动确认（acknowledge）：业务处理完成后才确认消息
 * 2. 消息重投（negativeAcknowledge）：业务处理失败时触发重投
 * 3. 死信队列（DLQ）：超过 max-retry-times 次的消息自动路由到 DLQ
 * 4. 业务幂等：Redis SETNX 记录 dataId，避免重复处理
 */
@Slf4j
//@Service
public class SnapshotFlowPulsarConsumer {

    /**
     * 注入 Pulsar 字符串消息消费者
     * 由 PulsarConsumerConfig 中 snapshotFlowConsumer() 方法创建
     * 与原 Kafka @KafkaListener 的功能等价，但更灵活的底层 API
     */
    @Autowired
    private Consumer<String> snapshotFlowConsumer;

    /**
     * 业务服务：写入 MySQL 分表
     * 与原 Kafka 消费者使用同一个 service，保证业务逻辑一致性
     */
    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowService;

    /**
     * 业务服务：写入 Elasticsearch
     * 与原 Kafka 消费者使用同一个 ES 服务
     */
    @Autowired
    private IEsService esService;

    /**
     * 注入 Redis 辅助工具（用于幂等性保证）
     * 与原 Kafka 版使用的 RedisHelper 相同
     */
    @Autowired
    private org.springframework.data.redis.core.StringRedisTemplate redisTemplate;

    /**
     * 幂等性过期时间（秒）
     * 与原 Kafka ${kafka.idempotent-ttl-seconds:86400} 对应
     * 默认 1 天：在此时间内重复的 dataId 会被忽略
     */
    @Value("${spring.pulsar.idempotent-ttl-seconds:86400}")
    private long idempotentTtlSeconds;

    /**
     * Redis 幂等性 Key 前缀
     * 与原 Kafka "kafka:msg:processed:" 前缀保持相同设计思路
     */
    private static final String IDEMPOTENT_KEY_PREFIX = "pulsar:msg:processed:";

    /**
     * 消费线程池
     * 与原 Kafka consumerExecutor 的作用相同：后台循环 receive()
     */
    private ExecutorService consumerExecutor;

    /**
     * 初始化消费者（Spring Bean 初始化后启动）
     *
     * 思路：
     * 1. 创建一个单线程线程池
     * 2. 调用 startConsume() 启动消费循环
     * 3. 与原 Kafka @PostConstruct 行为保持一致
     *
     * 与原 Kafka 的区别：
     * - Kafka: @KafkaListener 注解由 Spring 自动管理
     * - Pulsar: 手动启动 while(true) 循环，更可控
     */
    @PostConstruct
    public void init() {
        consumerExecutor = Executors.newSingleThreadExecutor();
        startConsume();
        log.info("[Pulsar快照消费者] 初始化完成，开始消费主题");
    }

    /**
     * 销毁消费者（Spring 容器关闭前）
     *
     * 思路：
     * 1. 关闭消费线程池
     * 2. 关闭 Pulsar Consumer（释放与 Broker 的连接）
     */
    @PreDestroy
    public void destroy() {
        log.info("[Pulsar快照消费者] 正在关闭...");
        if (consumerExecutor != null) {
            consumerExecutor.shutdownNow();
        }
        try {
            if (snapshotFlowConsumer != null) {
                snapshotFlowConsumer.close();
                log.info("[Pulsar快照消费者] Consumer 已关闭");
            }
        } catch (Exception e) {
            log.error("[Pulsar快照消费者] 关闭异常", e);
        }
    }

    /**
     * 启动消费循环（与原 Kafka @KafkaListener 等价）
     *
     * 思路：
     * 1. 使用 consumerExecutor.submit() 提交一个后台循环任务
     * 2. while(true) 循环中调用 consumer.receive() 阻塞获取消息
     * 3. 收到消息后：
     *    - 解析 JSON，提取 operationType 和 data
     *    - 检查幂等性（Redis SETNX）
     *    - 调用 processMessage() 处理业务
     *    - 成功：consumer.acknowledge(msg) 确认
     *    - 失败：consumer.negativeAcknowledge(msg) 触发重投
     * 4. 捕获异常：避免单条消息处理失败导致整个循环退出
     *
     * Pulsar consumer.receive() 说明：
     * - 默认无限阻塞等待下一条消息
     * - 返回 Message<String>：包含消息 key、value、messageId、properties 等
     * - 与 Kafka consumer.poll(Duration) 逻辑类似，但更简单直接
     */
    private void startConsume() {
        consumerExecutor.submit(() -> {
            log.info("[Pulsar快照消费者] 消费循环已启动");

            while (!Thread.currentThread().isInterrupted()) {
                Message<String> msg = null;
                try {
                    // 阻塞接收下一条消息（等效于 Kafka consumer.poll()）
                    // receive() 会一直阻塞直到有新消息或连接断开
                    // 也可使用 receive(5, TimeUnit.SECONDS) 限时版本，避免无限阻塞
                    msg = snapshotFlowConsumer.receive();

                    if (msg == null) {
                        continue;
                    }

                    // 提取消息元数据
                    MessageId messageId = msg.getMessageId();
                    String dataId = msg.getKey();        // 与 producer.newMessage().key() 对应
                    String messageJson = msg.getValue();  // JSON 字符串消息体

                    // 处理消息（@Async 异步执行，不阻塞消费循环）
                    // 注意：异步模式下，消息确认需要在业务处理成功后手动执行
                    // 这里采用同步处理 + 明确确认的方式，与原 Kafka 版一致
                    boolean success = processMessage(dataId, messageJson);

                    if (success) {
                        // 业务处理成功：手动确认消息
                        // 与 Kafka consumer.commitSync() 等价
                        snapshotFlowConsumer.acknowledge(msg);

                        log.info("[Pulsar快照消费者] 消息处理成功并确认: dataId={}, messageId={}",
                                dataId, messageId);
                    } else {
                        // 业务处理失败（如数据库/ES 不可用）：触发重投
                        // 与 Kafka consumer.seek() 或不 commit offset 等价
                        snapshotFlowConsumer.negativeAcknowledge(msg);

                        log.warn("[Pulsar快照消费者] 消息处理失败，触发重投: dataId={}", dataId);
                    }

                } catch (Exception e) {
                    // 其他异常：记录日志，继续下一条（避免死循环）
                    log.error("[Pulsar快照消费者] 消费异常，跳过当前消息", e);

                    // 如果消息存在且未确认，触发负确认让 Broker 重投
                    if (msg != null) {
                        try {
                            snapshotFlowConsumer.negativeAcknowledge(msg);
                        } catch (Exception ackEx) {
                            log.error("[Pulsar快照消费者] 负确认异常", ackEx);
                        }
                    }

                    // 短暂休眠，避免异常时 CPU 跑满
                    try {
                        TimeUnit.SECONDS.sleep(5);
                    } catch (InterruptedException ie2) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }

            log.info("[Pulsar快照消费者] 消费循环已退出");
        });
    }

    /**
     * 处理单条消息（核心业务逻辑）
     *
     * 思路（与原 Kafka 消费者完全一致）：
     * 1. 解析 JSON：{ operationType, data }
     * 2. 幂等性检查：Redis SETNX 标记 dataId
     * 3. 解析 data 为 OdsRtSzdnSnapshotFlowAddcode 对象
     * 4. 根据 operationType 执行对应的操作：
     *    - INSERT：写入 MySQL 分表 + 写入 Elasticsearch
     *    - UPDATE：更新 MySQL + 更新 Elasticsearch（按 dataId）
     *    - DELETE：删除 MySQL 记录 + 删除 Elasticsearch 文档
     *
     * @param dataId     消息 key（业务数据ID）
     * @param messageJson 消息体（JSON 字符串）
     * @return true=处理成功；false=处理失败（触发重投）
     */
    private boolean processMessage(String dataId, String messageJson) {
        long startTime = System.currentTimeMillis();

        try {
            // 1. 解析消息 JSON
            // 格式校验：必须包含 operationType 和 data 两个字段
            JSONObject messageObj = JSONObject.parseObject(messageJson);
            if (messageObj == null) {
                log.error("[Pulsar快照消费者] 消息格式错误: messageJson={}", messageJson);
                return true;  // 格式错误的消息：直接确认丢弃，不重试
            }

            String operationType = messageObj.getString("operationType");
            Object dataObj = messageObj.get("data");

            if (operationType == null || dataObj == null) {
                log.error("[Pulsar快照消费者] 消息缺少必要字段: operationType={}, data={}",
                        operationType, dataObj);
                return true;  // 缺失字段：确认丢弃，不重试
            }

            // 2. 幂等性检查（Redis SETNX）
            // 设计：key = pulsar:msg:processed:{dataId}，值=时间戳
            // - 如果 SETNX 返回 true：首次处理，执行业务
            // - 如果 SETNX 返回 false：重复消息，直接确认跳过
            // 与原 Kafka ${kafka.idempotent-ttl-seconds} 机制一致
            String idempotentKey = IDEMPOTENT_KEY_PREFIX + dataId;
            Boolean isNew = redisTemplate.opsForValue()
                    .setIfAbsent(idempotentKey, String.valueOf(System.currentTimeMillis()),
                            idempotentTtlSeconds, TimeUnit.SECONDS);

            if (isNew == null || !isNew) {
                log.info("[Pulsar快照消费者] 消息已处理（幂等去重）: dataId={}", dataId);
                return true;  // 已处理过：确认跳过，不重试
            }

            // 3. 解析 data 为业务实体对象
            // 使用 FastJSON 解析为 OdsRtSzdnSnapshotFlowAddcode 对象
            OdsRtSzdnSnapshotFlowAddcode flowData = null;
            try {
                if (dataObj instanceof JSONObject) {
                    flowData = ((JSONObject) dataObj).toJavaObject(OdsRtSzdnSnapshotFlowAddcode.class);
                } else {
                    flowData = JSONObject.parseObject(dataObj.toString(),
                            OdsRtSzdnSnapshotFlowAddcode.class);
                }
            } catch (Exception parseEx) {
                log.error("[Pulsar快照消费者] data 字段解析失败: dataId={}", dataId, parseEx);
                return true;  // 解析失败：确认丢弃，避免重试死循环
            }

            if (flowData == null) {
                log.error("[Pulsar快照消费者] flowData 解析为 null: dataId={}", dataId);
                return true;
            }

            // 4. 执行操作（与原 Kafka processMessage 逻辑一致）
            //    根据 operationType 分发到不同的处理路径
            switch (operationType.toUpperCase()) {
                case "INSERT":
                    return handleInsert(flowData, dataId);

                case "UPDATE":
                    return handleUpdate(flowData, dataId);

                case "DELETE":
                    return handleDelete(dataId);

                default:
                    log.warn("[Pulsar快照消费者] 未知操作类型: operationType={}, dataId={}",
                            operationType, dataId);
                    return true;  // 未知类型：确认丢弃，不重试
            }

        } catch (Exception e) {
            log.error("[Pulsar快照消费者] processMessage 异常: dataId={}", dataId, e);
            return false;  // 异常：返回 false，触发重投
        }
    }

    /**
     * 处理 INSERT 操作：写入 MySQL 分表 + 写入 Elasticsearch
     *
     * 思路（与原 Kafka handleInsert 等价）：
     * 1. 调用 snapshotFlowService.saveOrUpdate() 写入 MySQL 分表
     *    - MyBatis-Plus 自动按日期分表策略
     *    - 如果存在则更新，不存在则插入（保证幂等）
     * 2. 调用 esService.saveSnapshotFlow() 同步写入 Elasticsearch
     *    - ES 使用 dataId 作为文档 ID，天然幂等
     * 3. 两个步骤均成功才返回 true
     *
     * @param flowData 业务数据实体
     * @param dataId   业务数据ID（消息 key）
     * @return true=成功；false=失败（触发重投）
     */
    private boolean handleInsert(OdsRtSzdnSnapshotFlowAddcode flowData, String dataId) {
        try {
            // 1. 写入 MySQL 分表（与原 Kafka 逻辑相同）
            boolean dbSuccess = snapshotFlowService.saveOrUpdate(flowData);

            if (!dbSuccess) {
                log.error("[Pulsar快照消费者] 写入 MySQL 失败: dataId={}", dataId);
                return false;  // 返回 false，触发消息重投
            }

            // 2. 写入 Elasticsearch（与原 Kafka 逻辑相同）
            //    ES 的 saveSnapshotFlow 方法内部会捕获异常并返回 true/false
            //    即使 ES 暂时不可用，消息也会被重投，保证最终一致性
            boolean esSuccess = esService.saveSnapshotFlow(flowData);

            if (!esSuccess) {
                log.error("[Pulsar快照消费者] 写入 Elasticsearch 失败: dataId={}", dataId);
                return false;  // ES 失败：返回 false，触发重投
            }

            log.info("[Pulsar快照消费者] INSERT 操作成功: dataId={}", dataId);
            return true;

        } catch (Exception e) {
            log.error("[Pulsar快照消费者] handleInsert 异常: dataId={}", dataId, e);
            return false;
        }
    }

    /**
     * 处理 UPDATE 操作：更新 MySQL + 更新 Elasticsearch
     *
     * 思路（与原 Kafka handleUpdate 等价）：
     * 1. 更新 MySQL 分表（按 dataId 更新）
     * 2. 更新 Elasticsearch 文档（按 dataId 作为文档 ID）
     *
     * @param flowData 业务数据实体（已包含更新后的值）
     * @param dataId   业务数据ID
     * @return true=成功；false=失败
     */
    private boolean handleUpdate(OdsRtSzdnSnapshotFlowAddcode flowData, String dataId) {
        try {
            // 1. 更新 MySQL
            boolean dbSuccess = snapshotFlowService.updateById(flowData);

            if (!dbSuccess) {
                log.warn("[Pulsar快照消费者] UPDATE MySQL 失败（记录可能不存在）: dataId={}", dataId);
                // 记录不存在时：转为 INSERT，避免丢失更新
                dbSuccess = snapshotFlowService.saveOrUpdate(flowData);
                if (!dbSuccess) {
                    return false;
                }
            }

            // 2. 更新 Elasticsearch
            boolean esSuccess = esService.saveSnapshotFlow(flowData);

            if (!esSuccess) {
                log.error("[Pulsar快照消费者] UPDATE Elasticsearch 失败: dataId={}", dataId);
                return false;
            }

            log.info("[Pulsar快照消费者] UPDATE 操作成功: dataId={}", dataId);
            return true;

        } catch (Exception e) {
            log.error("[Pulsar快照消费者] handleUpdate 异常: dataId={}", dataId, e);
            return false;
        }
    }

    /**
     * 处理 DELETE 操作：删除 MySQL 记录 + 删除 Elasticsearch 文档
     *
     * @param dataId 业务数据ID
     * @return true=成功；false=失败
     */
    private boolean handleDelete(String dataId) {
        try {
            // 1. 从 MySQL 删除
            boolean dbSuccess = snapshotFlowService.removeById(dataId);
            if (!dbSuccess) {
                log.warn("[Pulsar快照消费者] DELETE MySQL 失败（记录可能不存在）: dataId={}", dataId);
            }

            // 2. 从 Elasticsearch 删除
            boolean esSuccess = esService.deleteSnapshotFlow(dataId);
            if (!esSuccess) {
                log.warn("[Pulsar快照消费者] DELETE Elasticsearch 失败（文档可能不存在）: dataId={}", dataId);
            }

            log.info("[Pulsar快照消费者] DELETE 操作完成: dataId={}", dataId);
            return true;  // 即使两边都不存在也视为成功（幂等）

        } catch (Exception e) {
            log.error("[Pulsar快照消费者] handleDelete 异常: dataId={}", dataId, e);
            return false;
        }
    }
}
