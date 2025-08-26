package com.ruoyi.modules.vo.sms;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import java.util.List;

@Data
@Accessors(chain = true)
public class HttpSendMessageRequest {
    @ApiModelProperty(value = "帐号用户名")
    private String userName	;

    @ApiModelProperty(value = "数组形式，包含多个JSON对象，对象参数见下表。每个JSON对象包含短信内容和号码数据，最大1000个号码。。")
    private List<MessageOne> messageList;

    @ApiModelProperty(value = "当前时间戳")
    private Long timestamp;

    @ApiModelProperty(value = "由以下参数值组合成字符串并计算MD5值，参考详细规则 计算：MD5(userName + content + timestamp + MD5(password))")
    private String sign;

    @ApiModelProperty(value = "短信定时发送时间，格式：yyyy-MM-dd HH:mm:ss。定时时间限制15天以内。")
    private String sendTime;

}
