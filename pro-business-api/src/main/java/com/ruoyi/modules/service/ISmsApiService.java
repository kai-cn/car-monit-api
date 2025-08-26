package com.ruoyi.modules.service;

import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.vo.sms.MessageOne;
import com.ruoyi.modules.vo.sms.SmsResult;

import java.util.List;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
public interface ISmsApiService {

    /**
     * 短信发送接口
     */
    Result<SmsResult> sendMessageOne(List<MessageOne> messageList);

}
