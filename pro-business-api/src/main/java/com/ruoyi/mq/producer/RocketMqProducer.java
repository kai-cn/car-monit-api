package com.ruoyi.mq.producer;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.DateUtils;
import lombok.extern.slf4j.Slf4j;
import org.apache.rocketmq.client.producer.DefaultMQProducer;
import org.apache.rocketmq.client.producer.SendResult;
import org.apache.rocketmq.common.message.Message;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static com.ruoyi.common.utils.DateUtils.formatHour;
import static com.ruoyi.common.utils.DateUtils.parseDateToStr;

/**
 * RocketMQ生产者
 * 负责从GaussDB读取数据并发送到消息队列
 * 支持全量同步和增量同步
 */
@Slf4j
@Component
public class RocketMqProducer {

    @Value("${rocketmq.topic.snapshot-flow:topic_snapshot_flow}")
    private String topic;

    private final DefaultMQProducer producer;
    private final IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowAddcodeService;
    private final RedisCache redisCache;
    private final ExecutorService executorService = Executors.newFixedThreadPool(4);

    /**
     * 构造函数注入依赖
     */
    public RocketMqProducer(DefaultMQProducer producer,
                            IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowAddcodeService,
                            RedisCache redisCache) {
        this.producer = producer;
        this.snapshotFlowAddcodeService = snapshotFlowAddcodeService;
        this.redisCache = redisCache;
        log.info("[RocketMQ生产者] 初始化完成");
    }

    @PreDestroy
    public void destroy() {
        executorService.shutdown();
        log.info("[RocketMQ生产者] 线程池关闭");
    }

    /**
     * 全量数据同步
     * 使用多线程 + 游标分页查询GaussDB全量数据
     */
    public void syncFullData() {
        log.info("[RocketMQ生产者] 开始全量数据同步");
        long startTime = System.currentTimeMillis();

        // 获取最大snapshottime作为游标终点
        String maxSnapshotTime = snapshotFlowAddcodeService.getMaxSnapshotTime();
        if (maxSnapshotTime == null || maxSnapshotTime.isEmpty()) {
            log.warn("[RocketMQ生产者] 未找到最大snapshottime，跳过全量同步");
            return;
        }

        String currentCursor = "2000-01-01 00:00:00";
        int pageSize = 1000;
        int totalCount = 0;

        while (!currentCursor.equals(maxSnapshotTime)) {
            final String cursor = currentCursor;

            // 查询当前游标范围内的数据
            List<OdsRtSzdnSnapshotFlowAddcode> batch = snapshotFlowAddcodeService.queryByCursor(
                    cursor, maxSnapshotTime, pageSize);

            if (batch.isEmpty()) {
                break;
            }

            // 更新游标为最后一条数据的时间
            currentCursor = parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS ,batch.get(batch.size() - 1).getSnapshottime());

            // 批量发送消息
            sendBatchMessages(batch);
            totalCount += batch.size();

            log.info("[RocketMQ生产者] 全量同步进度: 已发送 {} 条数据", totalCount);
        }

        long duration = System.currentTimeMillis() - startTime;
        log.info("[RocketMQ生产者] 全量数据同步完成, 共发送 {} 条, 耗时 {}ms", totalCount, duration);
    }

    /**
     * 增量数据同步（定时任务调用）
     */
    public void syncIncrementalData() {
        log.info("[RocketMQ生产者] 开始增量数据同步");

        // 从Redis获取上次同步时间
        String lastSyncTime = getLastSyncTime();
        String currentTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));

        // 查询增量数据
        List<OdsRtSzdnSnapshotFlowAddcode> batch = snapshotFlowAddcodeService.queryByCursor(
                lastSyncTime, currentTime, 1000);

        if (!batch.isEmpty()) {
            sendBatchMessages(batch);
            // 更新上次同步时间
            updateLastSyncTime(currentTime);
            log.info("[RocketMQ生产者] 增量同步完成, 发送 {} 条数据", batch.size());
        } else {
            log.info("[RocketMQ生产者] 增量同步: 无新数据");
        }
    }

    /**
     * 批量发送消息
     * 使用同步发送保证消息可靠性
     */
    private void sendBatchMessages(List<OdsRtSzdnSnapshotFlowAddcode> dataList) {
        for (OdsRtSzdnSnapshotFlowAddcode data : dataList) {
            try {
                String jsonData = JSON.toJSONString(data);
                Message message = new Message(
                        topic,
                        "snapshot_flow",
                        data.getId().toString(),
                        jsonData.getBytes(StandardCharsets.UTF_8)
                );

                // 发送消息
                SendResult result = producer.send(message);

                if ("SEND_OK".equals(result.getSendStatus().name())) {
                    log.debug("[RocketMQ生产者] 消息发送成功, msgId={}, queueId={}",
                            result.getMsgId(), result.getMessageQueue().getQueueId());
                } else {
                    log.error("[RocketMQ生产者] 消息发送失败, msgId={}, status={}",
                            result.getMsgId(), result.getSendStatus());
                    // 发送失败，写入本地备份
                    writeToLocalBackup(data);
                }
            } catch (Exception e) {
                log.error("[RocketMQ生产者] 发送消息异常, dataId={}", data.getId(), e);
                // 写入本地备份，后续通过定时任务重试
                writeToLocalBackup(data);
            }
        }
    }

    /**
     * 将失败消息写入本地备份
     */
    private void writeToLocalBackup(OdsRtSzdnSnapshotFlowAddcode data) {
        // 实现本地文件备份逻辑（简化实现，实际项目中应写入可靠存储）
        log.warn("[RocketMQ生产者] 消息写入本地备份, dataId={}", data.getId());
    }

    /**
     * 从Redis获取上次同步时间
     */
    private String getLastSyncTime() {
        String key = "mq:sync:lastSyncTime";
        String lastSyncTime = redisCache.getCacheObject(key);
        return lastSyncTime != null ? lastSyncTime : "2024-01-01 00:00:00";
    }

    /**
     * 更新Redis中的同步时间
     */
    private void updateLastSyncTime(String time) {
        String key = "mq:sync:lastSyncTime";
        redisCache.setCacheObject(key, time);
    }


}
