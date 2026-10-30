package com.ruoyi.base.domain;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.util.Date;

/**
 * Kafka消息发送记录实体类
 * 
 * 功能说明：
 * - 记录每条发送到Kafka的消息状态
 * - 用于实现消息重发机制，确保数据零丢失
 * - 支持消息追踪和故障排查
 */
@Data
@TableName(value = "kafka_message_record", schema = "jl_data01")
public class KafkaMessageRecord {

    /**
     * 主键ID
     * 
     * 说明：使用UUID自动生成
     * 目的：唯一标识每条消息记录
     */
    @TableId(value = "id", type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 业务数据ID
     * 
     * 说明：对应OdsRtSzdnSnapshotFlowAddcode表的bigId
     * 目的：关联原始业务数据，便于追溯
     */
    private String dataId;

    /**
     * Kafka主题名称
     * 
     * 说明：消息发送到的Topic
     * 目的：标识消息的目标队列
     */
    private String topic;

    /**
     * 消息JSON内容
     * 
     * 说明：业务数据的JSON序列化结果
     * 目的：保存消息的完整内容，用于重发时恢复
     */
    private String messageJson;

    /**
     * 发送状态
     * 
     * 说明：
     * - 0: 待发送（初始状态）
     * - 1: 发送成功
     * - 2: 发送失败，等待重试
     * 
     * 目的：跟踪消息的发送进度
     */
    private Integer status;

    /**
     * 重试次数
     * 
     * 说明：记录消息已经重试的次数
     * 目的：控制重试频率，避免无限重试占用资源
     */
    private Integer retryCount;

    /**
     * 记录创建时间
     * 
     * 说明：消息记录首次插入数据库的时间
     * 目的：用于按时间排序和统计
     */
    private Date createTime;

    /**
     * 发送成功时间
     * 
     * 说明：消息最终发送成功的时间
     * 目的：记录发送耗时和统计发送延迟
     */
    private Date sendTime;

    /**
     * 错误信息
     * 
     * 说明：记录发送失败时的异常信息
     * 目的：便于排查问题和分析失败原因
     */
    private String errorMsg;
}
