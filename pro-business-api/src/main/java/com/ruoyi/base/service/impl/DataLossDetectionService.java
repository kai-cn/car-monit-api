package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.common.utils.DateUtils;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * 数据丢失检测服务
 *
 * 功能说明：
 * 1. 检测设备上报数据与数据库实际存储数据之间的差异
 * 2. 识别丢失的数据记录
 * 3. 支持按时间窗口、设备维度进行检测
 * 4. 生成检测报告并触发补偿机制
 *
 * 检测机制：
 * - 基于消息ID的完整性校验
 * - 时间窗口内的数据完整性统计
 * - 设备上报频率分析
 * - 数据连续性检测（缺失序列号检测）
 */
@Slf4j
@Service
public class DataLossDetectionService {

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotFlowMapper;

    @Autowired
    private RedisTemplate redisTemplate;

    @Autowired
    private DataReliabilityService reliabilityService;

    // ==================== 配置参数 ====================

    /**
     * 检测窗口大小（分钟）
     */
    @Value("${detection.window-size-minutes:60}")
    private int windowSizeMinutes;

    /**
     * 检测间隔（分钟）
     */
    @Value("${detection.interval-minutes:30}")
    private int intervalMinutes;

    /**
     * 丢失率告警阈值（百分比）
     */
    @Value("${detection.loss-threshold-percent:5}")
    private double lossThresholdPercent;

    // ==================== Redis Key 常量 ====================

    /**
     * 上报消息ID集合前缀
     */
    private static final String REPORTED_MSG_PREFIX = "detection:reported:";

    /**
     * 检测报告前缀
     */
    private static final String REPORT_PREFIX = "detection:report:";

    /**
     * 设备上报计数前缀
     */
    private static final String DEVICE_COUNT_PREFIX = "detection:device:count:";

    // ==================== 线程池 ====================

    private ExecutorService detectionExecutor;

    @PostConstruct
    public void init() {
        detectionExecutor = Executors.newFixedThreadPool(4);
        log.info("[数据丢失检测] 初始化完成，窗口大小: {}分钟, 检测间隔: {}分钟, 告警阈值: {}%",
                windowSizeMinutes, intervalMinutes, lossThresholdPercent);
    }

    /**
     * 记录上报的消息ID
     *
     * 思路：设备上报数据时，将消息ID记录到Redis集合中
     * 用于后续与数据库数据进行对比
     *
     * @param messageId 消息ID
     * @param deviceId 设备ID
     * @param timestamp 上报时间戳
     */
    public void recordReportedMessage(String messageId, String deviceId, long timestamp) {
        // 按小时分组存储，便于后续按时间窗口查询
        String hourKey = REPORTED_MSG_PREFIX + DateUtils.formatHour(new Date(timestamp));
        redisTemplate.opsForSet().add(hourKey, messageId);
        redisTemplate.expire(hourKey, 48, TimeUnit.HOURS);

        // 设备上报计数
        String deviceKey = DEVICE_COUNT_PREFIX + deviceId + ":" + DateUtils.formatDate(new Date(timestamp));
        redisTemplate.opsForValue().increment(deviceKey);
        redisTemplate.expire(deviceKey, 2, TimeUnit.DAYS);
    }

    /**
     * 定时检测任务
     *
     * 思路：定期检测指定时间窗口内的数据完整性
     * 1. 获取窗口内上报的消息ID集合
     * 2. 查询数据库中同一窗口内的数据
     * 3. 对比找出丢失的数据
     * 4. 生成检测报告
     */
    @Scheduled(fixedRateString = "${detection.interval-minutes:30}000")
    public void scheduledDetection() {
        detectionExecutor.submit(() -> {
            try {
                // 计算检测窗口时间范围（当前时间 - 窗口大小）
                Date endTime = new Date();
                Date startTime = DateUtils.addMinutes(endTime, -windowSizeMinutes);

                log.info("[数据丢失检测] 开始检测，时间窗口: {} ~ {}", startTime, endTime);

                // 执行检测
                DetectionResult result = detectDataLoss(startTime, endTime);

                // 生成报告
                generateReport(result, startTime, endTime);

                // 如果丢失率超过阈值，发送告警
                if (result.getLossRate() > lossThresholdPercent) {
                    sendAlert(result);
                }

            } catch (Exception e) {
                log.error("[数据丢失检测] 定时检测异常", e);
            }
        });
    }

