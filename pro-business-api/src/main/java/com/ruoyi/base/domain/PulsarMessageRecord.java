package com.ruoyi.base.domain;

import lombok.Data;
import java.io.Serializable;
import java.util.Date;

/**
 * Pulsar 消息记录实体类
 * 等价于原 Kafka 项目中的 KafkaMessageRecord
 */
@Data
public class PulsarMessageRecord implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 主键 UUID */
    private String id;

    /** 业务数据ID（消息的 key） */
    private String dataId;

    /** Pulsar 主题名 */
    private String topic;

    /** 消息 JSON 内容 */
    private String messageJson;

    /** 发送状态：0=待发送 1=成功 2=失败 */
    private Integer status;

    /** 重试次数 */
    private Integer retryCount;

    /** Pulsar MessageId */
    private String messageId;

    /** 创建时间 */
    private Date createTime;

    /** 发送时间 */
    private Date sendTime;

    /** 错误信息 */
    private String errorMsg;
}
