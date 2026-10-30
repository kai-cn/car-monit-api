package com.ruoyi.mq.service;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.common.core.redis.RedisCache;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.action.index.IndexResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.concurrent.TimeUnit;

/**
 * 数据处理服务
 * 负责将消费的数据存入MySQL分表和ES
 */
@Slf4j
@Service
public class DataProcessService {

    /**
     * Redis缓存键前缀，用于记录已处理的消息
     */
    private static final String PROCESS_PREFIX = "mq:processed:";

    /**
     * 缓存过期时间（7天）
     */
    private static final int PROCESS_EXPIRE_DAYS = 7;

    /**
     * ES索引名称
     */
    private static final String ES_INDEX = "snapshot_flow";

    private final OdsRtSzdnSnapshotFlowAddcodeMapper mapper;
    private final RedisCache redisCache;
    private final RestHighLevelClient esClient;

    /**
     * 构造函数注入依赖
     */
    public DataProcessService(OdsRtSzdnSnapshotFlowAddcodeMapper mapper,
                              RedisCache redisCache,
                              RestHighLevelClient esClient) {
        this.mapper = mapper;
        this.redisCache = redisCache;
        this.esClient = esClient;
        log.info("[数据处理服务] 初始化完成");
    }

    /**
     * 检查消息是否已处理（幂等性检查）
     * 
     * @param msgId 消息ID
     * @return true-已处理，false-未处理
     */
    public boolean isProcessed(String msgId) {
        String key = PROCESS_PREFIX + msgId;
        return redisCache.hasKey(key);
    }

    /**
     * 标记消息已处理
     * 
     * @param msgId 消息ID
     * @param dataId 数据ID
     */
    public void markProcessed(String msgId, Long dataId) {
        String key = PROCESS_PREFIX + msgId;
        redisCache.setCacheObject(key, dataId, PROCESS_EXPIRE_DAYS, TimeUnit.DAYS);
        log.debug("[数据处理服务] 标记消息已处理, msgId={}, dataId={}", msgId, dataId);
    }

    /**
     * 处理数据：存入MySQL分表和ES
     * 使用@Transactional保证数据一致性
     * 
     * @param data 快照流量数据
     */
    @Transactional(rollbackFor = Exception.class)
    public void process(OdsRtSzdnSnapshotFlowAddcode data) {
        log.debug("[数据处理服务] 开始处理数据, dataId={}", data.getId());

        // 1. 写入MySQL分表
        insertIntoMysql(data);

        // 2. 写入ES
        insertIntoEs(data);

        log.debug("[数据处理服务] 数据处理完成, dataId={}", data.getId());
    }

    /**
     * 根据snapshottime字段插入对应的月分表
     * 
     * @param data 快照流量数据
     */
    private void insertIntoMysql(OdsRtSzdnSnapshotFlowAddcode data) {
        // 根据snapshottime确定分表名
        String tableName = getTableName(data.getSnapshottime());

        try {
            // 写入MySQL（使用BaseMapper的insert方法）
            mapper.insert(data);
            log.debug("[数据处理服务] 插入MySQL成功, dataId={}", data.getId());
        } catch (Exception e) {
            log.error("[数据处理服务] 插入MySQL失败, dataId={}", data.getId(), e);
            throw new RuntimeException("插入MySQL失败", e);
        }
    }

    /**
     * 获取分表名
     * 格式：ods_rt_szdn_snapshot_flow_addcode_202401
     * 
     * @param snapshottime 快照时间
     * @return 分表名
     */
    private String getTableName(Date snapshottime) {
        if (snapshottime == null) {
            // 如果时间为空，使用当前时间
            snapshottime = new Date();
        }
        LocalDateTime ldt = snapshottime.toInstant().atZone(java.time.ZoneId.systemDefault()).toLocalDateTime();
        String suffix = ldt.format(DateTimeFormatter.ofPattern("yyyyMM"));
        return "ods_rt_szdn_snapshot_flow_addcode_" + suffix;
    }

    /**
     * 插入ES
     * 
     * @param data 快照流量数据
     */
    private void insertIntoEs(OdsRtSzdnSnapshotFlowAddcode data) {
        try {
            // 创建ES索引请求
            IndexRequest request = new IndexRequest(ES_INDEX)
                    .id(data.getId().toString())
                    .source(JSON.toJSONString(data), XContentType.JSON);

            // 执行索引操作
            IndexResponse response = esClient.index(request, RequestOptions.DEFAULT);

            log.debug("[数据处理服务] 插入ES成功, index={}, id={}, result={}", 
                    ES_INDEX, data.getId(), response.getResult());
        } catch (Exception e) {
            log.error("[数据处理服务] 插入ES失败, id={}", data.getId(), e);
            throw new RuntimeException("插入ES失败", e);
        }
    }
}