    /**
     * 执行数据丢失检测
     *
     * 思路：
     * 1. 获取窗口内所有上报的消息ID
     * 2. 查询数据库中同一窗口的数据
     * 3. 对比找出丢失的数据
     *
     * @param startTime 开始时间
     * @param endTime 结束时间
     * @return 检测结果
     */
    public DetectionResult detectDataLoss(Date startTime, Date endTime) {
        DetectionResult result = new DetectionResult();
        result.setStartTime(startTime);
        result.setEndTime(endTime);

        // 1. 获取窗口内上报的消息ID集合
        Set<String> reportedMessageIds = getReportedMessageIds(startTime, endTime);
        result.setReportedCount(reportedMessageIds.size());
        log.debug("[数据丢失检测] 窗口内上报消息数: {}", reportedMessageIds.size());

        // 2. 查询数据库中同一窗口的数据
        List<OdsRtSzdnSnapshotFlowAddcode> dbRecords = queryDatabaseRecords(startTime, endTime);
        result.setStoredCount(dbRecords.size());
        log.debug("[数据丢失检测] 数据库存储记录数: {}", dbRecords.size());

        // 3. 提取数据库中的消息ID
        Set<String> storedMessageIds = dbRecords.stream()
                .map(OdsRtSzdnSnapshotFlowAddcode::getBigId)
                .collect(Collectors.toSet());

        // 4. 找出丢失的消息ID（上报了但未存储）
        Set<String> lostMessageIds = new HashSet<>(reportedMessageIds);
        lostMessageIds.removeAll(storedMessageIds);
        result.setLostCount(lostMessageIds.size());
        result.setLostMessageIds(lostMessageIds);

        // 5. 计算丢失率
        double lossRate = result.getReportedCount() > 0
                ? (double) result.getLostCount() / result.getReportedCount() * 100
                : 0;
        result.setLossRate(lossRate);

        // 6. 检测重复数据
        Set<String> duplicateIds = findDuplicateRecords(dbRecords);
        result.setDuplicateCount(duplicateIds.size());
        result.setDuplicateMessageIds(duplicateIds);

        log.info("[数据丢失检测] 检测完成: 上报={}, 存储={}, 丢失={}, 重复={}, 丢失率={}%",
                result.getReportedCount(), result.getStoredCount(),
                result.getLostCount(), result.getDuplicateCount(),
                String.format("%.2f", lossRate));

        return result;
    }

    /**
     * 获取窗口内上报的消息ID集合
     */
    private Set<String> getReportedMessageIds(Date startTime, Date endTime) {
        Set<String> messageIds = new HashSet<>();

        // 遍历窗口内的每个小时
        Date current = startTime;
        while (current.before(endTime)) {
            String hourKey = REPORTED_MSG_PREFIX + DateUtils.formatHour(current);
            Set<Object> ids = redisTemplate.opsForSet().members(hourKey);
            if (ids != null) {
                ids.forEach(id -> messageIds.add((String) id));
            }
            current = DateUtils.addHours(current, 1);
        }

        return messageIds;
    }

