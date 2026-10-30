# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.PulsarMessageRecordMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/PulsarMessageRecordMapper.java
"""
from __future__ import annotations

from datetime import datetime

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.PulsarMessageRecord import PulsarMessageRecord

__all__ = ["PulsarMessageRecordMapper"]


class PulsarMessageRecordMapper(BaseMapper[PulsarMessageRecord]):
    """Pulsar 消息记录 Mapper 接口

    功能说明：
    - INSERT：新消息入库（由 MyBatis-Plus 自动生成）
    - SELECT：查询待重试的消息
    - UPDATE：更新发送状态为成功/失败
    - UPDATE：原子性累加 retry_count（使用数据库层面 +1，避免并发丢数）

    与原 Kafka 对应关系：
      KafkaMessageRecordMapper  <=>  PulsarMessageRecordMapper
      方法签名保持一致，保证上层 PulsarProducerService 与原 KafkaProducerService 逻辑一致

    【Java→Python】
    1) Java 用 `@Mapper` 注解（MyBatis）而非 `@Repository`（Spring），
       Python 侧两者都退化为「普通类 + 容器注册」，无运行期差异。
    2) 三个方法在 Java 中由 `@Select`/`@Update` 注解 SQL 实现，
       Python 侧改为内存过滤/更新，原 SQL 逐字保留在方法注释中，便于对照。
    3) `int maxRetryCount`（基本类型）→ `int`；`Date` → `datetime`。
    4) `#{param}` 占位符 → Python 方法参数（`@Param("x")` 的绑定名与参数名一致）。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(PulsarMessageRecord)

    def selectFailedRecords(self, maxRetryCount: int, limit: int) -> list[PulsarMessageRecord]:
        """查询待重试的消息记录

        查询条件：
          status IN (0, 2)   0=从未发送过 2=发送失败
          retry_count < #{maxRetryCount}   超过最大重试次数的不再处理

        排序：按 create_time ASC 优先处理最早产生的消息（FIFO）
        限制：最多 100 条，单次批量大小可控

        :param maxRetryCount: 最大重试次数（从配置读取，默认10）
        :param limit: 单次查询最大条数
        :return: 待重试的消息列表

        【Java→Python】原注解 SQL（逐字对照）：
            @Select("SELECT * FROM jl_data01.pulsar_message_record " +
                    "WHERE status IN (0, 2) AND retry_count < #{maxRetryCount} " +
                    "ORDER BY create_time ASC LIMIT #{limit}")
        Python 侧用 selectWhere 复刻 WHERE/ORDER BY/LIMIT 三段语义。
        """
        return self.selectWhere(
            lambda r: r.status in (0, 2) and (r.retry_count or 0) < maxRetryCount,
            order_by=lambda r: r.create_time,
            limit=limit,
        )

    def updateStatusById(self, id: str, status: int, sendTime: datetime, messageId: str) -> int:
        """更新消息状态为成功

        思路：
        1. SET status=1, send_time=#{sendTime}, message_id=#{messageId}
        2. 只更新指定 id 的记录（主键定位，性能最优）

        :param id: 主键
        :param status: 新状态（通常传 1=成功）
        :param sendTime: 发送时间
        :param messageId: Pulsar MessageId
        :return: 受影响行数

        【Java→Python】原注解 SQL（逐字对照）：
            @Update("UPDATE jl_data01.pulsar_message_record " +
                    "SET status = #{status}, send_time = #{sendTime}, message_id = #{messageId} " +
                    "WHERE id = #{id}")
        与 Kafka 版本相比多一个 message_id 字段（Pulsar 的 MessageId 需要落库）。
        """
        return self.updateWhere(
            lambda r: r.id == id,
            {"status": status, "send_time": sendTime, "message_id": messageId},
        )

    def incrementRetryCount(self, id: str, errorMsg: str) -> int:
        """原子性累加 retry_count 并更新状态为 2（失败）

        关键设计点：
          使用数据库层面的 retry_count = retry_count + 1，而非 Java 层读取再写回
          避免并发场景下丢失计数（例如两个线程同时 retry_count=2 时都写回 3，实际应为 4）
          同时将 status 设为 2（待重试），并写入 error_msg

        :param id: 主键
        :param errorMsg: 错误信息（截断到 500 字符）
        :return: 受影响行数

        【Java→Python】原注解 SQL（逐字对照）：
            @Update("UPDATE jl_data01.pulsar_message_record " +
                    "SET status = 2, retry_count = retry_count + 1, error_msg = #{errorMsg} " +
                    "WHERE id = #{id}")
        注意：Java 的「原子自增」依赖数据库行锁；Python 内存表无并发，语义上等价，
        但**不提供跨进程/多线程的原子性保证**（原实现并发安全的核心在数据库侧）。
        """
        return self.updateWhere(
            lambda r: r.id == id,
            lambda r: {
                "status": 2,
                "retry_count": (r.retry_count or 0) + 1,
                "error_msg": errorMsg,
            },
        )
