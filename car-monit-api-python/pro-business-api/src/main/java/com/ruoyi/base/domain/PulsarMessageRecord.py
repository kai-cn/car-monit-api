# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.PulsarMessageRecord

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/PulsarMessageRecord.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class PulsarMessageRecord(JavaBean):
    """Pulsar 消息记录实体类 等价于原 Kafka 项目中的 KafkaMessageRecord

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    id: Optional[str] = None  # Java: private String id; // 主键 UUID

    data_id: Optional[str] = None  # Java: private String dataId; // 业务数据ID（消息的 key）

    topic: Optional[str] = None  # Java: private String topic; // Pulsar 主题名

    message_json: Optional[str] = None  # Java: private String messageJson; // 消息 JSON 内容

    status: Optional[int] = None  # Java: private Integer status; // 发送状态：0=待发送 1=成功 2=失败

    retry_count: Optional[int] = None  # Java: private Integer retryCount; // 重试次数

    message_id: Optional[str] = None  # Java: private String messageId; // Pulsar MessageId

    create_time: Optional[datetime] = None  # Java: private Date createTime; // 创建时间

    send_time: Optional[datetime] = None  # Java: private Date sendTime; // 发送时间

    error_msg: Optional[str] = None  # Java: private String errorMsg; // 错误信息

