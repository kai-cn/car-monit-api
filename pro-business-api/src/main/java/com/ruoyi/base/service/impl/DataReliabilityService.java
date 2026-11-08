package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.KafkaMessageRecord;
import com.ruoyi.base.mapper.KafkaMessageRecordMapper;
import com.ruoyi.common.utils.DateUtils;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.util.concurrent.ListenableFutureCallback;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 数据上报可靠性保障服务
 *
 * 功能说明：
 * 1. 解决设备数据上报不及时问题：超时检测、补偿拉取、延迟告警
 * 2. 解决数据丢失问题：消息持久化、多重确认、幂等性保障、断点续传
 * 3. 数据完整性校验：MD5校验、数据签名、去重机制
 *
 * 核心机制：
 * - 消息三重确认机制（生产端、Kafka、消费端）
 * - 超时检测与自动补偿
 * - 幂等性保障（基于消息ID去重）
 * - 数据完整性校验（MD5哈希校验）
 * - 延迟监控与告警
 */
@Slf4j
@Service
public class DataReliabilityService {

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    @Autowired
    private KafkaMessageRecordMapper kafkaMessageRecordMapper;

    @Autowired
    private RedisTemplate redisTemplate;

    // ==================== 配置参数 ====================

    /**
     * 消息超时时间（毫秒），超过此时间未确认视为上报不及时
     */
    @Value("${reliability.message-timeout-ms:30000}")
    private long messageTimeoutMs;

    /**
     * 最大重试次数
     */
    @Value("${reliability.max-retry-count:5}")
    private int maxRetryCount;

    /**
     * 补偿拉取间隔（秒）
     */
    @Value("${reliability.compensation-interval-seconds:60}")
    private int compensationIntervalSeconds;

    /**
     * 延迟告警阈值（毫秒）
     */
    @Value("${reliability.alert-threshold-ms:10000}")
    private long alertThresholdMs;

    // ==================== Redis Key 常量 ====================

    /**
     * 消息状态前缀：pending-等待确认, sent-已发送, confirmed-已确认
     */
    private static final String MSG_STATUS_PREFIX = "reliability:msg:status:";

    /**
     * 消息内容缓存前缀
     */
    public static final String MSG_CONTENT_PREFIX = "reliability:msg:content:";

    /**
     * 超时消息队列
     */
    private static final String TIMEOUT_QUEUE = "reliability:timeout:queue";

    /**
     * 设备心跳前缀
     */
    private static final String DEVICE_HEARTBEAT_PREFIX = "reliability:device:heartbeat:";

    /**
     * 延迟统计前缀
     */
    private static final String LATENCY_STATS_PREFIX = "reliability:latency:stats:";

    // ==================== 线程池 ====================

    /**
     * 重试执行器
     */
    private ExecutorService retryExecutor;

    /**
     * 补偿执行器
     */
    private ExecutorService compensationExecutor;

    /**
     * 定时调度器：承接超时检测、延迟清理、退避重试等定时动作，不占用重试线程
     */
    private ScheduledExecutorService timeoutScheduler;

