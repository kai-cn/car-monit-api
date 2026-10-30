package com.ruoyi.base.mapper;

import com.ruoyi.base.domain.PulsarMessageRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.Date;
import java.util.List;

/**
 * Pulsar 消息记录 Mapper 接口
 *
 * 功能说明：
 * - INSERT：新消息入库（由 MyBatis-Plus 自动生成）
 * - SELECT：查询待重试的消息
 * - UPDATE：更新发送状态为成功/失败
 * - UPDATE：原子性累加 retry_count（使用数据库层面 +1，避免并发丢数）
 *
 * 与原 Kafka 对应关系：
 *   KafkaMessageRecordMapper  <=>  PulsarMessageRecordMapper
 *   方法签名保持一致，保证上层 PulsarProducerService 与原 KafkaProducerService 逻辑一致
 */
@Mapper
public interface PulsarMessageRecordMapper extends com.baomidou.mybatisplus.core.mapper.BaseMapper<PulsarMessageRecord> {

    /**
     * 查询待重试的消息记录
     *
     * 查询条件：
     *   status IN (0, 2)   0=从未发送过 2=发送失败
     *   retry_count < #{maxRetryCount}   超过最大重试次数的不再处理
     *
     * 排序：按 create_time ASC 优先处理最早产生的消息（FIFO）
     * 限制：最多 100 条，单次批量大小可控
     *
     * @param maxRetryCount 最大重试次数（从配置读取，默认10）
     * @param limit         单次查询最大条数
     * @return 待重试的消息列表
     */
    @Select("SELECT * FROM jl_data01.pulsar_message_record " +
            "WHERE status IN (0, 2) AND retry_count < #{maxRetryCount} " +
            "ORDER BY create_time ASC LIMIT #{limit}")
    List<PulsarMessageRecord> selectFailedRecords(
            @Param("maxRetryCount") int maxRetryCount,
            @Param("limit") int limit
    );

    /**
     * 更新消息状态为成功
     *
     * 思路：
     * 1. SET status=1, send_time=#{sendTime}, message_id=#{messageId}
     * 2. 只更新指定 id 的记录（主键定位，性能最优）
     *
     * @param id         主键
     * @param status     新状态（通常传 1=成功）
     * @param sendTime   发送时间
     * @param messageId  Pulsar MessageId
     * @return 受影响行数
     */
    @Update("UPDATE jl_data01.pulsar_message_record " +
            "SET status = #{status}, send_time = #{sendTime}, message_id = #{messageId} " +
            "WHERE id = #{id}")
    int updateStatusById(
            @Param("id") String id,
            @Param("status") int status,
            @Param("sendTime") Date sendTime,
            @Param("messageId") String messageId
    );

    /**
     * 原子性累加 retry_count 并更新状态为 2（失败）
     *
     * 关键设计点：
     *   使用数据库层面的 retry_count = retry_count + 1，而非 Java 层读取再写回
     *   避免并发场景下丢失计数（例如两个线程同时 retry_count=2 时都写回 3，实际应为 4）
     *   同时将 status 设为 2（待重试），并写入 error_msg
     *
     * @param id        主键
     * @param errorMsg  错误信息（截断到 500 字符）
     * @return 受影响行数
     */
    @Update("UPDATE jl_data01.pulsar_message_record " +
            "SET status = 2, retry_count = retry_count + 1, error_msg = #{errorMsg} " +
            "WHERE id = #{id}")
    int incrementRetryCount(
            @Param("id") String id,
            @Param("errorMsg") String errorMsg
    );
}