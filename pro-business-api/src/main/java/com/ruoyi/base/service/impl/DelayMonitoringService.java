package com.ruoyi.base.service.impl;

import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 延迟监控服务
 *
 * 功能说明：
 * 1. 监控设备数据上报延迟
 * 2. 监控消息处理延迟（生产到消费的端到端延迟）
 * 3. 监控数据库写入延迟
 * 4. 生成延迟统计报告
 * 5. 超过阈值时发送告警
 *
 * 监控维度：
 * - 设备上报延迟（设备采集时间到服务接收时间）
 * - 消息传输延迟（生产到Kafka到消费）
 * - 数据处理延迟（消费到写入数据库）
 * - 端到端延迟（设备采集到最终存储）
 */
@Slf4j
@Service
public class DelayMonitoringService {

    @Autowired
    private RedisTemplate redisTemplate;

    // ==================== 配置参数 ====================

    /**
     * 设备上报延迟告警阈值（毫秒）
     */
    @Value("${monitoring.device-report-threshold-ms:5000}")
    private long deviceReportThresholdMs;

    /**
     * 消息传输延迟告警阈值（毫秒）
     */
    @Value("${monitoring.message-transfer-threshold-ms:3000}")
    private long messageTransferThresholdMs;

    /**
     * 数据处理延迟告警阈值（毫秒）
     */
    @Value("${monitoring.data-process-threshold-ms:10000}")
    private long dataProcessThresholdMs;

    /**
     * 端到端延迟告警阈值（毫秒）
     */
    @Value("${monitoring.end-to-end-threshold-ms:30000}")
    private long endToEndThresholdMs;

    /**
     * 统计窗口大小（分钟）
     */
    @Value("${monitoring.stats-window-minutes:10}")
    private int statsWindowMinutes;

    // ==================== Redis Key 常量 ====================

    /**
     * 设备上报延迟记录前缀
     */
    private static final String DEVICE_DELAY_PREFIX = "monitoring:delay:device:";

    /**
     * 消息传输延迟记录前缀
     */
    private static final String MESSAGE_DELAY_PREFIX = "monitoring:delay:message:";

    /**
     * 数据处理延迟记录前缀
     */
    private static final String PROCESS_DELAY_PREFIX = "monitoring:delay:process:";

    /**
     * 端到端延迟记录前缀
     */
    private static final String E2E_DELAY_PREFIX = "monitoring:delay:e2e:";

    /**
     * 延迟告警计数前缀
     */
    private static final String ALERT_COUNT_PREFIX = "monitoring:alert:count:";

    // ==================== 本地缓存 ====================

    /**
     * 存储消息生产时间（用于计算传输延迟）
     */
    private final ConcurrentHashMap<String, Long> messageProduceTimes = new ConcurrentHashMap<>();

    /**
     * 存储消息消费时间（用于计算处理延迟）
     */
    private final ConcurrentHashMap<String, Long> messageConsumeTimes = new ConcurrentHashMap<>();

    /**
     * 存储设备采集时间（用于计算上报延迟）
     */
    private final ConcurrentHashMap<String, Long> deviceCaptureTimes = new ConcurrentHashMap<>();

    // ==================== 线程池 ====================

    private ExecutorService statsExecutor;

    @PostConstruct
    public void init() {
        statsExecutor = Executors.newFixedThreadPool(2);
        log.info("[延迟监控] 初始化完成，设备上报阈值: {}ms, 消息传输阈值: {}ms, 数据处理阈值: {}ms, 端到端阈值: {}ms",
                deviceReportThresholdMs, messageTransferThresholdMs,
                dataProcessThresholdMs, endToEndThresholdMs);
    }

    // ==================== 设备上报延迟监控 ====================

    /**
     * 记录设备采集时间
     *
     * 思路：设备采集数据时记录时间戳
     *
     * @param dataId 数据ID
     * @param captureTime 设备采集时间戳
     */
    public void recordDeviceCaptureTime(String dataId, long captureTime) {
        deviceCaptureTimes.put(dataId, captureTime);
    }

    /**
     * 记录服务接收时间并计算上报延迟
     *
     * 思路：服务接收到设备数据时记录时间，计算与采集时间的差值
     *
     * @param dataId 数据ID
     * @param deviceId 设备ID
     */
    public long recordServiceReceiveTime(String dataId, String deviceId) {
        Long captureTime = deviceCaptureTimes.remove(dataId);
        long receiveTime = System.currentTimeMillis();

        if (captureTime != null) {
            long delay = receiveTime - captureTime;

            // 记录到Redis
            String key = DEVICE_DELAY_PREFIX + deviceId + ":" + formatDate(new Date());
            redisTemplate.opsForList().rightPush(key, delay);
            redisTemplate.expire(key, 2, TimeUnit.DAYS);

            // 检查是否超过阈值
            if (delay > deviceReportThresholdMs) {
                triggerAlert("DEVICE_REPORT_DELAY", deviceId, delay, deviceReportThresholdMs);
            }

            log.debug("[延迟监控] 设备上报延迟: deviceId={}, dataId={}, delay={}ms", deviceId, dataId, delay);
            return delay;
        }

        return -1;
    }

