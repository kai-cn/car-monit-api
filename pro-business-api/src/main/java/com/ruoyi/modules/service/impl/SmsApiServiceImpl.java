package com.ruoyi.modules.service.impl;

import cn.hutool.crypto.SecureUtil;
import com.ruoyi.modules.service.ISmsApiService;
import com.ruoyi.modules.service.forest.HttpSmsRequestService;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.vo.sms.HttpSendMessageRequest;
import com.ruoyi.modules.vo.sms.MessageOne;
import com.ruoyi.modules.vo.sms.SmsResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.Instant;
import java.util.List;
import java.util.Objects;

/**
 * @Description: 京东京麦接口
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
@Service
public class SmsApiServiceImpl implements ISmsApiService {
    @Value("${ret.sms.usr}")
    private String username;

    @Value("${ret.sms.pwd}")
    private String password;

    @Resource
    private HttpSmsRequestService httpSmsRequestService;

    @Override
    public Result<SmsResult> sendMessageOne(List<MessageOne> messageList) {
        HttpSendMessageRequest httpSendMessageRequest = new HttpSendMessageRequest();
        httpSendMessageRequest.setUserName(this.username);
        long timestamp = Instant.now().toEpochMilli();
        // 签名
        String sign = this.createSign(this.username, String.valueOf(timestamp), SecureUtil.md5(this.password));
        httpSendMessageRequest.setMessageList(messageList).setTimestamp(timestamp).setSign(sign);
        SmsResult smsResult = httpSmsRequestService.sendMessageOne(httpSendMessageRequest);
        if(Objects.equals(smsResult.getCode(),0)){
            return Result.OK("SMS_SUCCESS",smsResult);
        }else{
            return Result.error500("SMS_ERROR: 短信发送失败，系统发生异常，请联系管理员！");
        }
    }

    /**
     * MD5(userName + content + timestamp + MD5(password))，短信content字段有值就加入签名方法
     * @param args
     * @return
     */
    private String createSign(String ... args){
        return SecureUtil.md5(String.join("",args));
    }

}
