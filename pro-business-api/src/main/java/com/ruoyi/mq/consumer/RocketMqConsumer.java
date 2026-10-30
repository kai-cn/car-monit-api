package com.ruoyi.mq.consumer;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.mq.service.DataProcessService;
import lombok.extern.slf4j.Slf4j;
import org.apache.rocketmq.common.message.MessageExt;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;

/**
 * RocketMQ消费者
 * 消费快照流量数据，处理后存入MySQL分表和ES
 */
@Slf4j
/*@Component
@RocketMQMessageListener(
        topic = "${rocketmq.topic.snapshot-flow:topic_snapshot_flow}",
        consumerGroup = "${rocketmq.consumer.group:snapshot_flow_consumer}",
        maxReconsumeTimes = 3
)*/
public class RocketMqConsumer implements RocketMQListener<MessageExt> {

    private static final int MAX_RETRY_COUNT = 3;

    private final DataProcessService dataProcessService;

    /**
     * 构造函数注入数据处理服务
     */
    public RocketMqConsumer(DataProcessService dataProcessService) {
        this.dataProcessService = dataProcessService;
        log.info("[RocketMQ消费者] 初始化完成");
    }

    /**
     * 消息监听方法
     * @param messageExt 消息扩展对象，包含消息体和重试次数等信息
     */
    @Override
    public void onMessage(MessageExt messageExt) {
        String msgId = messageExt.getMsgId();
        int reconsumeTimes = messageExt.getReconsumeTimes();

        log.debug("[RocketMQ消费者] 收到消息, msgId={}, reconsumeTimes={}", msgId, reconsumeTimes);

        try {
            // 解析消息体
            String body = new String(messageExt.getBody(), StandardCharsets.UTF_8);
            OdsRtSzdnSnapshotFlowAddcode data = JSON.parseObject(body, OdsRtSzdnSnapshotFlowAddcode.class);

            // 幂等性检查
            if (dataProcessService.isProcessed(msgId)) {
                log.debug("[RocketMQ消费者] 消息已处理, msgId={}", msgId);
                return;
            }

            // 处理数据（存入MySQL分表和ES）
            dataProcessService.process(data);

            // 标记消息已处理
            dataProcessService.markProcessed(msgId, Long.valueOf(data.getId()));

            log.info("[RocketMQ消费者] 消息处理成功, msgId={}, dataId={}", msgId, data.getId());

        } catch (Exception e) {
            log.error("[RocketMQ消费者] 处理消息失败, msgId={}, reconsumeTimes={}", msgId, reconsumeTimes, e);

            // 如果重试次数超过阈值，发送到死信队列
            if (reconsumeTimes >= MAX_RETRY_COUNT) {
                log.warn("[RocketMQ消费者] 消息超过重试次数，进入死信队列, msgId={}", msgId);
                // RocketMQ会自动将超过maxReconsumeTimes的消息发送到死信队列
            }

            // 抛出异常触发重新投递
            throw new RuntimeException("消息处理失败", e);
        }
    }
}
