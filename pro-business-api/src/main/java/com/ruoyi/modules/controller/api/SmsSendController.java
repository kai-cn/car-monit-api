package com.ruoyi.modules.controller.api;

import com.ruoyi.common.config.annotation.ValidHeader;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.service.ISmsApiService;
import com.ruoyi.modules.vo.sms.MessageOne;
import com.ruoyi.modules.vo.sms.SmsResult;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * @Description: 短信发送
 * @Author HuangJun
 * @Date 2024/7/18 15:55
 * @Return
 */
@Slf4j
@Api(tags = {"短信发送相关接口"})
@RestController
@RequestMapping(value = "/api/sms")
public class SmsSendController {
    @Autowired
    private ISmsApiService smsApiService;

    @PostMapping(value = "/sendMessageOne")
    @ApiOperation(value = "一对一发送短信", notes = "一对一发送短信")
    @ValidHeader(value = {"d-anno"})
    @ApiImplicitParam(name = "d-anno", dataType = "string", paramType = "header")
    public Result<SmsResult> sendMessageOne(@RequestBody List<MessageOne> messageList) {
        return smsApiService.sendMessageOne(messageList);
    }
}