    // ==================== 消息传输延迟监控 ====================

    /**
     * 记录消息生产时间
     *
     * @param messageId 消息ID
     */
    public void recordMessageProduceTime(String messageId) {
        messageProduceTimes.put(messageId, System.currentTimeMillis());
    }

    /**
     * 记录消息消费时间并计算传输延迟
     *
     * 思路：消费端接收到消息时记录时间，计算与生产时间的差值
     *
     * @param messageId 消息ID
     */
    public long recordMessageConsumeTime(String messageId) {
        Long produceTime = messageProduceTimes.remove(messageId);
        long consumeTime = System.currentTimeMillis();

        if (produceTime != null) {
            long delay = consumeTime - produceTime;

            // 记录到Redis
            String key = MESSAGE_DELAY_PREFIX + formatDate(new Date());
            redisTemplate.opsForList().rightPush(key, delay);
            redisTemplate.expire(key, 2, TimeUnit.DAYS);

            // 检查是否超过阈值
            if (delay > messageTransferThresholdMs) {
                triggerAlert("MESSAGE_TRANSFER_DELAY", messageId, delay, messageTransferThresholdMs);
            }

            log.debug("[延迟监控] 消息传输延迟: messageId={}, delay={}ms", messageId, delay);
            return delay;
        }

        return -1;
    }

    // ==================== 数据处理延迟监控 ====================

    /**
     * 记录消息消费开始时间
     *
     * @param messageId 消息ID
     */
    public void recordProcessStartTime(String messageId) {
        messageConsumeTimes.put(messageId, System.currentTimeMillis());
    }

    /**
     * 记录数据写入完成时间并计算处理延迟
     *
     * 思路：数据写入数据库完成时记录时间，计算与消费开始时间的差值
     *
     * @param messageId 消息ID
     */
    public long recordProcessEndTime(String messageId) {
        Long consumeTime = messageConsumeTimes.remove(messageId);
        long endTime = System.currentTimeMillis();

        if (consumeTime != null) {
            long delay = endTime - consumeTime;

            // 记录到Redis
            String key = PROCESS_DELAY_PREFIX + formatDate(new Date());
            redisTemplate.opsForList().rightPush(key, delay);
            redisTemplate.expire(key, 2, TimeUnit.DAYS);

            // 检查是否超过阈值
            if (delay > dataProcessThresholdMs) {
                triggerAlert("DATA_PROCESS_DELAY", messageId, delay, dataProcessThresholdMs);
            }

            log.debug("[延迟监控] 数据处理延迟: messageId={}, delay={}ms", messageId, delay);
            return delay;
        }

        return -1;
    }

    // ==================== 端到端延迟监控 ====================

    /**
     * 计算端到端延迟
     *
     * 思路：从设备采集到最终存储的完整延迟
     *
     * @param dataId 数据ID
     * @param captureTime 设备采集时间
     * @param storageTime 存储完成时间
     * @param deviceId 设备ID
     */
    public long calculateEndToEndDelay(String dataId, long captureTime, long storageTime, String deviceId) {
        long delay = storageTime - captureTime;

        // 记录到Redis
        String key = E2E_DELAY_PREFIX + deviceId + ":" + formatDate(new Date());
        redisTemplate.opsForList().rightPush(key, delay);
        redisTemplate.expire(key, 2, TimeUnit.DAYS);

        // 检查是否超过阈值
        if (delay > endToEndThresholdMs) {
            triggerAlert("END_TO_END_DELAY", deviceId, delay, endToEndThresholdMs);
        }

        log.debug("[延迟监控] 端到端延迟: deviceId={}, dataId={}, delay={}ms", deviceId, dataId, delay);
        return delay;
    }

    // ==================== 告警触发 ====================

    /**
     * 触发告警
     *
     * 思路：检查告警频率，避免频繁告警
     *
     * @param alertType 告警类型
     * @param targetId 目标ID（设备ID或消息ID）
     * @param actualDelay 实际延迟
     * @param threshold 阈值
     */
    private void triggerAlert(String alertType, String targetId, long actualDelay, long threshold) {
        // 检查告警频率（每分钟最多告警1次）
        String alertKey = ALERT_COUNT_PREFIX + alertType + ":" + targetId;
        Object lastAlertObj = redisTemplate.opsForValue().get(alertKey);

        if (lastAlertObj != null) {
            long lastAlertTime = (Long) lastAlertObj;
            if (System.currentTimeMillis() - lastAlertTime < 60000) {
                // 1分钟内已告警过，跳过
                return;
            }
        }

        // 更新告警时间
        redisTemplate.opsForValue().set(alertKey, System.currentTimeMillis(), 1, TimeUnit.MINUTES);

        // 发送告警
        String alertMessage = String.format("[%s] 延迟超过阈值！目标: %s, 实际延迟: %dms, 阈值: %dms",
                alertType, targetId, actualDelay, threshold);

        log.error("[延迟监控告警] {}", alertMessage);
        // TODO: 集成告警系统
    }

