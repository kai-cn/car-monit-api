# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.KafkaMessageRecordMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/KafkaMessageRecordMapper.java
"""
from __future__ import annotations

from datetime import datetime

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.KafkaMessageRecord import KafkaMessageRecord

__all__ = ["KafkaMessageRecordMapper"]


class KafkaMessageRecordMapper(BaseMapper[KafkaMessageRecord]):
    """Kafka消息发送记录Mapper接口

    功能说明：
    - 提供消息记录的增删改查操作
    - 支持查询失败消息、更新状态等自定义操作
    - 继承MyBatis-Plus的BaseMapper，获得基础CRUD能力

    【Java→Python】
    1) `interface ... extends BaseMapper<KafkaMessageRecord>` → 继承 BaseMapper[KafkaMessageRecord]；
       Java 侧实现类由 MyBatis-Plus 动态代理生成，Python 侧直接实例化。
    2) 三个自定义方法在 Java 中由 Mapper XML / 注解 SQL 实现，
       Python 侧改为「内存表过滤 + 全行更新」，SQL 语义原样保留在方法注释中。
    3) Java 的 `Integer`（包装类型，可为 null）→ Python `int`（调用方保证非空，与 SQL 一致）；
       `java.util.Date` → `datetime`。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(KafkaMessageRecord)

    def selectFailedRecords(self, maxRetryCount: int, limit: int) -> list[KafkaMessageRecord]:
        """查询待重试的失败消息记录

        思路：查询状态为0（待发送）或2（发送失败）且重试次数未超限的记录
        目的：获取需要重新发送的消息列表，用于后台重试任务

        :param maxRetryCount: 最大重试次数，超过该次数的消息不再重试
        :param limit: 每次查询的最大记录数，防止一次性查询过多数据
        :return: 待重试的消息记录列表

        【Java→Python】对应 SQL（原工程由 XML/注解提供）：
            SELECT * FROM kafka_message_record
             WHERE status IN (0, 2) AND retry_count < #{maxRetryCount}
             ORDER BY create_time ASC LIMIT #{limit}
        Python 侧等价于 selectWhere(过滤, order_by=create_time, limit=limit)。
        注意：`retry_count` 为 NULL 时 Java 的 `NULL < n` 结果为 UNKNOWN（行被过滤），
        这里用 `(r.retry_count or 0)` 保留「NULL 视作 0 次重试」的业务语义。
        """
        return self.selectWhere(
            lambda r: r.status in (0, 2) and (r.retry_count or 0) < maxRetryCount,
            order_by=lambda r: r.create_time,
            limit=limit,
        )

    def updateStatusById(self, id: str, status: int, sendTime: datetime) -> int:
        """更新消息发送状态

        思路：根据主键ID更新状态和发送成功时间
        目的：标记消息为发送成功状态

        :param id: 消息记录ID
        :param status: 新状态（1表示成功）
        :param sendTime: 发送成功时间
        :return: 影响的行数

        【Java→Python】对应 SQL：
            UPDATE kafka_message_record SET status = #{status}, send_time = #{sendTime}
             WHERE id = #{id}
        `Date sendTime` → `datetime`；返回值语义保持一致（影响行数）。
        """
        return self.updateWhere(
            lambda r: r.id == id,
            {"status": status, "send_time": sendTime},
        )

    def incrementRetryCount(self, id: str, errorMsg: str) -> int:
        """增加重试次数并记录错误信息

        思路：重试次数+1，更新错误信息，状态设为2（失败）
        目的：记录发送失败的情况，为后续重试做准备

        :param id: 消息记录ID
        :param errorMsg: 错误信息
        :return: 影响的行数

        【Java→Python】对应 SQL：
            UPDATE kafka_message_record
               SET retry_count = retry_count + 1, error_msg = #{errorMsg}, status = 2
             WHERE id = #{id}
        注意：SQL 的 `retry_count = retry_count + 1` 是数据库端原子自增，
        Python 侧用 `values(row)` 回调在行对象上自增，语义一致（单线程内存表）。
        """
        return self.updateWhere(
            lambda r: r.id == id,
            lambda r: {
                "retry_count": (r.retry_count or 0) + 1,
                "error_msg": errorMsg,
                "status": 2,
            },
        )
