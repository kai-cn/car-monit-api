# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.KafkaMessageRecord

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/KafkaMessageRecord.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class KafkaMessageRecord(JavaBean):
    """Kafka消息发送记录实体类 功能说明： - 记录每条发送到Kafka的消息状态 - 用于实现消息重发机制，确保数据零丢失 - 支持消息追踪和故障排查

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("kafka_message_record") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    TABLE_NAME = "kafka_message_record"  # @TableName("kafka_message_record")

    # @TableId(value = "id", type = IdType.ASSIGN_UUID)
    id: Optional[str] = field(default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"})  # Java: private String id; // 主键ID 说明：使用UUID自动生成 目的：唯一标识每条消息记录

    data_id: Optional[str] = None  # Java: private String dataId; // 业务数据ID 说明：对应OdsRtSzdnSnapshotFlowAddcode表的bigId 目的：关联原始业务数据，便于追溯

    topic: Optional[str] = None  # Java: private String topic; // Kafka主题名称 说明：消息发送到的Topic 目的：标识消息的目标队列

    message_json: Optional[str] = None  # Java: private String messageJson; // 消息JSON内容 说明：业务数据的JSON序列化结果 目的：保存消息的完整内容，用于重发时恢复

    status: Optional[int] = None  # Java: private Integer status; // 发送状态 说明： - 0: 待发送（初始状态） - 1: 发送成功 - 2: 发送失败，等待重试 目的：跟踪消息的发送进度

    retry_count: Optional[int] = None  # Java: private Integer retryCount; // 重试次数 说明：记录消息已经重试的次数 目的：控制重试频率，避免无限重试占用资源

    create_time: Optional[datetime] = None  # Java: private Date createTime; // 记录创建时间 说明：消息记录首次插入数据库的时间 目的：用于按时间排序和统计

    send_time: Optional[datetime] = None  # Java: private Date sendTime; // 发送成功时间 说明：消息最终发送成功的时间 目的：记录发送耗时和统计发送延迟

    error_msg: Optional[str] = None  # Java: private String errorMsg; // 错误信息 说明：记录发送失败时的异常信息 目的：便于排查问题和分析失败原因

