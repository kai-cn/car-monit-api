package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.common.utils.DateUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class SnapshotFlowSyncService {

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotFlowMapper;

    @Autowired
    private KafkaProducerService kafkaProducerService;

    @Autowired
    public RedisTemplate redisTemplate;

    @Value("${sync.batch-size:1000}")
    private Integer batchSize;

    @Value("${sync.full-sync-enabled:true}")
    private Boolean fullSyncEnabled;

    @Value("${sync.incremental-sync-interval:60000}")
    private Long incrementalSyncInterval;

    private static final String LAST_SYNC_TIME_KEY = "snapshot_flow:last_sync_time";
    private static final String LAST_SYNC_ID_KEY = "snapshot_flow:last_sync_id";

    private ExecutorService syncExecutor;

    @PostConstruct
    public void init() {
        syncExecutor = Executors.newFixedThreadPool(2);

        if (fullSyncEnabled) {
            syncExecutor.submit(this::fullSync);
        }

        syncExecutor.submit(this::incrementalSync);
    }

    /**
     * 全量同步方法：处理历史300G数据
     * 思路：按主键ID分页，每次同步一批数据，确保不遗漏任何记录
     * 目的：将历史数据完整推送到Kafka，支持断点续传
     */
    public void fullSync() {
        log.info("开始全量同步数据");
        try {
            // 从Redis获取上次同步的最后一条ID，支持断点续传
            // 历史版本可能把该 key 写成 Integer/Long（序列化类型不一致），这里统一转字符串，
            // 避免 Integer cannot be cast to String 导致全量同步线程直接退出。
            Object cachedId = redisTemplate.opsForValue().get(LAST_SYNC_ID_KEY);
            String lastSyncId = null;
            if (cachedId != null) {
                if (!(cachedId instanceof String)) {
                    log.warn("全量同步断点 key 类型异常: {}，实际类型 {}，已按字符串兼容处理",
                            LAST_SYNC_ID_KEY, cachedId.getClass().getName());
                }
                lastSyncId = String.valueOf(cachedId);
            }

            while (true) {
                // 创建MyBatis-Plus查询条件构造器
                LambdaQueryWrapper<OdsRtSzdnSnapshotFlowAddcode> wrapper =
                    new LambdaQueryWrapper<>();

                // 如果不是第一次同步，从上次同步的ID之后继续查询，避免重复
                if (lastSyncId != null) {
                    wrapper.gt(OdsRtSzdnSnapshotFlowAddcode::getBigId, lastSyncId);
                }

                // 按主键ID升序排列，确保数据顺序一致
                wrapper.orderByAsc(OdsRtSzdnSnapshotFlowAddcode::getBigId);
                // 限制每批查询数量，防止一次性查询过多数据导致内存溢出
                wrapper.last("LIMIT " + batchSize);

                // 执行分页查询
                List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowMapper.selectList(wrapper);

                // 如果查询结果为空，说明全量同步已完成
                if (list == null || list.isEmpty()) {
                    log.info("全量同步完成");
                    break;
                }

                // 遍历每一条数据，发送到Kafka
                for (OdsRtSzdnSnapshotFlowAddcode data : list) {
                    // 发送数据到Kafka，消息key使用bigId确保分区有序
                    kafkaProducerService.sendSnapshotFlowData(data, data.getBigId());
                    // 更新当前批次的最后一条ID
                    lastSyncId = data.getBigId();
                }

                // 将当前进度保存到Redis，支持服务重启后继续同步
                redisTemplate.opsForValue().set(LAST_SYNC_ID_KEY, lastSyncId);
                log.info("已同步 {} 条数据，当前进度: {}", list.size(), lastSyncId);

                // 暂停100毫秒，避免对数据库造成过大压力
                Thread.sleep(100);
            }
        } catch (Exception e) {
            log.error("全量同步异常", e);
        }
    }

    /**
     * 增量同步方法：处理每日新增的50万条数据
     * 思路：基于抓拍时间(snapshottime)进行时间窗口查询，定期拉取新增数据
     * 目的：实时推送新产生的抓拍数据到Kafka，确保消费端能及时获取最新数据
     */
    public void incrementalSync() {
        log.info("开始增量同步数据");
        while (true) {
            try {
                // 从Redis获取上次同步的时间点
                Object cachedTime = redisTemplate.opsForValue().get(LAST_SYNC_TIME_KEY);
                Date lastSyncTime = toDate(cachedTime);
                // 获取当前时间作为本次同步的截止时间
                Date currentTime = new Date();

                // 如果是第一次增量同步，从1天前开始同步，防止遗漏数据
                if (lastSyncTime == null) {
                    lastSyncTime = DateUtils.addDays(currentTime, -1);
                }

                // 创建查询条件构造器
                LambdaQueryWrapper<OdsRtSzdnSnapshotFlowAddcode> wrapper =
                    new LambdaQueryWrapper<>();
                // 查询抓拍时间大于上次同步时间的记录（新数据）
                wrapper.gt(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime, lastSyncTime);
                // 查询抓拍时间小于等于当前时间的记录（防止未来数据）
                wrapper.le(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime, currentTime);
                // 按抓拍时间升序排列，确保数据按时间顺序推送
                wrapper.orderByAsc(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime);
                // 限制每批查询数量，防止一次性查询过多数据
                wrapper.last("LIMIT " + batchSize);

                // 执行查询获取新增数据
                List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowMapper.selectList(wrapper);

                // 如果有新增数据，则发送到Kafka
                if (list != null && !list.isEmpty()) {
                    for (OdsRtSzdnSnapshotFlowAddcode data : list) {
                        // 发送数据到Kafka
                        kafkaProducerService.sendSnapshotFlowData(data, data.getBigId());
                        // 更新同步时间为当前记录的抓拍时间
                        if (data.getSnapshottime() != null) {
                            lastSyncTime = data.getSnapshottime();
                        }
                    }

                    // 将本次同步的时间点保存到Redis
                    redisTemplate.opsForValue().set(LAST_SYNC_TIME_KEY, lastSyncTime);
                    log.info("增量同步 {} 条数据，同步时间: {}", list.size(), lastSyncTime);
                }

                // 等待配置的间隔时间后再次同步
                Thread.sleep(incrementalSyncInterval);
            } catch (Exception e) {
                log.error("增量同步异常", e);
                try {
                    Thread.sleep(incrementalSyncInterval);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
    }

    /**
     * 兼容 Redis 中历史类型：Date / epoch millis / 数字字符串。
     */
    private Date toDate(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Date) {
            return (Date) value;
        }
        if (value instanceof Number) {
            return new Date(((Number) value).longValue());
        }
        try {
            return new Date(Long.parseLong(String.valueOf(value)));
        } catch (NumberFormatException e) {
            log.warn("增量同步断点 key 类型异常: {}，无法转 Date，按首次同步处理", value);
            return null;
        }
    }
}