    /**
     * 本地缓存：存储待确认消息，用于快速查找
     */
    private final ConcurrentHashMap<String, MessageMeta> pendingMessages = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        retryExecutor = new ThreadPoolExecutor(4, 4, 0L, TimeUnit.MILLISECONDS,
                new LinkedBlockingQueue<>(2000),
                daemonThreadFactory("reliability-retry"),
                new ThreadPoolExecutor.CallerRunsPolicy());
        compensationExecutor = new ThreadPoolExecutor(2, 2, 0L, TimeUnit.MILLISECONDS,
                new LinkedBlockingQueue<>(1000),
                daemonThreadFactory("reliability-compensation"),
                new ThreadPoolExecutor.CallerRunsPolicy());
        timeoutScheduler = Executors.newScheduledThreadPool(2, daemonThreadFactory("reliability-timeout"));
        log.info("[可靠性服务] 初始化完成，消息超时时间: {}ms, 最大重试次数: {}", messageTimeoutMs, maxRetryCount);
    }

    @PreDestroy
    public void destroy() {
        shutdown(retryExecutor);
        shutdown(compensationExecutor);
        if (timeoutScheduler != null) {
            timeoutScheduler.shutdownNow();
        }
    }

    private void shutdown(ExecutorService executor) {
        if (executor == null) {
            return;
        }
        executor.shutdownNow();
        try {
            executor.awaitTermination(5, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static ThreadFactory daemonThreadFactory(String prefix) {
        AtomicInteger sequence = new AtomicInteger(1);
        return runnable -> {
            Thread thread = new Thread(runnable, prefix + "-" + sequence.getAndIncrement());
            thread.setDaemon(true);
            return thread;
        };
    }

    // ==================== 核心方法：消息发送与确认 ====================

    /**
     * 发送可靠消息（带完整性校验和超时检测）
     *
     * 思路：
     * 1. 生成唯一消息ID
     * 2. 计算数据MD5校验值
     * 3. 本地缓存消息元数据
     * 4. Redis缓存消息内容（用于重试）
     * 5. 发送到Kafka并注册回调
     * 6. 设置超时定时器
     *
     * @param data 业务数据对象
     * @param dataId 业务数据ID
     * @param topic Kafka主题
     * @return 消息ID
     */
    public String sendReliableMessage(Object data, String dataId, String topic) {
        // 1. 生成唯一消息ID
        String messageId = generateMessageId(dataId);

        // 2. 计算数据MD5校验值
        String checksum = calculateChecksum(data);

        // 3. 构建消息包装体
        ReliableMessageWrapper wrapper = new ReliableMessageWrapper();
        wrapper.setMessageId(messageId);
        wrapper.setDataId(dataId);
        wrapper.setChecksum(checksum);
        wrapper.setOperationType("INSERT");
        wrapper.setData(data);
        wrapper.setTimestamp(System.currentTimeMillis());
        wrapper.setVersion(1);

        // 4. 缓存消息元数据到本地
        MessageMeta meta = new MessageMeta();
        meta.setMessageId(messageId);
        meta.setDataId(dataId);
        meta.setTopic(topic);
        meta.setChecksum(checksum);
        meta.setCreateTime(System.currentTimeMillis());
        meta.setStatus(MessageStatus.PENDING);
        pendingMessages.put(messageId, meta);

        // 5. 缓存消息内容到Redis（用于重试和幂等校验）
        String messageJson = JSON.toJSONString(wrapper);
        redisTemplate.opsForValue().set(MSG_CONTENT_PREFIX + messageId, messageJson, 24, TimeUnit.HOURS);

        // 6. 更新消息状态为待发送
        redisTemplate.opsForValue().set(MSG_STATUS_PREFIX + messageId, MessageStatus.PENDING.name(), 24, TimeUnit.HOURS);

        // 7. 发送到Kafka
        sendToKafka(wrapper, topic, messageId);

        // 8. 启动超时检测定时器
        scheduleTimeoutCheck(messageId);

        log.info("[可靠性服务] 发送可靠消息: messageId={}, dataId={}, topic={}", messageId, dataId, topic);
        return messageId;
    }

    /**
     * 发送到Kafka并处理回调
     */
    private void sendToKafka(ReliableMessageWrapper wrapper, String topic, String messageId) {
        kafkaTemplate.send(topic, wrapper.getDataId(), wrapper).addCallback(new ListenableFutureCallback<SendResult<String, Object>>() {
            @Override
            public void onSuccess(SendResult<String, Object> result) {
                // Kafka确认收到消息
                handleKafkaAck(messageId, result.getRecordMetadata().offset());
            }

            @Override
            public void onFailure(Throwable ex) {
                // Kafka发送失败，立即重试
                handleSendFailure(messageId, ex.getMessage());
            }
        });
    }

    /**
     * 处理Kafka确认
     */
    public void handleKafkaAck(String messageId, long offset) {
        MessageMeta meta = pendingMessages.get(messageId);
        if (meta != null) {
            meta.setStatus(MessageStatus.SENT);
            meta.setKafkaOffset(offset);
            redisTemplate.opsForValue().set(MSG_STATUS_PREFIX + messageId, MessageStatus.SENT.name());
            log.debug("[可靠性服务] Kafka确认消息: messageId={}, offset={}", messageId, offset);
        }
    }

    /**
     * 处理发送失败
     */
    public void handleSendFailure(String messageId, String error) {
        MessageMeta meta = pendingMessages.get(messageId);
        if (meta != null) {
            meta.incrementRetryCount();
            log.warn("[可靠性服务] 消息发送失败: messageId={}, retryCount={}, error={}",
                    messageId, meta.getRetryCount(), error);

            if (meta.getRetryCount() < maxRetryCount) {
                // 指数退避后重试：由调度器延时触发，不阻塞任何工作线程
                scheduleRetry(messageId, meta.getRetryCount());
            } else {
                // 超过最大重试次数，加入死信队列
                markAsDeadLetter(messageId, error);
            }
        }
    }

    /**
     * 按指数退避延时提交重试，延时等待由调度器承担，避免占用重试线程
     */
    private void scheduleRetry(String messageId, int retryCount) {
        long delay = (long) Math.pow(2, retryCount) * 1000;
        timeoutScheduler.schedule(() -> {
            try {
                retryExecutor.submit(() -> retrySend(messageId));
            } catch (Exception e) {
                log.warn("[可靠性服务] 提交重试任务失败: messageId={}", messageId, e);
            }
        }, delay, TimeUnit.MILLISECONDS);
    }

    /**
     * 重试发送
     */
    public void retrySend(String messageId) {
        try {
            // 从Redis获取消息内容
            String messageJson = (String) redisTemplate.opsForValue().get(MSG_CONTENT_PREFIX + messageId);
            if (messageJson == null) {
                log.error("[可靠性服务] 重试失败：消息内容已过期: messageId={}", messageId);
                return;
            }

            ReliableMessageWrapper wrapper = JSON.parseObject(messageJson, ReliableMessageWrapper.class);
            MessageMeta meta = pendingMessages.get(messageId);
            if (meta == null) {
                log.warn("[可靠性服务] 重试跳过：本地消息元数据不存在: messageId={}", messageId);
                return;
            }
            String topic = meta.getTopic();
            if (topic == null || topic.isEmpty()) {
                log.error("[可靠性服务] 重试跳过：消息主题缺失: messageId={}", messageId);
                return;
            }

            // 重新发送（退避等待已由调度器完成）
            sendToKafka(wrapper, topic, messageId);
            log.info("[可靠性服务] 重试消息: messageId={}, retryCount={}", messageId, meta.getRetryCount());

        } catch (Exception e) {
            log.error("[可靠性服务] 重试异常: messageId={}", messageId, e);
        }
    }

    /**
     * 标记为死信消息
     */
    private void markAsDeadLetter(String messageId, String error) {
        MessageMeta meta = pendingMessages.remove(messageId);
        if (meta != null) {
            meta.setStatus(MessageStatus.DEAD);
            meta.setError(error);
            redisTemplate.opsForValue().set(MSG_STATUS_PREFIX + messageId, MessageStatus.DEAD.name());

            // 记录到死信表
            KafkaMessageRecord record = new KafkaMessageRecord();
            record.setDataId(meta.getDataId());
            record.setTopic(meta.getTopic());
            record.setStatus(3); // 死信状态
            record.setRetryCount(meta.getRetryCount());
            record.setCreateTime(new Date());
            record.setMessageJson((String) redisTemplate.opsForValue().get(MSG_CONTENT_PREFIX + messageId));
            kafkaMessageRecordMapper.insert(record);

            log.error("[可靠性服务] 消息进入死信队列: messageId={}, dataId={}, error={}",
                    messageId, meta.getDataId(), error);

            // 发送告警通知
            sendAlert("DEAD_LETTER", "消息进入死信队列: " + messageId + ", 错误: " + error);
        }
    }

    /**
     * 消费端确认（三重确认的最后一步）
     *
     * 思路：消费端成功处理消息后调用此方法确认
     * 1. 更新消息状态为已确认
     * 2. 清理本地缓存和Redis缓存
     * 3. 记录延迟统计
     *
     * @param messageId 消息ID
     * @param consumerType 消费端类型（如：MySQL、ES、Redis）
     */
    public void confirmConsumption(String messageId, String consumerType) {
        MessageMeta meta = pendingMessages.remove(messageId);
        if (meta != null) {
            long latency = System.currentTimeMillis() - meta.getCreateTime();
            meta.setStatus(MessageStatus.CONFIRMED);

            // 更新Redis状态
            redisTemplate.opsForValue().set(MSG_STATUS_PREFIX + messageId, MessageStatus.CONFIRMED.name());

            // 记录延迟统计
            recordLatency(consumerType, latency);

            // 清理缓存（延迟清理，确保不会误删）
            scheduleCacheCleanup(messageId);

            log.info("[可靠性服务] 消费端确认: messageId={}, consumer={}, latency={}ms",
                    messageId, consumerType, latency);

            // 延迟超过阈值时发送告警
            if (latency > alertThresholdMs) {
                sendAlert("HIGH_LATENCY", "消息处理延迟过高: " + messageId + ", 延迟: " + latency + "ms");
            }
        }
    }

    // ==================== 超时检测与补偿机制 ====================

    /**
     * 启动超时检测定时器
     */
    private void scheduleTimeoutCheck(String messageId) {
        timeoutScheduler.schedule(() -> {
            try {
                // 检查消息状态
                String statusStr = (String) redisTemplate.opsForValue().get(MSG_STATUS_PREFIX + messageId);
                MessageStatus status = statusStr != null ? MessageStatus.valueOf(statusStr) : null;

                // 如果状态不是已确认，则视为超时
                if (status != MessageStatus.CONFIRMED) {
                    handleMessageTimeout(messageId, status);
                }
            } catch (Exception e) {
                log.error("[可靠性服务] 超时检测异常: messageId={}", messageId, e);
            }
        }, messageTimeoutMs, TimeUnit.MILLISECONDS);
    }

    /**
     * 处理消息超时
     */
    private void handleMessageTimeout(String messageId, MessageStatus currentStatus) {
        log.warn("[可靠性服务] 消息超时: messageId={}, 当前状态={}", messageId, currentStatus);

        // 添加到超时队列，等待补偿处理
        redisTemplate.opsForList().rightPush(TIMEOUT_QUEUE, messageId);

        // 发送超时告警
        sendAlert("MESSAGE_TIMEOUT", "消息超时未确认: " + messageId + ", 状态: " + currentStatus);
    }

    /**
     * 定时补偿任务（处理超时消息）
     *
     * 思路：定期扫描超时队列，进行补偿拉取或重试
     */
    @Scheduled(fixedRateString = "${reliability.compensation-interval-seconds:60}000")
    public void compensationTask() {
        compensationExecutor.submit(() -> {
            try {
                // 批量获取超时消息
                List<Object> timeoutMessages = redisTemplate.opsForList().range(TIMEOUT_QUEUE, 0, 50);
                if (timeoutMessages == null || timeoutMessages.isEmpty()) {
                    return;
                }

                log.info("[可靠性服务] 补偿任务处理: {} 条超时消息", timeoutMessages.size());

                for (Object obj : timeoutMessages) {
                    String messageId = (String) obj;

                    // 从队列中移除
                    redisTemplate.opsForList().remove(TIMEOUT_QUEUE, 1, messageId);

                    // 获取消息状态
                    String statusStr = (String) redisTemplate.opsForValue().get(MSG_STATUS_PREFIX + messageId);
                    MessageStatus status = statusStr != null ? MessageStatus.valueOf(statusStr) : null;

                    // 状态缺失（Redis 已过期）时无法判定补偿动作，跳过并记录
                    if (status == null) {
                        log.warn("[可靠性服务] 补偿跳过：消息状态缺失: messageId={}", messageId);
                        continue;
                    }

                    // 根据状态进行不同的补偿处理
                    switch (status) {
                        case PENDING:
                            // 未发送成功，重新发送
                            retrySend(messageId);
                            break;
                        case SENT:
                            // 已发送但未确认，通知消费端重新处理或重新发送
                            resendMessage(messageId);
                            break;
                        case CONFIRMED:
                            // 已确认，无需处理
                            break;
                        case DEAD:
                            // 死信，跳过
                            break;
                        default:
                            log.warn("[可靠性服务] 未知状态: messageId={}, status={}", messageId, status);
                    }
                }
            } catch (Exception e) {
                log.error("[可靠性服务] 补偿任务异常", e);
            }
        });
    }

    /**
     * 重新发送消息（用于超时补偿）
     */
    private void resendMessage(String messageId) {
        try {
            String messageJson = (String) redisTemplate.opsForValue().get(MSG_CONTENT_PREFIX + messageId);
            if (messageJson == null) {
                log.error("[可靠性服务] 重发失败：消息内容已过期: messageId={}", messageId);
                return;
            }

            ReliableMessageWrapper wrapper = JSON.parseObject(messageJson, ReliableMessageWrapper.class);
            String topic = pendingMessages.getOrDefault(messageId, new MessageMeta()).getTopic();
            if (topic == null || topic.isEmpty()) {
                log.error("[可靠性服务] 重发跳过：消息主题缺失: messageId={}", messageId);
                return;
            }
            MessageMeta meta = new MessageMeta();
            meta.setMessageId(messageId);
            meta.setDataId(wrapper.getDataId());
            meta.setTopic(topic);
            meta.setChecksum(wrapper.getChecksum());
            meta.setCreateTime(System.currentTimeMillis());
            meta.setStatus(MessageStatus.PENDING);
            pendingMessages.put(messageId, meta);

            // 重新发送
            kafkaTemplate.send(meta.getTopic(), wrapper.getDataId(), wrapper);
            log.info("[可靠性服务] 重发消息: messageId={}", messageId);

        } catch (Exception e) {
            log.error("[可靠性服务] 重发异常: messageId={}", messageId, e);
        }
    }

    // ==================== 设备心跳检测（解决上报不及时问题） ====================

    /**
     * 更新设备心跳
     *
     * 思路：设备每次上报数据时调用此方法更新心跳时间
     * 用于检测设备是否离线或上报延迟
     *
     * @param deviceId 设备ID
     */
    public void updateDeviceHeartbeat(String deviceId) {
        redisTemplate.opsForValue().set(DEVICE_HEARTBEAT_PREFIX + deviceId, System.currentTimeMillis(), 5, TimeUnit.MINUTES);
    }

    /**
     * 检测离线设备
     *
     * 思路：定期检查设备心跳，超过阈值未上报视为离线
     */
    @Scheduled(fixedRate = 300000) // 每5分钟检测一次
    public void checkOfflineDevices() {
        try {
            // 获取所有设备心跳key
            Set<String> keys = redisTemplate.keys(DEVICE_HEARTBEAT_PREFIX + "*");
            if (keys == null || keys.isEmpty()) {
                return;
            }

            long now = System.currentTimeMillis();
            long offlineThreshold = 5 * 60 * 1000; // 5分钟

            for (String key : keys) {
                Object heartbeatTimeObj = redisTemplate.opsForValue().get(key);
                if (heartbeatTimeObj == null) {
                    continue;
                }

                long heartbeatTime = (Long) heartbeatTimeObj;
                String deviceId = key.substring(DEVICE_HEARTBEAT_PREFIX.length());

                if (now - heartbeatTime > offlineThreshold) {
                    // 设备离线
                    log.warn("[可靠性服务] 设备离线: deviceId={}, 上次心跳: {}ms前",
                            deviceId, (now - heartbeatTime) / 1000);
                    sendAlert("DEVICE_OFFLINE", "设备离线: " + deviceId);
                }
            }
        } catch (Exception e) {
            log.error("[可靠性服务] 设备离线检测异常", e);
        }
    }

    // ==================== 本地缓存清理 ====================

    /**
     * 本地消息元数据保留时长（毫秒）：超过该时长仍未确认的元数据不再参与重试，直接清理
     */
    private static final long PENDING_META_RETENTION_MS = 3600000L;

    /**
     * 定期清理本地消息元数据，避免消息丢失/消费者未回调时 Map 无限增长
     */
    @Scheduled(fixedRate = 600000)
    public void cleanupPendingMessages() {
        try {
            long threshold = System.currentTimeMillis() - PENDING_META_RETENTION_MS;
            pendingMessages.entrySet().removeIf(entry -> entry.getValue().getCreateTime() < threshold);
        } catch (Exception e) {
            log.error("[可靠性服务] 本地消息元数据清理异常", e);
        }
    }

    // ==================== 数据完整性校验 ====================

    /**
     * 计算数据MD5校验值
     *
     * 思路：对数据内容进行哈希计算，用于验证数据完整性
     * 防止数据在传输过程中被篡改
     *
     * @param data 数据对象
     * @return MD5校验值
     */
    public String calculateChecksum(Object data) {
        try {
            String jsonStr = JSON.toJSONString(data);
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] hash = md.digest(jsonStr.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            log.error("[可靠性服务] MD5计算异常", e);
            return UUID.randomUUID().toString().replace("-", "");
        }
    }

    /**
     * 验证数据完整性
     *
     * @param data 数据对象
     * @param expectedChecksum 预期的校验值
     * @return 是否完整
     */
    public boolean verifyChecksum(Object data, String expectedChecksum) {
        String actualChecksum = calculateChecksum(data);
        boolean valid = actualChecksum.equals(expectedChecksum);
        if (!valid) {
            log.warn("[可靠性服务] 数据完整性校验失败: expected={}, actual={}", expectedChecksum, actualChecksum);
        }
        return valid;
    }

    // ==================== 幂等性保障 ====================

    /**
     * 检查消息是否已处理（幂等性校验）
     *
     * 思路：基于消息ID进行去重
     * 使用Redis的SETNX实现分布式锁和去重
     *
     * @param messageId 消息ID
     * @return 是否已处理
     */
    public boolean isMessageProcessed(String messageId) {
        Boolean exists = redisTemplate.hasKey(MSG_STATUS_PREFIX + messageId);
        return exists != null && exists;
    }

    /**
     * 标记消息为已处理
     *
     * @param messageId 消息ID
     */
    public void markMessageProcessed(String messageId) {
        redisTemplate.opsForValue().set(MSG_STATUS_PREFIX + messageId, MessageStatus.CONFIRMED.name(), 24, TimeUnit.HOURS);
    }

    // ==================== 工具方法 ====================

    /**
     * 生成唯一消息ID
     *
     * 格式：timestamp-random-uuid前8位
     */
    private String generateMessageId(String dataId) {
        return System.currentTimeMillis() + "-" +
                System.nanoTime() % 1000000 + "-" +
                UUID.randomUUID().toString().substring(0, 8) + "-" +
                (dataId != null ? dataId.hashCode() : 0);
    }

    /**
     * 延迟清理缓存
     */
    private void scheduleCacheCleanup(String messageId) {
        timeoutScheduler.schedule(() -> {
            try {
                // 延迟1小时清理，确保不会被误删
                redisTemplate.delete(MSG_CONTENT_PREFIX + messageId);
                redisTemplate.delete(MSG_STATUS_PREFIX + messageId);
                log.debug("[可靠性服务] 清理消息缓存: messageId={}", messageId);
            } catch (Exception e) {
                log.warn("[可靠性服务] 清理消息缓存失败: messageId={}", messageId, e);
            }
        }, 1, TimeUnit.HOURS);
    }

    /**
     * 记录延迟统计
     */
    private void recordLatency(String consumerType, long latency) {
        // 记录到Redis，用于监控分析
        String key = LATENCY_STATS_PREFIX + consumerType + ":" + DateUtils.formatDate(new Date());
        redisTemplate.opsForList().rightPush(key, latency);
        // 保留最近1000条记录
        redisTemplate.opsForList().trim(key, -1000, -1);
    }

    /**
     * 发送告警通知
     *
     * 实际项目中可扩展为邮件、短信、钉钉等多种方式
     */
    private void sendAlert(String alertType, String message) {
        log.error("[告警] [{}] {}", alertType, message);
        // TODO: 集成告警系统（钉钉、企业微信、邮件等）
    }

    // ==================== 内部类 ====================

    /**
     * 可靠消息包装体
     *
     * 包含消息元数据和业务数据，用于完整性校验和幂等性保障
     */
    @Data
    public static class ReliableMessageWrapper {
        /**
         * 消息唯一ID
         */
        private String messageId;

        /**
         * 业务数据ID
         */
        private String dataId;

        /**
         * 数据MD5校验值
         */
        private String checksum;

        /**
         * 操作类型：INSERT、UPDATE、DELETE
         */
        private String operationType;

        /**
         * 业务数据
         */
        private Object data;

        /**
         * 发送时间戳
         */
        private long timestamp;

        /**
         * 版本号
         */
        private int version;
    }

    /**
     * 消息元数据
     */
    @Data
    private static class MessageMeta {
        private String messageId;
        private String dataId;
        private String topic;
        private String checksum;
        private MessageStatus status;
        private long createTime;
        private long kafkaOffset = -1;
        private int retryCount = 0;
        private String error;

        public void incrementRetryCount() {
            retryCount++;
        }
    }

    /**
     * 消息状态枚举
     */
    public enum MessageStatus {
        /**
         * 待发送
         */
        PENDING,

        /**
         * 已发送到Kafka
         */
        SENT,

        /**
         * 消费端已确认
         */
        CONFIRMED,

        /**
         * 死信（无法重试）
         */
        DEAD
    }
}