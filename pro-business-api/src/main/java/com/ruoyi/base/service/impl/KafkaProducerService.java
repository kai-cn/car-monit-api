package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.KafkaMessageRecord;
import com.ruoyi.base.mapper.KafkaMessageRecordMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;
import org.springframework.util.concurrent.ListenableFuture;
import org.springframework.util.concurrent.ListenableFutureCallback;

import javax.annotation.PostConstruct;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Kafka生产者服务类
 * 
 * 功能说明：
 * - 实现消息发送到Kafka的核心逻辑
 * - 集成数据可靠性保障服务，确保消息不丢失
 * - 实现后台重试任务，处理发送失败的消息
 * - 确保数据零丢失
 * 
 * 可靠性保障机制：
 * 1. 消息持久化：发送前先入库，确保消息不丢失
 * 2. 异步确认：注册回调处理发送结果
 * 3. 自动重试：失败消息自动重试，支持指数退避
 * 4. 死信处理：超过重试次数进入死信队列
 * 5. 幂等性：基于消息ID去重
 * 6. 超时检测：未确认消息自动触发补偿
 */
@Slf4j
@Service
public class KafkaProducerService {

    // 注入KafkaTemplate，用于发送消息
    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    // 注入消息记录Mapper，用于持久化消息状态
    @Autowired
    private KafkaMessageRecordMapper kafkaMessageRecordMapper;

    // 注入数据可靠性服务，用于集成可靠性保障机制
    @Autowired
    private DataReliabilityService reliabilityService;

    // 注入数据丢失检测服务，用于记录上报消息
    @Autowired
    private DataLossDetectionService lossDetectionService;

    // 注入延迟监控服务，用于监控消息延迟
    @Autowired
    private DelayMonitoringService delayMonitoringService;

    // 从配置文件读取主题名称，默认值为ods-rt-szdn-snapshot-flow
    @Value("${kafka.topic.snapshot-flow:ods-rt-szdn-snapshot-flow}")
    private String snapshotFlowTopic;

    // 从配置文件读取最大重试次数，默认值为10
    @Value("${kafka.max-retry-count:10}")
    private Integer maxRetryCount;

    // 重试任务线程池
    private ExecutorService retryExecutor;

    /**
     * 初始化方法
     * 
     * 思路：在Bean初始化后自动执行，启动后台重试线程
     * 目的：确保应用启动后立即开始处理失败消息的重试
     */
    @PostConstruct
    public void init() {
        // 创建单线程池，用于执行后台重试任务
        retryExecutor = Executors.newSingleThreadExecutor();
        // 启动重试任务
        startRetryTask();
        log.info("[Kafka生产者服务] 初始化完成，集成可靠性保障机制");
    }

    /**
     * 发送抓拍流水数据到Kafka（集成可靠性保障）
     * 
     * 思路：
     * 1. 记录消息生产时间（用于延迟监控）
     * 2. 调用可靠性服务发送消息（包含持久化、校验、超时检测）
     * 3. 记录上报消息ID（用于数据丢失检测）
     * 
     * 目的：实现消息的高可靠性发送，确保数据不丢失
     * 
     * @param data 业务数据对象
     * @param dataId 业务数据ID（作为Kafka消息的key）
     * @return 消息ID
     */
    public String sendSnapshotFlowData(Object data, String dataId) {
        // 1. 记录消息生产时间（用于延迟监控）
        delayMonitoringService.recordMessageProduceTime(dataId);

        // 2. 调用可靠性服务发送消息
        String messageId = reliabilityService.sendReliableMessage(data, dataId, snapshotFlowTopic);

        // 3. 记录上报业务主键（用于数据丢失检测，必须与数据库 big_id 同一命名空间）
        lossDetectionService.recordReportedMessage(dataId, extractDeviceId(data), System.currentTimeMillis());

        log.info("[Kafka生产者] 发送消息: dataId={}, messageId={}", dataId, messageId);
        return messageId;
    }