    // ==================== 统计报告 ====================

    /**
     * 定时生成统计报告
     */
    @Scheduled(fixedRate = 600000) // 每10分钟
    public void generateStatsReport() {
        statsExecutor.submit(() -> {
            try {
                DelayStats stats = calculateStats();
                log.info("[延迟监控统计] 设备上报: avg={}ms, max={}ms | 消息传输: avg={}ms, max={}ms | " +
                                "数据处理: avg={}ms, max={}ms | 端到端: avg={}ms, max={}ms",
                        stats.getDeviceReportAvg(), stats.getDeviceReportMax(),
                        stats.getMessageTransferAvg(), stats.getMessageTransferMax(),
                        stats.getDataProcessAvg(), stats.getDataProcessMax(),
                        stats.getEndToEndAvg(), stats.getEndToEndMax());
            } catch (Exception e) {
                log.error("[延迟监控] 生成统计报告异常", e);
            }
        });
    }

    /**
     * 计算延迟统计数据
     */
    private DelayStats calculateStats() {
        DelayStats stats = new DelayStats();

        // 计算设备上报延迟统计
        List<Long> deviceDelays = getDelays(DEVICE_DELAY_PREFIX);
        stats.setDeviceReportAvg(calculateAvg(deviceDelays));
        stats.setDeviceReportMax(calculateMax(deviceDelays));

        // 计算消息传输延迟统计
        List<Long> messageDelays = getDelays(MESSAGE_DELAY_PREFIX);
        stats.setMessageTransferAvg(calculateAvg(messageDelays));
        stats.setMessageTransferMax(calculateMax(messageDelays));

        // 计算数据处理延迟统计
        List<Long> processDelays = getDelays(PROCESS_DELAY_PREFIX);
        stats.setDataProcessAvg(calculateAvg(processDelays));
        stats.setDataProcessMax(calculateMax(processDelays));

        // 计算端到端延迟统计
        List<Long> e2eDelays = getDelays(E2E_DELAY_PREFIX);
        stats.setEndToEndAvg(calculateAvg(e2eDelays));
        stats.setEndToEndMax(calculateMax(e2eDelays));

        return stats;
    }

    /**
     * 获取延迟数据列表
     */
    private List<Long> getDelays(String prefix) {
        List<Long> delays = new ArrayList<>();
        String today = formatDate(new Date());

        Set<String> keys = redisTemplate.keys(prefix + "*:" + today);
        if (keys != null) {
            for (String key : keys) {
                List<Object> values = redisTemplate.opsForList().range(key, 0, -1);
                if (values != null) {
                    values.forEach(v -> delays.add((Long) v));
                }
            }
        }

        return delays;
    }

    /**
     * 计算平均值
     */
    private long calculateAvg(List<Long> values) {
        if (values == null || values.isEmpty()) {
            return 0;
        }
        return (long) values.stream().mapToLong(Long::longValue).average().orElse(0);
    }

    /**
     * 计算最大值
     */
    private long calculateMax(List<Long> values) {
        if (values == null || values.isEmpty()) {
            return 0;
        }
        return values.stream().mapToLong(Long::longValue).max().orElse(0);
    }

    /**
     * 格式化日期
     */
    private String formatDate(Date date) {
        return String.format("%04d%02d%02d",
                date.getYear() + 1900,
                date.getMonth() + 1,
                date.getDate());
    }

    /**
     * 延迟统计数据
     */
    @Data
    public static class DelayStats {
        /**
         * 设备上报延迟 - 平均值
         */
        private long deviceReportAvg;

        /**
         * 设备上报延迟 - 最大值
         */
        private long deviceReportMax;

        /**
         * 消息传输延迟 - 平均值
         */
        private long messageTransferAvg;

        /**
         * 消息传输延迟 - 最大值
         */
        private long messageTransferMax;

        /**
         * 数据处理延迟 - 平均值
         */
        private long dataProcessAvg;

        /**
         * 数据处理延迟 - 最大值
         */
        private long dataProcessMax;

        /**
         * 端到端延迟 - 平均值
         */
        private long endToEndAvg;

        /**
         * 端到端延迟 - 最大值
         */
        private long endToEndMax;
    }
}