    /**
     * 查询数据库中指定时间窗口的数据
     */
    private List<OdsRtSzdnSnapshotFlowAddcode> queryDatabaseRecords(Date startTime, Date endTime) {
        LambdaQueryWrapper<OdsRtSzdnSnapshotFlowAddcode> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime, startTime, endTime);
        wrapper.select(OdsRtSzdnSnapshotFlowAddcode::getBigId);
        return snapshotFlowMapper.selectList(wrapper);
    }

    /**
     * 找出重复记录
     */
    private Set<String> findDuplicateRecords(List<OdsRtSzdnSnapshotFlowAddcode> records) {
        Set<String> seen = new HashSet<>();
        Set<String> duplicates = new HashSet<>();

        for (OdsRtSzdnSnapshotFlowAddcode record : records) {
            String bigId = record.getBigId();
            if (seen.contains(bigId)) {
                duplicates.add(bigId);
            } else {
                seen.add(bigId);
            }
        }

        return duplicates;
    }

    /**
     * 生成检测报告
     */
    private void generateReport(DetectionResult result, Date startTime, Date endTime) {
        String reportId = UUID.randomUUID().toString().substring(0, 8);
        String reportKey = REPORT_PREFIX + reportId;

        Map<String, Object> report = new HashMap<>();
        report.put("reportId", reportId);
        report.put("startTime", startTime);
        report.put("endTime", endTime);
        report.put("reportedCount", result.getReportedCount());
        report.put("storedCount", result.getStoredCount());
        report.put("lostCount", result.getLostCount());
        report.put("duplicateCount", result.getDuplicateCount());
        report.put("lossRate", result.getLossRate());
        report.put("generatedTime", new Date());

        redisTemplate.opsForValue().set(reportKey, report, 7, TimeUnit.DAYS);

        log.info("[数据丢失检测] 生成报告: reportId={}", reportId);
    }

    /**
     * 发送告警通知
     */
    private void sendAlert(DetectionResult result) {
        String alertMessage = String.format(
                "数据丢失率超过阈值！时间窗口: %s ~ %s, 上报: %d, 存储: %d, 丢失: %d, 丢失率: %.2f%%",
                result.getStartTime(), result.getEndTime(),
                result.getReportedCount(), result.getStoredCount(),
                result.getLostCount(), result.getLossRate());

        log.error("[数据丢失检测告警] {}", alertMessage);
        // TODO: 集成告警系统
    }

    /**
     * 触发补偿拉取
     *
     * 思路：根据检测结果，对丢失的数据进行补偿拉取
     *
     * @param result 检测结果
     */
    public void triggerCompensation(DetectionResult result) {
        if (result.getLostCount() == 0) {
            return;
        }

        log.info("[数据丢失检测] 触发补偿拉取，丢失消息数: {}", result.getLostCount());

        // 逐个处理丢失的消息
        for (String messageId : result.getLostMessageIds()) {
            try {
                // 尝试从缓存获取消息内容并重发
                String messageJson = (String) redisTemplate.opsForValue().get(
                        DataReliabilityService.MSG_CONTENT_PREFIX + messageId);

                if (messageJson != null) {
                    // 重新发送消息
                    reliabilityService.retrySend(messageId);
                } else {
                    log.warn("[数据丢失检测] 丢失消息内容已过期: messageId={}", messageId);
                }
            } catch (Exception e) {
                log.error("[数据丢失检测] 补偿拉取异常: messageId={}", messageId, e);
            }
        }
    }

    /**
     * 获取设备上报统计
     *
     * @param deviceId 设备ID（可选，为空则返回所有设备）
     * @param date 日期
     * @return 统计数据
     */
    public Map<String, Long> getDeviceReportStats(String deviceId, Date date) {
        Map<String, Long> stats = new HashMap<>();

        if (deviceId != null) {
            String key = DEVICE_COUNT_PREFIX + deviceId + ":" + DateUtils.formatDate(date);
            Long count = (Long) redisTemplate.opsForValue().get(key);
            stats.put(deviceId, count != null ? count : 0L);
        } else {
            // 获取所有设备的统计
            Set<String> keys = redisTemplate.keys(DEVICE_COUNT_PREFIX + "*:" + DateUtils.formatDate(date));
            if (keys != null) {
                for (String key : keys) {
                    String devId = key.substring(DEVICE_COUNT_PREFIX.length(), key.lastIndexOf(":"));
                    Long count = (Long) redisTemplate.opsForValue().get(key);
                    stats.put(devId, count != null ? count : 0L);
                }
            }
        }

        return stats;
    }

    /**
     * 检测结果
     */
    @Data
    public static class DetectionResult {
        /**
         * 检测开始时间
         */
        private Date startTime;

        /**
         * 检测结束时间
         */
        private Date endTime;

        /**
         * 上报消息总数
         */
        private int reportedCount;

        /**
         * 数据库存储数量
         */
        private int storedCount;

        /**
         * 丢失数量
         */
        private int lostCount;

        /**
         * 丢失率（百分比）
         */
        private double lossRate;

        /**
         * 丢失的消息ID列表
         */
        private Set<String> lostMessageIds;

        /**
         * 重复数量
         */
        private int duplicateCount;

        /**
         * 重复的消息ID列表
         */
        private Set<String> duplicateMessageIds;

        /**
         * 是否检测通过
         */
        public boolean isPassed() {
            return lossRate == 0 && duplicateCount == 0;
        }
    }
}
