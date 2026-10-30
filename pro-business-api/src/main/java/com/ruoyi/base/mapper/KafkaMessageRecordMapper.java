package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.KafkaMessageRecord;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Kafka消息发送记录Mapper接口
 * 
 * 功能说明：
 * - 提供消息记录的增删改查操作
 * - 支持查询失败消息、更新状态等自定义操作
 * - 继承MyBatis-Plus的BaseMapper，获得基础CRUD能力
 */
@Repository
public interface KafkaMessageRecordMapper extends BaseMapper<KafkaMessageRecord> {

    /**
     * 查询待重试的失败消息记录
     * 
     * 思路：查询状态为0（待发送）或2（发送失败）且重试次数未超限的记录
     * 目的：获取需要重新发送的消息列表，用于后台重试任务
     * 
     * @param maxRetryCount 最大重试次数，超过该次数的消息不再重试
     * @param limit 每次查询的最大记录数，防止一次性查询过多数据
     * @return List<KafkaMessageRecord> 待重试的消息记录列表
     */
    List<KafkaMessageRecord> selectFailedRecords(@Param("maxRetryCount") Integer maxRetryCount, @Param("limit") Integer limit);

    /**
     * 更新消息发送状态
     * 
     * 思路：根据主键ID更新状态和发送成功时间
     * 目的：标记消息为发送成功状态
     * 
     * @param id 消息记录ID
     * @param status 新状态（1表示成功）
     * @param sendTime 发送成功时间
     * @return int 影响的行数
     */
    int updateStatusById(@Param("id") String id, @Param("status") Integer status, @Param("sendTime") java.util.Date sendTime);

    /**
     * 增加重试次数并记录错误信息
     * 
     * 思路：重试次数+1，更新错误信息，状态设为2（失败）
     * 目的：记录发送失败的情况，为后续重试做准备
     * 
     * @param id 消息记录ID
     * @param errorMsg 错误信息
     * @return int 影响的行数
     */
    int incrementRetryCount(@Param("id") String id, @Param("errorMsg") String errorMsg);
}