    /**
     * 发送消息到Kafka（内部方法）
     * 
     * 思路：
     * 1. 使用KafkaTemplate发送异步消息
     * 2. 注册回调函数，处理发送成功和失败的情况
     * 3. 成功时更新数据库状态为成功
     * 4. 失败时更新数据库状态为失败并记录错误
     * 
     * 目的：实现异步发送和状态更新
     * 
     * @param record 消息记录实体
     */
    private void sendMessage(KafkaMessageRecord record) {
        // 发送异步消息到Kafka
        // 参数说明：
        // - topic: 目标主题
        // - key: dataId，确保相同dataId的消息发送到同一个分区，保证顺序
        // - value: 消息内容，从JSON反序列化为对象
        ListenableFuture<SendResult<String, Object>> future = 
            kafkaTemplate.send(record.getTopic(), record.getDataId(), JSON.parse(record.getMessageJson()));
        
        // 注册回调函数，处理异步发送结果
        future.addCallback(new ListenableFutureCallback<SendResult<String, Object>>() {
            
            /**
             * 发送成功回调
             * 
             * 思路：更新数据库状态为成功，记录发送时间和offset
             * 目的：标记消息已成功送达
             */
            @Override
            public void onSuccess(SendResult<String, Object> result) {
                log.info("[Kafka生产者] 消息发送成功: dataId={}, offset={}", record.getDataId(), 
                    result.getRecordMetadata().offset());
                // 通知可靠性服务Kafka已确认（内部统一更新数据库状态为1与发送时间，使用 messageId 对齐）
                reliabilityService.handleKafkaAck(record.getId(), result.getRecordMetadata().offset());
            }

            /**
             * 发送失败回调
             * 
             * 思路：更新数据库状态为失败，记录错误信息，增加重试次数
             * 目的：为后续重试做准备
             */
            @Override
            public void onFailure(Throwable ex) {
                log.error("[Kafka生产者] 消息发送失败: dataId={}, error={}", record.getDataId(), ex.getMessage());
                // 通知可靠性服务发送失败（内部统一增加重试次数、记录错误并将状态置为2，使用 messageId 对齐）
                reliabilityService.handleSendFailure(record.getId(), ex.getMessage());
            }
        });
    }

    /**
     * 启动后台重试任务
     * 
     * 思路：
     * 1. 无限循环，定期查询失败消息
     * 2. 每次查询一批失败消息进行重试
     * 3. 两次重试之间休眠30秒
     * 4. 发生异常时休眠60秒后继续
     * 
     * 目的：自动处理发送失败的消息，确保最终送达
     */
    private void startRetryTask() {
        retryExecutor.submit(() -> {
            while (true) {
                try {
                    // 查询待重试的失败消息
                    // 参数：maxRetryCount-最大重试次数，100-每批最多100条
                    List<KafkaMessageRecord> failedRecords = 
                        kafkaMessageRecordMapper.selectFailedRecords(maxRetryCount, 100);
                    
                    // 如果有待重试的消息，则逐个发送
                    if (failedRecords != null && !failedRecords.isEmpty()) {
                        log.info("[Kafka生产者] 开始重试 {} 条消息", failedRecords.size());
                        for (KafkaMessageRecord record : failedRecords) {
                            sendMessage(record);
                        }
                    }
                    
                    // 休眠30秒后再次查询
                    Thread.sleep(30000);
                } catch (Exception e) {
                    log.error("[Kafka生产者] 重试任务异常", e);
                    try {
                        // 发生异常时，休眠60秒后继续
                        Thread.sleep(60000);
                    } catch (InterruptedException ie) {
                        // 如果被中断，退出循环
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        });
    }

    /**
     * 从数据对象中提取设备ID
     * 
     * 思路：根据不同的数据类型提取设备标识字段
     * 目的：用于数据丢失检测中的设备维度统计
     * 
     * @param data 数据对象
     * @return 设备ID
     */
    private String extractDeviceId(Object data) {
        if (data instanceof JSONObject) {
            JSONObject json = (JSONObject) data;
            // 尝试从多个可能的字段中提取设备ID
            String[] possibleFields = {"deviceId", "deviceid", "device_ip", "deviceIp", "gantrycode", "gantryId"};
            for (String field : possibleFields) {
                Object value = json.get(field);
                if (value != null) {
                    return value.toString();
                }
            }
        }
        return "unknown";
    }

    /**
     * 批量发送消息
     * 
     * 思路：批量发送多条消息，提高发送效率
     * 目的：减少网络开销，提高吞吐量
     * 
     * @param dataList 数据列表
     */
    public void sendBatchSnapshotFlowData(List<Object> dataList) {
        log.info("[Kafka生产者] 批量发送消息: count={}", dataList.size());
        
        for (Object data : dataList) {
            try {
                String dataId = extractDataId(data);
                if (dataId != null) {
                    sendSnapshotFlowData(data, dataId);
                }
            } catch (Exception e) {
                log.error("[Kafka生产者] 批量发送异常", e);
            }
        }
    }

    /**
     * 从数据对象中提取数据ID
     */
    private String extractDataId(Object data) {
        if (data instanceof JSONObject) {
            JSONObject json = (JSONObject) data;
            String[] possibleFields = {"bigId", "id", "uuid", "dataId"};
            for (String field : possibleFields) {
                Object value = json.get(field);
                if (value != null) {
                    return value.toString();
                }
            }
        }
        return null;
    }
}