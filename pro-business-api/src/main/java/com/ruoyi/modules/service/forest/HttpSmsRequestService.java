package com.ruoyi.modules.service.forest;

import com.ruoyi.modules.vo.sms.HttpSendMessageRequest;
import com.ruoyi.modules.vo.sms.MessageOneResultDataDetail;
import com.ruoyi.modules.vo.sms.SmsResult;
import com.dtflys.forest.annotation.BaseRequest;
import com.dtflys.forest.annotation.Headers;
import com.dtflys.forest.annotation.JSONBody;
import com.dtflys.forest.annotation.Post;

import java.util.List;

@BaseRequest(baseURL = "#{ret.sms.url}")
public interface HttpSmsRequestService {
    /**
     * 1.	短信一对一发送接口
     * @param httpSendMessageRequest
     * @return
     */
    @Post(url = "/api/sendMessageOne")
    @Headers({
            "Content-Type:application/json;charset=utf-8",
            "Accept: application/json"
    })
    SmsResult<List<MessageOneResultDataDetail>> sendMessageOne(@JSONBody HttpSendMessageRequest httpSendMessageRequest);
}
